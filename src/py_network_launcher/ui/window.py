"""Fenêtre principale : navigation, barre d'état, zone de notification et liaison avec le service."""

from __future__ import annotations

import asyncio
import atexit
import threading
from collections.abc import Callable
from typing import Any, Optional

import flet as ft

from py_network_launcher import APP_NAME
from py_network_launcher.executor import OUTCOME_FAILED, OUTCOME_SUCCESS
from py_network_launcher.logs import LogEntry, get_logger, log_file_path, memory_handler
from py_network_launcher.models import CLOSE_ACTION_QUIT, ActionStep, AppConfig
from py_network_launcher.paths import app_icon_path, data_dir
from py_network_launcher.service import LauncherService, ServiceListener
from py_network_launcher.storage import ConfigStore
from py_network_launcher.tray import SystemTray
from py_network_launcher.ui.logs_view import LogsView
from py_network_launcher.ui.peers_view import PeersView
from py_network_launcher.ui.sequences_view import SequencesView
from py_network_launcher.ui.settings_view import SettingsView
from py_network_launcher.ui.widgets import COLOR_ERROR, COLOR_MUTED, COLOR_RUNNING, COLOR_SUCCESS, build_theme
from py_network_launcher.windows import IS_WINDOWS, open_in_explorer, registered_startup_command, set_launch_at_startup, startup_command

logger = get_logger("ui")

SECTIONS = (
    ("sequences", "Séquences", ft.Icons.PLAYLIST_PLAY_OUTLINED, ft.Icons.PLAYLIST_PLAY),
    ("peers", "Postes", ft.Icons.DEVICES_OUTLINED, ft.Icons.DEVICES),
    ("logs", "Journal", ft.Icons.RECEIPT_LONG_OUTLINED, ft.Icons.RECEIPT_LONG),
    ("settings", "Réglages", ft.Icons.SETTINGS_OUTLINED, ft.Icons.SETTINGS),
)


class _Listener(ServiceListener):
    """Relaie les événements du service (threads de fond) vers la boucle de l'UI."""

    def __init__(self, window: MainWindow) -> None:
        self.window = window

    def peers_changed(self) -> None:
        self.window.invalidate("peers")

    def run_state_changed(self, sequence_id: str) -> None:
        self.window.invalidate("runs")

    def run_finished(self, sequence_id: str, outcome: str, error: Optional[str]) -> None:
        self.window.on_run_finished(sequence_id, outcome, error)

    def network_state_changed(self) -> None:
        self.window.invalidate("network")

    def show_window_requested(self) -> None:
        self.window.run_on_ui(self.window.show_window)


