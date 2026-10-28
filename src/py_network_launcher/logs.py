from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

LOGGER_NAME = "py_network_launcher"
LOG_FILE_NAME = "py-network-launcher.log"


def get_logger(suffix: str = "") -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{suffix}" if suffix else LOGGER_NAME)


@dataclass(frozen=True, slots=True)
class LogEntry:
    time: str
    level: str
    message: str

    @property
    def is_error(self) -> bool:
        return self.level in ("ERROR", "CRITICAL")

    @property
    def is_warning(self) -> bool:
        return self.level == "WARNING"

    def format(self) -> str:
        return f"[{self.time}] {self.message}"


class MemoryLogHandler(logging.Handler):
    """Garde les derniers messages en mémoire pour l'onglet Journal."""

    def __init__(self, capacity: int = 500) -> None:
        super().__init__(level=logging.INFO)
        self._entries: deque[LogEntry] = deque(maxlen=capacity)
        self._entries_lock = threading.Lock()
        self._listeners: list[Callable[[LogEntry], None]] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)
        entry = LogEntry(time=time.strftime("%H:%M:%S", time.localtime(record.created)), level=record.levelname, message=message)
        with self._entries_lock:
            self._entries.append(entry)
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(entry)
            except Exception:
                pass

    def entries(self) -> list[LogEntry]:
        with self._entries_lock:
            return list(self._entries)

    def clear(self) -> None:
        with self._entries_lock:
            self._entries.clear()

    def add_listener(self, listener: Callable[[LogEntry], None]) -> None:
        with self._entries_lock:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[LogEntry], None]) -> None:
        with self._entries_lock:
            if listener in self._listeners:
                self._listeners.remove(listener)


_memory_handler: Optional[MemoryLogHandler] = None
_log_file: Optional[Path] = None


def setup_logging(log_dir: Optional[Path]) -> MemoryLogHandler:
    """Configure le logger de l'application (mémoire + fichier tournant). Idempotent."""
    global _memory_handler, _log_file
    logger = get_logger()
    if _memory_handler is not None:
        return _memory_handler
    logger.setLevel(logging.INFO)
    logger.propagate = False
    _memory_handler = MemoryLogHandler()
    logger.addHandler(_memory_handler)
    if log_dir is not None:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            _log_file = log_dir / LOG_FILE_NAME
            file_handler = RotatingFileHandler(_log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
            logger.addHandler(file_handler)
        except OSError:
            _log_file = None
    return _memory_handler


def memory_handler() -> MemoryLogHandler:
    return _memory_handler if _memory_handler is not None else setup_logging(None)


def log_file_path() -> Optional[Path]:
    return _log_file
