"""Lanceur sans installation : `python main.py` (utilisé aussi comme point d'entrée PyInstaller)."""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from py_network_launcher.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
