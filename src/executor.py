from __future__ import annotations

import json
import os
import shlex
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Callable
from typing import Optional

from models import (
    ACTION_CALL_WEBHOOK,
    ACTION_DELAY,
    ACTION_HOME_ASSISTANT,
    ACTION_LAUNCH_APP,
    ACTION_LOCAL_SEQUENCE,
    ACTION_OPEN_WEBPAGE,
    ACTION_REMOTE_SEQUENCE,
    ACTION_SHELL_COMMAND,
    ACTION_WAKE_ON_LAN,
    ActionStep,
    HOME_ASSISTANT_ACTIONS,
    HOME_ASSISTANT_DOMAINS,
    LaunchSequence,
    WAIT_MODE_EXIT,
    WAIT_MODE_NONE,
    WAIT_MODE_OPENED,
    WAIT_MODE_PORT,
    WAIT_MODE_STARTED,
)


class SequenceStopRequested(RuntimeError):
    pass


class SequenceExecutor:
    def __init__(
        self,
        *,
        remote_runner: Callable[[str, str], None],
        local_runner: Callable[[str, Optional[threading.Event]], None],
        home_assistant_config_provider: Callable[[], tuple[str, str]],
        on_sequence_started: Callable[[str], None],
        on_step_started: Callable[[str, str], None],
        on_step_completed: Callable[[str, str], None],
        on_sequence_finished: Callable[[str], None],
        logger: Callable[[str], None],
    ) -> None:
        self._remote_runner = remote_runner
        self._local_runner = local_runner
        self._home_assistant_config_provider = home_assistant_config_provider
        self._on_sequence_started = on_sequence_started
        self._on_step_started = on_step_started
        self._on_step_completed = on_step_completed
        self._on_sequence_finished = on_sequence_finished
        self._logger = logger
        self._lock = threading.RLock()
        self._thread_local = threading.local()
        self._sequence_stop_events: dict[str, threading.Event] = {}
        self._sequence_threads: dict[str, threading.Thread] = {}

    def run_sequence(self, sequence: LaunchSequence, source: str = "manual") -> None:
        stop_event = threading.Event()
        worker = threading.Thread(
            target=self._run_sequence_worker,
            args=(sequence, source, stop_event),
            name=f"sequence-{sequence.id}",
            daemon=True,
        )
        with self._lock:
            self._sequence_stop_events[sequence.id] = stop_event
            self._sequence_threads[sequence.id] = worker
        worker.start()

    def run_sequence_synchronous(self, sequence: LaunchSequence, source: str = "manual", stop_event: Optional[threading.Event] = None) -> None:
        sequence_stop_event = stop_event or self._current_stop_event() or threading.Event()
        with self._lock:
            self._sequence_stop_events[sequence.id] = sequence_stop_event
        self._run_sequence_worker(sequence, source, sequence_stop_event)

    def run_step(self, step: ActionStep, source: str = "manual_step") -> None:
        worker = threading.Thread(
            target=self._run_step_worker,
            args=(step, source),
            name=f"step-{step.id}",
            daemon=True,
        )
        worker.start()

    def request_stop(self, sequence_id: str) -> bool:
        with self._lock:
            stop_event = self._sequence_stop_events.get(sequence_id)
        if stop_event is None:
            return False
        stop_event.set()
        return True

    def _run_sequence_worker(self, sequence: LaunchSequence, source: str, stop_event: threading.Event) -> None:
        self._logger(f"Début de la séquence '{sequence.name}' ({source})")
        self._push_stop_event(stop_event)
        self._on_sequence_started(sequence.id)
        try:
            for index, step in enumerate(sequence.steps, start=1):
                self._check_stop_requested(stop_event)
                self._logger(f"Étape {index}/{len(sequence.steps)}: {step.display_name()}")
                self._on_step_started(sequence.id, step.id)
                self._run_step(step, stop_event=stop_event)
                self._check_stop_requested(stop_event)
                self._on_step_completed(sequence.id, step.id)
            self._logger(f"Séquence '{sequence.name}' terminée")
        except SequenceStopRequested:
            self._logger(f"Séquence '{sequence.name}' arrêtée")
        except Exception as exc:
            self._logger(f"Séquence '{sequence.name}' en erreur: {exc}")
        finally:
            self._on_sequence_finished(sequence.id)
            self._pop_stop_event(stop_event)
            with self._lock:
                if self._sequence_stop_events.get(sequence.id) is stop_event:
                    self._sequence_stop_events.pop(sequence.id, None)
                self._sequence_threads.pop(sequence.id, None)

    def _run_step_worker(self, step: ActionStep, source: str) -> None:
        step_name = step.display_name()
        self._logger(f"Début de l'étape '{step_name}' ({source})")
        try:
            self._run_step(step)
            self._logger(f"Étape '{step_name}' terminée")
        except Exception as exc:
            self._logger(f"Étape '{step_name}' en erreur: {exc}")

    def _run_step(self, step: ActionStep, *, stop_event: Optional[threading.Event] = None) -> None:
        current_stop_event = stop_event or self._current_stop_event()
        self._check_stop_requested(current_stop_event)
        if step.action_type == ACTION_LAUNCH_APP:
            self._run_launch_app(step, current_stop_event)
            return
        if step.action_type == ACTION_SHELL_COMMAND:
            self._run_shell_command(step, current_stop_event)
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
            self._sleep_with_stop(max(0.0, float(step.seconds)), current_stop_event)
            return
        if step.action_type == ACTION_LOCAL_SEQUENCE:
            if not step.local_sequence_id.strip():
                raise ValueError("Séquence locale manquante")
            self._local_runner(step.local_sequence_id.strip(), current_stop_event)
            return
        if step.action_type == ACTION_REMOTE_SEQUENCE:
            if not step.remote_sequence_id.strip():
                raise ValueError("Séquence distante manquante")
            if not step.remote_peer_id.strip():
                raise ValueError("Poste distant manquant")
            self._remote_runner(step.remote_peer_id.strip(), step.remote_sequence_id.strip())
            return
        if step.action_type == ACTION_HOME_ASSISTANT:
            self._run_home_assistant(step)
            return
        raise ValueError(f"Type d'action inconnu: {step.action_type}")

    def _run_launch_app(self, step: ActionStep, stop_event: Optional[threading.Event]) -> None:
        command = step.command.strip()
        if not command:
            raise ValueError("Commande vide")
        cwd = step.working_directory.strip() or None
        try:
            args = [command]
            if step.arguments.strip():
                args.extend(shlex.split(step.arguments.strip(), posix=False))
            process = subprocess.Popen(args, cwd=cwd, shell=False)
            self._wait_for_launch_condition(process, step, stop_event)
        except FileNotFoundError as exc:
            raise RuntimeError(f"Application introuvable: {command}") from exc
        except OSError as exc:
            raise RuntimeError(f"Impossible de lancer l'application: {exc}") from exc

    def _run_shell_command(self, step: ActionStep, stop_event: Optional[threading.Event]) -> None:
        command = step.command.strip()
        if not command:
            raise ValueError("Commande shell vide")
        cwd = step.working_directory.strip() or None
        try:
            process = subprocess.Popen(command, cwd=cwd, shell=True)
            self._wait_for_launch_condition(process, step, stop_event)
        except OSError as exc:
            raise RuntimeError(f"Impossible d'exécuter la commande shell: {exc}") from exc

    def _wait_for_launch_condition(self, process: subprocess.Popen, step: ActionStep, stop_event: Optional[threading.Event]) -> None:
        wait_mode = step.wait_mode
        if wait_mode == WAIT_MODE_NONE:
            return
        if wait_mode == WAIT_MODE_EXIT:
            while True:
                self._check_stop_requested(stop_event)
                return_code = process.poll()
                if return_code is None:
                    time.sleep(0.2)
                    continue
                if return_code != 0:
                    raise RuntimeError(f"L'application s'est terminée avec le code {return_code}")
                return
        timeout_s = max(0.5, float(step.wait_timeout_s))
        deadline = time.monotonic() + timeout_s
        if wait_mode == WAIT_MODE_OPENED:
            validation_window_s = min(timeout_s, 1.0)
            validation_deadline = time.monotonic() + validation_window_s
            while time.monotonic() < validation_deadline:
                self._check_stop_requested(stop_event)
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
                self._check_stop_requested(stop_event)
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
                self._check_stop_requested(stop_event)
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

    def _sleep_with_stop(self, duration_s: float, stop_event: Optional[threading.Event]) -> None:
        deadline = time.monotonic() + max(0.0, duration_s)
        while time.monotonic() < deadline:
            self._check_stop_requested(stop_event)
            time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))

    def _current_stop_event(self) -> Optional[threading.Event]:
        stack = getattr(self._thread_local, "stop_event_stack", None)
        if not stack:
            return None
        return stack[-1]

    def _push_stop_event(self, stop_event: threading.Event) -> None:
        stack = list(getattr(self._thread_local, "stop_event_stack", []))
        stack.append(stop_event)
        self._thread_local.stop_event_stack = stack

    def _pop_stop_event(self, stop_event: threading.Event) -> None:
        stack = list(getattr(self._thread_local, "stop_event_stack", []))
        if stack and stack[-1] is stop_event:
            stack.pop()
        else:
            stack = [item for item in stack if item is not stop_event]
        self._thread_local.stop_event_stack = stack

    def _check_stop_requested(self, stop_event: Optional[threading.Event]) -> None:
        if stop_event is not None and stop_event.is_set():
            raise SequenceStopRequested()

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

    def _run_home_assistant(self, step: ActionStep) -> None:
        base_url, token = self._home_assistant_config_provider()
        base_url = str(base_url or "").strip().rstrip("/")
        token = str(token or "").strip()
        if not base_url:
            raise ValueError("URL Home Assistant non configurée")
        if not token:
            raise ValueError("Token Home Assistant non configuré")
        entity_id = step.home_assistant_entity_id.strip()
        if not entity_id:
            raise ValueError("Entity ID Home Assistant manquant")
        domain = entity_id.split(".", 1)[0].strip().lower()
        if domain not in HOME_ASSISTANT_DOMAINS:
            raise ValueError("Entity ID Home Assistant invalide. Utilise un ID complet comme light.salon ou switch.prise_bureau")
        action = step.home_assistant_action.strip().lower()
        if action not in HOME_ASSISTANT_ACTIONS:
            raise ValueError("Action Home Assistant invalide")
        service_name = f"turn_{action}"
        url = f"{base_url}/api/services/{domain}/{service_name}"
        payload = json.dumps({"entity_id": entity_id}).encode("utf-8")
        request = urllib.request.Request(url=url, data=payload, method="POST")
        request.add_header("Authorization", f"Bearer {token}")
        request.add_header("Content-Type", "application/json; charset=utf-8")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                status = getattr(response, "status", 200)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Home Assistant HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Home Assistant inaccessible: {exc.reason}") from exc
        except ValueError as exc:
            raise RuntimeError(f"Home Assistant invalide: {exc}") from exc
        self._logger(f"Home Assistant {domain}.{service_name} envoyé pour {entity_id} ({status})")

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
