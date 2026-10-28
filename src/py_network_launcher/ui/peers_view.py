"""Vue « Postes » : machines découvertes sur le LAN et leurs séquences."""

from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from py_network_launcher.models import PeerInfo
from py_network_launcher.ui.widgets import COLOR_ERROR, COLOR_SUCCESS, RADIUS, badge, empty_state, muted_text, panel

if TYPE_CHECKING:
    from py_network_launcher.ui.window import MainWindow


class PeersView:
    def __init__(self, window: MainWindow) -> None:
        self.window = window
        self._grid = ft.ResponsiveRow(spacing=12, run_spacing=12)
        self._this_host = muted_text("", selectable=True)
        self.control = panel(
            title="Postes du réseau",
            subtitle="Machines où Py Network Launcher est ouvert. Leurs séquences peuvent être lancées d'ici ou depuis une étape « Séquence distante ».",
            actions=[ft.IconButton(icon=ft.Icons.SYNC_ROUNDED, tooltip="Relancer la détection", on_click=lambda _: self.window.service.announce_now())],
            content=ft.Column(
                expand=True,
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
                controls=[self._this_host, self._grid],
            ),
        )
        self.refresh()

    def refresh(self) -> None:
        status = self.window.service.network_status()
        addresses = ", ".join(f"{address}:{status.api_port}" for address in status.addresses) or "adresse inconnue"
        self._this_host.value = f"Ce poste : {self.window.config.settings.node_name} — {addresses}"
        peers = self.window.service.peers()
        if not peers:
            self._grid.controls = [
                ft.Container(
                    col=12,
                    content=empty_state(
                        icon=ft.Icons.DEVICES_OTHER,
                        title="Aucun autre poste détecté",
                        message=(
                            "Lance l'application sur un autre PC du même réseau. S'il n'apparaît pas : "
                            "vérifie que le réseau Windows est en mode « Privé », que le pare-feu autorise "
                            "l'application et que les ports de découverte sont identiques des deux côtés."
                        ),
                    ),
                )
            ]
            return
        self._grid.controls = [self._peer_card(peer) for peer in peers]

    def _peer_card(self, peer: PeerInfo) -> ft.Control:
        if not peer.reachable:
            status = badge(
                "API injoignable",
                color=COLOR_ERROR,
                icon=ft.Icons.WIFI_TETHERING_ERROR,
                tooltip="Le poste est visible mais son API HTTP ne répond pas (pare-feu ?)",
            )
        else:
            status = badge("En ligne", color=COLOR_SUCCESS, icon=ft.Icons.CIRCLE)
        if not peer.sequences_loaded:
            sequences: list[ft.Control] = [muted_text("Chargement des séquences…" if peer.reachable else "Séquences indisponibles")]
        elif not peer.sequences:
            sequences = [muted_text("Aucune séquence publiée")]
        else:
            sequences = [
                ft.Container(
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    border_radius=10,
                    padding=ft.Padding.only(left=12, right=4, top=2, bottom=2),
                    content=ft.Row(
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text(item.name, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.IconButton(
                                icon=ft.Icons.PLAY_ARROW_ROUNDED,
                                icon_color=ft.Colors.PRIMARY,
                                tooltip=f"Lancer « {item.name} » sur {peer.name}",
                                on_click=lambda _, sid=item.id: self.window.run_remote(peer.node_id, sid),
                            ),
                        ],
                    ),
                )
                for item in peer.sequences
            ]
        version = f" · v{peer.app_version}" if peer.app_version else ""
        return ft.Container(
            col={"xs": 12, "md": 6, "xl": 4},
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            border_radius=RADIUS,
            padding=16,
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.COMPUTER, color=ft.Colors.PRIMARY),
                            ft.Text(peer.name, size=16, weight=ft.FontWeight.W_600, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            status,
                        ],
                    ),
                    muted_text(f"{peer.address}{version}", selectable=True),
                    *sequences,
                ],
            ),
        )
