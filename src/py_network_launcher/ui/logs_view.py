"""Vue « Journal » : derniers événements, erreurs en évidence."""

from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from py_network_launcher.logs import LogEntry, log_file_path, memory_handler
from py_network_launcher.ui.widgets import COLOR_ERROR, COLOR_MUTED, empty_state, panel

if TYPE_CHECKING:
    from py_network_launcher.ui.window import MainWindow

MAX_VISIBLE_ENTRIES = 300


class LogsView:
    def __init__(self, window: MainWindow) -> None:
        self.window = window
        self._errors_only = False
        self._list = ft.ListView(expand=True, spacing=2, auto_scroll=True, padding=ft.Padding.only(right=8))
        self._filter = ft.Switch(label="Erreurs seulement", value=False, on_change=self._on_filter, label_text_style=ft.TextStyle(size=13))
        actions: list[ft.Control] = [
            self._filter,
            ft.IconButton(icon=ft.Icons.CLEAR_ALL, tooltip="Vider le journal", on_click=lambda _: self._clear()),
        ]
        if log_file_path() is not None:
            actions.append(
                ft.IconButton(icon=ft.Icons.FOLDER_OPEN, tooltip="Ouvrir le dossier des journaux", on_click=lambda _: self.window.open_logs_folder())
            )
        self.control = panel(
            title="Journal",
            subtitle="Lancements, erreurs et activité réseau de cette session.",
            actions=actions,
            content=ft.Container(
                expand=True,
                bgcolor=ft.Colors.SURFACE_CONTAINER_LOWEST,
                border_radius=10,
                padding=ft.Padding.only(left=12, top=8, bottom=8, right=4),
                content=self._list,
            ),
        )
        self.refresh()

    def refresh(self) -> None:
        entries = [entry for entry in memory_handler().entries() if not self._errors_only or entry.is_error or entry.is_warning]
        if not entries:
            self._list.controls = [
                empty_state(icon=ft.Icons.RECEIPT_LONG_OUTLINED, title="Rien à afficher", message="Les événements de l'application apparaîtront ici.")
            ]
            return
        self._list.controls = [self._line(entry) for entry in entries[-MAX_VISIBLE_ENTRIES:]]

    def _line(self, entry: LogEntry) -> ft.Control:
        color = COLOR_ERROR if entry.is_error else (ft.Colors.AMBER_200 if entry.is_warning else None)
        return ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Text(entry.time, size=12, font_family="Consolas", color=COLOR_MUTED),
                ft.Text(entry.message, size=12, font_family="Consolas", color=color, selectable=True, expand=True),
            ],
        )

    def _on_filter(self, event) -> None:
        self._errors_only = bool(event.control.value)
        self.refresh()

    def _clear(self) -> None:
        memory_handler().clear()
        self.refresh()
