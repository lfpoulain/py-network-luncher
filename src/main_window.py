from __future__ import annotations

import atexit
import asyncio
import os
import threading
from pathlib import Path
from typing import Optional

import flet as ft

from runtime_paths import app_icon_path
from system_tray import SystemTrayController
from ui_components import (
    build_logs_tab,
    build_main_layout,
    build_nav_button,
    build_peer_card,
    build_peers_tab,
    build_sequence_editor_header,
    build_sequence_list_card,
    build_sequences_tab,
    build_settings_tab,
    build_step_card,
)
from models import (
    ACTION_LABELS,
    ACTION_CALL_WEBHOOK,
    ACTION_DELAY,
    ACTION_LAUNCH_APP,
    ACTION_OPEN_WEBPAGE,
    ACTION_REMOTE_SEQUENCE,
    ACTION_SHELL_COMMAND,
    ACTION_WAKE_ON_LAN,
    ActionStep,
    AppConfig,
    CLOSE_ACTIONS,
    CLOSE_ACTION_LABELS,
    CLOSE_ACTION_MINIMIZE,
    CLOSE_ACTION_QUIT,
    LaunchSequence,
)
from service import LauncherService
from startup import install_startup_task, remove_startup_task, startup_registration_label
from storage import config_path, load_config, save_config


