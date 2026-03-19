from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

import flet as ft

from models import (
    ACTION_CALL_WEBHOOK,
    ACTION_DELAY,
    ACTION_HOME_ASSISTANT,
    ACTION_LAUNCH_APP,
    ACTION_LOCAL_SEQUENCE,
    ACTION_OPEN_WEBPAGE,
    ACTION_REMOTE_SEQUENCE,
    ACTION_SHELL_COMMAND,
    ACTION_TYPES,
    ACTION_WAKE_ON_LAN,
    ActionStep,
    HOME_ASSISTANT_ACTION_LABELS,
    LaunchSequence,
    PeerInfo,
    WAIT_MODE_LABELS,
    WAIT_MODE_PORT,
    WAIT_MODE_STARTED,
)


ACTION_ICONS = {
    ACTION_LAUNCH_APP: ft.Icons.APPS,
    ACTION_SHELL_COMMAND: ft.Icons.TERMINAL,
    ACTION_OPEN_WEBPAGE: ft.Icons.LANGUAGE,
    ACTION_CALL_WEBHOOK: ft.Icons.WIFI_TETHERING,
    ACTION_WAKE_ON_LAN: ft.Icons.POWER,
    ACTION_DELAY: ft.Icons.TIMER,
    ACTION_LOCAL_SEQUENCE: ft.Icons.REPEAT,
    ACTION_REMOTE_SEQUENCE: ft.Icons.DEVICE_HUB,
    ACTION_HOME_ASSISTANT: ft.Icons.HOME,
}

ACTION_ACCENT_COLORS = {
    ACTION_LAUNCH_APP: ft.Colors.BLUE_300,
    ACTION_SHELL_COMMAND: ft.Colors.DEEP_PURPLE_300,
    ACTION_OPEN_WEBPAGE: ft.Colors.CYAN_300,
    ACTION_CALL_WEBHOOK: ft.Colors.ORANGE_300,
    ACTION_WAKE_ON_LAN: ft.Colors.GREEN_300,
    ACTION_DELAY: ft.Colors.AMBER_300,
    ACTION_LOCAL_SEQUENCE: ft.Colors.TEAL_300,
    ACTION_REMOTE_SEQUENCE: ft.Colors.INDIGO_300,
    ACTION_HOME_ASSISTANT: ft.Colors.PINK_300,
}


def _build_badge(*, text: str, bgcolor: str, color: str = ft.Colors.WHITE) -> ft.Control:
    return ft.Container(
        bgcolor=bgcolor,
        border_radius=999,
        padding=ft.padding.symmetric(horizontal=10, vertical=4),
        content=ft.Text(text, size=11, weight=ft.FontWeight.W_600, color=color),
    )


def _build_section_shell(*, title: str, subtitle: str, content: ft.Control, actions: Sequence[ft.Control] | None = None) -> ft.Control:
    header_controls: list[ft.Control] = [
        ft.Column(
            spacing=4,
            expand=True,
            controls=[
                ft.Text(title, size=21, weight=ft.FontWeight.BOLD),
                ft.Text(subtitle, size=12, color=ft.Colors.OUTLINE),
            ],
        )
    ]
    if actions:
        header_controls.append(ft.Row(spacing=8, controls=list(actions)))
    return ft.Container(
        expand=True,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border_radius=18,
        padding=18,
        content=ft.Column(
            expand=True,
            spacing=16,
            controls=[
                ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.START, controls=header_controls),
                content,
            ],
        ),
    )


def _build_empty_state(*, icon: str, title: str, subtitle: str) -> ft.Control:
    return ft.Container(
        padding=24,
        border_radius=16,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[
                ft.Icon(icon, size=38, color=ft.Colors.OUTLINE),
                ft.Text(title, size=16, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Text(subtitle, size=12, color=ft.Colors.OUTLINE, text_align=ft.TextAlign.CENTER),
            ],
        ),
    )


