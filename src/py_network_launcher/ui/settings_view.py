"""Vue « Réglages » : identité réseau, Home Assistant, démarrage Windows."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Optional

import flet as ft

from py_network_launcher import __version__
from py_network_launcher.actions import check_home_assistant, normalize_url
from py_network_launcher.models import CLOSE_ACTION_LABELS
from py_network_launcher.ui.widgets import COLOR_ERROR, COLOR_MUTED, COLOR_SUCCESS, group, labeled_switch, muted_text, panel, text_field
from py_network_launcher.windows import IS_WINDOWS, startup_entry_label

if TYPE_CHECKING:
    from py_network_launcher.ui.window import MainWindow


def _parse_port(raw: Optional[str]) -> Optional[int]:
    try:
        port = int(str(raw or "").strip())
    except ValueError:
        return None
    return port if 1 <= port <= 65535 else None


class SettingsView:
    def __init__(self, window: MainWindow) -> None:
        self.window = window
        settings = window.config.settings

        self._node_name = text_field(
            "Nom du poste",
            settings.node_name,
            on_blur=self._save_node_name,
            on_submit=self._save_node_name,
            expand=True,
            helper="Nom affiché sur les autres postes",
        )
        self._api_port = text_field("Port API (TCP)", str(settings.api_port), on_change=self._on_ports_change, width=160)
        self._discovery_port = text_field("Port découverte (UDP)", str(settings.discovery_port), on_change=self._on_ports_change, width=190)
        self._apply_ports = ft.FilledTonalButton("Appliquer", icon=ft.Icons.SYNC_ROUNDED, on_click=self._apply_ports_click, disabled=True)
        self._network_status = ft.Text(size=12, selectable=True)

        self._ha_url = text_field(
            "URL de Home Assistant", settings.home_assistant_url, on_blur=self._save_home_assistant, expand=True, hint="http://homeassistant.local:8123"
        )
        self._ha_token = text_field(
            "Jeton d'accès longue durée",
            settings.home_assistant_token,
            on_blur=self._save_home_assistant,
            expand=True,
            password=True,
            can_reveal_password=True,
            helper="Profil Home Assistant → Sécurité → Jetons d'accès longue durée",
        )
        self._ha_test = ft.OutlinedButton("Tester la connexion", icon=ft.Icons.VERIFIED_OUTLINED, on_click=self._test_home_assistant)
        self._ha_result = ft.Text(size=12, expand=True)

        self._start_with_windows = labeled_switch(
            "Lancer Py Network Launcher à l'ouverture de session Windows", settings.start_with_windows, on_change=self._on_startup_change
        )
        self._start_hidden = labeled_switch("Démarrer réduit dans la zone de notification", settings.start_minimized, on_change=self._on_startup_change)
        self._close_action = ft.RadioGroup(
            value=settings.close_action,
            on_change=self._on_close_action_change,
            content=ft.Column(spacing=0, controls=[ft.Radio(value=key, label=label) for key, label in CLOSE_ACTION_LABELS.items()]),
        )
        self._startup_info = muted_text("", selectable=True)

        startup_controls: list[ft.Control] = [self._start_with_windows, self._start_hidden, self._startup_info]
        if not IS_WINDOWS:
            startup_controls = [muted_text("Disponible uniquement sous Windows.")]

        self.control = panel(
            title="Réglages",
            content=ft.Column(
                expand=True,
                spacing=14,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    group(
                        title="Ce poste sur le réseau",
                        icon=ft.Icons.LAN_OUTLINED,
                        description="Les autres postes doivent utiliser le même port de découverte. Pense à autoriser ces ports dans le pare-feu Windows (réseau privé).",
                        controls=[
                            ft.Row(spacing=12, vertical_alignment=ft.CrossAxisAlignment.START, controls=[self._node_name]),
                            ft.Row(
                                spacing=12,
                                wrap=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[self._api_port, self._discovery_port, self._apply_ports],
                            ),
                            self._network_status,
                        ],
                    ),
                    group(
                        title="Home Assistant",
                        icon=ft.Icons.HOME_OUTLINED,
                        description="Utilisé par les étapes « Home Assistant ». Enregistré automatiquement quand tu quittes un champ.",
                        controls=[
                            self._ha_url,
                            self._ha_token,
                            ft.Row(spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[self._ha_test, self._ha_result]),
                        ],
                    ),
                    group(title="Démarrage", icon=ft.Icons.ROCKET_LAUNCH_OUTLINED, controls=startup_controls),
                    group(title="Quand je ferme la fenêtre", icon=ft.Icons.CLOSE_FULLSCREEN, controls=[self._close_action]),
                    group(
                        title="À propos",
                        icon=ft.Icons.INFO_OUTLINE,
                        controls=[
                            ft.Text(f"Py Network Launcher {__version__}", weight=ft.FontWeight.W_600),
                            ft.Row(
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    muted_text(f"Configuration : {window.store.path}", selectable=True, expand=True),
                                    ft.TextButton("Ouvrir le dossier", icon=ft.Icons.FOLDER_OPEN, on_click=lambda _: self.window.open_data_folder()),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        )
        self.refresh()

    # --- Rafraîchissement -----------------------------------------------------------------

    def refresh(self) -> None:
        self.refresh_network()
        settings = self.window.config.settings
        self._start_hidden.disabled = not settings.start_with_windows
        self._startup_info.value = (
            f"Entrée de démarrage : {startup_entry_label()}" if settings.start_with_windows else "Le démarrage automatique est désactivé."
        )

    def refresh_network(self) -> None:
        status = self.window.service.network_status()
        if status.ok:
            addresses = ", ".join(status.addresses) or "adresse IP inconnue"
            self._network_status.value = f"● Actif — API sur le port {status.api_port}, découverte sur le port {status.discovery_port} ({addresses})"
            self._network_status.color = COLOR_SUCCESS
        else:
            self._network_status.value = "● " + " · ".join(message for message in (status.api_error, status.discovery_error) if message)
            self._network_status.color = COLOR_ERROR
        self._update_apply_button()

    # --- Réseau ---------------------------------------------------------------------------

    def _save_node_name(self, _: Any = None) -> None:
        name = str(self._node_name.value or "").strip()
        if not name:
            self._node_name.value = self.window.config.settings.node_name
            return
        if name == self.window.config.settings.node_name:
            return
        self.window.config.settings.node_name = name
        self.window.save_now()
        self.window.service.announce_now()
        self.window.notify("Nom du poste mis à jour")

    def _on_ports_change(self, _: Any = None) -> None:
        for field in (self._api_port, self._discovery_port):
            field.error = None if _parse_port(field.value) is not None else "Port entre 1 et 65535"
        if _parse_port(self._api_port.value) is not None and _parse_port(self._api_port.value) == _parse_port(self._discovery_port.value):
            self._discovery_port.error = "Doit différer du port API"
        self._update_apply_button()

    def _update_apply_button(self) -> None:
        settings = self.window.config.settings
        api, discovery = _parse_port(self._api_port.value), _parse_port(self._discovery_port.value)
        valid = api is not None and discovery is not None and api != discovery
        changed = (api, discovery) != (settings.api_port, settings.discovery_port)
        failed = not self.window.service.network_status().ok
        self._apply_ports.disabled = not valid or not (changed or failed)
        self._apply_ports.content = "Appliquer" if changed or not failed else "Réessayer"

    async def _apply_ports_click(self, _: Any = None) -> None:
        api, discovery = _parse_port(self._api_port.value), _parse_port(self._discovery_port.value)
        if api is None or discovery is None:
            return
        self._apply_ports.disabled = True
        self._network_status.value, self._network_status.color = "Redémarrage du service réseau…", COLOR_MUTED
        self.window.page.update()
        await self.window.apply_network_settings(api, discovery)
        self.refresh_network()

    # --- Home Assistant -------------------------------------------------------------------

    def _home_assistant_values(self) -> tuple[str, str]:
        url = normalize_url(str(self._ha_url.value or "")).rstrip("/") if str(self._ha_url.value or "").strip() else ""
        return url, str(self._ha_token.value or "").strip()

    def _save_home_assistant(self, _: Any = None) -> None:
        settings = self.window.config.settings
        url, token = self._home_assistant_values()
        if (url, token) == (settings.home_assistant_url, settings.home_assistant_token):
            return
        settings.home_assistant_url, settings.home_assistant_token = url, token
        self._ha_url.value = url
        self._ha_result.value = ""
        self.window.save_now()
        self.window.notify("Réglages Home Assistant enregistrés")

    async def _test_home_assistant(self, _: Any = None) -> None:
        self._save_home_assistant()
        url, token = self._home_assistant_values()
        self._ha_test.disabled = True
        self._ha_result.value, self._ha_result.color = "Test en cours…", COLOR_MUTED
        self.window.page.update()
        try:
            message = await asyncio.to_thread(check_home_assistant, url, token)
            self._ha_result.value, self._ha_result.color = f"✓ {message}", COLOR_SUCCESS
        except Exception as exc:
            self._ha_result.value, self._ha_result.color = f"✗ {exc}", COLOR_ERROR
        finally:
            self._ha_test.disabled = False

    # --- Démarrage et fermeture -----------------------------------------------------------

    def _on_startup_change(self, _: Any = None) -> None:
        enabled = bool(self._start_with_windows.value)
        hidden = enabled and bool(self._start_hidden.value)
        if not self.window.set_startup(enabled, hidden):
            # Échec (registre) : les interrupteurs reflètent l'état réel, pas le clic.
            settings = self.window.config.settings
            enabled, hidden = settings.start_with_windows, settings.start_minimized
        self._start_with_windows.value, self._start_hidden.value = enabled, hidden
        self.refresh()

    def _on_close_action_change(self, event: Any) -> None:
        value = str(event.control.value or "")
        if value in CLOSE_ACTION_LABELS:
            self.window.config.settings.close_action = value
            self.window.save_now()
