from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

import flet as ft

from models import (
    ACTION_CALL_WEBHOOK,
    ACTION_DELAY,
    ACTION_HOME_ASSISTANT,
    ACTION_LAUNCH_APP,
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
                    ft.Row(
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Image(src="logo_64.png", width=40, height=40, fit=ft.BoxFit.CONTAIN),
                            ft.Text("Py Network Launcher", size=28, weight=ft.FontWeight.BOLD),
                        ],
                    ),
                ],
            ),
            ft.Text("Séquences locales et distantes avec autodiscovery LAN, webhooks, pages web, Wake-on-LAN et démarrage automatique."),
            navigation_row,
            section_container,
            ft.Container(
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                border_radius=12,
                padding=12,
                content=ft.Row(controls=[ft.Icon(ft.Icons.INFO_OUTLINE), status_text]),
            ),
        ],
    )


def build_nav_button(*, key: str, label: str, selected: bool, on_click: Callable[[str], None]) -> ft.Control:
    if selected:
        return ft.ElevatedButton(label, on_click=lambda _, section=key: on_click(section))
    return ft.OutlinedButton(label, on_click=lambda _, section=key: on_click(section))


def build_sequence_list_card(*, sequence: LaunchSequence, selected: bool, subtitle: str, on_select: Callable[[str], None]) -> ft.Control:
    return ft.Card(
        content=ft.Container(
            bgcolor=ft.Colors.PRIMARY_CONTAINER if selected else None,
            border_radius=12,
            content=ft.ListTile(
                title=ft.Text(sequence.name, weight=ft.FontWeight.BOLD),
                subtitle=ft.Text(f"{len(sequence.steps)} étape(s) - {subtitle}"),
                leading=ft.Icon(ft.Icons.PLAYLIST_PLAY),
                on_click=lambda _, sequence_id=sequence.id: on_select(sequence_id),
            ),
        ),
    )


def build_sequences_tab(*, sequence_list_column: ft.Column, sequence_editor_column: ft.Column, on_add_sequence: Callable) -> ft.Control:
    left = ft.Container(
        expand=1,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border_radius=16,
        padding=16,
        content=ft.Column(
            expand=True,
            spacing=12,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Séquences locales", size=20, weight=ft.FontWeight.BOLD),
                        ft.ElevatedButton("Ajouter", icon=ft.Icons.ADD, on_click=on_add_sequence),
                    ],
                ),
                sequence_list_column,
            ],
        ),
    )
    right = ft.Container(
        expand=2,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border_radius=16,
        padding=16,
        content=sequence_editor_column,
    )
    return ft.Row(expand=True, vertical_alignment=ft.CrossAxisAlignment.START, controls=[left, right])


def build_sequence_editor_header(
    *,
    sequence_name_field: ft.TextField,
    run_on_app_start_checkbox: ft.Checkbox,
    action_labels: Mapping[str, str],
    on_run_sequence: Callable,
    on_delete_sequence: Callable,
    on_add_step: Callable[[str], None],
) -> list[ft.Control]:
    return [
        ft.Row(
            controls=[
                sequence_name_field,
                ft.ElevatedButton("Lancer", icon=ft.Icons.PLAY_ARROW, on_click=on_run_sequence),
                ft.OutlinedButton("Supprimer", icon=ft.Icons.DELETE, on_click=on_delete_sequence),
            ]
        ),
        ft.Row(controls=[run_on_app_start_checkbox]),
        ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Text("Étapes", size=18, weight=ft.FontWeight.BOLD),
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
    return ft.Container(
        expand=True,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border_radius=16,
        padding=16,
        content=ft.Column(
            expand=True,
            controls=[
                ft.Row(
                    controls=[ft.Text("Pairs découverts", size=20, weight=ft.FontWeight.BOLD)],
                ),
                peer_column,
            ],
        ),
    )


def build_peer_card(*, peer: PeerInfo, sequence_names: str) -> ft.Control:
    return ft.Card(
        content=ft.Container(
            padding=12,
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Text(peer.name, size=18, weight=ft.FontWeight.BOLD),
                    ft.Text(f"{peer.host}:{peer.port}"),
                    ft.Text(f"ID: {peer.node_id}"),
                    ft.Text(f"Séquences: {sequence_names}"),
                ],
            ),
        )
    )