def _build_settings_group(*, title: str, subtitle: str, controls: Sequence[ft.Control]) -> ft.Control:
    return ft.Container(
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border_radius=16,
        padding=16,
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Text(title, size=16, weight=ft.FontWeight.BOLD),
                ft.Text(subtitle, size=12, color=ft.Colors.OUTLINE),
                *controls,
            ],
        ),
    )


def build_main_layout(
    *,
    navigation_row: ft.Row,
    section_container: ft.Container,
    status_text: ft.Text,
) -> ft.Control:
    return ft.Column(
        expand=True,
        spacing=16,
        controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=16, vertical=14),
                        border_radius=18,
                        bgcolor=ft.Colors.SURFACE_CONTAINER,
                        content=ft.Row(
                            spacing=14,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Container(
                                    width=52,
                                    height=52,
                                    border_radius=14,
                                    bgcolor=ft.Colors.PRIMARY_CONTAINER,
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Image(src="logo_64.png", width=34, height=34, fit=ft.BoxFit.CONTAIN),
                                ),
                                ft.Column(
                                    spacing=3,
                                    controls=[
                                        ft.Text("Py Network Launcher", size=28, weight=ft.FontWeight.BOLD),
                                        ft.Text("Automatisation locale et distante pour postes Windows sur le LAN.", size=12, color=ft.Colors.OUTLINE),
                                    ],
                                ),
                            ],
                        ),
                    ),
                ],
            ),
            navigation_row,
            section_container,
            ft.Container(
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                border_radius=16,
                padding=14,
                content=ft.Row(spacing=10, controls=[ft.Icon(ft.Icons.INFO_OUTLINE), status_text]),
            ),
        ],
    )


def build_nav_button(*, key: str, label: str, selected: bool, on_click: Callable[[str], None]) -> ft.Control:
    if selected:
        return ft.ElevatedButton(label, icon=ft.Icons.CHEVRON_RIGHT, on_click=lambda _, section=key: on_click(section))
    return ft.OutlinedButton(label, on_click=lambda _, section=key: on_click(section))


def build_sequence_list_card(*, sequence: LaunchSequence, selected: bool, subtitle: str, on_select: Callable[[str], None]) -> ft.Control:
    badges: list[ft.Control] = []
    if subtitle == "manuel":
        badges.append(_build_badge(text="Manuel", bgcolor=ft.Colors.BLUE_GREY_700))
    else:
        for item in subtitle.split(" | "):
            if item == "app":
                badges.append(_build_badge(text="Auto-start", bgcolor=ft.Colors.GREEN_700))
    return ft.Card(
        content=ft.Container(
            bgcolor=ft.Colors.PRIMARY_CONTAINER if selected else None,
            border_radius=16,
            padding=16,
            content=ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        width=42,
                        height=42,
                        border_radius=12,
                        bgcolor=ft.Colors.PRIMARY if selected else ft.Colors.SURFACE_CONTAINER_HIGHEST,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.PLAYLIST_PLAY, color=ft.Colors.WHITE if selected else ft.Colors.PRIMARY),
                    ),
                    ft.Column(
                        expand=True,
                        spacing=6,
                        controls=[
                            ft.Text(sequence.name, weight=ft.FontWeight.BOLD, size=16),
                            ft.Text(f"{len(sequence.steps)} étape(s)", size=12, color=ft.Colors.OUTLINE),
                            ft.Row(wrap=True, spacing=6, controls=badges),
                        ],
                    ),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, color=ft.Colors.OUTLINE),
                ],
            ),
            on_click=lambda _, sequence_id=sequence.id: on_select(sequence_id),
        ),
    )


def build_sequences_tab(*, sequence_list_column: ft.Column, sequence_editor_column: ft.Column, on_add_sequence: Callable) -> ft.Control:
    left = _build_section_shell(
        title="Séquences locales",
        subtitle="Organise tes scénarios et déclenche-les à la demande ou au démarrage.",
        actions=[ft.ElevatedButton("Ajouter", icon=ft.Icons.ADD, on_click=on_add_sequence)],
        content=ft.Column(
            expand=True,
            spacing=12,
            controls=[sequence_list_column],
        ),
    )
    right = _build_section_shell(
        title="Éditeur de séquence",
        subtitle="Sélectionne une séquence pour modifier ses étapes, son ordre et son comportement.",
        content=sequence_editor_column,
    )
    return ft.Row(expand=True, spacing=16, vertical_alignment=ft.CrossAxisAlignment.START, controls=[left, right])


