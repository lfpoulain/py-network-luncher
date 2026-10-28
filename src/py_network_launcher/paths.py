from __future__ import annotations

import os
import sys
from pathlib import Path

from py_network_launcher import APP_ID

HOME_ENV_VAR = "PY_NETWORK_LAUNCHER_HOME"
LEGACY_CONFIG_FILE_NAME = "py-network-launcher.json"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """Dossier contenant `assets/` (racine du dépôt ou dossier de l'exécutable)."""
    if is_frozen():
        candidates: list[Path] = []
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates += [Path(meipass), Path(meipass).parent]
        executable_dir = Path(sys.executable).resolve().parent
        candidates.append(executable_dir)
        return next((path for path in candidates if (path / "assets").exists()), executable_dir)
    return Path(__file__).resolve().parents[2]


def assets_dir() -> Path:
    return app_root() / "assets"


def app_icon_path() -> Path:
    return assets_dir() / "app_icon.ico"


def data_dir() -> Path:
    """Dossier des données utilisateur (`%APPDATA%\\PyNetworkLauncher`)."""
    override = os.environ.get(HOME_ENV_VAR, "").strip()
    if override:
        return Path(override)
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / APP_ID


def config_path() -> Path:
    return data_dir() / "config.json"


def legacy_config_path() -> Path:
    """Emplacement utilisé jusqu'à la v0.1 (`%USERPROFILE%\\py-network-launcher.json`)."""
    return Path.home() / LEGACY_CONFIG_FILE_NAME


def logs_dir() -> Path:
    return data_dir() / "logs"
