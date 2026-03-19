from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import importlib.util

def collect_tree(root: Path, target_root: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    if not root.exists():
        return items
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative_parent = path.parent.relative_to(root)
        target_dir = Path(target_root, relative_parent).as_posix() if str(relative_parent) != "." else Path(target_root).as_posix()
        items.append((str(path), target_dir))
    return items

project_root = Path(SPECPATH)
src_dir = project_root / "src"
assets_dir = project_root / "assets"

flet_desktop_spec = importlib.util.find_spec("flet_desktop")
if flet_desktop_spec is None or flet_desktop_spec.origin is None:
    raise RuntimeError("flet_desktop package introuvable pour le packaging. Installe la dépendance build 'flet-desktop'.")
flet_desktop_dir = Path(flet_desktop_spec.origin).resolve().parent

hiddenimports = collect_submodules("flet") + collect_submodules("pystray") + collect_submodules("flet_desktop")
datas = collect_data_files("flet") + [(str(assets_dir), "assets")] + collect_tree(flet_desktop_dir / "app", "flet_desktop/app")

analysis = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root), str(src_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Py Network Launcher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(assets_dir / "app_icon.ico"),
)
coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    analysis.zipfiles,
    strip=False,
    upx=False,
    name="Py Network Launcher",
)
