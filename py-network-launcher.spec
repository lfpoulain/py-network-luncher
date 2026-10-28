# -*- mode: python ; coding: utf-8 -*-
# Build : `python -m PyInstaller --noconfirm py-network-launcher.spec` (ou scripts\build.ps1).
import importlib.util
import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

APP_NAME = "Py Network Launcher"

project_root = Path(SPECPATH)
src_dir = project_root / "src"
assets_dir = project_root / "assets"

version = re.search(r'__version__ = "([^"]+)"', (src_dir / "py_network_launcher" / "__init__.py").read_text(encoding="utf-8")).group(1)
numeric = (*(int(part) for part in re.findall(r"\d+", version)[:3]), 0, 0, 0, 0)[:4]


def collect_tree(root: Path, target_root: str) -> list[tuple[str, str]]:
    items = []
    for path in root.rglob("*"):
        if path.is_file():
            relative_parent = path.parent.relative_to(root)
            items.append((str(path), str(Path(target_root, relative_parent).as_posix())))
    return items


flet_desktop_spec = importlib.util.find_spec("flet_desktop")
if flet_desktop_spec is None or flet_desktop_spec.origin is None:
    raise RuntimeError("Paquet 'flet-desktop' introuvable : installe les dépendances (pip install -e .[build]).")
flet_desktop_dir = Path(flet_desktop_spec.origin).resolve().parent

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=numeric, prodvers=numeric),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040C04B0",
                    [
                        StringStruct("CompanyName", "LFPoulain"),
                        StringStruct("FileDescription", APP_NAME),
                        StringStruct("FileVersion", version),
                        StringStruct("InternalName", "py-network-launcher"),
                        StringStruct("LegalCopyright", "Licence propriétaire non commerciale"),
                        StringStruct("OriginalFilename", f"{APP_NAME}.exe"),
                        StringStruct("ProductName", APP_NAME),
                        StringStruct("ProductVersion", version),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [0x040C, 1200])]),
    ],
)

analysis = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(src_dir)],
    datas=collect_data_files("flet") + [(str(assets_dir), "assets")] + collect_tree(flet_desktop_dir / "app", "flet_desktop/app"),
    hiddenimports=collect_submodules("py_network_launcher") + collect_submodules("flet") + collect_submodules("flet_desktop") + collect_submodules("pystray"),
    excludes=["flet_web", "fastapi", "uvicorn", "pytest", "tkinter"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    upx=False,
    icon=str(assets_dir / "app_icon.ico"),
    version=version_info,
)
coll = COLLECT(exe, analysis.binaries, analysis.datas, analysis.zipfiles, upx=False, name=APP_NAME)
