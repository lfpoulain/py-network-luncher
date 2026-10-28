"""Service réseau : API HTTP locale, découverte des postes et suivi des exécutions."""

from __future__ import annotations

import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, replace
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from py_network_launcher import __version__
from py_network_launcher.actions import StopToken
from py_network_launcher.discovery import DiscoveryBeacon, DiscoveryListener, DiscoveryRecord, build_beacon
from py_network_launcher.executor import SequenceExecutor
from py_network_launcher.logs import get_logger
from py_network_launcher.models import (
    TRIGGER_APP_START,
    TRIGGER_ONCE_PER_SESSION,
    ActionStep,
    AppConfig,
    LaunchSequence,
    PeerInfo,
    PeerSequenceSummary,
)
from py_network_launcher.network import local_ipv4_addresses
from py_network_launcher.storage import ConfigStore
from py_network_launcher.windows import current_session_id

RUN_RUNNING = "running"
MAX_REQUEST_BODY = 64 * 1024

logger = get_logger("service")


class _ApiServer(ThreadingHTTPServer):
    """Serveur HTTP qui refuse de partager son port.

    `HTTPServer` active SO_REUSEADDR, ce qui sous Windows laisse un second processus
    écouter le même port sans erreur : on veut au contraire détecter le conflit.
    """

    daemon_threads = True
    allow_reuse_address = os.name != "nt"

    def server_bind(self) -> None:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class ServiceListener:
    """Notifications émises par le service (depuis des threads de fond)."""

    def peers_changed(self) -> None: ...

    def run_state_changed(self, sequence_id: str) -> None: ...

    def run_finished(self, sequence_id: str, outcome: str, error: Optional[str]) -> None: ...

    def network_state_changed(self) -> None: ...

    def show_window_requested(self) -> None: ...


@dataclass
class RunState:
    status: str
    source: str = ""
    active_step_id: str = ""
    done_step_ids: set[str] = field(default_factory=set)
    failed_steps: dict[str, str] = field(default_factory=dict)
    error: str = ""
    finished_at: Optional[float] = None

    @property
    def is_running(self) -> bool:
        return self.status == RUN_RUNNING


@dataclass(frozen=True)
class NetworkStatus:
    api_port: int
    discovery_port: int
    api_error: str = ""
    discovery_error: str = ""
    addresses: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.api_error and not self.discovery_error