class MainWindow:
    def __init__(self, page: ft.Page, *, hidden: bool) -> None:
        self.page = page
        self.hidden = hidden
        self._quitting = False
        self._shutdown_registered = False
        self._peer_refresh_pending = False
        self._startup_warning: Optional[str] = None
        self._tray_warning: Optional[str] = None
        self.config = self._load_initial_config()
        self._collapsed_step_ids: set[str] = {step.id for sequence in self.config.sequences for step in sequence.steps}
        self.service = LauncherService(self.config, on_peers_updated=self._schedule_peer_refresh)
        self.tray_icon_path = app_icon_path()
        self.system_tray: Optional[SystemTrayController] = None
        self.selected_sequence_id: Optional[str] = self.config.sequences[0].id if self.config.sequences else None
        self.active_section = "sequences"

        self.node_name_field = ft.TextField(label="Nom du poste", expand=True)
        self.api_port_field = ft.TextField(label="Port API", width=140)
        self.discovery_port_field = ft.TextField(label="Port discovery", width=160)
        self.start_minimized_checkbox = ft.Checkbox(label="Démarrer cachée avec Windows")
        self.start_with_windows_checkbox = ft.Checkbox(label="Lancer avec Windows")
        self.close_action_group = ft.RadioGroup(
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Radio(value=item, label=CLOSE_ACTION_LABELS[item])
                    for item in CLOSE_ACTION_LABELS
                ],
            )
        )
        self.close_action_control = ft.Column(
            spacing=6,
            controls=[
                ft.Text("Comportement à la fermeture"),
                self.close_action_group,
            ],
        )

        self.sequence_name_field = ft.TextField(label="Nom de la séquence", expand=True)
        self.run_on_app_start_checkbox = ft.Checkbox(label="Lancer au démarrage de l'application")

        self.sequence_list_column = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
        self.sequence_editor_column = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
        self.peer_column = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
        self.log_list = ft.ListView(spacing=6, auto_scroll=True, expand=True)
        self.status_text = ft.Text(value="Prêt")
        self.config_path_text = ft.Text(selectable=True)
        self.startup_path_text = ft.Text(selectable=True)
        self.navigation_row = ft.Row(wrap=True, spacing=8)
        self.section_container = ft.Container(expand=True)

        self._configure_page()
        self._build_layout()
        self._bind_static_events()
        self._refresh_all()
        self._register_shutdown_handler()
        self._start_system_tray()
        self._start_service()
        self.service.launch_trigger_sequences()
        if self._startup_warning:
            self._set_status(self._startup_warning, error=True)
        elif self._tray_warning:
            self._set_status(self._tray_warning, error=True)

    async def apply_window_state(self) -> None:
        if self.hidden and self.system_tray is not None:
            await asyncio.sleep(0)
            self.page.window.skip_task_bar = True
            self.page.window.visible = False
            self.page.update()
        else:
            self.page.window.skip_task_bar = False
            self.page.window.visible = True
            self.page.update()

    def _load_initial_config(self) -> AppConfig:
        try:
            return load_config()
        except Exception as exc:
            self._startup_warning = self._format_exception(exc, prefix="Configuration réinitialisée")
            return AppConfig()

    def _configure_page(self) -> None:
        self.page.title = "Py Network Launcher"
        if self.tray_icon_path.exists():
            self.page.window.icon = str(self.tray_icon_path)
        self.page.window.width = 1480
        self.page.window.height = 920
        self.page.window.prevent_close = False
        self.page.window.on_event = self._on_window_event
        self.page.padding = 16
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.scroll = ft.ScrollMode.AUTO

    def _build_layout(self) -> None:
        controls = build_main_layout(
            navigation_row=self.navigation_row,
            section_container=self.section_container,
            status_text=self.status_text,
        )
        self.page.add(controls)
        self._refresh_navigation()
        self._refresh_active_section()

    def _bind_static_events(self) -> None:
        self.node_name_field.on_blur = self._on_node_name_blur
        self.sequence_name_field.on_change = self._on_sequence_name_changed
        self.run_on_app_start_checkbox.on_change = self._on_sequence_flags_changed
        self.start_with_windows_checkbox.on_change = self._on_startup_settings_changed
        self.start_minimized_checkbox.on_change = self._on_startup_settings_changed
        self.close_action_group.on_change = self._on_close_action_changed

    def _register_shutdown_handler(self) -> None:
        if self._shutdown_registered:
            return
        atexit.register(self._shutdown_service)
        self._shutdown_registered = True

    def _shutdown_service(self) -> None:
        if self.system_tray is not None:
            try:
                self.system_tray.stop()
            except Exception:
                pass
            self.system_tray = None
        try:
            self.service.stop()
        except Exception:
            return

    def _start_system_tray(self) -> None:
        if self.system_tray is not None:
            return
        if not self.tray_icon_path.exists():
            self._tray_warning = "System tray indisponible: icône introuvable"
            return
        try:
            self.system_tray = SystemTrayController(
                page=self.page,
                icon_path=self.tray_icon_path,
                title="Py Network Launcher",
                on_quit_requested=self._quit_from_tray,
            )
            self.system_tray.start()
            self.page.window.prevent_close = True
        except Exception as exc:
            self.system_tray = None
            self.page.window.prevent_close = False
            self._tray_warning = self._format_exception(exc, prefix="System tray indisponible")

    def _on_window_event(self, event) -> None:
        event_type = getattr(getattr(event, "type", None), "value", getattr(event, "type", None))
        if event_type == ft.WindowEventType.CLOSE.value and not self._quitting and self.system_tray is not None:
            if self._selected_close_action_value() == CLOSE_ACTION_QUIT:
                self.page.run_task(self._quit_from_tray)
            else:
                self.page.run_task(self._hide_to_tray)

    async def _hide_to_tray(self) -> None:
        self.page.window.skip_task_bar = True
        self.page.window.visible = False
        self._set_status("Application réduite dans la zone de notification")
        self.page.update()

    async def _quit_from_tray(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        self.page.window.prevent_close = False
        self.page.window.visible = False
        self.page.update()
        await asyncio.to_thread(self._shutdown_service)
        await self.page.window.close()

    def _refresh_navigation(self) -> None:
        items = [
            ("sequences", "Séquences"),
            ("peers", "Pairs"),
            ("logs", "Logs"),
            ("settings", "Réglages"),
        ]
        self.navigation_row.controls = [
            build_nav_button(key=key, label=label, selected=key == self.active_section, on_click=self._set_active_section)
            for key, label in items
        ]

    def _refresh_active_section(self) -> None:
        builders = {
            "sequences": lambda: build_sequences_tab(
                sequence_list_column=self.sequence_list_column,
                sequence_editor_column=self.sequence_editor_column,
                on_add_sequence=self._add_sequence,
            ),
            "peers": lambda: build_peers_tab(peer_column=self.peer_column),
            "logs": lambda: build_logs_tab(log_list=self.log_list),
            "settings": lambda: build_settings_tab(
                node_name_field=self.node_name_field,
                api_port_field=self.api_port_field,
                discovery_port_field=self.discovery_port_field,
                start_with_windows_checkbox=self.start_with_windows_checkbox,
                start_minimized_checkbox=self.start_minimized_checkbox,
                close_action_control=self.close_action_control,
                config_path_text=self.config_path_text,
                startup_path_text=self.startup_path_text,
                on_save_settings=self._save_settings_only,
            ),
        }
        builder = builders.get(self.active_section, builders["sequences"])
        self.section_container.content = builder()

    def _set_active_section(self, section: str) -> None:
        if self.active_section == "settings":
            self._persist_close_action(show_status=False)
        self.active_section = section
        self._refresh_section_data(section)
        self._refresh_navigation()
        self._refresh_active_section()
        self.page.update()

    def _refresh_section_data(self, section: str) -> None:
        if section == "sequences":
            self._refresh_sequence_section()
            return
        if section == "peers":
            self._refresh_peers()
            return
        if section == "logs":
            self._refresh_logs()
            return
        if section == "settings":
            self._refresh_settings_fields()

    def _refresh_all(self, _=None) -> None:
        self._refresh_settings_fields()
        self._refresh_sequence_list()
        self._refresh_sequence_editor()
        self._refresh_peers()
        self._refresh_logs()
        self.page.update()

    def _refresh_settings_fields(self) -> None:
        settings = self.config.settings
        self.node_name_field.value = settings.node_name
        self.api_port_field.value = str(settings.api_port)
        self.discovery_port_field.value = str(settings.discovery_port)
        self.start_minimized_checkbox.value = settings.start_minimized
        self.start_with_windows_checkbox.value = settings.start_with_windows
        self.close_action_group.value = settings.close_action
        self.config_path_text.value = str(config_path())
        self.startup_path_text.value = startup_registration_label() if settings.start_with_windows else "Non activée"

    def _refresh_sequence_list(self) -> None:
        self.sequence_list_column.controls.clear()
        for sequence in self.config.sequences:
            selected = sequence.id == self.selected_sequence_id
            summary: list[str] = []
            if sequence.run_on_app_start:
                summary.append("app")
            subtitle = " | ".join(summary) if summary else "manuel"
            self.sequence_list_column.controls.append(
                build_sequence_list_card(sequence=sequence, selected=selected, subtitle=subtitle, on_select=self._select_sequence)
            )
        if not self.config.sequences:
            self.sequence_list_column.controls.append(ft.Text("Aucune séquence"))

    def _refresh_sequence_editor(self) -> None:
        self.sequence_editor_column.controls.clear()
        sequence = self._selected_sequence()
        if sequence is None:
            self.sequence_editor_column.controls.append(ft.Text("Sélectionnez ou créez une séquence."))
            return
        self.sequence_name_field.value = sequence.name
        self.run_on_app_start_checkbox.value = sequence.run_on_app_start
        self.sequence_editor_column.controls.extend(
            build_sequence_editor_header(
                sequence_name_field=self.sequence_name_field,
                run_on_app_start_checkbox=self.run_on_app_start_checkbox,
                action_labels=ACTION_LABELS,
                on_run_sequence=self._run_selected_sequence,
                on_delete_sequence=self._delete_selected_sequence,
                on_add_step=self._add_step,
            )
        )
        if not sequence.steps:
            self.sequence_editor_column.controls.append(ft.Text("Aucune étape dans cette séquence."))
        for index, step in enumerate(sequence.steps):
            self.sequence_editor_column.controls.append(self._build_step_card(sequence, step, index))

    def _refresh_peers(self) -> None:
        peers = self.service.get_peers()
        self.peer_column.controls.clear()
        if not peers:
            self.peer_column.controls.append(ft.Text("Aucun pair découvert pour l'instant."))
            return
        for peer in peers:
            sequence_names = ", ".join(item.name for item in peer.sequences) if peer.sequences else "Aucune séquence annoncée"
            self.peer_column.controls.append(build_peer_card(peer=peer, sequence_names=sequence_names))

    def _refresh_logs(self) -> None:
        self.log_list.controls = [ft.Text(line) for line in self.service.logs()[-200:]]

    def _selected_sequence(self) -> Optional[LaunchSequence]:
        if not self.selected_sequence_id:
            return None
        return self.service.get_sequence(self.selected_sequence_id)

    def _refresh_sequence_section(self) -> None:
        self._refresh_sequence_list()
        self._refresh_sequence_editor()

    def _refresh_runtime_section(self) -> None:
        self._refresh_peers()
        self._refresh_logs()

    def _schedule_peer_refresh(self) -> None:
        if self._peer_refresh_pending:
            return
        self._peer_refresh_pending = True
        try:
            self.page.run_task(self._apply_peer_refresh)
        except Exception:
            self._peer_refresh_pending = False

    async def _apply_peer_refresh(self) -> None:
        try:
            self._refresh_peers()
            self._refresh_sequence_editor()
            self.page.update()
        finally:
            self._peer_refresh_pending = False

    def _select_sequence(self, sequence_id: str) -> None:
        self.selected_sequence_id = sequence_id
        self._refresh_sequence_section()
        self.page.update()

    def _sync_sequence_ui(self) -> None:
        self._refresh_sequence_section()

    def _add_sequence(self, _=None) -> None:
        sequence = LaunchSequence(name=f"Séquence {len(self.config.sequences) + 1}")
        self.config.sequences.append(sequence)
        self.selected_sequence_id = sequence.id
        if self._persist_safe():
            self._sync_sequence_ui()
            self._set_status("Séquence ajoutée")
            self.page.update()

    def _delete_selected_sequence(self, _=None) -> None:
        sequence = self._selected_sequence()
        if sequence is None:
            return
        self.config.sequences = [item for item in self.config.sequences if item.id != sequence.id]
        self.selected_sequence_id = self.config.sequences[0].id if self.config.sequences else None
        if self._persist_safe():
            self._sync_sequence_ui()
            self._set_status("Séquence supprimée")
            self.page.update()

    def _run_selected_sequence(self, _=None) -> None:
        sequence = self._selected_sequence()
        if sequence is None:
            return
        try:
            self.service.run_local_sequence(sequence.id)
            self._set_status(f"Séquence '{sequence.name}' lancée")
        except Exception as exc:
            self._set_status(self._format_exception(exc), error=True)
        self._refresh_logs()
        self.page.update()

    def _on_sequence_name_changed(self, _=None) -> None:
        sequence = self._selected_sequence()
        if sequence is None:
            return
        sequence.name = (self.sequence_name_field.value or "Nouvelle séquence").strip() or "Nouvelle séquence"
        if self._persist_safe():
            self._refresh_sequence_list()
            self.page.update()

    def _on_sequence_flags_changed(self, _=None) -> None:
        sequence = self._selected_sequence()
        if sequence is None:
            return
        sequence.run_on_app_start = bool(self.run_on_app_start_checkbox.value)
        if self._persist_safe():
            self._refresh_sequence_list()
            self.page.update()

    def _add_step(self, action_type: str) -> None:
        sequence = self._selected_sequence()
        if sequence is None:
            return
        step = ActionStep(action_type=action_type)
        sequence.steps.append(step)
        self._collapsed_step_ids.add(step.id)
        if self._persist_safe():
            self._refresh_sequence_editor()
            self.page.update()

    def _build_step_card(self, sequence: LaunchSequence, step: ActionStep, index: int) -> ft.Control:
        peers = self.service.get_peers()

        def update_string(attr: str):
            def handler(event):
                value = str(event.control.value or "")
                if attr == "method":
                    value = value.upper()
                if attr == "wait_timeout_s":
                    try:
                        timeout_s = float(value.strip())
                    except ValueError:
                        self._set_status("Le timeout d'attente doit être un nombre", error=True)
                        self.page.update()
                        return
                    if timeout_s < 0.5:
                        self._set_status("Le timeout d'attente doit être supérieur ou égal à 0,5 s", error=True)
                        self.page.update()
                        return
                    step.wait_timeout_s = timeout_s
                    self._persist_safe()
                    return
                if attr == "wait_port":
                    raw_value = value.strip()
                    try:
                        wait_port = int(raw_value or "0")
                    except ValueError:
                        self._set_status("Le port d'attente doit être un entier", error=True)
                        self.page.update()
                        return
                    if not 0 <= wait_port <= 65535:
                        self._set_status("Le port d'attente doit être compris entre 0 et 65535", error=True)
                        self.page.update()
                        return
                    step.wait_port = wait_port
                    self._persist_safe()
                    return
                setattr(step, attr, value)
                if attr == "wait_mode":
                    if self._persist_safe():
                        self._refresh_sequence_editor()
                        self.page.update()
                    return
                self._persist_safe()
            return handler

        def update_bool(attr: str):
            def handler(event):
                setattr(step, attr, bool(event.control.value))
                self._persist_safe()
            return handler

        def update_seconds(event):
            try:
                raw_value = str(event.control.value or "0").strip()
                seconds = float(raw_value)
                if seconds < 0:
                    raise ValueError()
                step.seconds = seconds
            except ValueError:
                self._set_status("Le délai doit être un nombre positif ou nul", error=True)
                self.page.update()
                return
            self._persist_safe()

        def update_remote_peer(event):
            selected_peer = str(event.control.value or "")
            step.remote_peer_id = selected_peer
            step.remote_sequence_id = ""
            if self._persist_safe():
                self._refresh_sequence_editor()
                self.page.update()

        def pick_command(_):
            async def choose_command_file() -> None:
                try:
                    files = await ft.FilePicker().pick_files(allow_multiple=False)
                except Exception as exc:
                    self._set_status(self._format_exception(exc, prefix="Sélection de fichier impossible"), error=True)
                    self.page.update()
                    return
                if not files:
                    return
                selected_path = str(getattr(files[0], "path", "") or "")
                if not selected_path:
                    self._set_status("Aucun chemin de fichier n'a été renvoyé", error=True)
                    self.page.update()
                    return
                step.command = selected_path
                if not step.working_directory.strip():
                    step.working_directory = os.path.dirname(selected_path)
                if self._persist_safe():
                    self._refresh_sequence_editor()
                    self.page.update()

            self.page.run_task(choose_command_file)

        def toggle_collapse(_):
            if step.id in self._collapsed_step_ids:
                self._collapsed_step_ids.remove(step.id)
            else:
                self._collapsed_step_ids.add(step.id)
            self._refresh_sequence_editor()
            self.page.update()

        def run_step(_):
            try:
                self.service.run_local_step(step, source=f"step:{sequence.name}")
                self._set_status(f"Étape '{step.display_name()}' lancée")
            except Exception as exc:
                self._set_status(self._format_exception(exc), error=True)
            self._refresh_logs()
            self.page.update()

        def remove_step(_):
            sequence.steps = [item for item in sequence.steps if item.id != step.id]
            self._collapsed_step_ids.discard(step.id)
            if self._persist_safe():
                self._refresh_sequence_editor()
                self.page.update()

        def move_step(delta: int):
            def handler(_):
                current_index = next((i for i, item in enumerate(sequence.steps) if item.id == step.id), None)
                if current_index is None:
                    return
                new_index = max(0, min(len(sequence.steps) - 1, current_index + delta))
                if new_index == current_index:
                    return
                sequence.steps.insert(new_index, sequence.steps.pop(current_index))
                if self._persist_safe():
                    self._refresh_sequence_editor()
                    self.page.update()
            return handler

        return build_step_card(
            sequence=sequence,
            step=step,
            index=index,
            peers=peers,
            action_labels=ACTION_LABELS,
            on_update_string=update_string,
            on_update_bool=update_bool,
            on_update_seconds=update_seconds,
            on_update_remote_peer=update_remote_peer,
            on_pick_command=pick_command,
            is_collapsed=step.id in self._collapsed_step_ids,
            on_toggle_collapse=toggle_collapse,
            on_run_step=run_step,
            on_remove_step=remove_step,
            on_move_step=move_step,
        )

    def _save_settings_only(self, _=None) -> None:
        try:
            self._apply_network_settings_from_fields()
            self._persist()
            self._restart_service()
            self._set_status("Réglages réseau appliqués")
        except Exception as exc:
            self._set_status(self._format_exception(exc), error=True)
        self._refresh_runtime_section()
        self.page.update()

    def _on_node_name_blur(self, _=None) -> None:
        node_name = (self.node_name_field.value or "Mon poste").strip() or "Mon poste"
        if node_name == self.config.settings.node_name:
            return
        self.config.settings.node_name = node_name
        if self._persist_safe():
            self._set_status("Nom du poste sauvegardé. Clique sur 'Appliquer les réglages réseau' pour l'annoncer sur le réseau.")
            self.page.update()

    def _on_startup_settings_changed(self, _=None) -> None:
        try:
            self._apply_startup_settings_from_fields()
            self._persist()
            self._sync_startup_script()
            self._set_status("Démarrage Windows mis à jour")
        except Exception as exc:
            self._set_status(self._format_exception(exc), error=True)
        self.page.update()

    def _selected_close_action_value(self, event=None) -> str:
        candidates = [
            getattr(getattr(event, "control", None), "value", None),
            self.close_action_group.value,
            self.config.settings.close_action,
        ]
        for candidate in candidates:
            value = str(candidate or "").strip()
            if value in CLOSE_ACTIONS:
                return value
        return CLOSE_ACTION_MINIMIZE

    def _persist_close_action(self, *, event=None, show_status: bool) -> None:
        selected_value = self._selected_close_action_value(event)
        self.config.settings.close_action = selected_value
        self.close_action_group.value = selected_value
        self._persist()
        if show_status:
            self._set_status("Comportement de fermeture mis à jour")

    def _on_close_action_changed(self, event=None) -> None:
        try:
            self._persist_close_action(event=event, show_status=True)
        except Exception as exc:
            self._set_status(self._format_exception(exc), error=True)
            self._refresh_settings_fields()
        self.page.update()

    def _apply_network_settings_from_fields(self) -> None:
        node_name = (self.node_name_field.value or "Mon poste").strip() or "Mon poste"
        api_port = self._parse_port(self.api_port_field.value, "Port API")
        discovery_port = self._parse_port(self.discovery_port_field.value, "Port discovery")
        self.config.settings.node_name = node_name
        self.config.settings.api_port = api_port
        self.config.settings.discovery_port = discovery_port

    def _apply_startup_settings_from_fields(self) -> None:
        self.config.settings.start_minimized = bool(self.start_minimized_checkbox.value)
        self.config.settings.start_with_windows = bool(self.start_with_windows_checkbox.value)

    def _parse_port(self, raw_value: Optional[str], label: str) -> int:
        value = str(raw_value or "").strip()
        try:
            port = int(value)
        except ValueError as exc:
            raise ValueError(f"{label} invalide") from exc
        if not 1 <= port <= 65535:
            raise ValueError(f"{label} doit être compris entre 1 et 65535")
        return port

    def _sync_startup_script(self, _=None) -> None:
        if self.config.settings.start_with_windows:
            install_startup_task(hidden=bool(self.config.settings.start_minimized))
        else:
            remove_startup_task()
        self.startup_path_text.value = startup_registration_label() if self.config.settings.start_with_windows else "Non activée"

    def _persist(self) -> Path:
        path = save_config(self.config)
        self.config_path_text.value = str(path)
        return path

    def _persist_safe(self) -> bool:
        try:
            self._persist()
        except Exception as exc:
            self._set_status(self._format_exception(exc), error=True)
            self.page.update()
            return False
        return True

    def _restart_service(self) -> None:
        self.service.stop()
        self.service = LauncherService(self.config, on_peers_updated=self._schedule_peer_refresh)
        self._start_service()

    def _start_service(self) -> None:
        try:
            self.service.start()
        except Exception as exc:
            self._set_status(self._format_exception(exc, prefix="Impossible de démarrer le service"), error=True)
            self.page.update()
            raise

    def _format_exception(self, exc: Exception, *, prefix: Optional[str] = None) -> str:
        message = str(exc).strip() or exc.__class__.__name__
        if prefix:
            return f"{prefix}: {message}"
        return message

    def _set_status(self, message: str, *, error: bool = False) -> None:
        self.status_text.value = message
        self.status_text.color = ft.Colors.RED_300 if error else None


LauncherApp = MainWindow


async def main(page: ft.Page, *, hidden: bool) -> None:
    window = MainWindow(page, hidden=hidden)
    window.page.update()
    await window.apply_window_state()
