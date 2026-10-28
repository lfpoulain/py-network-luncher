from __future__ import annotations

import threading
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any, Optional

from py_network_launcher.logs import get_logger

logger = get_logger("tray")


class SystemTray:
    """Icône de la zone de notification (pystray), avec lancement rapide des séquences.

    Les callbacks sont appelés depuis le thread de pystray : ils doivent être thread-safe.
    """

    def __init__(
        self,
        *,
        icon_path: Path,
        title: str,
        on_show: Callable[[], None],
        on_quit: Callable[[], None],
        list_sequences: Callable[[], list[tuple[str, str, bool]]],
        on_toggle_sequence: Callable[[str], None],
    ) -> None:
        self._icon_path = icon_path
        self._title = title
        self._on_show = on_show
        self._on_quit = on_quit
        self._list_sequences = list_sequences
        self._on_toggle_sequence = on_toggle_sequence
        self._icon: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        import pystray
        from PIL import Image

        with Image.open(self._icon_path) as source:
            image = source.copy()
        menu = pystray.Menu(
            pystray.MenuItem("Afficher", lambda: self._on_show(), default=True),
            pystray.MenuItem("Séquences", pystray.Menu(self._sequence_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quitter", lambda: self._on_quit()),
        )
        self._icon = pystray.Icon("py-network-launcher", image, self._title, menu)
        self._thread = threading.Thread(target=self._icon.run, name="system-tray", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        icon, thread = self._icon, self._thread
        self._icon = self._thread = None
        if icon is None:
            return
        try:
            icon.stop()
        except Exception as exc:
            logger.warning(f"Arrêt de l'icône de notification incomplet: {exc}")
        if thread is not None and thread.is_alive() and threading.current_thread() is not thread:
            thread.join(timeout=1.0)

    def refresh_menu(self) -> None:
        if self._icon is not None:
            try:
                self._icon.update_menu()
            except Exception:
                pass

    def notify(self, message: str, title: str = "") -> None:
        if self._icon is None:
            return
        try:
            self._icon.notify(message, title or self._title)
        except Exception:
            pass

    def _sequence_items(self):
        import pystray

        sequences = self._list_sequences()
        if not sequences:
            yield pystray.MenuItem("Aucune séquence", None, enabled=False)
            return
        for sequence_id, name, running in sequences:
            label = f"■ Arrêter « {name} »" if running else f"▶ {name}"
            # Un `partial` (sans __code__) est appelé par pystray avec (icon, item).
            yield pystray.MenuItem(label, partial(self._toggle_from_menu, sequence_id))

    def _toggle_from_menu(self, sequence_id: str, _icon: Any, _item: Any) -> None:
        self._on_toggle_sequence(sequence_id)
