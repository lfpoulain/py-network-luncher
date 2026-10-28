"""Orchestration des séquences : threads, arrêt, sous-séquences et suivi d'avancement."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Optional, Protocol

from py_network_launcher import actions
from py_network_launcher.actions import StopRequested, StopToken
from py_network_launcher.logs import get_logger
from py_network_launcher.models import (
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
    LaunchSequence,
)

OUTCOME_SUCCESS = "success"
OUTCOME_FAILED = "failed"
OUTCOME_STOPPED = "stopped"

logger = get_logger("executor")


class ExecutionListener(Protocol):
    def run_started(self, sequence_id: str, source: str) -> None: ...

    def step_started(self, sequence_id: str, step_id: str) -> None: ...

    def step_finished(self, sequence_id: str, step_id: str, error: Optional[str]) -> None: ...

    def run_finished(self, sequence_id: str, outcome: str, error: Optional[str]) -> None: ...


class StepFailed(RuntimeError):
    pass


@dataclass
class _RunContext:
    """État partagé par une séquence et ses sous-séquences (même thread, même bouton Stop)."""

    stop: StopToken = field(default_factory=StopToken)
    stack: list[str] = field(default_factory=list)


class SequenceExecutor:
    def __init__(
        self,
        *,
        resolve_sequence: Callable[[str], Optional[LaunchSequence]],
        run_remote: Callable[[ActionStep, StopToken], None],
        home_assistant_settings: Callable[[], tuple[str, str]],
        listener: ExecutionListener,
    ) -> None:
        self._resolve_sequence = resolve_sequence
        self._run_remote = run_remote
        self._home_assistant_settings = home_assistant_settings
        self._listener = listener
        self._lock = threading.Lock()
        self._runs: dict[str, _RunContext] = {}

    # --- API publique ---------------------------------------------------------------------

    def start_sequence(self, sequence_id: str, source: str = "manuel") -> bool:
        """Lance une séquence dans un thread. Renvoie False si elle tourne déjà."""
        sequence = self._resolve_sequence(sequence_id)
        if sequence is None:
            raise ValueError("Séquence introuvable")
        context = _RunContext()
        if not self._register(sequence.id, context):
            return False
        snapshot = sequence.clone()
        threading.Thread(
            target=self._run_top_level,
            args=(snapshot, source, context),
            name=f"sequence-{sequence.id}",
            daemon=True,
        ).start()
        return True

    def run_single_step(self, step: ActionStep, on_done: Callable[[Optional[str]], None]) -> None:
        """Teste une étape isolée dans un thread ; `on_done` reçoit l'erreur éventuelle."""
        snapshot = step.clone()

        def worker() -> None:
            try:
                self._run_step(snapshot, _RunContext())
            except StopRequested:
                on_done("Arrêtée")
            except Exception as exc:
                logger.error(f"Test de l'étape « {snapshot.label} » en erreur: {exc}")
                on_done(_describe(exc))
            else:
                logger.info(f"Test de l'étape « {snapshot.label} » réussi")
                on_done(None)

        threading.Thread(target=worker, name=f"step-{step.id}", daemon=True).start()

    def stop_sequence(self, sequence_id: str) -> bool:
        with self._lock:
            context = self._runs.get(sequence_id)
        if context is None:
            return False
        context.stop.set()
        return True

    def stop_all(self) -> None:
        with self._lock:
            contexts = list(self._runs.values())
        for context in contexts:
            context.stop.set()

    def is_running(self, sequence_id: str) -> bool:
        with self._lock:
            return sequence_id in self._runs

    def running_ids(self) -> set[str]:
        with self._lock:
            return set(self._runs)

    # --- Exécution ------------------------------------------------------------------------

    def _register(self, sequence_id: str, context: _RunContext) -> bool:
        with self._lock:
            if sequence_id in self._runs:
                return False
            self._runs[sequence_id] = context
            return True

    def _unregister(self, sequence_id: str, context: _RunContext) -> None:
        with self._lock:
            if self._runs.get(sequence_id) is context:
                del self._runs[sequence_id]

    def _run_top_level(self, sequence: LaunchSequence, source: str, context: _RunContext) -> None:
        logger.info(f"Séquence « {sequence.name} » démarrée ({source})")
        self._listener.run_started(sequence.id, source)
        outcome, error = OUTCOME_SUCCESS, None
        try:
            self._execute(sequence, context)
            logger.info(f"Séquence « {sequence.name} » terminée")
        except StopRequested:
            outcome = OUTCOME_STOPPED
            logger.warning(f"Séquence « {sequence.name} » arrêtée")
        except Exception as exc:
            outcome, error = OUTCOME_FAILED, _describe(exc)
            logger.error(f"Séquence « {sequence.name} » en échec: {error}")
        finally:
            # Notifier avant de libérer : une relance immédiate ne doit pas voir son état écrasé.
            self._listener.run_finished(sequence.id, outcome, error)
            self._unregister(sequence.id, context)

    def _execute(self, sequence: LaunchSequence, context: _RunContext) -> None:
        context.stack.append(sequence.id)
        try:
            total = len(sequence.steps)
            for index, step in enumerate(sequence.steps, start=1):
                if not step.enabled:
                    continue
                context.stop.check()
                self._listener.step_started(sequence.id, step.id)
                try:
                    self._run_step(step, context)
                except StopRequested:
                    raise
                except Exception as exc:
                    message = _describe(exc)
                    self._listener.step_finished(sequence.id, step.id, message)
                    if step.continue_on_error:
                        logger.warning(f"Étape {index}/{total} ({step.label}) en erreur, on continue: {message}")
                        continue
                    raise StepFailed(f"Étape {index} ({step.label}) : {message}") from exc
                self._listener.step_finished(sequence.id, step.id, None)
        finally:
            context.stack.pop()

    def _run_nested(self, sequence_id: str, context: _RunContext) -> None:
        sequence = self._resolve_sequence(sequence_id)
        if sequence is None:
            raise ValueError("La séquence appelée n'existe plus")
        if sequence.id in context.stack:
            raise ValueError(f"Boucle détectée : « {sequence.name} » s'appelle elle-même")
        if not self._register(sequence.id, context):
            raise RuntimeError(f"La séquence « {sequence.name} » est déjà en cours")
        snapshot = sequence.clone()
        self._listener.run_started(snapshot.id, "sous-séquence")
        outcome, error = OUTCOME_SUCCESS, None
        try:
            self._execute(snapshot, context)
        except StopRequested:
            outcome = OUTCOME_STOPPED
            raise
        except Exception as exc:
            outcome, error = OUTCOME_FAILED, _describe(exc)
            raise RuntimeError(f"Sous-séquence « {snapshot.name} » : {error}") from exc
        finally:
            self._listener.run_finished(snapshot.id, outcome, error)
            self._unregister(snapshot.id, context)

    def _run_step(self, step: ActionStep, context: _RunContext) -> None:
        stop = context.stop
        stop.check()
        kind = step.action_type
        if kind == ACTION_LAUNCH_APP:
            actions.launch_app(step, stop)
        elif kind == ACTION_SHELL_COMMAND:
            actions.run_shell_command(step, stop)
        elif kind == ACTION_OPEN_WEBPAGE:
            actions.open_webpage(step)
        elif kind == ACTION_CALL_WEBHOOK:
            status = actions.call_webhook(step)
            logger.info(f"Webhook appelé (HTTP {status})")
        elif kind == ACTION_WAKE_ON_LAN:
            actions.wake_on_lan(step)
            logger.info(f"Wake-on-LAN envoyé à {step.mac_address.strip()}")
        elif kind == ACTION_DELAY:
            stop.sleep(step.seconds)
        elif kind == ACTION_LOCAL_SEQUENCE:
            if not step.local_sequence_id.strip():
                raise ValueError("Aucune séquence locale sélectionnée")
            self._run_nested(step.local_sequence_id.strip(), context)
        elif kind == ACTION_REMOTE_SEQUENCE:
            self._run_remote(step, stop)
        elif kind == ACTION_HOME_ASSISTANT:
            base_url, token = self._home_assistant_settings()
            logger.info(f"Home Assistant: {actions.call_home_assistant(step, base_url, token)}")
        else:
            raise ValueError(f"Type d'action inconnu: {kind}")


def _describe(exc: BaseException) -> str:
    return str(exc).strip() or exc.__class__.__name__
