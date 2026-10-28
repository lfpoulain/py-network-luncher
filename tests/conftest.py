from __future__ import annotations

import socket
import threading
from pathlib import Path
from typing import Optional

import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Chaque test écrit sa configuration dans un dossier temporaire."""
    home = tmp_path / "data"
    monkeypatch.setenv("PY_NETWORK_LAUNCHER_HOME", str(home))
    return home


def free_port(kind: int = socket.SOCK_STREAM) -> int:
    with socket.socket(socket.AF_INET, kind) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class RecordingListener:
    """Enregistre les événements de l'exécuteur et permet d'attendre la fin d'une séquence."""

    def __init__(self) -> None:
        self.events: list[tuple] = []
        self.finished: dict[str, tuple[str, Optional[str]]] = {}
        self._done = threading.Condition()

    def run_started(self, sequence_id: str, source: str) -> None:
        self.events.append(("run_started", sequence_id))

    def step_started(self, sequence_id: str, step_id: str) -> None:
        self.events.append(("step_started", sequence_id, step_id))

    def step_finished(self, sequence_id: str, step_id: str, error: Optional[str]) -> None:
        self.events.append(("step_finished", sequence_id, step_id, error))

    def run_finished(self, sequence_id: str, outcome: str, error: Optional[str]) -> None:
        with self._done:
            self.events.append(("run_finished", sequence_id, outcome))
            self.finished[sequence_id] = (outcome, error)
            self._done.notify_all()

    def wait(self, sequence_id: str, timeout: float = 10.0) -> tuple[str, Optional[str]]:
        with self._done:
            assert self._done.wait_for(lambda: sequence_id in self.finished, timeout), f"{sequence_id} n'a pas terminé"
            return self.finished[sequence_id]
