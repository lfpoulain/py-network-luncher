from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional

from py_network_launcher.logs import get_logger
from py_network_launcher.network import send_broadcast

BEACON_TYPE = "py-network-launcher-beacon"
PROTOCOL_VERSION = 1
MAX_DATAGRAM_SIZE = 4096

logger = get_logger("discovery")


@dataclass(slots=True, frozen=True)
class DiscoveryRecord:
    node_id: str
    name: str
    host: str
    port: int
    version: int = PROTOCOL_VERSION
    app_version: str = ""
    last_seen: float = field(default_factory=time.monotonic)


def build_beacon(*, node_id: str, node_name: str, api_port: int, app_version: str) -> bytes:
    data = {
        "type": BEACON_TYPE,
        "version": PROTOCOL_VERSION,
        "node_id": node_id,
        "name": node_name,
        "port": api_port,
        "app_version": app_version,
    }
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def parse_beacon(payload: bytes, host: str) -> Optional[DiscoveryRecord]:
    """Décode un beacon UDP ; renvoie None pour tout paquet invalide ou étranger."""
    try:
        data: Any = json.loads(payload.decode("utf-8"))
        if not isinstance(data, dict) or data.get("type") != BEACON_TYPE:
            return None
        node_id = str(data.get("node_id") or "").strip()
        port = int(data.get("port", 0))
        version = int(data.get("version", PROTOCOL_VERSION))
    except (UnicodeDecodeError, ValueError, TypeError):
        return None
    if not node_id or not 1 <= port <= 65535:
        return None
    return DiscoveryRecord(
        node_id=node_id,
        name=str(data.get("name") or host).strip() or host,
        host=host,
        port=port,
        version=version,
        app_version=str(data.get("app_version") or ""),
    )


class DiscoveryBeacon:
    """Annonce périodiquement la présence du poste sur le LAN."""

    def __init__(self, *, port: int, interval_s: float, payload_provider: Callable[[], bytes]) -> None:
        self._port = port
        self._interval_s = interval_s
        self._payload_provider = payload_provider
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="discovery-beacon", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    def announce_now(self) -> None:
        self._wake.set()

    def _run(self) -> None:
        error_logged = False
        while not self._stop.is_set():
            error = send_broadcast(self._payload_provider(), self._port)
            if error is not None and not error_logged:
                logger.warning(f"Annonce UDP impossible: {error}")
            error_logged = error is not None
            self._wake.wait(self._interval_s)
            self._wake.clear()


class DiscoveryListener:
    """Écoute les beacons des autres postes. Le port est ouvert dès `start()` pour remonter les erreurs."""

    def __init__(self, *, port: int, on_record: Callable[[DiscoveryRecord], None]) -> None:
        self._port = port
        self._on_record = on_record
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._sock: Optional[socket.socket] = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", self._port))
            sock.settimeout(1.0)
        except OSError:
            sock.close()
            raise
        self._sock = sock
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="discovery-listener", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def _run(self) -> None:
        sock = self._sock
        assert sock is not None
        while not self._stop.is_set():
            try:
                payload, address = sock.recvfrom(MAX_DATAGRAM_SIZE)
            except TimeoutError:
                continue
            except OSError:
                if self._stop.is_set():
                    break
                time.sleep(0.5)
                continue
            record = parse_beacon(payload, address[0])
            if record is None:
                continue
            try:
                self._on_record(record)
            except Exception as exc:
                logger.error(f"Erreur lors du traitement d'un poste découvert: {exc}")
