from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Optional


BEACON_TYPE = "py-network-launcher-beacon"
BEACON_VERSION = 1


@dataclass(slots=True, frozen=True)
class DiscoveryRecord:
    node_id: str
    name: str
    host: str
    port: int
    version: int
    last_seen: float = field(default_factory=time.monotonic)


class DiscoveryBeacon:
    def __init__(
        self,
        *,
        node_id: str,
        node_name: str,
        api_port: int,
        discovery_port: int,
        interval_s: float,
        logger: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._node_id = node_id
        self._node_name = node_name
        self._api_port = api_port
        self._discovery_port = discovery_port
        self._interval_s = interval_s
        self._logger = logger
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="network-launcher-beacon", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    def _payload(self) -> bytes:
        data = {
            "type": BEACON_TYPE,
            "version": BEACON_VERSION,
            "node_id": self._node_id,
            "name": self._node_name,
            "port": self._api_port,
        }
        return json.dumps(data, ensure_ascii=False).encode("utf-8")

    def _run(self) -> None:
        sock: Optional[socket.socket] = None
        send_error_logged = False
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            payload = self._payload()
            while not self._stop.is_set():
                try:
                    sock.sendto(payload, ("255.255.255.255", self._discovery_port))
                    send_error_logged = False
                except OSError as exc:
                    if not send_error_logged and self._logger is not None:
                        self._logger(f"Beacon UDP indisponible: {exc}")
                    send_error_logged = True
                self._stop.wait(self._interval_s)
        except OSError as exc:
            if self._logger is not None:
                self._logger(f"Impossible d'initialiser le beacon UDP: {exc}")
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass


class DiscoveryListener:
    def __init__(
        self,
        *,
        discovery_port: int,
        expiry_s: float,
        on_record: Optional[Callable[[DiscoveryRecord], None]] = None,
        logger: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._discovery_port = discovery_port
        self._expiry_s = expiry_s
        self._on_record = on_record
        self._logger = logger
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._records: dict[str, DiscoveryRecord] = {}

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="network-launcher-listener", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        with self._lock:
            self._records.clear()

    def records(self) -> dict[str, DiscoveryRecord]:
        with self._lock:
            self._purge_locked()
            return dict(self._records)

    def _purge_locked(self) -> None:
        now = time.monotonic()
        expired = [key for key, value in self._records.items() if now - value.last_seen > self._expiry_s]
        for key in expired:
            self._records.pop(key, None)

    def _run(self) -> None:
        sock: Optional[socket.socket] = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except (AttributeError, OSError):
                pass
            sock.bind(("", self._discovery_port))
            sock.settimeout(1.0)
            while not self._stop.is_set():
                try:
                    payload, address = sock.recvfrom(4096)
                except socket.timeout:
                    with self._lock:
                        self._purge_locked()
                    continue
                except OSError:
                    if self._stop.is_set():
                        break
                    continue
                record = self._parse_payload(payload, address[0])
                if record is None:
                    continue
                with self._lock:
                    self._records[record.node_id] = record
                    self._purge_locked()
                if self._on_record is not None:
                    try:
                        self._on_record(record)
                    except Exception as exc:
                        if self._logger is not None:
                            self._logger(f"Erreur lors du traitement d'un pair découvert: {exc}")
        except OSError as exc:
            if self._logger is not None:
                self._logger(f"Impossible d'initialiser l'écoute UDP: {exc}")
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass

    def _parse_payload(self, payload: bytes, host: str) -> Optional[DiscoveryRecord]:
        try:
            data = json.loads(payload.decode("utf-8"))
        except Exception:
            return None
        if not isinstance(data, dict) or data.get("type") != BEACON_TYPE:
            return None
        node_id = str(data.get("node_id") or "").strip()
        if not node_id:
            return None
        try:
            port = int(data.get("port", 0))
        except Exception:
            return None
        if port <= 0:
            return None
        return DiscoveryRecord(
            node_id=node_id,
            name=str(data.get("name") or host),
            host=host,
            port=port,
            version=int(data.get("version", 1)),
            last_seen=time.monotonic(),
        )