def build_sequence_editor_header(
    *,
    sequence_name_field: ft.TextField,
    run_on_app_start_checkbox: ft.Checkbox,
    action_labels: Mapping[str, str],
    on_run_sequence: Callable,
    on_stop_sequence: Callable,
    on_delete_sequence: Callable,
    on_add_step: Callable[[str], None],
    is_sequence_running: bool,
) -> list[ft.Control]:
    return [
        ft.Container(
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=16,
            padding=16,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row(
                        controls=[
                            sequence_name_field,
                            ft.ElevatedButton("Lancer", icon=ft.Icons.PLAY_ARROW, on_click=on_run_sequence),
                            ft.OutlinedButton("Stop", icon=ft.Icons.STOP, on_click=on_stop_sequence, disabled=not is_sequence_running),
                            ft.OutlinedButton("Supprimer", icon=ft.Icons.DELETE, on_click=on_delete_sequence),
                        ]
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(controls=[run_on_app_start_checkbox]),
                            _build_badge(text="Étapes repliées par défaut", bgcolor=ft.Colors.BLUE_GREY_700),
                        ],
                    ),
                ],
            ),
        ),
        ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(
                    spacing=2,
                    controls=[
                        ft.Text("Étapes", size=18, weight=ft.FontWeight.BOLD),
                        ft.Text("Ajoute des actions locales, distantes ou Home Assistant.", size=12, color=ft.Colors.OUTLINE),
                    ],
                ),
                ft.PopupMenuButton(
                    icon=ft.Icons.ADD,
                    items=[
                        ft.PopupMenuItem(content=action_labels[action_type], on_click=lambda _, current=action_type: on_add_step(current))
                        for action_type in ACTION_TYPES
                    ],
                ),
            ],
        ),
    ]


def build_peers_tab(*, peer_column: ft.Column) -> ft.Control:
    return _build_section_shell(
        title="Pairs découverts",
        subtitle="Machines visibles sur le réseau local avec leurs séquences publiées.",
        content=ft.Column(
            expand=True,
            spacing=12,
            controls=[peer_column],
        ),
    )


def build_peer_card(*, peer: PeerInfo, sequence_names: str) -> ft.Control:
    return ft.Card(
        content=ft.Container(
            padding=16,
            border_radius=16,
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(peer.name, size=18, weight=ft.FontWeight.BOLD),
                            _build_badge(text="En ligne", bgcolor=ft.Colors.GREEN_700),
                        ],
                    ),
                    ft.Row(wrap=True, spacing=8, controls=[
                        _build_badge(text=f"{peer.host}:{peer.port}", bgcolor=ft.Colors.BLUE_GREY_700),
                        _build_badge(text=f"{len(peer.sequences)} séquence(s)", bgcolor=ft.Colors.INDIGO_700),
                    ]),
                    ft.Text(f"ID: {peer.node_id}", size=12, color=ft.Colors.OUTLINE),
                    ft.Text(f"Séquences: {sequence_names}"),
                ],
            ),
        )
    )


def build_logs_tab(*, log_list: ft.ListView) -> ft.Control:
    return _build_section_shell(
        title="Historique",
        subtitle="Suivi des lancements, des erreurs et des échanges réseau récents.",
        content=ft.Column(
            expand=True,
            spacing=12,
            controls=[log_list],
        ),
    )


