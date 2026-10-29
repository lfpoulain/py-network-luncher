import socket
import subprocess
import sys
import threading
import time

import pytest

from py_network_launcher import actions
from py_network_launcher.actions import StopRequested, StopToken
from py_network_launcher.models import WAIT_MODE_EXIT, WAIT_MODE_OPENED, WAIT_MODE_PORT, WAIT_MODE_STARTED, ActionStep
from tests.conftest import free_port

PYTHON = sys.executable


def python_step(code: str, **kwargs) -> ActionStep:
    return ActionStep(command=PYTHON, arguments=f'-c "{code}"', **kwargs)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("example.com", "https://example.com"),
        ("  http://a.b/c ", "http://a.b/c"),
        ("mailto:x@y.z", "mailto:x@y.z"),
        ("ms-settings:display", "ms-settings:display"),
        ("homeassistant.local:8123", "http://homeassistant.local:8123"),
        ("localhost:8123/api/webhook/x", "http://localhost:8123/api/webhook/x"),
        ("192.168.1.10/hook", "http://192.168.1.10/hook"),
        ("nas.lan", "http://nas.lan"),
        ("", ""),
    ],
)
def test_normalize_url(raw: str, expected: str) -> None:
    assert actions.normalize_url(raw) == expected


@pytest.mark.parametrize("raw", ["AA:BB:CC:DD:EE:FF", "aa-bb-cc-dd-ee-ff", "aabb.ccdd.eeff", "AABBCCDDEEFF"])
def test_parse_mac_address_accepts_common_formats(raw: str) -> None:
    assert actions.parse_mac_address(raw) == bytes.fromhex("AABBCCDDEEFF")


@pytest.mark.parametrize("raw", ["", "AA:BB:CC", "GG:BB:CC:DD:EE:FF", "AA:BB:CC:DD:EE:FF:00"])
def test_parse_mac_address_rejects_invalid(raw: str) -> None:
    with pytest.raises(ValueError):
        actions.parse_mac_address(raw)


def test_parse_headers() -> None:
    assert actions.parse_headers("") == {}
    assert actions.parse_headers('{"A": 1}') == {"A": "1"}
    with pytest.raises(ValueError):
        actions.parse_headers("[1, 2]")
    with pytest.raises(ValueError):
        actions.parse_headers("{oops")


def test_stop_token_interrupts_sleep() -> None:
    token = StopToken()
    threading.Timer(0.1, token.set).start()
    started = time.monotonic()
    with pytest.raises(StopRequested):
        token.sleep(5)
    assert time.monotonic() - started < 2


def test_launch_app_waits_for_exit_and_reports_exit_code() -> None:
    actions.launch_app(python_step("import sys; sys.exit(0)", wait_mode=WAIT_MODE_EXIT), StopToken())
    with pytest.raises(RuntimeError, match="code 3"):
        actions.launch_app(python_step("import sys; sys.exit(3)", wait_mode=WAIT_MODE_EXIT), StopToken())


def test_launch_app_keeps_quoted_arguments(tmp_path) -> None:
    target = tmp_path / "dossier avec espaces" / "out.txt"
    target.parent.mkdir()
    step = ActionStep(
        command=f'"{PYTHON}"',  # chemin collé avec « Copier en tant que chemin »
        arguments=f'-c "import sys, pathlib; pathlib.Path(sys.argv[1]).write_text(sys.argv[1])" "{target}"',
        wait_mode=WAIT_MODE_EXIT,
    )
    actions.launch_app(step, StopToken())
    assert target.read_text() == str(target)


def test_launch_app_detects_immediate_exit() -> None:
    with pytest.raises(RuntimeError, match="fermée aussitôt"):
        actions.launch_app(python_step("pass", wait_mode=WAIT_MODE_OPENED), StopToken())
    actions.launch_app(python_step("import time; time.sleep(3)", wait_mode=WAIT_MODE_STARTED, wait_timeout_s=0.6), StopToken())


def test_launch_app_missing_program() -> None:
    with pytest.raises(FileNotFoundError):
        actions.launch_app(ActionStep(command=r"C:\nexiste\pas\app.exe"), StopToken())
    with pytest.raises(ValueError):
        actions.launch_app(ActionStep(command=""), StopToken())


def test_wait_for_port() -> None:
    port = free_port()
    server = socket.socket()
    server.bind(("127.0.0.1", port))
    server.listen()
    try:
        actions.launch_app(python_step("import time; time.sleep(2)", wait_mode=WAIT_MODE_PORT, wait_port=port, wait_timeout_s=2), StopToken())
    finally:
        server.close()
    with pytest.raises(RuntimeError, match="ne répond pas"):
        actions.launch_app(python_step("import time; time.sleep(3)", wait_mode=WAIT_MODE_PORT, wait_port=free_port(), wait_timeout_s=0.6), StopToken())


def test_shell_command_failure_includes_output() -> None:
    actions.run_shell_command(ActionStep(command="echo ok", wait_mode=WAIT_MODE_EXIT), StopToken())
    with pytest.raises(RuntimeError) as error:
        actions.run_shell_command(ActionStep(command="echo message-d-erreur && exit 4", wait_mode=WAIT_MODE_EXIT), StopToken())
    assert "code 4" in str(error.value)
    assert "message-d-erreur" in str(error.value)


def test_output_tail_closes_the_pipe() -> None:
    process = subprocess.Popen([PYTHON, "-c", "print('a'); print('b')"], stdout=subprocess.PIPE, text=True)
    tail = actions.OutputTail(process)
    process.wait(timeout=10)
    assert tail.summary() == "a | b"
    assert process.stdout is not None and process.stdout.closed


def test_shell_command_can_be_stopped() -> None:
    token = StopToken()
    threading.Timer(0.3, token.set).start()
    with pytest.raises(StopRequested):
        actions.run_shell_command(ActionStep(command=f'"{PYTHON}" -c "import time; time.sleep(5)"', wait_mode=WAIT_MODE_EXIT), token)


def test_home_assistant_requires_configuration() -> None:
    step = ActionStep(home_assistant_entity_id="light.salon")
    with pytest.raises(ValueError, match="URL"):
        actions.call_home_assistant(step, "", "token")
    with pytest.raises(ValueError, match="Token"):
        actions.call_home_assistant(step, "http://ha", "")
    with pytest.raises(ValueError, match="Entity ID"):
        actions.call_home_assistant(ActionStep(home_assistant_entity_id="salon"), "http://ha", "t")


def test_shell_open_passes_string_arguments(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """os.startfile refuse `arguments=None` (TypeError en Python 3.12)."""
    calls: list[tuple] = []

    def fake_startfile(path, operation="open", arguments="", cwd=None, show_cmd=1):
        assert isinstance(arguments, str)
        calls.append((path, operation, arguments, cwd))

    monkeypatch.setattr(actions, "IS_WINDOWS", True)
    monkeypatch.setattr(actions.os, "startfile", fake_startfile, raising=False)
    actions.open_webpage(ActionStep(url="example.com"))
    shortcut = tmp_path / "OBS.lnk"
    shortcut.write_bytes(b"")
    actions.launch_app(ActionStep(command=str(shortcut)), StopToken())
    assert calls[0][:3] == ("https://example.com", "open", "")
    assert calls[1] == (str(shortcut), "open", "", str(tmp_path))
