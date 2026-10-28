from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Optional

from py_network_launcher.logs import get_logger
from py_network_launcher.models import AppConfig
from py_network_launcher.paths import config_path, legacy_config_path

logger = get_logger("storage")


class ConfigStore:
    """Lecture/écriture atomique du fichier de configuration JSON.

    - migre automatiquement l'ancien fichier `%USERPROFILE%\\py-network-launcher.json` ;
    - met de côté un fichier illisible au lieu de l'écraser ;
    - regroupe les sauvegardes rapprochées (`save_soon`) pour éviter d'écrire à chaque frappe.
    """

    def __init__(
        self,
        path: Optional[Path] = None,
        *,
        legacy_path: Optional[Path] = None,
        on_save_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        self.path = path or config_path()
        self.legacy_path = legacy_path if legacy_path is not None else (legacy_config_path() if path is None else None)
        self.on_save_error = on_save_error
        self.load_warning: Optional[str] = None
        self.read_only = False
        self._write_lock = threading.Lock()
        self._timer_lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None
        self._pending: Optional[AppConfig] = None

    def load(self) -> AppConfig:
        self.load_warning = None
        self._migrate_legacy_file()
        if not self.path.exists():
            return AppConfig()
        try:
            raw = self._read_with_retries()
        except OSError as exc:
            # Fichier verrouillé (antivirus, sauvegarde…) : surtout ne pas l'écraser avec une config vierge.
            self.read_only = True
            self.load_warning = f"Configuration inaccessible ({exc}). Les modifications ne seront pas enregistrées : redémarre l'application."
            logger.error(self.load_warning)
            return AppConfig()
        try:
            # utf-8-sig : tolère le BOM ajouté par certains éditeurs (Bloc-notes, PowerShell).
            data = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            backup = self._quarantine_unreadable_file()
            self.read_only = backup is None  # sans copie de secours, on n'écrase pas l'original
            self.load_warning = (
                f"Configuration illisible ({exc.__class__.__name__}). "
                + (f"Copie conservée dans {backup.name}. " if backup else "")
                + "Une configuration vierge a été chargée."
            )
            logger.error(self.load_warning)
            return AppConfig()
        return AppConfig.from_dict(data)

    def _read_with_retries(self, attempts: int = 3) -> bytes:
        for attempt in range(attempts):
            try:
                return self.path.read_bytes()
            except OSError:
                if attempt == attempts - 1:
                    raise
                time.sleep(0.3)
        raise AssertionError("unreachable")

    def save(self, config: AppConfig) -> None:
        """Écrit immédiatement la configuration (annule une sauvegarde différée en attente)."""
        with self._timer_lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._pending = None
        self._write(config)

    def save_soon(self, config: AppConfig, delay_s: float = 0.6) -> None:
        with self._timer_lock:
            self._pending = config
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(delay_s, self._flush_pending)
            self._timer.daemon = True
            self._timer.start()

    def flush(self) -> None:
        self._flush_pending()

    def _flush_pending(self) -> None:
        with self._timer_lock:
            config = self._pending
            self._pending = None
            self._timer = None
        if config is None:
            return
        try:
            self._write(config)
        except Exception as exc:
            logger.error(str(exc))
            if self.on_save_error is not None:
                self.on_save_error(exc)

    def _write(self, config: AppConfig) -> None:
        if self.read_only:
            raise RuntimeError("Configuration non enregistrée : le fichier n'a pas pu être lu au démarrage.")
        with self._write_lock:
            payload = json.dumps(config.to_dict(), ensure_ascii=False, indent=2)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
            try:
                tmp.write_text(payload, encoding="utf-8", newline="\n")
                os.replace(tmp, self.path)
            except OSError as exc:
                tmp.unlink(missing_ok=True)
                raise RuntimeError(f"Impossible d'enregistrer la configuration dans {self.path}: {exc}") from exc

    def _quarantine_unreadable_file(self) -> Optional[Path]:
        backup = self.path.with_name(f"{self.path.stem}.illisible-{time.strftime('%Y%m%d-%H%M%S')}{self.path.suffix}")
        try:
            os.replace(self.path, backup)
            return backup
        except OSError:
            return None

    def _migrate_legacy_file(self) -> None:
        legacy = self.legacy_path
        if legacy is None or self.path.exists() or not legacy.exists():
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(legacy, self.path)
            logger.info(f"Configuration migrée de {legacy} vers {self.path}")
        except OSError as exc:
            logger.warning(f"Migration de la configuration impossible ({exc}), lecture de l'ancien fichier")
            self.path = legacy
