"""Thème et petits composants réutilisés par toutes les vues."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Optional

import flet as ft

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
)

SEED_COLOR = "#1E9EC4"

ACTION_ICONS = {
    ACTION_LAUNCH_APP: ft.Icons.APPS,
    ACTION_SHELL_COMMAND: ft.Icons.TERMINAL,
    ACTION_OPEN_WEBPAGE: ft.Icons.LANGUAGE,
    ACTION_CALL_WEBHOOK: ft.Icons.WEBHOOK,
    ACTION_WAKE_ON_LAN: ft.Icons.POWER_SETTINGS_NEW,
    ACTION_DELAY: ft.Icons.TIMER_OUTLINED,
    ACTION_LOCAL_SEQUENCE: ft.Icons.ACCOUNT_TREE_OUTLINED,
    ACTION_REMOTE_SEQUENCE: ft.Icons.HUB_OUTLINED,
    ACTION_HOME_ASSISTANT: ft.Icons.HOME_OUTLINED,
}

ACTION_COLORS = {
    ACTION_LAUNCH_APP: ft.Colors.BLUE_300,
    ACTION_SHELL_COMMAND: ft.Colors.DEEP_PURPLE_200,
    ACTION_OPEN_WEBPAGE: ft.Colors.CYAN_300,
    ACTION_CALL_WEBHOOK: ft.Colors.ORANGE_300,
    ACTION_WAKE_ON_LAN: ft.Colors.GREEN_300,
    ACTION_DELAY: ft.Colors.AMBER_300,
    ACTION_LOCAL_SEQUENCE: ft.Colors.TEAL_300,
    ACTION_REMOTE_SEQUENCE: ft.Colors.INDIGO_200,
    ACTION_HOME_ASSISTANT: ft.Colors.PINK_200,
}

COLOR_RUNNING = ft.Colors.AMBER_400
COLOR_SUCCESS = ft.Colors.GREEN_400
COLOR_ERROR = ft.Colors.RED_300
COLOR_MUTED = ft.Colors.ON_SURFACE_VARIANT

RADIUS = 14


def build_theme() -> ft.Theme:
    return ft.Theme(color_scheme_seed=SEED_COLOR, visual_density=ft.VisualDensity.COMFORTABLE)


def muted_text(value: str, *, size: int = 12, **kwargs) -> ft.Text:
    return ft.Text(value, size=size, color=COLOR_MUTED, **kwargs)


def badge(text: str, *, color: str, icon: Optional[ft.IconData] = None, tooltip: Optional[str] = None) -> ft.Control:
    controls: list[ft.Control] = []
    if icon is not None:
        controls.append(ft.Icon(icon, size=13, color=color))
    controls.append(ft.Text(text, size=11, weight=ft.FontWeight.W_600, color=color))
    return ft.Container(
        bgcolor=ft.Colors.with_opacity(0.14, color),
        border_radius=999,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        content=ft.Row(spacing=4, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=controls),
        tooltip=tooltip,
    )


def action_avatar(icon: ft.IconData, color: str, *, size: int = 36) -> ft.Control:
    return ft.Container(
        width=size,
        height=size,
        border_radius=size // 3,
        bgcolor=ft.Colors.with_opacity(0.18, color),
        alignment=ft.Alignment.CENTER,
        content=ft.Icon(icon, color=color, size=size * 0.55),
    )


def panel(
    *,
    title: str,
    content: ft.Control,
    subtitle: Optional[str] = None,
    actions: Sequence[ft.Control] = (),
    expand: bool | int = True,
    width: Optional[float] = None,
) -> ft.Container:
    header: list[ft.Control] = [ft.Text(title, size=18, weight=ft.FontWeight.BOLD)]
    if subtitle:
        header.append(muted_text(subtitle))
    return ft.Container(
        expand=expand,
        width=width,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
        border_radius=RADIUS,
        padding=16,
        content=ft.Column(
            expand=True,
            spacing=14,
            controls=[
                ft.Row(
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[ft.Column(spacing=2, expand=True, controls=header), *actions],
                ),
                content,
            ],
        ),
    )


def group(*, title: str, controls: Sequence[ft.Control], description: Optional[str] = None, icon: Optional[ft.IconData] = None) -> ft.Container:
    title_row: list[ft.Control] = []
    if icon is not None:
        title_row.append(ft.Icon(icon, size=18, color=ft.Colors.PRIMARY))
    title_row.append(ft.Text(title, size=15, weight=ft.FontWeight.W_600))
    header: list[ft.Control] = [ft.Row(spacing=8, controls=title_row)]
    if description:
        header.append(muted_text(description))
    return ft.Container(
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border_radius=RADIUS,
        padding=16,
        content=ft.Column(spacing=12, controls=[ft.Column(spacing=4, controls=header), *controls]),
    )


def empty_state(*, icon: ft.IconData, title: str, message: str, action: Optional[ft.Control] = None) -> ft.Control:
    controls: list[ft.Control] = [
        ft.Icon(icon, size=40, color=ft.Colors.OUTLINE),
        ft.Text(title, size=16, weight=ft.FontWeight.W_600, text_align=ft.TextAlign.CENTER),
        muted_text(message, text_align=ft.TextAlign.CENTER),
    ]
    if action is not None:
        controls.append(ft.Container(content=action, margin=ft.Margin.only(top=6)))
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=24, vertical=32),
        alignment=ft.Alignment.CENTER,
        content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8, tight=True, controls=controls),
    )


def field_border() -> ft.OutlineInputBorder:
    return ft.OutlineInputBorder(border_radius=10)


def text_field(
    label: str,
    value: str = "",
    *,
    on_change: Optional[Callable] = None,
    on_blur: Optional[Callable] = None,
    hint: Optional[str] = None,
    helper: Optional[str] = None,
    expand: bool | int | None = None,
    width: Optional[float] = None,
    multiline: bool = False,
    monospace: bool = False,
    **kwargs,
) -> ft.TextField:
    return ft.TextField(
        label=label,
        value=value,
        hint_text=hint,
        helper=helper,
        on_change=on_change,
        on_blur=on_blur,
        expand=expand,
        width=width,
        dense=True,
        border=field_border(),
        multiline=multiline,
        min_lines=2 if multiline else None,
        max_lines=6 if multiline else None,
        text_style=ft.TextStyle(font_family="Consolas") if monospace else None,
        **kwargs,
    )


def dropdown(
    label: str,
    value: Optional[str],
    options: Sequence[tuple[str, str]],
    *,
    on_select: Optional[Callable] = None,
    expand: bool | int | None = None,
    width: Optional[float] = None,
    hint: Optional[str] = None,
) -> ft.Dropdown:
    return ft.Dropdown(
        label=label,
        value=value,
        options=[ft.DropdownOption(key=key, text=text) for key, text in options],
        on_select=on_select,
        expand=expand,
        width=width,
        dense=True,
        border=field_border(),
        hint_text=hint,
    )


def labeled_switch(label: str, value: bool, *, on_change: Callable, tooltip: Optional[str] = None) -> ft.Switch:
    return ft.Switch(label=label, value=value, on_change=on_change, tooltip=tooltip, label_text_style=ft.TextStyle(size=13))
