from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from discovery import DiscoveryBeacon, DiscoveryListener, DiscoveryRecord
from executor import SequenceExecutor
from models import ActionStep, AppConfig, LaunchSequence, PeerInfo, PeerSequenceSummary
from storage import save_config


class LauncherService:
    def __init__(self, config: AppConfig, *, on_peers_updated: Optional[Callable[[], None]] = None) -> None:
        self.config = config
        self._lock = threading.RLock()
        self._peers: dict[str, PeerInfo] = {}
        self._logs: list[str] = []
        self._http_server: Optional[ThreadingHTTPServer] = None
        self._http_thread: Optional[threading.Thread] = None
        self._refresh_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._on_peers_updated = on_peers_updated
        self._beacon = DiscoveryBeacon(
            node_id=self.config.settings.node_id,
            node_name=self.config.settings.node_name,
            api_port=self.config.settings.api_port,
            discovery_port=self.config.settings.discovery_port,
            interval_s=self.config.settings.discovery_interval_s,
            logger=self.log,
        )
        self._listener = DiscoveryListener(
            discovery_port=self.config.settings.discovery_port,
            expiry_s=self.config.settings.peer_expiry_s,
            on_record=self._on_discovery_record,
            logger=self.log,
        )
        self._executor = SequenceExecutor(
            remote_runner=self.run_remote_sequence,
            home_assistant_config_provider=lambda: (self.config.settings.home_assistant_url, self.config.settings.home_assistant_token),
            logger=self.log,
        )

    def start(self) -> None:
        self._stop.clear()
        self._start_http_server()
        self._listener.start()
        self._beacon.start()
        self._refresh_thread = threading.Thread(target=self._refresh_peers_loop, name="peer-refresh", daemon=True)
        self._refresh_thread.start()
        self.log("Service réseau démarré")

    def stop(self) -> None:
        self._stop.set()
        self._beacon.stop()
        self._listener.stop()
        if self._http_server is not None:
            try:
                self._http_server.shutdown()
                self._http_server.server_close()
            except Exception as exc:
                self.log(f"Arrêt du serveur HTTP incomplet: {exc}")
        if self._http_thread is not None and self._http_thread.is_alive():
            self._http_thread.join(timeout=2.0)
        if self._refresh_thread is not None and self._refresh_thread.is_alive():
            self._refresh_thread.join(timeout=2.0)
        self._http_server = None
        self._http_thread = None
        self._refresh_thread = None
        self.log("Service réseau arrêté")

    def log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        with self._lock:
            self._logs.append(line)
            if len(self._logs) > 300:
                self._logs = self._logs[-300:]

    def logs(self) -> list[str]:
        with self._lock:
            return list(self._logs)

    def get_sequences(self) -> list[LaunchSequence]:
        return list(self.config.sequences)

    def get_sequence(self, sequence_id: str) -> Optional[LaunchSequence]:
        for sequence in self.config.sequences:
            if sequence.id == sequence_id:
                return sequence
        return None

    def save(self) -> None:
        save_config(self.config)

    def get_peers(self) -> list[PeerInfo]:
        with self._lock:
            self._purge_peers_locked()
            return sorted(self._peers.values(), key=lambda peer: (peer.name.lower(), peer.host, peer.port))

    def run_local_sequence(self, sequence_id: str, source: str = "manual") -> None:
        sequence = self.get_sequence(sequence_id)
        if sequence is None:
            raise ValueError("Séquence introuvable")
        self._executor.run_sequence(sequence.clone(), source=source)

    def run_local_step(self, step: ActionStep, source: str = "manual_step") -> None:
        self._executor.run_step(step.clone(), source=source)

    def run_remote_sequence(self, peer_id: str, sequence_id: str) -> None:
        peer = self._resolve_peer(peer_id=peer_id)
        if peer is None:
            raise ValueError("Poste distant introuvable")
        url = f"http://{peer.host}:{peer.port}/api/run-sequence"
        payload = json.dumps({"sequence_id": sequence_id}).encode("utf-8")
        request = urllib.request.Request(url, data=payload, method="POST")
        request.add_header("Content-Type", "application/json; charset=utf-8")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                status = getattr(response, "status", 200)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Lancement distant refusé ({exc.code})") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Poste distant inaccessible: {exc.reason}") from exc
        self.log(f"Séquence distante '{sequence_id}' lancée sur {peer.name} ({status})")

    def launch_trigger_sequences(self) -> None:
        for sequence in list(self.config.sequences):
            if sequence.run_on_app_start:
                self._executor.run_sequence(sequence.clone(), source="app_start")

    def _start_http_server(self) -> None:
        service = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path == "/api/status":
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "node_id": service.config.settings.node_id,
                            "node_name": service.config.settings.node_name,
                            "version": 1,
                        },
                    )
                    return
                if self.path == "/api/sequences":
                    items = [
                        {"id": sequence.id, "name": sequence.name}
                        for sequence in service.config.sequences
                    ]
                    self._send_json(HTTPStatus.OK, items)
                    return
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

            def do_POST(self) -> None:
                if self.path != "/api/run-sequence":
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                    return
                payload = self._read_json_body()
                sequence_id = ""
                if isinstance(payload, dict):
                    sequence_id = str(payload.get("sequence_id") or "").strip()
                if not sequence_id:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "sequence_id_required"})
                    return
                try:
                    service.run_local_sequence(sequence_id, source="remote")
                except Exception as exc:
                    service.log(f"Lancement distant refusé pour '{sequence_id}': {exc}")
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                    return
                self._send_json(HTTPStatus.OK, {"ok": True})

            def log_message(self, format: str, *args) -> None:
                return

            def _read_json_body(self):
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                except Exception:
                    size = 0
                raw = self.rfile.read(size) if size > 0 else b""
                if not raw:
                    return {}
                try:
                    return json.loads(raw.decode("utf-8"))
                except Exception:
                    return {}

            def _send_json(self, status: HTTPStatus, payload) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(int(status))
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._http_server = ThreadingHTTPServer(("0.0.0.0", self.config.settings.api_port), Handler)
        self._http_thread = threading.Thread(target=self._http_server.serve_forever, name="launcher-http", daemon=True)
        self._http_thread.start()

    def _on_discovery_record(self, record: DiscoveryRecord) -> None:
        if record.node_id == self.config.settings.node_id:
            return
        changed = False
        with self._lock:
            existing = self._peers.get(record.node_id)
            sequences = existing.sequences if existing is not None else []
            changed = existing is None or any(
                [
                    existing.name != record.name,
                    existing.host != record.host,
                    existing.port != record.port,
                    existing.version != record.version,
                ]
            )
            self._peers[record.node_id] = PeerInfo(
                node_id=record.node_id,
                name=record.name,
                host=record.host,
                port=record.port,
                version=record.version,
                last_seen=record.last_seen,
                sequences=list(sequences),
            )
        if changed:
            self._notify_peers_updated()

    def _purge_peers_locked(self) -> None:
        now = time.monotonic()
        expired = [
            peer_id
            for peer_id, peer in self._peers.items()
            if now - float(peer.last_seen) > float(self.config.settings.peer_expiry_s)
        ]
        for peer_id in expired:
            self._peers.pop(peer_id, None)

    def _refresh_peers_loop(self) -> None:
        while not self._stop.wait(self.config.settings.peer_refresh_interval_s):
            peers = self.get_peers()
            for peer in peers:
                sequences = self._fetch_peer_sequences(peer)
                if sequences is None:
                    continue
                changed = False
                with self._lock:
                    current = self._peers.get(peer.node_id)
                    if current is not None:
                        changed = [(item.id, item.name) for item in current.sequences] != [(item.id, item.name) for item in sequences]
                        current.sequences = sequences
                if changed:
                    self._notify_peers_updated()

    def _fetch_peer_sequences(self, peer: PeerInfo) -> Optional[list[PeerSequenceSummary]]:
        url = f"http://{peer.host}:{peer.port}/api/sequences"
        request = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            self.log(f"Impossible de récupérer les séquences de {peer.name}: {exc}")
            return None
        if not isinstance(payload, list):
            self.log(f"Réponse de séquences invalide reçue depuis {peer.name}")
            return None
        items: list[PeerSequenceSummary] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            sequence_id = str(item.get("id") or "").strip()
            if not sequence_id:
                continue
            items.append(PeerSequenceSummary(id=sequence_id, name=str(item.get("name") or sequence_id)))
        return items

    def _resolve_peer(self, *, peer_id: str) -> Optional[PeerInfo]:
        peers = self.get_peers()
        if peer_id:
            for peer in peers:
                if peer.node_id == peer_id:
                    return peer
        return None

    def _notify_peers_updated(self) -> None:
        if self._on_peers_updated is None:
            return
        try:
            self._on_peers_updated()
        except Exception:
            return
