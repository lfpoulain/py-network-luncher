import json
import socket
import time
import urllib.error
import urllib.request

import pytest

from py_network_launcher.discovery import build_beacon, parse_beacon
from py_network_launcher.models import ACTION_DELAY, ActionStep, AppConfig, AppSettings, LaunchSequence
from py_network_launcher.service import LauncherService
from py_network_launcher.storage import ConfigStore
from tests.conftest import free_port


def test_parse_beacon_round_trip_and_garbage() -> None:
    payload = build_beacon(node_id="node-1", node_name="PC", api_port=8765, app_version="1.2.3")
    record = parse_beacon(payload, "192.168.1.5")
    assert record is not None
    assert (record.node_id, record.name, record.host, record.port, record.app_version) == ("node-1", "PC", "192.168.1.5", 8765, "1.2.3")
    for garbage in (b"", b"\xff\xfe", b"[]", b'{"type": "autre"}', b'{"type": "py-network-launcher-beacon", "node_id": "x", "port": "abc"}'):
        assert parse_beacon(garbage, "1.2.3.4") is None
    assert parse_beacon(b'{"type": "py-network-launcher-beacon", "node_id": "x", "port": 8765, "version": "v2"}', "h") is None


@pytest.fixture
def service(tmp_path):
    sequence = LaunchSequence(id="sequence-demo", name="Démo", steps=[ActionStep(action_type=ACTION_DELAY, seconds=1)])
    config = AppConfig(
        settings=AppSettings(api_port=free_port(), discovery_port=free_port(socket.SOCK_DGRAM)),
        sequences=[sequence],
    )
    instance = LauncherService(config, ConfigStore(tmp_path / "config.json", legacy_path=None))
    instance.start()
    yield instance
    instance.stop()


def request(service: LauncherService, path: str, payload=None):
    url = f"http://127.0.0.1:{service.config.settings.api_port}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    with urllib.request.urlopen(urllib.request.Request(url, data=data, method="POST" if data else "GET"), timeout=5) as response:
        return response.status, json.loads(response.read())


def test_api_lists_and_runs_sequences(service: LauncherService) -> None:
    assert service.network_status().ok
    status, body = request(service, "/api/sequences")
    assert status == 200 and body == [{"id": "sequence-demo", "name": "Démo"}]
    status, body = request(service, "/api/status")
    assert body["node_id"] == service.config.settings.node_id

    status, body = request(service, "/api/run-sequence", {"sequence_id": "sequence-demo"})
    assert status == 200 and body == {"ok": True}
    with pytest.raises(urllib.error.HTTPError) as conflict:
        request(service, "/api/run-sequence", {"sequence_id": "sequence-demo"})
    assert conflict.value.code == 409
    with pytest.raises(urllib.error.HTTPError) as missing:
        request(service, "/api/run-sequence", {"sequence_id": "inconnue"})
    assert missing.value.code == 404


def test_run_state_is_kept_after_the_run(service: LauncherService) -> None:
    service.start_sequence("sequence-demo")
    deadline = time.monotonic() + 5
    while service.is_running("sequence-demo") and time.monotonic() < deadline:
        time.sleep(0.05)
    state = service.run_state("sequence-demo")
    assert state is not None and state.status == "success"
    assert state.done_step_ids == {service.config.sequences[0].steps[0].id}


def test_port_conflict_is_reported_not_raised(service: LauncherService, tmp_path) -> None:
    other = LauncherService(
        AppConfig(settings=AppSettings(api_port=service.config.settings.api_port, discovery_port=free_port(socket.SOCK_DGRAM))),
        ConfigStore(tmp_path / "other.json", legacy_path=None),
    )
    other.start()
    try:
        status = other.network_status()
        assert not status.ok
        assert str(service.config.settings.api_port) in status.api_error
    finally:
        other.stop()


def test_restart_network_applies_new_port(service: LauncherService) -> None:
    service.config.settings.api_port = free_port()
    assert service.restart_network().ok
    status, _ = request(service, "/api/sequences")
    assert status == 200


def test_remote_step_runs_a_sequence_on_another_node(service: LauncherService, tmp_path) -> None:
    from py_network_launcher.actions import StopToken
    from py_network_launcher.models import ACTION_REMOTE_SEQUENCE, PeerInfo

    caller = LauncherService(
        AppConfig(settings=AppSettings(api_port=free_port(), discovery_port=free_port(socket.SOCK_DGRAM))),
        ConfigStore(tmp_path / "caller.json", legacy_path=None),
    )
    target = service.config.settings
    # Injection directe du pair : la découverte UDP n'est pas fiable sur les runners CI.
    caller._peers[target.node_id] = PeerInfo(node_id=target.node_id, name="cible", host="127.0.0.1", port=target.api_port)
    step = ActionStep(action_type=ACTION_REMOTE_SEQUENCE, remote_peer_id=target.node_id, remote_sequence_id="sequence-demo")
    caller._run_remote_step(step, StopToken())
    assert service.is_running("sequence-demo")

    absent = ActionStep(action_type=ACTION_REMOTE_SEQUENCE, remote_peer_id="node-absent", remote_sequence_id="x", wait_timeout_s=0.5)
    with pytest.raises(RuntimeError, match="introuvable"):
        caller._run_remote_step(absent, StopToken())
