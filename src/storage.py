from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from models import AppConfig


CONFIG_FILE_NAME = "py-network-launcher.json"


def read_json_file(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Configuration JSON invalide dans {path}") from exc
    except OSError as exc:
        raise RuntimeError(f"Impossible de lire la configuration dans {path}: {exc}") from exc


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        raise RuntimeError(f"Impossible d'écrire la configuration dans {path}: {exc}") from exc


def config_path() -> Path:
    return Path.home() / CONFIG_FILE_NAME


def load_config() -> AppConfig:
    loaded = read_json_file(config_path())
    if isinstance(loaded, dict):
        return AppConfig.from_dict(loaded)
    return AppConfig()


def save_config(config: AppConfig) -> Path:
    path = config_path()
    atomic_write_json(path, config.to_dict())
    return path
