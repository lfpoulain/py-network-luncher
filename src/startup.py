from __future__ import annotations

import subprocess
import sys
import winreg
from pathlib import Path

from runtime_paths import app_root, is_frozen


RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "Py Network Launcher"


def project_root() -> Path:
    return app_root()


def startup_registration_label() -> str:
    return rf"HKCU\{RUN_KEY_PATH}\{RUN_VALUE_NAME}"


def _python_command() -> str:
    executable = Path(sys.executable)
    pythonw = executable.with_name("pythonw.exe")
    if pythonw.exists():
        return str(pythonw)
    return str(executable)


def _startup_command(*, hidden: bool) -> str:
    if is_frozen():
        args = [str(Path(sys.executable).resolve())]
    else:
        main_script = project_root() / "main.py"
        args = [str(_python_command()), str(main_script)]
    if hidden:
        args.append("--hidden")
    return subprocess.list2cmdline(args)


def install_startup_task(*, hidden: bool) -> str:
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH) as key:
            winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, _startup_command(hidden=hidden))
    except OSError as exc:
        raise RuntimeError(f"Impossible d'enregistrer le démarrage Windows: {exc}") from exc
    return startup_registration_label()


def remove_startup_task() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, RUN_VALUE_NAME)
            except FileNotFoundError:
                return
    except FileNotFoundError:
        return
    except OSError as exc:
        raise RuntimeError(f"Impossible de supprimer le démarrage Windows: {exc}") from exc
