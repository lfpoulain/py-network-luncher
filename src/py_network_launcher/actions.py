"""Implémentation des actions unitaires exécutées par les étapes d'une séquence."""

from __future__ import annotations

import json
import os
import re
import shlex
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from collections import deque
from pathlib import Path
from typing import Optional

from py_network_launcher.logs import get_logger
from py_network_launcher.models import (
    HOME_ASSISTANT_SERVICES,
    WAIT_MODE_EXIT,
    WAIT_MODE_NONE,
    WAIT_MODE_OPENED,
    WAIT_MODE_PORT,
    ActionStep,
)
from py_network_launcher.network import send_broadcast

IS_WINDOWS = os.name == "nt"
EXECUTABLE_EXTENSIONS = {".exe", ".com", ".bat", ".cmd"}
ERROR_ELEVATION_REQUIRED = 740
HTTP_TIMEOUT_S = 10.0
POLL_INTERVAL_S = 0.2

logger = get_logger("actions")


class StopRequested(Exception):
    """Levée quand l'utilisateur demande l'arrêt de la séquence en cours."""


class StopToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def set(self) -> None:
        self._event.set()

    @property
    def is_set(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        if self._event.is_set():
            raise StopRequested()

    def sleep(self, duration_s: float) -> None:
        """Attend `duration_s` secondes en restant interruptible."""
        if self._event.wait(max(0.0, duration_s)):
            raise StopRequested()


# --- Applications et commandes ----------------------------------------------------------


def _clean_path(value: str) -> str:
    """Retire les guillemets (« Copier en tant que chemin ») et développe %VARIABLES%."""
    return os.path.expandvars(value.strip().strip('"').strip())


def _creation_flags(*, hide_console: bool) -> int:
    if not IS_WINDOWS:
        return 0
    return subprocess.CREATE_NO_WINDOW if hide_console else subprocess.CREATE_NEW_CONSOLE


def launch_app(step: ActionStep, stop: StopToken) -> None:
    command = _clean_path(step.command)
    if not command:
        raise ValueError("Aucune application indiquée")
    arguments = os.path.expandvars(step.arguments.strip())
    cwd = _clean_path(step.working_directory) or None
    target = Path(command)
    if target.is_absolute() and not target.exists():
        raise FileNotFoundError(f"Introuvable : {command}")
    if cwd is None and target.is_absolute():
        # Beaucoup d'applications (OBS, jeux…) exigent d'être lancées depuis leur dossier.
        cwd = str(target.parent)
    if cwd is not None and not Path(cwd).is_dir():
        raise ValueError(f"Dossier de travail introuvable: {cwd}")

    if IS_WINDOWS and target.suffix.lower() not in EXECUTABLE_EXTENSIONS and target.exists():
        # Raccourci (.lnk), document, dossier… : on délègue au shell Windows.
        _shell_open(command, arguments, cwd)
        _wait_without_process(step, stop)
        return

    try:
        if IS_WINDOWS:
            command_line = subprocess.list2cmdline([command]) + (f" {arguments}" if arguments else "")
            process = subprocess.Popen(command_line, cwd=cwd)
        else:
            process = subprocess.Popen([command, *shlex.split(arguments)], cwd=cwd)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Application introuvable: {command}") from exc
    except OSError as exc:
        if getattr(exc, "winerror", None) == ERROR_ELEVATION_REQUIRED:
            logger.info(f"« {target.name} » demande les droits administrateur, ouverture via UAC")
            _shell_open(command, arguments, cwd, operation="runas")
            _wait_without_process(step, stop)
            return
        raise RuntimeError(f"Impossible de lancer l'application: {exc}") from exc
    wait_for_process(process, step, stop)


def run_shell_command(step: ActionStep, stop: StopToken) -> None:
    command = step.command.strip()
    if not command:
        raise ValueError("Commande shell vide")
    cwd = _clean_path(step.working_directory) or None
    if cwd is not None and not Path(cwd).is_dir():
        raise ValueError(f"Dossier de travail introuvable: {cwd}")
    hidden = not step.show_console
    capture = hidden and step.wait_mode == WAIT_MODE_EXIT
    output = subprocess.PIPE if capture else (subprocess.DEVNULL if hidden else None)
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            stdin=subprocess.DEVNULL if hidden else None,
            stdout=output,
            stderr=subprocess.STDOUT if capture else output,
            creationflags=_creation_flags(hide_console=hidden),
            text=capture,
            encoding=("oem" if IS_WINDOWS else "utf-8") if capture else None,
            errors="replace" if capture else None,
        )
    except OSError as exc:
        raise RuntimeError(f"Impossible d'exécuter la commande: {exc}") from exc
    wait_for_process(process, step, stop, output=OutputTail(process) if capture else None)


