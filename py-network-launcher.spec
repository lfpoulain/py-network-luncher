# -*- mode: python ; coding: utf-8 -*-
# Build : `python -m PyInstaller --noconfirm py-network-launcher.spec` (ou scripts\build.ps1).
import hashlib
import importlib.metadata
import re
import shutil
import urllib.request
import zipfile
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

# Depuis Flet 0.83, le client de bureau (flet.exe) n'est plus dans le paquet flet-desktop : Flet le télécharge au
# premier lancement. On l'embarque pour que l'application fonctionne hors ligne. À chaque montée de version de Flet,
# ajoute l'empreinte de flet-windows.zip (champ « digest » de l'asset dans la release GitHub de Flet).
FLET_CLIENT_SHA256 = {
    "1.0.5": "6b5bddbcf2df8d0986dec60eab0b28c8cd8be1c0cd96cd73d5e34a3122ca867d",
}

project_root = Path(SPECPATH)
src_dir = project_root / "src"
assets_dir = project_root / "assets"

version = re.search(r'__version__ = "([^"]+)"', (src_dir / "py_network_launcher" / "__init__.py").read_text(encoding="utf-8")).group(1)
numeric = (*(int(part) for part in re.findall(r"\d+", version)[:3]), 0, 0, 0, 0)[:4]


def collect_tree(root: Path, target_root: str) -> list[tuple[str, str, str]]:
    """Copie telle quelle, pour COLLECT : passées par Analysis, les DLL seraient analysées et dupliquées à la racine."""
    return [(str(Path(target_root, path.relative_to(root))), str(path), "DATA") for path in root.rglob("*") if path.is_file()]


def flet_client_dir() -> Path:
    """Client Flet de la version installée, téléchargé et vérifié une fois dans .cache/."""
    try:
        flet_version = importlib.metadata.version("flet-desktop")
    except importlib.metadata.PackageNotFoundError:
        raise RuntimeError("Paquet 'flet-desktop' introuvable : installe les dépendances (pip install -e .[build]).") from None
    expected = FLET_CLIENT_SHA256.get(flet_version)
    if expected is None:
        raise RuntimeError(f"Empreinte du client Flet {flet_version} inconnue : ajoute-la à FLET_CLIENT_SHA256 dans le .spec.")
    cache = project_root / ".cache" / f"flet-client-{flet_version}"
    client = cache / "flet"
    if (client / "flet.exe").is_file():
        return client
    archive = cache / "flet-windows.zip"
    if not archive.is_file():
        cache.mkdir(parents=True, exist_ok=True)
        print(f"Téléchargement du client Flet {flet_version}…")
        partial = archive.with_suffix(".part")
        urllib.request.urlretrieve(f"https://github.com/flet-dev/flet/releases/download/v{flet_version}/flet-windows.zip", partial)
        partial.replace(archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != expected:
        archive.unlink()
        raise RuntimeError(f"Empreinte inattendue pour le client Flet {flet_version} : {digest}")
    staging = cache / "extraction"
    shutil.rmtree(staging, ignore_errors=True)
    with zipfile.ZipFile(archive) as content:
        content.extractall(staging)
    if not (staging / "flet" / "flet.exe").is_file():
        raise RuntimeError("flet.exe absent de l'archive du client Flet")
    (staging / "flet").replace(client)
    shutil.rmtree(staging, ignore_errors=True)
    return client

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
    datas=collect_data_files("flet") + [(str(assets_dir), "assets")],
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
coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    analysis.zipfiles,
    collect_tree(flet_client_dir(), "flet_client/flet"),
    upx=False,
    name=APP_NAME,
)
