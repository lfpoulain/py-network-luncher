from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    if is_frozen():
        executable_dir = Path(sys.executable).resolve().parent
        candidates: list[Path] = []
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            meipass_path = Path(meipass)
            candidates.append(meipass_path)
            candidates.append(meipass_path.parent)
        candidates.append(executable_dir)
        for candidate in candidates:
            if (candidate / "assets").exists():
                return candidate
        return executable_dir
    return Path(__file__).resolve().parents[1]


def assets_dir() -> Path:
    return app_root() / "assets"


def app_icon_path() -> Path:
    return assets_dir() / "app_icon.ico"