def build_settings_tab(
    *,
    node_name_field: ft.TextField,
    api_port_field: ft.TextField,
    discovery_port_field: ft.TextField,
    home_assistant_url_field: ft.TextField,
    home_assistant_token_field: ft.TextField,
    start_with_windows_checkbox: ft.Checkbox,
    start_minimized_checkbox: ft.Checkbox,
    close_action_control: ft.Control,
    config_path_text: ft.Text,
    startup_path_text: ft.Text,
    on_save_settings: Callable,
) -> ft.Control:
    return _build_section_shell(
        title="Réglages du poste",
        subtitle="Personnalise le réseau local, Windows et les intégrations externes.",
        actions=[ft.ElevatedButton("Appliquer les réglages", icon=ft.Icons.SAVE, on_click=on_save_settings)],
        content=ft.Column(
            spacing=14,
            controls=[
                _build_settings_group(
                    title="Réseau local",
                    subtitle="Nom du poste et ports de communication entre machines.",
                    controls=[ft.Row(spacing=10, controls=[node_name_field, api_port_field, discovery_port_field])],
                ),
                _build_settings_group(
                    title="Home Assistant",
                    subtitle="Connexion utilisée par les étapes Home Assistant.",
                    controls=[home_assistant_url_field, home_assistant_token_field],
                ),
                _build_settings_group(
                    title="Démarrage Windows",
                    subtitle="Choisis comment l'application démarre et comment elle se ferme.",
                    controls=[
                        ft.Row(spacing=10, controls=[start_with_windows_checkbox, start_minimized_checkbox]),
                        close_action_control,
                        ft.Text("Le démarrage Windows est mis à jour automatiquement quand tu changes les cases ci-dessus.", size=12, color=ft.Colors.OUTLINE),
                    ],
                ),
                _build_settings_group(
                    title="Fichiers et configuration",
                    subtitle="Localisation des éléments utilisés par l'application.",
                    controls=[
                        ft.Text("Le nom du poste est sauvegardé quand tu quittes le champ. Les réglages réseau et Home Assistant sont appliqués avec le bouton ci-dessus.", size=12, color=ft.Colors.OUTLINE),
                        ft.Text("Fichier de configuration", weight=ft.FontWeight.BOLD),
                        config_path_text,
                        ft.Text("Entrée de démarrage Windows", weight=ft.FontWeight.BOLD),
                        startup_path_text,
                    ],
                ),
            ],
        ),
    )