def build_logs_tab(*, log_list: ft.ListView) -> ft.Control:
    return ft.Container(
        expand=True,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border_radius=16,
        padding=16,
        content=ft.Column(
            expand=True,
            controls=[
                ft.Row(
                    controls=[ft.Text("Historique", size=20, weight=ft.FontWeight.BOLD)],
                ),
                log_list,
            ],
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
    return ft.Container(
        expand=True,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border_radius=16,
        padding=16,
        content=ft.Column(
            expand=True,
            spacing=14,
            controls=[
                ft.Text("Réglages du poste", size=20, weight=ft.FontWeight.BOLD),
                ft.Row(controls=[node_name_field, api_port_field, discovery_port_field]),
                ft.Column(
                    spacing=8,
                    controls=[
                        ft.Text("Home Assistant"),
                        home_assistant_url_field,
                        home_assistant_token_field,
                    ],
                ),
                ft.Row(controls=[start_with_windows_checkbox, start_minimized_checkbox]),
                close_action_control,
                ft.Text("Le démarrage Windows est mis à jour automatiquement quand tu changes les cases ci-dessus."),
                ft.Text("Le nom du poste est sauvegardé quand tu quittes le champ. Les réglages réseau et Home Assistant sont appliqués avec le bouton ci-dessous."),
                ft.Row(
                    controls=[
                        ft.ElevatedButton("Appliquer les réglages", icon=ft.Icons.SAVE, on_click=on_save_settings),
                    ],
                ),
                ft.Text("Fichier de configuration"),
                config_path_text,
                ft.Text("Entrée de démarrage Windows"),
                startup_path_text,
            ],
        ),
    )


def build_step_card(
    *,
    sequence: LaunchSequence,
    step: ActionStep,
    index: int,
    peers: Sequence[PeerInfo],
    action_labels: Mapping[str, str],
    on_update_string: Callable[[str], Callable],
    on_update_bool: Callable[[str], Callable],
    on_update_seconds: Callable,
    on_update_remote_peer: Callable,
    on_pick_command: Callable,
    is_collapsed: bool,
    on_toggle_collapse: Callable,
    on_run_step: Callable,
    on_remove_step: Callable,
    on_move_step: Callable[[int], Callable],
) -> ft.Control:
    peer_options = [ft.dropdown.Option(key="", text="")]
    remote_sequence_options: list[ft.dropdown.Option] = []
    peer_option_keys = {""}
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

    fields: list[ft.Control] = [
        ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.CHEVRON_RIGHT if is_collapsed else ft.Icons.EXPAND_MORE,
                            on_click=on_toggle_collapse,
                        ),
                        ft.Column(
                            spacing=2,
                            controls=[
                                ft.Text(f"Étape {index + 1} - {action_labels[step.action_type]}", size=16, weight=ft.FontWeight.BOLD),
                                ft.Text(step_summary, size=12, color=ft.Colors.OUTLINE),
                            ],
                        ),
                    ],
                ),
                ft.Row(
                    spacing=4,
                    controls=[
                        ft.TextButton("Lancer", icon=ft.Icons.PLAY_ARROW, on_click=on_run_step),
                        ft.IconButton(icon=ft.Icons.ARROW_UPWARD, on_click=on_move_step(-1)),
                        ft.IconButton(icon=ft.Icons.ARROW_DOWNWARD, on_click=on_move_step(1)),
                        ft.IconButton(icon=ft.Icons.DELETE, on_click=on_remove_step),
                    ],
                ),
            ],
        ),
    ]

    if is_collapsed:
        return ft.Card(content=ft.Container(padding=12, content=ft.Column(spacing=10, controls=fields)))

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
    elif step.action_type == ACTION_REMOTE_SEQUENCE:
        fields.extend(
            [
                ft.Dropdown(label="Poste distant", value=step.remote_peer_id, options=peer_options, on_select=on_update_remote_peer),
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

    return ft.Card(content=ft.Container(padding=12, content=ft.Column(spacing=10, controls=fields)))