class LauncherService:
    def __init__(self, config: AppConfig, store: ConfigStore, listener: Optional[ServiceListener] = None) -> None:
        self.config = config
        self.store = store
        self.listener = listener or ServiceListener()
        self._lock = threading.RLock()
        self._peers: dict[str, PeerInfo] = {}
        self._run_states: dict[str, RunState] = {}
        self._http_server: Optional[_ApiServer] = None
        self._beacon: Optional[DiscoveryBeacon] = None
        self._discovery: Optional[DiscoveryListener] = None
        self._refresh_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._network_status = NetworkStatus(config.settings.api_port, config.settings.discovery_port)
        self.executor = SequenceExecutor(
            resolve_sequence=self.config.find_sequence,
            run_remote=self._run_remote_step,
            home_assistant_settings=lambda: (self.config.settings.home_assistant_url, self.config.settings.home_assistant_token),
            listener=self,
        )

    # --- Cycle de vie ---------------------------------------------------------------------

    def start(self) -> None:
        self._stop.clear()
        self._start_network()
        self._refresh_thread = threading.Thread(target=self._refresh_loop, name="peer-refresh", daemon=True)
        self._refresh_thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.executor.stop_all()
        self._stop_network()
        if self._refresh_thread is not None and self._refresh_thread.is_alive():
            self._refresh_thread.join(timeout=2.0)
        self._refresh_thread = None

    def restart_network(self) -> NetworkStatus:
        """Applique de nouveaux ports sans interrompre les séquences en cours."""
        self._stop_network()
        with self._lock:
            self._peers.clear()
        self.listener.peers_changed()
        self._start_network()
        return self._network_status

    def network_status(self) -> NetworkStatus:
        return self._network_status

    def announce_now(self) -> None:
        if self._beacon is not None:
            self._beacon.announce_now()

    def _start_network(self) -> None:
        settings = self.config.settings
        api_error = discovery_error = ""
        try:
            self._http_server = _ApiServer(("0.0.0.0", settings.api_port), _make_handler(self))
            threading.Thread(target=self._http_server.serve_forever, name="api-http", daemon=True).start()
        except OSError as exc:
            self._http_server = None
            api_error = f"Port API {settings.api_port} indisponible ({_os_error_text(exc)})"
            logger.error(api_error)
        try:
            self._discovery = DiscoveryListener(port=settings.discovery_port, on_record=self._on_discovery_record)
            self._discovery.start()
        except OSError as exc:
            self._discovery = None
            discovery_error = f"Port de découverte {settings.discovery_port} indisponible ({_os_error_text(exc)})"
            logger.error(discovery_error)
        self._beacon = DiscoveryBeacon(port=settings.discovery_port, interval_s=settings.discovery_interval_s, payload_provider=self._beacon_payload)
        self._beacon.start()
        self._network_status = NetworkStatus(
            api_port=settings.api_port,
            discovery_port=settings.discovery_port,
            api_error=api_error,
            discovery_error=discovery_error,
            addresses=tuple(local_ipv4_addresses(max_age_s=0)),
        )
        if self._network_status.ok:
            logger.info(f"Service réseau actif (API {settings.api_port}, découverte {settings.discovery_port})")
        self.listener.network_state_changed()

    def _stop_network(self) -> None:
        if self._beacon is not None:
            self._beacon.stop()
            self._beacon = None
        if self._discovery is not None:
            self._discovery.stop()
            self._discovery = None
        if self._http_server is not None:
            try:
                self._http_server.shutdown()
                self._http_server.server_close()
            except Exception as exc:
                logger.warning(f"Arrêt du serveur HTTP incomplet: {exc}")
            self._http_server = None

    def _beacon_payload(self) -> bytes:
        settings = self.config.settings
        return build_beacon(node_id=settings.node_id, node_name=settings.node_name, api_port=settings.api_port, app_version=__version__)

    # --- Séquences ------------------------------------------------------------------------

    def start_sequence(self, sequence_id: str, source: str = "manuel") -> bool:
        return self.executor.start_sequence(sequence_id, source)

    def stop_sequence(self, sequence_id: str) -> bool:
        stopped = self.executor.stop_sequence(sequence_id)
        if stopped:
            logger.info("Arrêt demandé")
        return stopped

    def is_running(self, sequence_id: str) -> bool:
        return self.executor.is_running(sequence_id)

    def run_state(self, sequence_id: str) -> Optional[RunState]:
        with self._lock:
            state = self._run_states.get(sequence_id)
            if state is None:
                return None
            return replace(state, done_step_ids=set(state.done_step_ids), failed_steps=dict(state.failed_steps))

    def clear_run_state(self, sequence_id: str) -> None:
        with self._lock:
            state = self._run_states.get(sequence_id)
            if state is not None and not state.is_running:
                del self._run_states[sequence_id]

    def launch_startup_sequences(self) -> None:
        session_id = current_session_id()
        changed = False
        for sequence in list(self.config.sequences):
            source = ""
            if sequence.trigger == TRIGGER_APP_START:
                source = "démarrage de l'application"
            elif sequence.trigger == TRIGGER_ONCE_PER_SESSION and sequence.last_session_id != session_id:
                sequence.last_session_id = session_id
                changed = True
                source = "ouverture de session"
            if source:
                self.executor.start_sequence(sequence.id, source)
        if changed:
            try:
                self.store.save(self.config)
            except RuntimeError as exc:
                logger.error(str(exc))

    # Callbacks de l'exécuteur (threads de fond)

    def run_started(self, sequence_id: str, source: str) -> None:
        with self._lock:
            self._run_states[sequence_id] = RunState(status=RUN_RUNNING, source=source)
        self.listener.run_state_changed(sequence_id)

    def step_started(self, sequence_id: str, step_id: str) -> None:
        with self._lock:
            state = self._run_states.get(sequence_id)
            if state is not None:
                state.active_step_id = step_id
        self.listener.run_state_changed(sequence_id)

    def step_finished(self, sequence_id: str, step_id: str, error: Optional[str]) -> None:
        with self._lock:
            state = self._run_states.get(sequence_id)
            if state is not None:
                if error is None:
                    state.done_step_ids.add(step_id)
                else:
                    state.failed_steps[step_id] = error
                if state.active_step_id == step_id:
                    state.active_step_id = ""
        self.listener.run_state_changed(sequence_id)

    def run_finished(self, sequence_id: str, outcome: str, error: Optional[str]) -> None:
        with self._lock:
            state = self._run_states.setdefault(sequence_id, RunState(status=outcome))
            state.status = outcome
            state.active_step_id = ""
            state.error = error or ""
            state.finished_at = time.time()
        self.listener.run_state_changed(sequence_id)
        self.listener.run_finished(sequence_id, outcome, error)

    # --- Postes distants ------------------------------------------------------------------

    def peers(self) -> list[PeerInfo]:
        with self._lock:
            return sorted((replace(peer, sequences=list(peer.sequences)) for peer in self._peers.values()), key=lambda peer: (peer.name.lower(), peer.host))

    def find_peer(self, node_id: str) -> Optional[PeerInfo]:
        with self._lock:
            peer = self._peers.get(node_id)
            return replace(peer, sequences=list(peer.sequences)) if peer is not None else None

    def run_remote_sequence(self, peer: PeerInfo, sequence_id: str) -> None:
        url = f"http://{peer.host}:{peer.port}/api/run-sequence"
        request = urllib.request.Request(url, data=json.dumps({"sequence_id": sequence_id}).encode("utf-8"), method="POST")
        request.add_header("Content-Type", "application/json; charset=utf-8")
        try:
            with urllib.request.urlopen(request, timeout=10):
                pass
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{peer.name} a refusé le lancement: {_remote_error(exc)}") from exc
        except (urllib.error.URLError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise RuntimeError(f"{peer.name} injoignable ({peer.address}): {reason}") from exc
        name = next((item.name for item in peer.sequences if item.id == sequence_id), sequence_id)
        logger.info(f"Séquence « {name} » lancée sur {peer.name}")

    def _run_remote_step(self, step: ActionStep, stop: StopToken) -> None:
        peer_id = step.remote_peer_id.strip()
        sequence_id = step.remote_sequence_id.strip()
        if not peer_id:
            raise ValueError("Aucun poste distant sélectionné")
        if not sequence_id:
            raise ValueError("Aucune séquence distante sélectionnée")
        peer = self.find_peer(peer_id)
        if peer is None:
            # Le poste vient peut-être d'être réveillé (Wake-on-LAN) : on lui laisse le temps d'apparaître.
            label = step.remote_peer_name or peer_id
            logger.info(f"En attente du poste « {label} » (jusqu'à {step.wait_timeout_s:g} s)")
            deadline = time.monotonic() + step.wait_timeout_s
            while peer is None and time.monotonic() < deadline:
                stop.sleep(0.5)
                peer = self.find_peer(peer_id)
            if peer is None:
                raise RuntimeError(f"Poste « {label} » introuvable sur le réseau")
        self.run_remote_sequence(peer, sequence_id)

    def _on_discovery_record(self, record: DiscoveryRecord) -> None:
        if record.node_id == self.config.settings.node_id:
            return
        with self._lock:
            existing = self._peers.get(record.node_id)
            is_new = existing is None
            changed = is_new or (existing.name, existing.host, existing.port) != (record.name, record.host, record.port)
            if is_new:
                self._peers[record.node_id] = PeerInfo(
                    node_id=record.node_id,
                    name=record.name,
                    host=record.host,
                    port=record.port,
                    version=record.version,
                    app_version=record.app_version,
                    last_seen=record.last_seen,
                )
            else:
                existing.name, existing.host, existing.port = record.name, record.host, record.port
                existing.version, existing.app_version, existing.last_seen = record.version, record.app_version, record.last_seen
        if is_new:
            logger.info(f"Poste découvert : {record.name} ({record.host}:{record.port})")
            threading.Thread(target=self._refresh_peer_sequences, args=(record.node_id,), name="peer-fetch", daemon=True).start()
        if changed:
            self.listener.peers_changed()

    def _refresh_loop(self) -> None:
        while not self._stop.wait(self.config.settings.peer_refresh_interval_s):
            self._purge_expired_peers()
            with self._lock:
                peer_ids = list(self._peers)
            for peer_id in peer_ids:
                if self._stop.is_set():
                    return
                self._refresh_peer_sequences(peer_id)

    def _purge_expired_peers(self) -> None:
        now = time.monotonic()
        with self._lock:
            expired = [peer for peer in self._peers.values() if now - peer.last_seen > self.config.settings.peer_expiry_s]
            for peer in expired:
                del self._peers[peer.node_id]
        for peer in expired:
            logger.info(f"Poste hors ligne : {peer.name}")
        if expired:
            self.listener.peers_changed()

    def _refresh_peer_sequences(self, peer_id: str) -> None:
        peer = self.find_peer(peer_id)
        if peer is None:
            return
        sequences: Optional[list[PeerSequenceSummary]] = None
        error = ""
        try:
            with urllib.request.urlopen(f"http://{peer.host}:{peer.port}/api/sequences", timeout=5) as response:
                payload: Any = json.loads(response.read(MAX_REQUEST_BODY).decode("utf-8"))
            if not isinstance(payload, list):
                raise ValueError("réponse inattendue")
            sequences = [
                PeerSequenceSummary(id=str(item["id"]), name=str(item.get("name") or item["id"]))
                for item in payload
                if isinstance(item, dict) and str(item.get("id") or "").strip()
            ]
        except Exception as exc:
            error = str(getattr(exc, "reason", exc))
        changed = False
        with self._lock:
            current = self._peers.get(peer_id)
            if current is None:
                return
            if sequences is None:
                if current.reachable:
                    logger.warning(f"API de {current.name} injoignable ({current.address}): {error}. Vérifie le pare-feu.")
                    current.reachable = False
                    changed = True
            else:
                if not current.reachable:
                    logger.info(f"API de {current.name} de nouveau joignable")
                old = [(item.id, item.name) for item in current.sequences]
                changed = not current.reachable or not current.sequences_loaded or old != [(item.id, item.name) for item in sequences]
                current.sequences, current.sequences_loaded, current.reachable = sequences, True, True
        if changed:
            self.listener.peers_changed()


def _os_error_text(exc: OSError) -> str:
    if getattr(exc, "winerror", None) == 10048 or exc.errno in (98, 10048):
        return "déjà utilisé par un autre programme"
    if getattr(exc, "winerror", None) == 10013:
        return "accès refusé"
    return exc.strerror or str(exc)


def _remote_error(exc: urllib.error.HTTPError) -> str:
    try:
        payload = json.loads(exc.read(2000).decode("utf-8"))
        if isinstance(payload, dict) and payload.get("error"):
            return str(payload["error"])
    except Exception:
        pass
    return f"HTTP {exc.code}"


def _make_handler(service: LauncherService) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = f"PyNetworkLauncher/{__version__}"

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0].rstrip("/")
            settings = service.config.settings
            if path == "/api/status":
                self._send_json(HTTPStatus.OK, {"node_id": settings.node_id, "node_name": settings.node_name, "version": 1, "app_version": __version__})
            elif path == "/api/sequences":
                self._send_json(HTTPStatus.OK, [{"id": sequence.id, "name": sequence.name} for sequence in list(service.config.sequences)])
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0].rstrip("/")
            if path == "/api/show":
                if self.client_address[0] not in ("127.0.0.1", "::1"):
                    self._send_json(HTTPStatus.FORBIDDEN, {"error": "forbidden"})
                    return
                service.listener.show_window_requested()
                self._send_json(HTTPStatus.OK, {"ok": True})
                return
            if path != "/api/run-sequence":
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            payload = self._read_json_body()
            sequence_id = str(payload.get("sequence_id") or "").strip() if isinstance(payload, dict) else ""
            sequence: Optional[LaunchSequence] = service.config.find_sequence(sequence_id) if sequence_id else None
            if sequence is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Séquence introuvable"})
                return
            caller = self.client_address[0]
            if not service.start_sequence(sequence.id, source=f"demande de {caller}"):
                self._send_json(HTTPStatus.CONFLICT, {"error": f"« {sequence.name} » est déjà en cours"})
                return
            self._send_json(HTTPStatus.OK, {"ok": True})

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _read_json_body(self) -> Any:
            try:
                size = min(int(self.headers.get("Content-Length", "0")), MAX_REQUEST_BODY)
                raw = self.rfile.read(size) if size > 0 else b""
                return json.loads(raw.decode("utf-8")) if raw else {}
            except (ValueError, OSError):
                return {}

        def _send_json(self, status: HTTPStatus, payload: Any) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler
