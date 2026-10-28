"""Carte d'édition d'une étape de séquence.

La carte est construite une fois puis mise à jour sur place (état d'exécution, résumé,
listes de postes) : on ne reconstruit jamais un champ pendant que l'utilisateur tape.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

import flet as ft

from py_network_launcher.actions import normalize_url, parse_headers, parse_mac_address
from py_network_launcher.models import (
    ACTION_CALL_WEBHOOK,
    ACTION_DELAY,
    ACTION_HOME_ASSISTANT,
    ACTION_LAUNCH_APP,
    ACTION_LOCAL_SEQUENCE,
    ACTION_OPEN_WEBPAGE,
    ACTION_REMOTE_SEQUENCE,
    ACTION_SHELL_COMMAND,
    ACTION_WAKE_ON_LAN,
    HOME_ASSISTANT_ACTION_LABELS,
    WAIT_MODE_LABELS,
    WAIT_MODE_PORT,
    WAIT_MODE_STARTED,
    WEBHOOK_METHODS,
    ActionStep,
    LaunchSequence,
    PeerInfo,
)
from py_network_launcher.ui.widgets import (
    ACTION_COLORS,
    ACTION_ICONS,
    COLOR_ERROR,
    COLOR_MUTED,
    COLOR_RUNNING,
    COLOR_SUCCESS,
    RADIUS,
    action_avatar,
    badge,
    dropdown,
    labeled_switch,
    muted_text,
    text_field,
)

STATE_RUNNING = "running"
STATE_DONE = "done"
STATE_FAILED = "failed"


@dataclass
class StepCardHost:
    """Ce dont une carte a besoin de la part de la vue qui l'affiche."""

    sequence: LaunchSequence
    peers: Callable[[], list[PeerInfo]]
    other_sequences: Callable[[], list[LaunchSequence]]
    on_changed: Callable[[ActionStep], None]
    on_toggle: Callable[[ActionStep], None]
    on_test: Callable[[ActionStep], None]
    on_delete: Callable[[ActionStep], None]
    on_duplicate: Callable[[ActionStep], None]
    on_move: Callable[[ActionStep, int], None]
    pick_file: Callable[[Callable[[str], None]], None]
    pick_folder: Callable[[Callable[[str], None]], None]


def step_summary(step: ActionStep, peers: list[PeerInfo], other_sequences: list[LaunchSequence]) -> str:
    kind = step.action_type
    if kind == ACTION_LAUNCH_APP:
        command = step.command.strip().strip('"')
        if not command:
            return "Aucune application choisie"
        return f"{command} {step.arguments.strip()}".strip()
    if kind == ACTION_SHELL_COMMAND:
        return step.command.strip().splitlines()[0] if step.command.strip() else "Commande non définie"
    if kind == ACTION_OPEN_WEBPAGE:
        return normalize_url(step.url) or "URL non définie"
    if kind == ACTION_CALL_WEBHOOK:
        return f"{step.method} {normalize_url(step.url) or 'URL non définie'}"
    if kind == ACTION_WAKE_ON_LAN:
        return step.mac_address.strip() or "Adresse MAC non définie"
    if kind == ACTION_DELAY:
        return f"Attendre {step.seconds:g} s"
    if kind == ACTION_LOCAL_SEQUENCE:
        target = next((item for item in other_sequences if item.id == step.local_sequence_id), None)
        if target is not None:
            return f"Exécuter « {target.name} »"
        return "Séquence supprimée" if step.local_sequence_id else "Aucune séquence choisie"
    if kind == ACTION_REMOTE_SEQUENCE:
        peer = next((item for item in peers if item.node_id == step.remote_peer_id), None)
        peer_name = peer.name if peer is not None else step.remote_peer_name or ""
        remote = peer.find_sequence(step.remote_sequence_id) if peer is not None else None
        sequence_name = remote.name if remote is not None else step.remote_sequence_name or ""
        if not peer_name:
            return "Aucun poste choisi"
        offline = "" if peer is not None else " (hors ligne)"
        return f"{peer_name}{offline} → {sequence_name or 'séquence non choisie'}"
    if kind == ACTION_HOME_ASSISTANT:
        entity = step.home_assistant_entity_id.strip() or "entité non définie"
        return f"{HOME_ASSISTANT_ACTION_LABELS.get(step.home_assistant_action, '')} {entity}".strip()
    return ""


class StepCard:
    def __init__(self, step: ActionStep, index: int, count: int, host: StepCardHost, *, expanded: bool) -> None:
        self.step = step
        self.host = host
        self.expanded = expanded
        self._run_state: Optional[str] = None
        self._run_error = ""
        self._remote_peer_dropdown: Optional[ft.Dropdown] = None
        self._remote_sequence_dropdown: Optional[ft.Dropdown] = None
        self._local_sequence_dropdown: Optional[ft.Dropdown] = None

        color = ACTION_COLORS.get(step.action_type, ft.Colors.PRIMARY)
        self._index_text = ft.Text(str(index + 1), size=12, weight=ft.FontWeight.W_600, color=COLOR_MUTED, width=18, text_align=ft.TextAlign.CENTER)
        self._summary_text = muted_text("", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, no_wrap=True)
        self._state_slot = ft.Container(width=24, height=24, alignment=ft.Alignment.CENTER)
        self._disabled_badge = badge("Désactivée", color=COLOR_MUTED)
        self._continue_badge = badge("Continue si erreur", color=ft.Colors.AMBER_200, tooltip="Une erreur sur cette étape n'interrompt pas la séquence")
        self._menu = ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, tooltip="Plus d'actions", items=[])
        self._chevron = ft.IconButton(on_click=lambda _: self.host.on_toggle(self.step), icon_size=20)
        self._header_content = ft.Row(
            expand=True,
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                action_avatar(ACTION_ICONS.get(step.action_type, ft.Icons.PLAY_ARROW), color),
                ft.Column(
                    expand=True,
                    spacing=1,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Text(step.label, size=14, weight=ft.FontWeight.W_600, no_wrap=True),
                                self._disabled_badge,
                                self._continue_badge,
                            ],
                        ),
                        self._summary_text,
                    ],
                ),
            ],
        )
        header = ft.Row(
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.ReorderableDragHandle(
                    content=ft.Icon(ft.Icons.DRAG_INDICATOR, size=20, color=ft.Colors.OUTLINE),
                    mouse_cursor=ft.MouseCursor.GRAB,
                    tooltip="Glisser pour réordonner",
                ),
                self._index_text,
                ft.Container(
                    expand=True,
                    border_radius=10,
                    ink=True,
                    padding=ft.Padding.symmetric(vertical=4, horizontal=4),
                    on_click=lambda _: self.host.on_toggle(self.step),
                    content=self._header_content,
                ),
                self._state_slot,
                ft.IconButton(icon=ft.Icons.PLAY_ARROW_ROUNDED, tooltip="Tester cette étape seule", on_click=lambda _: self.host.on_test(self.step)),
                self._menu,
                self._chevron,
            ],
        )
        self._body = ft.Column(spacing=12, visible=expanded)
        self.control = ft.Container(
            key=step.id,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            border_radius=RADIUS,
            border=ft.Border.all(1.5, ft.Colors.TRANSPARENT),
            padding=ft.Padding.only(left=6, right=8, top=6, bottom=6),
            margin=ft.Margin.only(bottom=8),
            content=ft.Column(spacing=8, controls=[header, self._body]),
        )
        self.set_index(index, count)
        self._refresh_header()
        if expanded:
            self._build_body()

    # --- Mises à jour sur place ----------------------------------------------------------

    def set_index(self, index: int, count: int) -> None:
        self._index_text.value = str(index + 1)
        self._build_menu(index, count)

    def set_expanded(self, expanded: bool) -> None:
        self.expanded = expanded
        if expanded and not self._body.controls:
            self._build_body()
        self._body.visible = expanded
        self._refresh_header()

    def set_run_state(self, state: Optional[str], error: str = "") -> None:
        self._run_state, self._run_error = state, error
        self._refresh_state()

    def refresh_summary(self) -> None:
        self._summary_text.value = step_summary(self.step, self.host.peers(), self.host.other_sequences())
        self._summary_text.tooltip = self._summary_text.value

    def refresh_dynamic_options(self) -> None:
        """Met à jour les listes de postes/séquences sans toucher aux autres champs."""
        if self._remote_peer_dropdown is not None and self._remote_sequence_dropdown is not None:
            peer_options, sequence_options = self._remote_options()
            self._remote_peer_dropdown.options = [ft.DropdownOption(key=key, text=text) for key, text in peer_options]
            self._remote_sequence_dropdown.options = [ft.DropdownOption(key=key, text=text) for key, text in sequence_options]
        if self._local_sequence_dropdown is not None:
            self._local_sequence_dropdown.options = [ft.DropdownOption(key=key, text=text) for key, text in self._local_options()]
        self.refresh_summary()

    def _refresh_header(self) -> None:
        self._chevron.icon = ft.Icons.EXPAND_LESS if self.expanded else ft.Icons.EXPAND_MORE
        self._chevron.tooltip = "Replier" if self.expanded else "Modifier"
        self._disabled_badge.visible = not self.step.enabled
        self._continue_badge.visible = self.step.continue_on_error and self.step.enabled
        self._header_content.opacity = 1.0 if self.step.enabled else 0.45
        self.refresh_summary()
        self._refresh_state()

    def _refresh_state(self) -> None:
        state = self._run_state
        border_color = ft.Colors.TRANSPARENT
        content: Optional[ft.Control] = None
        if state == STATE_RUNNING:
            border_color = COLOR_RUNNING
            content = ft.ProgressRing(width=18, height=18, stroke_width=2.5, color=COLOR_RUNNING, tooltip="En cours")
        elif state == STATE_DONE:
            border_color = ft.Colors.with_opacity(0.6, COLOR_SUCCESS)
            content = ft.Icon(ft.Icons.CHECK_CIRCLE, color=COLOR_SUCCESS, size=20, tooltip="Terminée")
        elif state == STATE_FAILED:
            border_color = COLOR_ERROR
            content = ft.Icon(ft.Icons.ERROR, color=COLOR_ERROR, size=20, tooltip=self._run_error or "Erreur")
        self.control.border = ft.Border.all(1.5, border_color)
        self._state_slot.content = content

    def _build_menu(self, index: int, count: int) -> None:
        def item(text: str, icon: ft.IconData, handler: Callable[[], None], *, disabled: bool = False) -> ft.PopupMenuItem:
            return ft.PopupMenuItem(content=text, icon=icon, disabled=disabled, on_click=lambda _: handler())

        step = self.step
        self._menu.items = [
            item("Monter", ft.Icons.ARROW_UPWARD, lambda: self.host.on_move(step, -1), disabled=index == 0),
            item("Descendre", ft.Icons.ARROW_DOWNWARD, lambda: self.host.on_move(step, 1), disabled=index >= count - 1),
            item("Dupliquer", ft.Icons.CONTENT_COPY, lambda: self.host.on_duplicate(step)),
            item("Réactiver" if not step.enabled else "Désactiver", ft.Icons.TOGGLE_ON_OUTLINED, self._toggle_enabled),
            ft.PopupMenuItem(),
            item("Supprimer", ft.Icons.DELETE_OUTLINE, lambda: self.host.on_delete(step)),
        ]

    def _toggle_enabled(self) -> None:
        self.step.enabled = not self.step.enabled
        if self._body.controls:
            self._build_body()
        self._refresh_header()
        self.host.on_changed(self.step)

    # --- Champs --------------------------------------------------------------------------

    def _set(self, attribute: str, *, rebuild: bool = False) -> Callable[[Any], None]:
        def handler(event: Any) -> None:
            setattr(self.step, attribute, str(event.control.value or ""))
            self._after_change(rebuild=rebuild)

        return handler

    def _set_bool(self, attribute: str) -> Callable[[Any], None]:
        def handler(event: Any) -> None:
            setattr(self.step, attribute, bool(event.control.value))
            self._refresh_header()
            self.host.on_changed(self.step)

        return handler

    def _set_number(self, attribute: str, *, minimum: float, maximum: Optional[float] = None, integer: bool = False) -> Callable[[Any], None]:
        def handler(event: Any) -> None:
            field = event.control
            raw = str(field.value or "").strip().replace(",", ".")
            try:
                value: float = int(raw) if integer else float(raw)
            except ValueError:
                field.error = "Nombre entier attendu" if integer else "Nombre attendu"
                return
            if value < minimum or (maximum is not None and value > maximum):
                field.error = f"Entre {minimum:g} et {maximum:g}" if maximum is not None else f"Minimum {minimum:g}"
                return
            field.error = None
            setattr(self.step, attribute, value)
            self._after_change()

        return handler

    def _validated(self, attribute: str, validator: Callable[[str], None]) -> Callable[[Any], None]:
        def handler(event: Any) -> None:
            field = event.control
            value = str(field.value or "")
            setattr(self.step, attribute, value)
            try:
                if value.strip():
                    validator(value)
                field.error = None
            except ValueError as exc:
                field.error = str(exc)
            self._after_change()

        return handler

    def _after_change(self, *, rebuild: bool = False) -> None:
        if rebuild:
            self._build_body()
        self.refresh_summary()
        self.host.on_changed(self.step)

    def _build_body(self) -> None:
        self._remote_peer_dropdown = self._remote_sequence_dropdown = self._local_sequence_dropdown = None
        builder = {
            ACTION_LAUNCH_APP: self._fields_launch_app,
            ACTION_SHELL_COMMAND: self._fields_shell,
            ACTION_OPEN_WEBPAGE: self._fields_webpage,
            ACTION_CALL_WEBHOOK: self._fields_webhook,
            ACTION_WAKE_ON_LAN: self._fields_wol,
            ACTION_DELAY: self._fields_delay,
            ACTION_LOCAL_SEQUENCE: self._fields_local_sequence,
            ACTION_REMOTE_SEQUENCE: self._fields_remote_sequence,
            ACTION_HOME_ASSISTANT: self._fields_home_assistant,
        }.get(self.step.action_type)
        fields = builder() if builder is not None else []
        options = ft.Row(
            wrap=True,
            spacing=24,
            controls=[
                labeled_switch("Étape active", self.step.enabled, on_change=self._on_enabled_switch),
                labeled_switch(
                    "Continuer si elle échoue",
                    self.step.continue_on_error,
                    on_change=self._set_bool("continue_on_error"),
                    tooltip="Sinon, une erreur sur cette étape arrête la séquence",
                ),
            ],
        )
        self._body.controls = [
            ft.Container(
                padding=ft.Padding.only(left=34, right=6, top=4, bottom=6),
                content=ft.Column(spacing=12, controls=[*fields, ft.Divider(height=1), options]),
            )
        ]

    def _on_enabled_switch(self, event: Any) -> None:
        self.step.enabled = bool(event.control.value)
        self._refresh_header()
        self.host.on_changed(self.step)

    def _wait_fields(self) -> list[ft.Control]:
        step = self.step
        controls: list[ft.Control] = [
            dropdown("Après le lancement", step.wait_mode, list(WAIT_MODE_LABELS.items()), on_select=self._set("wait_mode", rebuild=True), expand=True),
        ]
        if step.wait_mode in (WAIT_MODE_STARTED, WAIT_MODE_PORT):
            controls.append(
                text_field(
                    "Délai max (s)" if step.wait_mode == WAIT_MODE_PORT else "Durée (s)",
                    f"{step.wait_timeout_s:g}",
                    on_change=self._set_number("wait_timeout_s", minimum=0.5),
                    width=130,
                )
            )
        rows: list[ft.Control] = [ft.Row(spacing=10, vertical_alignment=ft.CrossAxisAlignment.START, controls=controls)]
        if step.wait_mode == WAIT_MODE_PORT:
            rows.append(
                ft.Row(
                    spacing=10,
                    controls=[
                        text_field("Hôte à surveiller", step.wait_host, on_change=self._set("wait_host"), expand=True),
                        text_field(
                            "Port", str(step.wait_port or ""), on_change=self._set_number("wait_port", minimum=1, maximum=65535, integer=True), width=130
                        ),
                    ],
                )
            )
        return rows

    def _browse_button(self, *, folder: bool, attribute: str) -> ft.Control:
        def apply(path: str) -> None:
            setattr(self.step, attribute, path)
            self._after_change(rebuild=True)

        def on_click(_: Any) -> None:
            (self.host.pick_folder if folder else self.host.pick_file)(apply)

        return ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="Choisir un dossier…" if folder else "Choisir un fichier…",
            on_click=on_click,
        )

    def _fields_launch_app(self) -> list[ft.Control]:
        step = self.step
        return [
            ft.Row(
                spacing=6,
                controls=[
                    text_field(
                        "Programme, raccourci ou fichier",
                        step.command,
                        on_change=self._set("command"),
                        expand=True,
                        hint=r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
                    ),
                    self._browse_button(folder=False, attribute="command"),
                ],
            ),
            ft.Row(
                spacing=6,
                controls=[
                    text_field("Arguments", step.arguments, on_change=self._set("arguments"), expand=True, hint='--minimize "C:\\Mon dossier"'),
                    text_field(
                        "Dossier de travail",
                        step.working_directory,
                        on_change=self._set("working_directory"),
                        expand=True,
                        hint="Par défaut : dossier du programme",
                    ),
                    self._browse_button(folder=True, attribute="working_directory"),
                ],
            ),
            *self._wait_fields(),
            muted_text(
                "Les guillemets autour du chemin et les variables comme %APPDATA% sont gérés. Si l'application demande les droits administrateur, Windows affichera l'invite UAC."
            ),
        ]

    def _fields_shell(self) -> list[ft.Control]:
        step = self.step
        return [
            text_field("Commande", step.command, on_change=self._set("command"), multiline=True, monospace=True, hint='ipconfig /flushdns && start "" notepad'),
            ft.Row(
                spacing=6,
                controls=[
                    text_field("Dossier de travail", step.working_directory, on_change=self._set("working_directory"), expand=True),
                    self._browse_button(folder=True, attribute="working_directory"),
                ],
            ),
            *self._wait_fields(),
            labeled_switch("Afficher la fenêtre de console", step.show_console, on_change=self._set_bool("show_console")),
            muted_text(
                "Exécutée par cmd.exe (pipes, redirections, &&…). Console masquée par défaut ; avec « Attendre la fin », la sortie est reprise dans le journal en cas d'erreur."
            ),
        ]

    def _fields_webpage(self) -> list[ft.Control]:
        return [text_field("URL", self.step.url, on_change=self._set("url"), hint="https://example.com")]

    def _fields_webhook(self) -> list[ft.Control]:
        step = self.step
        return [
            ft.Row(
                spacing=10,
                controls=[
                    dropdown("Méthode", step.method, [(method, method) for method in WEBHOOK_METHODS], on_select=self._set("method"), width=130),
                    text_field("URL", step.url, on_change=self._set("url"), expand=True, hint="http://192.168.1.10:8123/api/webhook/mon-id"),
                ],
            ),
            text_field(
                "Headers (JSON)",
                step.headers_json,
                on_change=self._validated("headers_json", parse_headers),
                multiline=True,
                monospace=True,
                hint='{"Authorization": "Bearer …"}',
            ),
            text_field("Corps de la requête", step.body, on_change=self._set("body"), multiline=True, monospace=True, hint='{"event": "stream_start"}'),
        ]

    def _fields_wol(self) -> list[ft.Control]:
        step = self.step
        return [
            ft.Row(
                spacing=10,
                controls=[
                    text_field(
                        "Adresse MAC", step.mac_address, on_change=self._validated("mac_address", parse_mac_address), expand=True, hint="AA:BB:CC:DD:EE:FF"
                    ),
                    text_field("Adresse de broadcast", step.broadcast_ip, on_change=self._set("broadcast_ip"), width=200),
                ],
            ),
            muted_text(
                "Le poste cible doit avoir le Wake-on-LAN activé dans le BIOS et sur sa carte réseau. Pour lancer ensuite une séquence dessus, ajoute une étape « Séquence distante » : elle attendra que le poste réapparaisse."
            ),
        ]

    def _fields_delay(self) -> list[ft.Control]:
        return [text_field("Durée (secondes)", f"{self.step.seconds:g}", on_change=self._set_number("seconds", minimum=0), width=180)]

    def _local_options(self) -> list[tuple[str, str]]:
        options = [(item.id, item.name) for item in self.host.other_sequences()]
        if self.step.local_sequence_id and all(key != self.step.local_sequence_id for key, _ in options):
            options.append((self.step.local_sequence_id, "Séquence supprimée"))
        return options

    def _fields_local_sequence(self) -> list[ft.Control]:
        self._local_sequence_dropdown = dropdown(
            "Séquence à exécuter",
            self.step.local_sequence_id or None,
            self._local_options(),
            on_select=self._set("local_sequence_id"),
            expand=True,
        )
        return [
            self._local_sequence_dropdown,
            muted_text("La séquence choisie s'exécute entièrement avant de passer à l'étape suivante. Les boucles sont détectées."),
        ]

    def _remote_options(self) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        step = self.step
        peers = self.host.peers()
        peer_options = [(peer.node_id, f"{peer.name} ({peer.host})") for peer in peers]
        selected = next((peer for peer in peers if peer.node_id == step.remote_peer_id), None)
        if step.remote_peer_id and selected is None:
            peer_options.append((step.remote_peer_id, f"{step.remote_peer_name or step.remote_peer_id} (hors ligne)"))
        sequence_options = [(item.id, item.name) for item in selected.sequences] if selected is not None else []
        if step.remote_sequence_id and all(key != step.remote_sequence_id for key, _ in sequence_options):
            sequence_options.append((step.remote_sequence_id, step.remote_sequence_name or step.remote_sequence_id))
        return peer_options, sequence_options

    def _fields_remote_sequence(self) -> list[ft.Control]:
        step = self.step
        peer_options, sequence_options = self._remote_options()

        def on_peer(event: Any) -> None:
            peer_id = str(event.control.value or "")
            peer = next((item for item in self.host.peers() if item.node_id == peer_id), None)
            if peer_id != step.remote_peer_id:
                step.remote_sequence_id = step.remote_sequence_name = ""
            step.remote_peer_id = peer_id
            step.remote_peer_name = peer.name if peer is not None else step.remote_peer_name
            self._after_change(rebuild=True)

        def on_sequence(event: Any) -> None:
            step.remote_sequence_id = str(event.control.value or "")
            peer = next((item for item in self.host.peers() if item.node_id == step.remote_peer_id), None)
            remote = peer.find_sequence(step.remote_sequence_id) if peer is not None else None
            if remote is not None:
                step.remote_sequence_name = remote.name
            self._after_change()

        self._remote_peer_dropdown = dropdown("Poste", step.remote_peer_id or None, peer_options, on_select=on_peer, expand=True, hint="Aucun poste détecté")
        self._remote_sequence_dropdown = dropdown("Séquence", step.remote_sequence_id or None, sequence_options, on_select=on_sequence, expand=True)
        return [
            ft.Row(spacing=10, controls=[self._remote_peer_dropdown, self._remote_sequence_dropdown]),
            ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    text_field("Attendre le poste (s)", f"{step.wait_timeout_s:g}", on_change=self._set_number("wait_timeout_s", minimum=0.5), width=180),
                    muted_text("Si le poste n'est pas encore visible (ex. juste réveillé), l'étape patiente jusqu'à ce délai.", expand=True),
                ],
            ),
        ]

    def _fields_home_assistant(self) -> list[ft.Control]:
        step = self.step
        return [
            ft.Row(
                spacing=10,
                controls=[
                    text_field(
                        "Entity ID",
                        step.home_assistant_entity_id,
                        on_change=self._set("home_assistant_entity_id"),
                        expand=True,
                        hint="light.salon, switch.prise_bureau, scene.stream…",
                    ),
                    dropdown(
                        "Action",
                        step.home_assistant_action,
                        list(HOME_ASSISTANT_ACTION_LABELS.items()),
                        on_select=self._set("home_assistant_action"),
                        width=160,
                    ),
                ],
            ),
            muted_text(
                "Fonctionne avec toute entité qui accepte turn_on / turn_off / toggle (lumières, prises, scènes, scripts, input_boolean…). L'URL et le token se règlent dans Réglages."
            ),
        ]


__all__ = ["STATE_DONE", "STATE_FAILED", "STATE_RUNNING", "StepCard", "StepCardHost", "step_summary"]
