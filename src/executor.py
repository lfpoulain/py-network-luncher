from __future__ import annotations

import json
import os
import shlex
import socket
import subprocess
import time
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Callable
from typing import Optional

from models import (
    ACTION_CALL_WEBHOOK,
    ACTION_DELAY,
    ACTION_LAUNCH_APP,
    ACTION_OPEN_WEBPAGE,
    ACTION_REMOTE_SEQUENCE,
    ACTION_SHELL_COMMAND,
    ACTION_WAKE_ON_LAN,
    ActionStep,
    LaunchSequence,
    WAIT_MODE_EXIT,
    WAIT_MODE_NONE,
    WAIT_MODE_OPENED,
    WAIT_MODE_PORT,
    WAIT_MODE_STARTED,
)


class SequenceExecutor:
    def __init__(
        self,
        *,
        remote_runner: Callable[[str, str], None],
        logger: Callable[[str], None],
    ) -> None:
        self._remote_runner = remote_runner
        self._logger = logger

    def run_sequence(self, sequence: LaunchSequence, source: str = "manual") -> None:
        import threading

        worker = threading.Thread(
            target=self._run_sequence_worker,
            args=(sequence, source),
            name=f"sequence-{sequence.id}",
            daemon=True,
        )
        worker.start()

    def run_step(self, step: ActionStep, source: str = "manual_step") -> None:
        import threading

        worker = threading.Thread(
            target=self._run_step_worker,
            args=(step, source),
            name=f"step-{step.id}",
            daemon=True,
        )
        worker.start()

    def _run_sequence_worker(self, sequence: LaunchSequence, source: str) -> None:
        self._logger(f"Début de la séquence '{sequence.name}' ({source})")
        try:
            for index, step in enumerate(sequence.steps, start=1):
                self._logger(f"Étape {index}/{len(sequence.steps)}: {step.display_name()}")
                self._run_step(step)
            self._logger(f"Séquence '{sequence.name}' terminée")
        except Exception as exc:
            self._logger(f"Séquence '{sequence.name}' en erreur: {exc}")

    def _run_step_worker(self, step: ActionStep, source: str) -> None:
        step_name = step.display_name()
        self._logger(f"Début de l'étape '{step_name}' ({source})")
        try:
            self._run_step(step)
            self._logger(f"Étape '{step_name}' terminée")
        except Exception as exc:
            self._logger(f"Étape '{step_name}' en erreur: {exc}")

    def _run_step(self, step: ActionStep) -> None:
        if step.action_type == ACTION_LAUNCH_APP:
            self._run_launch_app(step)
            return
        if step.action_type == ACTION_SHELL_COMMAND:
            self._run_shell_command(step)
            return
        if step.action_type == ACTION_OPEN_WEBPAGE:
            if not step.url.strip():
                raise ValueError("URL de page web manquante")
            if os.name == "nt":
                try:
                    os.startfile(step.url.strip())
                    return
                except OSError as exc:
                    raise RuntimeError(f"Impossible d'ouvrir la page web: {exc}") from exc
            opened = webbrowser.open(step.url.strip(), new=2)
            if not opened:
                raise RuntimeError("Impossible d'ouvrir la page web")
            return
        if step.action_type == ACTION_CALL_WEBHOOK:
            self._run_webhook(step)
            return
        if step.action_type == ACTION_WAKE_ON_LAN:
            self._run_wol(step)
            return
        if step.action_type == ACTION_DELAY:
            time.sleep(max(0.0, float(step.seconds)))
            return
        if step.action_type == ACTION_REMOTE_SEQUENCE:
            if not step.remote_sequence_id.strip():
                raise ValueError("Séquence distante manquante")
            if not step.remote_peer_id.strip():
                raise ValueError("Poste distant manquant")
            self._remote_runner(step.remote_peer_id.strip(), step.remote_sequence_id.strip())
            return
        raise ValueError(f"Type d'action inconnu: {step.action_type}")

    def _run_launch_app(self, step: ActionStep) -> None:
        command = step.command.strip()
        if not command:
            raise ValueError("Commande vide")
        cwd = step.working_directory.strip() or None
        try:
            args = [command]
            if step.arguments.strip():
                args.extend(shlex.split(step.arguments.strip(), posix=False))
            process = subprocess.Popen(args, cwd=cwd, shell=False)
            self._wait_for_launch_condition(process, step)
        except FileNotFoundError as exc:
            raise RuntimeError(f"Application introuvable: {command}") from exc
        except OSError as exc:
            raise RuntimeError(f"Impossible de lancer l'application: {exc}") from exc

    def _run_shell_command(self, step: ActionStep) -> None:
        command = step.command.strip()
        if not command:
            raise ValueError("Commande shell vide")
        cwd = step.working_directory.strip() or None
        try:
            process = subprocess.Popen(command, cwd=cwd, shell=True)
            self._wait_for_launch_condition(process, step)
        except OSError as exc:
            raise RuntimeError(f"Impossible d'exécuter la commande shell: {exc}") from exc

    def _wait_for_launch_condition(self, process: subprocess.Popen, step: ActionStep) -> None:
        wait_mode = step.wait_mode
        if wait_mode == WAIT_MODE_NONE:
            return
        if wait_mode == WAIT_MODE_EXIT:
            return_code = process.wait()
            if return_code != 0:
                raise RuntimeError(f"L'application s'est terminée avec le code {return_code}")
            return
        timeout_s = max(0.5, float(step.wait_timeout_s))
        deadline = time.monotonic() + timeout_s
        if wait_mode == WAIT_MODE_OPENED:
            validation_window_s = min(timeout_s, 1.0)
            validation_deadline = time.monotonic() + validation_window_s
            while time.monotonic() < validation_deadline:
                return_code = process.poll()
                if return_code is not None:
                    raise RuntimeError(
                        "L'application s'est fermée avant d'être considérée comme ouverte"
                        if return_code == 0
                        else f"L'application s'est terminée avec le code {return_code}"
                    )
                time.sleep(0.2)
            return
        if wait_mode == WAIT_MODE_STARTED:
            while time.monotonic() < deadline:
                return_code = process.poll()
                if return_code is not None:
                    raise RuntimeError(
                        "L'application s'est fermée avant la fin du délai de validation"
                        if return_code == 0
                        else f"L'application s'est terminée avec le code {return_code}"
                    )
                time.sleep(0.2)
            return
        if wait_mode == WAIT_MODE_PORT:
            wait_host = step.wait_host.strip() or "127.0.0.1"
            wait_port = int(step.wait_port)
            if not 1 <= wait_port <= 65535:
                raise ValueError("Port d'attente invalide")
            last_error: Optional[Exception] = None
            while time.monotonic() < deadline:
                return_code = process.poll()
                if return_code is not None:
                    raise RuntimeError(
                        "L'application s'est fermée avant que le port réponde"
                        if return_code == 0
                        else f"L'application s'est terminée avec le code {return_code}"
                    )
                try:
                    with socket.create_connection((wait_host, wait_port), timeout=0.5):
                        return
                except OSError as exc:
                    last_error = exc
                    time.sleep(0.2)
            raise RuntimeError(f"Le port {wait_host}:{wait_port} ne répond pas après {timeout_s:g}s") from last_error

    def _run_webhook(self, step: ActionStep) -> None:
        url = step.url.strip()
        if not url:
            raise ValueError("URL de webhook vide")
        headers: dict[str, str] = {}
        if step.headers_json.strip():
            try:
                parsed = json.loads(step.headers_json)
            except json.JSONDecodeError as exc:
                raise ValueError("Headers JSON invalide") from exc
            if isinstance(parsed, dict):
                headers = {str(key): str(value) for key, value in parsed.items()}
            else:
                raise ValueError("Headers JSON doit être un objet JSON")
        body: Optional[bytes] = None
        if step.body:
            body = step.body.encode("utf-8")
            headers.setdefault("Content-Type", "application/json; charset=utf-8")
        request = urllib.request.Request(url=url, data=body, method=step.method.strip().upper() or "POST")
        for key, value in headers.items():
            request.add_header(key, value)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                status = getattr(response, "status", 200)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Webhook HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Webhook inaccessible: {exc.reason}") from exc
        except ValueError as exc:
            raise RuntimeError(f"Webhook invalide: {exc}") from exc
        self._logger(f"Webhook appelé ({status})")

    def _run_wol(self, step: ActionStep) -> None:
        mac = step.mac_address.replace(":", "").replace("-", "").strip()
        if len(mac) != 12:
            raise ValueError("Adresse MAC invalide")
        try:
            data = bytes.fromhex("FF" * 6 + mac * 16)
        except ValueError as exc:
            raise ValueError("Adresse MAC invalide") from exc
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.sendto(data, (step.broadcast_ip.strip() or "255.255.255.255", 9))
        except OSError as exc:
            raise RuntimeError(f"Impossible d'envoyer le Wake-on-LAN: {exc}") from exc