class OutputTail:
    """Lit la sortie d'un processus en tâche de fond et garde les dernières lignes."""

    def __init__(self, process: subprocess.Popen, max_lines: int = 8) -> None:
        self.lines: deque[str] = deque(maxlen=max_lines)
        self._thread = threading.Thread(target=self._read, args=(process,), name="shell-output", daemon=True)
        self._thread.start()

    def _read(self, process: subprocess.Popen) -> None:
        assert process.stdout is not None
        for line in process.stdout:
            if line.strip():
                self.lines.append(line.rstrip())

    def summary(self) -> str:
        self._thread.join(timeout=1.0)
        return " | ".join(list(self.lines)[-3:])


def _shell_open(path: str, arguments: str, cwd: Optional[str], *, operation: str = "open") -> None:
    if not IS_WINDOWS:
        raise RuntimeError("Ouverture via le shell disponible uniquement sous Windows")
    try:
        # `arguments` doit être une chaîne (None lève TypeError en Python 3.12).
        os.startfile(path, operation, arguments or "", cwd)
    except OSError as exc:
        raise RuntimeError(f"Impossible d'ouvrir « {path} »: {exc}") from exc


def _wait_without_process(step: ActionStep, stop: StopToken) -> None:
    if step.wait_mode == WAIT_MODE_PORT:
        _wait_for_port(step, stop, process=None)
    elif step.wait_mode != WAIT_MODE_NONE:
        logger.warning("Lancé via le shell Windows : l'attente choisie ne peut pas être vérifiée")


def _exit_error(return_code: int, output: Optional[OutputTail], default: str) -> RuntimeError:
    message = default if return_code == 0 else f"Le processus s'est terminé avec le code {return_code}"
    details = output.summary() if output is not None else ""
    return RuntimeError(f"{message} — {details}" if details else message)


def wait_for_process(
    process: subprocess.Popen,
    step: ActionStep,
    stop: StopToken,
    *,
    output: Optional[OutputTail] = None,
) -> None:
    mode = step.wait_mode
    if mode == WAIT_MODE_NONE:
        return
    if mode == WAIT_MODE_EXIT:
        while (return_code := process.poll()) is None:
            stop.sleep(POLL_INTERVAL_S)
        if return_code != 0:
            raise _exit_error(return_code, output, "")
        return
    if mode == WAIT_MODE_PORT:
        _wait_for_port(step, stop, process=process)
        return
    window_s = min(step.wait_timeout_s, 1.0) if mode == WAIT_MODE_OPENED else max(0.5, step.wait_timeout_s)
    deadline = time.monotonic() + window_s
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise _exit_error(
                return_code,
                output,
                "L'application s'est fermée aussitôt" if mode == WAIT_MODE_OPENED else "L'application s'est fermée avant la fin du délai",
            )
        stop.sleep(POLL_INTERVAL_S)


def _wait_for_port(step: ActionStep, stop: StopToken, *, process: Optional[subprocess.Popen]) -> None:
    host = step.wait_host.strip() or "127.0.0.1"
    port = int(step.wait_port)
    if not 1 <= port <= 65535:
        raise ValueError("Port à surveiller invalide (1-65535)")
    timeout_s = max(0.5, step.wait_timeout_s)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if process is not None and (return_code := process.poll()) is not None:
            raise _exit_error(return_code, None, "L'application s'est fermée avant que le port réponde")
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            stop.sleep(POLL_INTERVAL_S)
    raise RuntimeError(f"Le port {host}:{port} ne répond pas après {timeout_s:g} s")


# --- Web ---------------------------------------------------------------------------------


_LOCAL_HOST = re.compile(r"^(localhost|[^/:]+\.(local|lan|home|internal)|\d{1,3}(\.\d{1,3}){3})(?=[:/]|$)", re.IGNORECASE)


def normalize_url(raw: str) -> str:
    """Ajoute un schéma si l'utilisateur l'a omis.

    `mailto:x` ou `ms-settings:display` sont conservés, mais `homeassistant.local:8123`
    n'est pas un schéma : c'est un hôte et un port. Les adresses locales reçoivent `http://`.
    """
    url = raw.strip()
    if not url or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        return url
    scheme = re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:(?!\d)", url)
    if scheme:
        return url
    has_port = re.match(r"^[^/]+:\d", url) is not None
    return f"{'http' if has_port or _LOCAL_HOST.match(url) else 'https'}://{url}"


def open_webpage(step: ActionStep) -> None:
    url = normalize_url(step.url)
    if not url:
        raise ValueError("URL manquante")
    if IS_WINDOWS:
        _shell_open(url, "", None)
        return
    if not webbrowser.open(url, new=2):
        raise RuntimeError("Impossible d'ouvrir le navigateur")