class MainWindow:
    def __init__(self, page: ft.Page, *, hidden: bool, web: bool) -> None:
        self.page = page
        self.hidden = hidden
        self.web = web
        self._quitting = False
        self._window_visible = not hidden
        self._dirty: set[str] = set()
        self._dirty_lock = threading.Lock()
        self._flush_scheduled = False
        self._ready = False
        self._snack: Optional[ft.SnackBar] = None
        self.tray: Optional[SystemTray] = None

        self.store = ConfigStore(on_save_error=lambda exc: self.run_on_ui(lambda: self.notify(str(exc), error=True)))
        self.config: AppConfig = self.store.load()
        self.service = LauncherService(self.config, self.store, _Listener(self))
        self.file_picker = ft.FilePicker()

        self._configure_page()
        self.service.start()
        self.sequences_view = SequencesView(self)
        self.peers_view = PeersView(self)
        self.logs_view = LogsView(self)
        self.settings_view = SettingsView(self)
        self._views = {
            "sequences": self.sequences_view.control,
            "peers": self.peers_view.control,
            "logs": self.logs_view.control,
            "settings": self.settings_view.control,
        }
        self._build_layout()
        memory_handler().add_listener(self._on_log_entry)
        if web:
            # Mode développement : une session web fermée ou rechargée libère ses ports.
            page.on_disconnect = lambda _: self._shutdown()
        else:
            self._start_tray()
            atexit.register(self._shutdown)
        self._ready = True
        self._sync_startup_registration()
        self.service.launch_startup_sequences()
        if self.store.load_warning:
            self.notify(self.store.load_warning, error=True)

    # --- Mise en page ---------------------------------------------------------------------

    def _configure_page(self) -> None:
        page = self.page
        page.title = APP_NAME
        page.theme = build_theme()
        page.dark_theme = build_theme()
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 0
        page.spacing = 0
        if self.web:
            return
        icon = app_icon_path()
        if icon.exists():
            page.window.icon = str(icon)
        page.window.width = 1280
        page.window.height = 820
        page.window.min_width = 960
        page.window.min_height = 620
        page.window.on_event = self._on_window_event
        if self.hidden:
            page.window.skip_task_bar = True
            page.window.visible = False

    def _build_layout(self) -> None:
        self._rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=88,
            group_alignment=-0.9,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            leading=ft.Container(
                padding=ft.Padding.only(top=18, bottom=12),
                content=ft.Image(src="logo_64.png", width=44, height=44, tooltip=APP_NAME),
            ),
            destinations=[ft.NavigationRailDestination(icon=icon, selected_icon=selected_icon, label=label) for _key, label, icon, selected_icon in SECTIONS],
            on_change=self._on_navigate,
        )
        self._content = ft.Container(expand=True, padding=ft.Padding.only(left=16, right=16, top=16, bottom=8), content=self._views["sequences"])
        self._status_network = ft.Text(size=12)
        self._status_network_dot = ft.Icon(ft.Icons.CIRCLE, size=10)
        self._status_runs = ft.Text(size=12, color=COLOR_RUNNING)
        status_bar = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=6),
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            content=ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    self._status_runs,
                    ft.Container(expand=True),
                    ft.Container(
                        ink=True,
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                        on_click=lambda _: self.navigate("peers"),
                        tooltip="Voir les postes du réseau",
                        content=ft.Row(
                            spacing=6, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[self._status_network_dot, self._status_network]
                        ),
                    ),
                ],
            ),
        )
        self.page.add(
            ft.Row(
                expand=True,
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    self._rail,
                    ft.VerticalDivider(width=1),
                    ft.Column(expand=True, spacing=0, controls=[self._content, status_bar]),
                ],
            )
        )
        self._refresh_status_bar()

    def navigate(self, section: str) -> None:
        keys = [key for key, *_ in SECTIONS]
        if section not in keys:
            return
        self.flush_pending_save()
        self._rail.selected_index = keys.index(section)
        if section == "peers":
            self.peers_view.refresh()
        elif section == "logs":
            self.logs_view.refresh()
        elif section == "settings":
            self.settings_view.refresh()
        self._content.content = self._views[section]

    def _on_navigate(self, event: Any) -> None:
        self.navigate(SECTIONS[int(event.control.selected_index or 0)][0])

    def _current_section(self) -> str:
        return SECTIONS[int(self._rail.selected_index or 0)][0]

    def _refresh_status_bar(self) -> None:
        status = self.service.network_status()
        peers = len(self.service.peers())
        if status.ok:
            self._status_network_dot.color = COLOR_SUCCESS
            peers_text = "aucun autre poste" if peers == 0 else f"{peers} poste{'s' if peers > 1 else ''} en ligne"
            self._status_network.value = f"{self.config.settings.node_name} · port {status.api_port} · {peers_text}"
            self._status_network.color = COLOR_MUTED
        else:
            self._status_network_dot.color = COLOR_ERROR
            self._status_network.value = status.api_error or status.discovery_error
            self._status_network.color = COLOR_ERROR
        running = [sequence.name for sequence in self.config.sequences if self.service.is_running(sequence.id)]
        self._status_runs.value = f"▶ En cours : {', '.join(running)}" if running else ""

    # --- Rafraîchissements depuis les threads de fond -------------------------------------

    def run_on_ui(self, callback: Callable[[], Any]) -> None:
        async def runner() -> None:
            result = callback()
            if asyncio.iscoroutine(result):
                await result
            self.page.update()

        try:
            self.page.run_task(runner)
        except Exception:
            pass

    def invalidate(self, *parts: str) -> None:
        with self._dirty_lock:
            self._dirty.update(parts)
            if self._flush_scheduled:
                return
            self._flush_scheduled = True
        try:
            self.page.run_task(self._flush)
        except Exception:
            with self._dirty_lock:
                self._flush_scheduled = False

    async def _flush(self) -> None:
        await asyncio.sleep(0.08)  # regroupe les rafales d'événements
        with self._dirty_lock:
            parts, self._dirty = self._dirty, set()
            self._flush_scheduled = False
        if not self._ready:
            return
        section = self._current_section()
        if "runs" in parts:
            self.sequences_view.refresh_list()
            self.sequences_view.refresh_run_state()
        if "peers" in parts:
            self.sequences_view.refresh_dynamic_options()
            if section == "peers":
                self.peers_view.refresh()
        if "network" in parts:
            self.settings_view.refresh_network()
            if section == "peers":
                self.peers_view.refresh()
        if "logs" in parts and section == "logs":
            self.logs_view.refresh()
        if parts & {"runs", "sequences"} and self.tray is not None:
            self.tray.refresh_menu()
        self._refresh_status_bar()
        self.page.update()

    def _on_log_entry(self, _entry: LogEntry) -> None:
        if not self._quitting:
            self.invalidate("logs")

    def sequences_changed(self) -> None:
        self.invalidate("sequences")

    # --- Persistance ----------------------------------------------------------------------

    def save_soon(self) -> None:
        self.store.save_soon(self.config)

    def save_now(self) -> None:
        try:
            self.store.save(self.config)
        except RuntimeError as exc:
            self.notify(str(exc), error=True)

    def flush_pending_save(self) -> None:
        self.store.flush()

    # --- Feedback -------------------------------------------------------------------------

    def notify(self, message: str, *, error: bool = False, action_label: Optional[str] = None, on_action: Optional[Callable[[], None]] = None) -> None:
        if self._snack is not None and self._snack.open:
            self._snack.open = False
        snack = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.ON_ERROR_CONTAINER if error else None),
            bgcolor=ft.Colors.ERROR_CONTAINER if error else None,
            behavior=ft.SnackBarBehavior.FLOATING,
            width=560,
            duration=ft.Duration(seconds=8 if error else 4),
            show_close_icon=error,
            action=action_label,
            on_action=(lambda _: on_action()) if on_action is not None else None,
        )
        self._snack = snack
        self.page.show_dialog(snack)

    def confirm(self, *, title: str, message: str, confirm_label: str, on_confirm: Callable[[], None], destructive: bool = False) -> None:
        def close(confirmed: bool) -> None:
            # Ferme cette boîte précisément (pop_dialog() fermerait une notification affichée par-dessus).
            dialog.open = False
            if confirmed:
                on_confirm()

        dialog = ft.AlertDialog(
            modal=True,
            title=title,
            content=ft.Text(message),
            actions=[
                ft.TextButton("Annuler", on_click=lambda _: close(False)),
                ft.FilledButton(
                    confirm_label,
                    on_click=lambda _: close(True),
                    style=ft.ButtonStyle(bgcolor=ft.Colors.ERROR, color=ft.Colors.ON_ERROR) if destructive else None,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dialog)

    def on_run_finished(self, sequence_id: str, outcome: str, error: Optional[str]) -> None:
        sequence = self.config.find_sequence(sequence_id)
        name = sequence.name if sequence is not None else sequence_id

        def report() -> None:
            if outcome == OUTCOME_FAILED:
                self.notify(f"« {name} » a échoué : {error}", error=True)
                if not self._window_visible and self.tray is not None:
                    self.tray.notify(f"« {name} » a échoué : {error}")
            elif outcome == OUTCOME_SUCCESS and self._window_visible:
                self.notify(f"« {name} » terminée")

        self.run_on_ui(report)

    # --- Actions déclenchées par les vues -------------------------------------------------

    def toggle_run(self, sequence_id: str) -> None:
        sequence = self.config.find_sequence(sequence_id)
        if sequence is None:
            return
        if self.service.is_running(sequence_id):
            self.service.stop_sequence(sequence_id)
            self.notify(f"Arrêt de « {sequence.name} » demandé")
            return
        self.flush_pending_save()
        if not sequence.steps:
            self.notify(f"« {sequence.name} » n'a aucune étape", error=True)
            return
        try:
            self.service.start_sequence(sequence_id)
        except ValueError as exc:
            self.notify(str(exc), error=True)

    def test_step(self, step: ActionStep) -> None:
        self.notify(f"Test de « {step.label} »…")

        def done(error: Optional[str]) -> None:
            self.run_on_ui(lambda: self.notify(f"Échec du test : {error}", error=True) if error else self.notify(f"« {step.label} » : test réussi"))

        self.service.executor.run_single_step(step, done)

    def run_remote(self, peer_id: str, sequence_id: str) -> None:
        peer = self.service.find_peer(peer_id)
        if peer is None:
            self.notify("Ce poste n'est plus en ligne", error=True)
            return

        def worker() -> None:
            try:
                self.service.run_remote_sequence(peer, sequence_id)
                name = next((item.name for item in peer.sequences if item.id == sequence_id), sequence_id)
                self.run_on_ui(lambda: self.notify(f"« {name} » lancée sur {peer.name}"))
            except Exception as exc:
                message = str(exc)
                self.run_on_ui(lambda: self.notify(message, error=True))

        threading.Thread(target=worker, name="remote-run", daemon=True).start()

    def pick_file(self, callback: Callable[[str], None]) -> None:
        async def pick() -> None:
            files = await self.file_picker.pick_files(dialog_title="Choisir un programme ou un fichier", allow_multiple=False)
            path = str(getattr(files[0], "path", "") or "") if files else ""
            if path:
                callback(path)

        self.run_on_ui(pick)

    def pick_folder(self, callback: Callable[[str], None]) -> None:
        async def pick() -> None:
            path = await self.file_picker.get_directory_path(dialog_title="Choisir le dossier de travail")
            if path:
                callback(path)

        self.run_on_ui(pick)

    async def apply_network_settings(self, api_port: int, discovery_port: int) -> None:
        settings = self.config.settings
        settings.api_port, settings.discovery_port = api_port, discovery_port
        self.save_now()
        status = await asyncio.to_thread(self.service.restart_network)
        if status.ok:
            self.notify("Service réseau redémarré avec les nouveaux ports")
        else:
            self.notify(status.api_error or status.discovery_error, error=True)
        self._refresh_status_bar()

    def set_startup(self, enabled: bool, hidden: bool) -> bool:
        settings = self.config.settings
        try:
            set_launch_at_startup(enabled, hidden=hidden)
        except RuntimeError as exc:
            self.notify(str(exc), error=True)
            return False
        settings.start_with_windows, settings.start_minimized = enabled, hidden
        self.save_now()
        self.notify("Démarrage automatique activé" if enabled else "Démarrage automatique désactivé")
        return True

    def _sync_startup_registration(self) -> None:
        """Réécrit l'entrée de démarrage si l'application a été déplacée ou mise à jour."""
        settings = self.config.settings
        if not IS_WINDOWS or self.web or not settings.start_with_windows:
            return
        expected = startup_command(hidden=settings.start_minimized)
        if registered_startup_command() != expected:
            try:
                set_launch_at_startup(True, hidden=settings.start_minimized)
                logger.info("Entrée de démarrage Windows mise à jour")
            except RuntimeError as exc:
                logger.warning(str(exc))

    def open_data_folder(self) -> None:
        open_in_explorer(data_dir())

    def open_logs_folder(self) -> None:
        path = log_file_path()
        open_in_explorer(path if path is not None else data_dir())

    # --- Fenêtre et zone de notification --------------------------------------------------

    def _start_tray(self) -> None:
        icon = app_icon_path()
        if not icon.exists():
            logger.warning("Zone de notification indisponible : icône introuvable")
            return
        try:
            self.tray = SystemTray(
                icon_path=icon,
                title=APP_NAME,
                on_show=lambda: self.run_on_ui(self.show_window),
                on_quit=lambda: self.run_on_ui(self.quit),
                list_sequences=lambda: [(item.id, item.name, self.service.is_running(item.id)) for item in self.config.sequences],
                on_toggle_sequence=lambda sid: self.run_on_ui(lambda: self.toggle_run(sid)),
            )
            self.tray.start()
            self.page.window.prevent_close = True
        except Exception as exc:
            self.tray = None
            self.page.window.prevent_close = False
            logger.warning(f"Zone de notification indisponible: {exc}")

    async def apply_initial_visibility(self) -> None:
        if self.web:
            return
        if self.hidden and self.tray is not None:
            await self.hide_window()
        else:
            await self.show_window()

    async def show_window(self) -> None:
        window = self.page.window
        window.skip_task_bar = False
        window.visible = True
        window.minimized = False
        self._window_visible = True
        self.page.update()
        await window.to_front()

    async def hide_window(self) -> None:
        self.page.window.skip_task_bar = True
        self.page.window.visible = False
        self._window_visible = False
        self.page.update()

    def _on_window_event(self, event: Any) -> None:
        event_type = getattr(event, "type", None)
        if event_type != ft.WindowEventType.CLOSE or self._quitting or self.tray is None:
            return
        if self.config.settings.close_action == CLOSE_ACTION_QUIT:
            self.page.run_task(self.quit)
        else:
            self.page.run_task(self.hide_window)

    async def quit(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        memory_handler().remove_listener(self._on_log_entry)
        self.page.window.prevent_close = False
        self.page.window.visible = False
        self.page.update()
        await asyncio.to_thread(self._shutdown)
        await self.page.window.close()

    def _shutdown(self) -> None:
        if self.tray is not None:
            self.tray.stop()
            self.tray = None
        try:
            self.store.flush()
        except Exception:
            pass
        self.service.stop()


async def run_main_window(page: ft.Page, *, hidden: bool = False, web: bool = False) -> None:
    window = MainWindow(page, hidden=hidden, web=web)
    page.update()
    await window.apply_initial_visibility()
