"""Intégrations Windows : démarrage automatique, session courante, instance unique."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

from py_network_launcher import APP_ID, APP_NAME
from py_network_launcher.paths import app_root, is_frozen

IS_WINDOWS = os.name == "nt"

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = APP_NAME
ERROR_ALREADY_EXISTS = 183


# --- Démarrage avec Windows -------------------------------------------------------------


def startup_entry_label() -> str:
    return rf"HKCU\{RUN_KEY_PATH}\{RUN_VALUE_NAME}"


def startup_command(*, hidden: bool) -> str:
    if is_frozen():
        args = [str(Path(sys.executable).resolve())]
    else:
        executable = Path(sys.executable)
        pythonw = executable.with_name("pythonw.exe")
        args = [str(pythonw if pythonw.exists() else executable), str(app_root() / "main.py")]
    if hidden:
        args.append("--hidden")
    return subprocess.list2cmdline(args)


def set_launch_at_startup(enabled: bool, *, hidden: bool) -> None:
    """Crée, met à jour ou supprime l'entrée `Run` de l'utilisateur courant."""
    if not IS_WINDOWS:
        raise RuntimeError("Le démarrage automatique n'est disponible que sous Windows")
    import winreg

    try:
        if enabled:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH) as key:
                winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, startup_command(hidden=hidden))
            return
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, RUN_VALUE_NAME)
    except FileNotFoundError:
        return
    except OSError as exc:
        action = "enregistrer" if enabled else "supprimer"
        raise RuntimeError(f"Impossible d'{action} le démarrage Windows: {exc}") from exc


def registered_startup_command() -> Optional[str]:
    if not IS_WINDOWS:
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH) as key:
            value, _ = winreg.QueryValueEx(key, RUN_VALUE_NAME)
            return str(value)
    except OSError:
        return None


# --- Identifiant de session -------------------------------------------------------------


def current_session_id() -> str:
    """Identifie la session Windows courante (change à chaque ouverture de session).

    On s'appuie sur l'heure d'ouverture de session plutôt que sur l'heure de démarrage
    du système : avec le « démarrage rapide » de Windows, un arrêt/rallumage ne remet pas
    le compteur de temps système à zéro, alors qu'il crée bien une nouvelle session.
    """
    logon = _session_logon_time()
    if logon is not None:
        return f"logon-{int(logon)}"
    return f"boot-{round(_boot_time() / 60.0)}"


def _session_logon_time() -> Optional[float]:
    if not IS_WINDOWS:
        return None
    from ctypes import wintypes

    class WTSINFOW(ctypes.Structure):
        _fields_ = [
            ("State", ctypes.c_int),
            ("SessionId", wintypes.DWORD),
            ("IncomingBytes", wintypes.DWORD),
            ("OutgoingBytes", wintypes.DWORD),
            ("IncomingFrames", wintypes.DWORD),
            ("OutgoingFrames", wintypes.DWORD),
            ("IncomingCompressedBytes", wintypes.DWORD),
            ("OutgoingCompressedBytes", wintypes.DWORD),
            ("WinStationName", wintypes.WCHAR * 32),
            ("Domain", wintypes.WCHAR * 17),
            ("UserName", wintypes.WCHAR * 21),
            ("ConnectTime", ctypes.c_longlong),
            ("DisconnectTime", ctypes.c_longlong),
            ("LastInputTime", ctypes.c_longlong),
            ("LogonTime", ctypes.c_longlong),
            ("CurrentTime", ctypes.c_longlong),
        ]

    wts_current_session = wintypes.DWORD(0xFFFFFFFF)
    wts_session_info = 24
    buffer = ctypes.c_void_p()
    size = wintypes.DWORD()
    try:
        wtsapi = ctypes.WinDLL("wtsapi32")
        if not wtsapi.WTSQuerySessionInformationW(None, wts_current_session, wts_session_info, ctypes.byref(buffer), ctypes.byref(size)):
            return None
        try:
            if size.value < ctypes.sizeof(WTSINFOW):
                return None
            logon_filetime = ctypes.cast(buffer, ctypes.POINTER(WTSINFOW)).contents.LogonTime
        finally:
            wtsapi.WTSFreeMemory(buffer)
    except (OSError, AttributeError):
        return None
    if logon_filetime <= 0:
        return None
    return logon_filetime / 10_000_000 - 11_644_473_600


def _boot_time() -> float:
    uptime_s = 0.0
    if IS_WINDOWS:
        try:
            kernel32 = ctypes.windll.kernel32
            kernel32.GetTickCount64.restype = ctypes.c_ulonglong
            uptime_s = kernel32.GetTickCount64() / 1000.0
        except (OSError, AttributeError):
            uptime_s = 0.0
    if uptime_s <= 0.0:
        uptime_s = time.monotonic()
    return max(0.0, time.time() - uptime_s)


# --- Instance unique --------------------------------------------------------------------


class SingleInstanceLock:
    """Mutex nommé Windows : permet de détecter une instance déjà lancée."""

    NAME = f"Local\\{APP_ID}-single-instance"

    def __init__(self) -> None:
        self._handle: Any = None
        self.already_running = False
        if not IS_WINDOWS:
            return
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateMutexW.restype = ctypes.c_void_p
            self._handle = kernel32.CreateMutexW(None, False, self.NAME)
            self.already_running = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
        except (OSError, AttributeError):
            self._handle = None

    def release(self) -> None:
        if self._handle:
            try:
                ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(self._handle))
            except (OSError, AttributeError):
                pass
            self._handle = None


# --- Divers -----------------------------------------------------------------------------


def open_in_explorer(path: Path) -> None:
    target = path if path.exists() else path.parent
    if IS_WINDOWS:
        os.startfile(str(target))
        return
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, str(target)])