def _http_error_detail(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read(500).decode("utf-8", errors="replace").strip()
    except Exception:
        body = ""
    try:
        parsed = json.loads(body)
        if isinstance(parsed, dict):
            body = str(parsed.get("message") or parsed.get("error") or body)
    except ValueError:
        pass
    return f"HTTP {exc.code}" + (f" — {body[:200]}" if body else "")


def parse_headers(raw: str) -> dict[str, str]:
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Headers JSON invalides: {exc.msg} (ligne {exc.lineno})") from exc
    if not isinstance(parsed, dict):
        raise ValueError('Les headers doivent être un objet JSON, ex. {"Authorization": "Bearer …"}')
    return {str(key): str(value) for key, value in parsed.items()}


def call_webhook(step: ActionStep) -> int:
    url = normalize_url(step.url)
    if not url:
        raise ValueError("URL du webhook manquante")
    headers = parse_headers(step.headers_json)
    body = step.body.encode("utf-8") if step.body else None
    if body is not None and not any(key.lower() == "content-type" for key in headers):
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(url=url, data=body, method=step.method or "POST", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S) as response:
            return int(getattr(response, "status", 200))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Webhook refusé: {_http_error_detail(exc)}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Webhook inaccessible: {exc.reason}") from exc
    except (ValueError, OSError) as exc:
        raise RuntimeError(f"Webhook en erreur: {exc}") from exc


# --- Wake-on-LAN -------------------------------------------------------------------------


def parse_mac_address(raw: str) -> bytes:
    digits = re.sub(r"[^0-9A-Fa-f]", "", raw)
    if len(digits) != 12 or len(re.sub(r"[\s:.\-]", "", raw)) != 12:
        raise ValueError("Adresse MAC invalide (format attendu AA:BB:CC:DD:EE:FF)")
    return bytes.fromhex(digits)


def wake_on_lan(step: ActionStep) -> None:
    mac = parse_mac_address(step.mac_address)
    packet = b"\xff" * 6 + mac * 16
    target = step.broadcast_ip.strip() or "255.255.255.255"
    for _ in range(3):
        error = send_broadcast(packet, 9, target)
        if error is not None:
            raise RuntimeError(f"Envoi du paquet Wake-on-LAN impossible: {error}")
        time.sleep(0.05)


# --- Home Assistant ----------------------------------------------------------------------


def _home_assistant_request(base_url: str, token: str, path: str, payload: Optional[dict] = None) -> urllib.request.Request:
    base_url = base_url.strip().rstrip("/")
    token = token.strip()
    if not base_url:
        raise ValueError("URL Home Assistant non configurée (Réglages)")
    if not token:
        raise ValueError("Token Home Assistant non configuré (Réglages)")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url=f"{base_url}{path}", data=data, method="POST" if data is not None else "GET")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json; charset=utf-8")
    return request


def _home_assistant_error(exc: Exception) -> RuntimeError:
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 401:
            return RuntimeError("Home Assistant a refusé le token (401). Vérifie-le dans les réglages.")
        if exc.code in (400, 404):
            return RuntimeError(f"Entité ou service inconnu de Home Assistant ({exc.code})")
        return RuntimeError(f"Home Assistant: {_http_error_detail(exc)}")
    if isinstance(exc, urllib.error.URLError):
        return RuntimeError(f"Home Assistant inaccessible: {exc.reason}")
    return RuntimeError(f"Home Assistant: {exc}")


def call_home_assistant(step: ActionStep, base_url: str, token: str) -> str:
    entity_id = step.home_assistant_entity_id.strip().lower()
    domain, _, object_id = entity_id.partition(".")
    if not domain or not object_id:
        raise ValueError("Entity ID invalide : format attendu domaine.nom, ex. light.salon")
    service = HOME_ASSISTANT_SERVICES.get(step.home_assistant_action, "turn_on")
    request = _home_assistant_request(base_url, token, f"/api/services/{domain}/{service}", {"entity_id": entity_id})
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S):
            pass
    except (urllib.error.URLError, ValueError, OSError) as exc:
        raise _home_assistant_error(exc) from exc
    return f"{domain}.{service} → {entity_id}"


def check_home_assistant(base_url: str, token: str) -> str:
    """Vérifie l'URL et le token ; renvoie un message lisible en cas de succès."""
    request = _home_assistant_request(base_url, token, "/api/")
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
    except (urllib.error.URLError, ValueError, OSError) as exc:
        raise _home_assistant_error(exc) from exc
    message = payload.get("message") if isinstance(payload, dict) else None
    return f"Connexion réussie ({message})" if message else "Connexion réussie"
