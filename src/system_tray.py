from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

import flet as ft


class SystemTrayController:
    def __init__(
        self,
        *,
        page: ft.Page,
        icon_path: Path,
        title: str,
        on_quit_requested: Callable[[], Awaitable[None]],
    ) -> None:
        self.page = page
        self.icon_path = icon_path
        self.title = title
        self.on_quit_requested = on_quit_requested
        self._icon: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        pystray, image = self._load_dependencies()
        menu = pystray.Menu(
            pystray.MenuItem("Afficher", self._on_show),
            pystray.MenuItem("Masquer", self._on_hide),
            pystray.MenuItem("Quitter", self._on_quit),
        )
        self._icon = pystray.Icon("py-network-launcher", image, self.title, menu)
        self._thread = threading.Thread(target=self._icon.run, name="py-network-launcher-tray", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        icon = self._icon
        thread = self._thread
        if icon is None:
            return
        icon.stop()
        if thread is not None and thread.is_alive() and threading.current_thread() is not thread:
            thread.join(timeout=1.0)
        self._icon = None
        self._thread = None

    def _load_dependencies(self):
        try:
            import pystray
        except ImportError as exc:
            raise RuntimeError("Le system tray nécessite la dépendance 'pystray'") from exc
        try:
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError("Le system tray nécessite la dépendance 'Pillow'") from exc
        with Image.open(self.icon_path) as image:
            return pystray, image.copy()

    def _on_show(self, icon, item) -> None:
        self.page.run_task(self._show_window)

    def _on_hide(self, icon, item) -> None:
        self.page.run_task(self._hide_window)

    def _on_quit(self, icon, item) -> None:
        self.page.run_task(self.on_quit_requested)

    async def _show_window(self) -> None:
        self.page.window.skip_task_bar = False
        self.page.window.visible = True
        self.page.window.minimized = False
        self.page.update()
        await self.page.window.to_front()

    async def _hide_window(self) -> None:
        self.page.window.skip_task_bar = True
        self.page.window.visible = False
        self.page.update()