def build_step_card(
    *,
    sequence: LaunchSequence,
    step: ActionStep,
    index: int,
    peers: Sequence[PeerInfo],
    local_sequences: Sequence[LaunchSequence],
    action_labels: Mapping[str, str],
    on_update_string: Callable[[str], Callable],
    on_update_bool: Callable[[str], Callable],
    on_update_seconds: Callable,
    on_update_remote_peer: Callable,
    on_pick_command: Callable,
    is_collapsed: bool,
    is_running: bool,
    is_completed: bool,
    show_drag_handle: bool,
    drag_group: str | None,
    on_step_drop: Callable | None,
    on_toggle_collapse: Callable,
    on_run_step: Callable,
    on_remove_step: Callable,
    on_move_step: Callable[[int], Callable],
) -> ft.Control:
    def build_card_shell(*, content_controls: list[ft.Control], spacing: int) -> ft.Container:
        return ft.Container(
            key=step.id,
            content=ft.Card(
                content=ft.Container(
                    padding=ft.padding.symmetric(horizontal=14, vertical=10),
                    border_radius=16,
                    border=state_border,
                    content=ft.Column(spacing=spacing, controls=content_controls),
                )
            ),
        )

    def build_drag_handle(*, color: str, bgcolor: str) -> ft.Control:
        return ft.Container(
            width=34,
            height=34,
            border_radius=10,
            bgcolor=bgcolor,
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(ft.Icons.DRAG_INDICATOR, color=color, size=18),
        )

    def build_drag_feedback() -> ft.Control:
        return ft.Container(
            width=760,
            opacity=0.92,
            shadow=ft.BoxShadow(blur_radius=18, color=ft.Colors.BLACK26, offset=ft.Offset(0, 8)),
            content=ft.Card(
                content=ft.Container(
                    padding=14,
                    border_radius=16,
                    border=ft.border.all(2, accent_color),
                    bgcolor=ft.Colors.SURFACE,
                    content=ft.Row(
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            build_drag_handle(color=ft.Colors.PRIMARY, bgcolor=ft.Colors.PRIMARY_CONTAINER),
                            ft.Container(
                                width=40,
                                height=40,
                                border_radius=12,
                                bgcolor=accent_color,
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(action_icon, color=ft.Colors.BLACK),
                            ),
                            ft.Column(
                                spacing=2,
                                expand=True,
                                controls=[
                                    ft.Text(f"Étape {index + 1} - {action_labels[step.action_type]}", size=16, weight=ft.FontWeight.BOLD),
                                    ft.Text(step_summary, size=12, color=ft.Colors.OUTLINE),
                                ],
                            ),
                        ],
                    ),
                )
            ),
        )

    accent_color = ACTION_ACCENT_COLORS.get(step.action_type, ft.Colors.PRIMARY)
    action_icon = ACTION_ICONS.get(step.action_type, ft.Icons.PLAY_ARROW)
    peer_options: list[ft.dropdown.Option] = []
    remote_sequence_options: list[ft.dropdown.Option] = []
    peer_option_keys: set[str] = set()
    remote_sequence_option_keys: set[str] = set()
    selected_peer = next((peer for peer in peers if peer.node_id == step.remote_peer_id), None)
    selected_remote_sequence = None
    for peer in peers:
        peer_options.append(ft.dropdown.Option(key=peer.node_id, text=f"{peer.name} ({peer.host})"))
        peer_option_keys.add(peer.node_id)
        if peer.node_id == step.remote_peer_id:
            for item in peer.sequences:
                remote_sequence_options.append(ft.dropdown.Option(key=item.id, text=item.name))
                remote_sequence_option_keys.add(item.id)
                if item.id == step.remote_sequence_id:
                    selected_remote_sequence = item

    if step.remote_peer_id and step.remote_peer_id not in peer_option_keys:
        peer_options.append(ft.dropdown.Option(key=step.remote_peer_id, text=f"ID mémorisé: {step.remote_peer_id}"))
    if step.remote_sequence_id and step.remote_sequence_id not in remote_sequence_option_keys:
        remote_sequence_options.append(ft.dropdown.Option(key=step.remote_sequence_id, text=f"ID mémorisé: {step.remote_sequence_id}"))

    step_summary = ""
    if step.action_type == ACTION_LAUNCH_APP:
        parts = [step.command.strip() or "Commande non définie"]
        if step.arguments.strip():
            parts.append(step.arguments.strip())
        step_summary = " ".join(parts)
    elif step.action_type == ACTION_SHELL_COMMAND:
        step_summary = step.command.strip() or "Commande shell non définie"
    elif step.action_type == ACTION_OPEN_WEBPAGE:
        step_summary = step.url.strip() or "URL non définie"
    elif step.action_type == ACTION_CALL_WEBHOOK:
        step_summary = f"{step.method.strip().upper() or 'POST'} {step.url.strip() or 'URL non définie'}"
    elif step.action_type == ACTION_WAKE_ON_LAN:
        step_summary = step.mac_address.strip() or "Adresse MAC non définie"
    elif step.action_type == ACTION_DELAY:
        step_summary = f"{step.seconds:g}s"
    elif step.action_type == ACTION_LOCAL_SEQUENCE:
        selected_local = next((s for s in local_sequences if s.id == step.local_sequence_id), None)
        step_summary = selected_local.name if selected_local is not None else (step.local_sequence_id.strip() or "Séquence locale non définie")
    elif step.action_type == ACTION_REMOTE_SEQUENCE:
        selected_peer_label = selected_peer.name if selected_peer is not None else step.remote_peer_id.strip()
        selected_sequence_label = selected_remote_sequence.name if selected_remote_sequence is not None else step.remote_sequence_id.strip()
        if selected_sequence_label and selected_peer_label:
            step_summary = f"{selected_peer_label} - {selected_sequence_label}"
        else:
            step_summary = selected_sequence_label or selected_peer_label or "Sélection distante non définie"
    elif step.action_type == ACTION_HOME_ASSISTANT:
        action_label = HOME_ASSISTANT_ACTION_LABELS.get(step.home_assistant_action, step.home_assistant_action)
        entity_label = step.home_assistant_entity_id.strip() or "Entité non définie"
        step_summary = f"{entity_label} - {action_label}"

    leading_controls: list[ft.Control] = []
    if show_drag_handle:
        leading_controls.append(
            ft.Draggable(
                key=step.id,
                group=drag_group or "sequence-step",
                axis=ft.Axis.VERTICAL,
                max_simultaneous_drags=1,
                content=build_drag_handle(color=ft.Colors.ON_SURFACE_VARIANT, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST),
                content_when_dragging=build_drag_handle(color=ft.Colors.OUTLINE_VARIANT, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH),
                content_feedback=build_drag_feedback(),
            )
        )
    leading_controls.extend(
        [
            ft.IconButton(
                icon=ft.Icons.CHEVRON_RIGHT if is_collapsed else ft.Icons.EXPAND_MORE,
                tooltip="Replier / déplier",
                on_click=on_toggle_collapse,
            ),
            ft.Container(
                width=40,
                height=40,
                border_radius=12,
                bgcolor=accent_color,
                alignment=ft.Alignment.CENTER,
                content=ft.Icon(action_icon, color=ft.Colors.BLACK),
            ),
            ft.Column(
                spacing=2,
                controls=[
                    ft.Text(f"Étape {index + 1} - {action_labels[step.action_type]}", size=16, weight=ft.FontWeight.BOLD),
                    ft.Text(step_summary, size=12, color=ft.Colors.OUTLINE),
                ],
            ),
        ]
    )
    trailing_controls: list[ft.Control] = []
    if is_running:
        trailing_controls.append(_build_badge(text="En attente", bgcolor=ft.Colors.ORANGE_700))
    elif is_completed:
        trailing_controls.append(ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_400))
    trailing_controls.extend(
        [
            ft.IconButton(icon=ft.Icons.PLAY_ARROW, tooltip="Lancer l'étape", on_click=on_run_step),
            ft.IconButton(icon=ft.Icons.ARROW_UPWARD, tooltip="Monter", on_click=on_move_step(-1)),
            ft.IconButton(icon=ft.Icons.ARROW_DOWNWARD, tooltip="Descendre", on_click=on_move_step(1)),
            ft.IconButton(icon=ft.Icons.DELETE, tooltip="Supprimer", on_click=on_remove_step),
        ]
    )

    state_border = None
    if is_running:
        state_border = ft.border.all(2, ft.Colors.ORANGE_400)
    elif is_completed:
        state_border = ft.border.all(2, ft.Colors.GREEN_400)

    fields: list[ft.Control] = [
        ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=leading_controls,
                ),
                ft.Row(spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=trailing_controls),
            ],
        ),
    ]

    if is_collapsed:
        card_content = build_card_shell(content_controls=fields, spacing=10)
        if on_step_drop is not None and show_drag_handle:
            target_shell = ft.Container(
                border_radius=18,
                border=ft.border.all(2, ft.Colors.TRANSPARENT),
                padding=0,
                content=card_content,
            )

            def on_target_will_accept(event: ft.DragWillAcceptEvent) -> None:
                target_shell.border = ft.border.all(2, ft.Colors.PRIMARY if event.accept else ft.Colors.ERROR)
                target_shell.bgcolor = ft.Colors.PRIMARY_CONTAINER if event.accept else ft.Colors.ERROR_CONTAINER
                target_shell.update()

            def on_target_leave(_: ft.DragTargetLeaveEvent) -> None:
                target_shell.border = ft.border.all(2, ft.Colors.TRANSPARENT)
                target_shell.bgcolor = None
                target_shell.update()

            def on_target_accept(event: ft.DragTargetEvent) -> None:
                target_shell.border = ft.border.all(2, ft.Colors.TRANSPARENT)
                target_shell.bgcolor = None
                target_shell.update()
                on_step_drop(event)

            return ft.DragTarget(
                group=drag_group or "sequence-step",
                content=target_shell,
                on_will_accept=on_target_will_accept,
                on_leave=on_target_leave,
                on_accept=on_target_accept,
            )
        return card_content

    if step.action_type == ACTION_LAUNCH_APP:
        fields.extend(
            [
                ft.Row(
                    controls=[
                        ft.TextField(label="Commande ou chemin exécutable", value=step.command, on_change=on_update_string("command"), expand=True),
                        ft.OutlinedButton("Choisir…", icon=ft.Icons.FOLDER_OPEN, on_click=on_pick_command),
                    ]
                ),
                ft.TextField(label="Arguments", value=step.arguments, on_change=on_update_string("arguments")),
                ft.TextField(label="Dossier de travail", value=step.working_directory, on_change=on_update_string("working_directory")),
                ft.Dropdown(
                    label="Attente après lancement",
                    value=step.wait_mode,
                    options=[ft.dropdown.Option(key=item, text=WAIT_MODE_LABELS[item]) for item in WAIT_MODE_LABELS],
                    on_select=on_update_string("wait_mode"),
                ),
            ]
        )
        if step.wait_mode in (WAIT_MODE_STARTED, WAIT_MODE_PORT):
            fields.append(ft.TextField(label="Timeout d'attente (s)", value=f"{step.wait_timeout_s:g}", on_change=on_update_string("wait_timeout_s")))
        if step.wait_mode == WAIT_MODE_PORT:
            fields.extend(
                [
                    ft.TextField(label="Hôte à tester", value=step.wait_host, on_change=on_update_string("wait_host")),
                    ft.TextField(label="Port à tester", value=str(step.wait_port or ""), on_change=on_update_string("wait_port")),
                ]
            )
    elif step.action_type == ACTION_SHELL_COMMAND:
        fields.extend(
            [
                ft.TextField(label="Commande shell", value=step.command, on_change=on_update_string("command"), multiline=True, min_lines=2, max_lines=4),
                ft.TextField(label="Dossier de travail", value=step.working_directory, on_change=on_update_string("working_directory")),
                ft.Text("La commande est exécutée via le shell Windows. Utilise ce mode pour `cmd`, les pipes, les redirections ou une ligne de commande composée.", size=12, color=ft.Colors.OUTLINE),
                ft.Dropdown(
                    label="Attente après lancement",
                    value=step.wait_mode,
                    options=[ft.dropdown.Option(key=item, text=WAIT_MODE_LABELS[item]) for item in WAIT_MODE_LABELS],
                    on_select=on_update_string("wait_mode"),
                ),
            ]
        )
        if step.wait_mode in (WAIT_MODE_STARTED, WAIT_MODE_PORT):
            fields.append(ft.TextField(label="Timeout d'attente (s)", value=f"{step.wait_timeout_s:g}", on_change=on_update_string("wait_timeout_s")))
        if step.wait_mode == WAIT_MODE_PORT:
            fields.extend(
                [
                    ft.TextField(label="Hôte à tester", value=step.wait_host, on_change=on_update_string("wait_host")),
                    ft.TextField(label="Port à tester", value=str(step.wait_port or ""), on_change=on_update_string("wait_port")),
                ]
            )
    elif step.action_type == ACTION_OPEN_WEBPAGE:
        fields.extend(
            [
                ft.TextField(label="URL", value=step.url, on_change=on_update_string("url")),
                ft.Text("Indique une URL complète, par exemple `https://example.com` ou `https://www.example.com`.", size=12, color=ft.Colors.OUTLINE),
            ]
        )
    elif step.action_type == ACTION_CALL_WEBHOOK:
        fields.extend(
            [
                ft.TextField(label="URL", value=step.url, on_change=on_update_string("url")),
                ft.Dropdown(
                    label="Méthode",
                    value=step.method,
                    options=[ft.dropdown.Option(key=item, text=item) for item in ["GET", "POST", "PUT", "PATCH", "DELETE"]],
                    on_select=on_update_string("method"),
                ),
                ft.TextField(label="Headers JSON", value=step.headers_json, multiline=True, min_lines=2, max_lines=4, on_change=on_update_string("headers_json")),
                ft.TextField(label="Body", value=step.body, multiline=True, min_lines=3, max_lines=6, on_change=on_update_string("body")),
            ]
        )
    elif step.action_type == ACTION_WAKE_ON_LAN:
        fields.extend(
            [
                ft.TextField(label="Adresse MAC", value=step.mac_address, on_change=on_update_string("mac_address")),
                ft.TextField(label="IP broadcast", value=step.broadcast_ip, on_change=on_update_string("broadcast_ip")),
            ]
        )
    elif step.action_type == ACTION_DELAY:
        fields.append(ft.TextField(label="Secondes", value=f"{step.seconds:g}", on_change=on_update_seconds))
    elif step.action_type == ACTION_LOCAL_SEQUENCE:
        local_seq_options = [ft.dropdown.Option(key=s.id, text=s.name) for s in local_sequences]
        fields.append(
            ft.Dropdown(
                label="Séquence locale",
                value=step.local_sequence_id or None,
                options=local_seq_options,
                on_select=on_update_string("local_sequence_id"),
            )
        )
        if not local_sequences:
            fields.append(ft.Text("Aucune autre séquence disponible.", size=12, color=ft.Colors.OUTLINE))
    elif step.action_type == ACTION_REMOTE_SEQUENCE:
        fields.extend(
            [
                ft.Dropdown(label="Poste distant", value=step.remote_peer_id or None, options=peer_options, on_select=on_update_remote_peer),
                ft.Dropdown(label="Séquence distante", value=step.remote_sequence_id or None, options=remote_sequence_options, on_select=on_update_string("remote_sequence_id")),
            ]
        )
    elif step.action_type == ACTION_HOME_ASSISTANT:
        fields.extend(
            [
                ft.TextField(label="Entity ID", value=step.home_assistant_entity_id, on_change=on_update_string("home_assistant_entity_id")),
                ft.Dropdown(
                    label="Action",
                    value=step.home_assistant_action,
                    options=[ft.dropdown.Option(key=item, text=HOME_ASSISTANT_ACTION_LABELS[item]) for item in HOME_ASSISTANT_ACTION_LABELS],
                    on_select=on_update_string("home_assistant_action"),
                ),
                ft.Text("Utilise un entity ID complet comme `light.salon` ou `switch.prise_bureau`. Le type est détecté automatiquement.", size=12, color=ft.Colors.OUTLINE),
            ]
        )

    card_content = build_card_shell(content_controls=fields, spacing=12)
    if on_step_drop is not None and show_drag_handle:
        target_shell = ft.Container(
            border_radius=18,
            border=ft.border.all(2, ft.Colors.TRANSPARENT),
            padding=0,
            content=card_content,
        )

        def on_target_will_accept(event: ft.DragWillAcceptEvent) -> None:
            target_shell.border = ft.border.all(2, ft.Colors.PRIMARY if event.accept else ft.Colors.ERROR)
            target_shell.bgcolor = ft.Colors.PRIMARY_CONTAINER if event.accept else ft.Colors.ERROR_CONTAINER
            target_shell.update()

        def on_target_leave(_: ft.DragTargetLeaveEvent) -> None:
            target_shell.border = ft.border.all(2, ft.Colors.TRANSPARENT)
            target_shell.bgcolor = None
            target_shell.update()

        def on_target_accept(event: ft.DragTargetEvent) -> None:
            target_shell.border = ft.border.all(2, ft.Colors.TRANSPARENT)
            target_shell.bgcolor = None
            target_shell.update()
            on_step_drop(event)

        return ft.DragTarget(
            group=drag_group or "sequence-step",
            content=target_shell,
            on_will_accept=on_target_will_accept,
            on_leave=on_target_leave,
            on_accept=on_target_accept,
        )
    return card_content
