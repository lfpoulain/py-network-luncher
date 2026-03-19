from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Any
from uuid import uuid4


ACTION_LAUNCH_APP = "launch_app"
ACTION_SHELL_COMMAND = "shell_command"
ACTION_OPEN_WEBPAGE = "open_webpage"
ACTION_CALL_WEBHOOK = "call_webhook"
ACTION_WAKE_ON_LAN = "wake_on_lan"
ACTION_DELAY = "delay"
ACTION_LOCAL_SEQUENCE = "local_sequence"
ACTION_REMOTE_SEQUENCE = "remote_sequence"
ACTION_HOME_ASSISTANT = "home_assistant"

ACTION_TYPES = (
    ACTION_LAUNCH_APP,
    ACTION_SHELL_COMMAND,
    ACTION_OPEN_WEBPAGE,
    ACTION_CALL_WEBHOOK,
    ACTION_WAKE_ON_LAN,
    ACTION_DELAY,
    ACTION_LOCAL_SEQUENCE,
    ACTION_REMOTE_SEQUENCE,
    ACTION_HOME_ASSISTANT,
)

ACTION_LABELS = {
    ACTION_LAUNCH_APP: "Lancer une application",
    ACTION_SHELL_COMMAND: "Commande shell",
    ACTION_OPEN_WEBPAGE: "Ouvrir une page web",
    ACTION_CALL_WEBHOOK: "Appeler un webhook",
    ACTION_WAKE_ON_LAN: "Wake on LAN",
    ACTION_DELAY: "Délai",
    ACTION_LOCAL_SEQUENCE: "Séquence locale",
    ACTION_REMOTE_SEQUENCE: "Séquence distante",
    ACTION_HOME_ASSISTANT: "Home Assistant",
}

HOME_ASSISTANT_DOMAIN_LIGHT = "light"
HOME_ASSISTANT_DOMAIN_SWITCH = "switch"

HOME_ASSISTANT_DOMAINS = (
    HOME_ASSISTANT_DOMAIN_LIGHT,
    HOME_ASSISTANT_DOMAIN_SWITCH,
)

HOME_ASSISTANT_DOMAIN_LABELS = {
    HOME_ASSISTANT_DOMAIN_LIGHT: "Lumière",
    HOME_ASSISTANT_DOMAIN_SWITCH: "Switch",
}

HOME_ASSISTANT_ACTION_ON = "on"
HOME_ASSISTANT_ACTION_OFF = "off"

HOME_ASSISTANT_ACTIONS = (
    HOME_ASSISTANT_ACTION_ON,
    HOME_ASSISTANT_ACTION_OFF,
)

HOME_ASSISTANT_ACTION_LABELS = {
    HOME_ASSISTANT_ACTION_ON: "On",
    HOME_ASSISTANT_ACTION_OFF: "Off",
}

WAIT_MODE_NONE = "none"
WAIT_MODE_OPENED = "opened"
WAIT_MODE_STARTED = "started"
WAIT_MODE_PORT = "port"
WAIT_MODE_EXIT = "exit"

WAIT_MODES = (
    WAIT_MODE_NONE,
    WAIT_MODE_OPENED,
    WAIT_MODE_STARTED,
    WAIT_MODE_PORT,
    WAIT_MODE_EXIT,
)

WAIT_MODE_LABELS = {
    WAIT_MODE_NONE: "Ne pas attendre",
    WAIT_MODE_OPENED: "Valider quand l'application est ouverte",
    WAIT_MODE_STARTED: "Valider que l'application reste ouverte",
    WAIT_MODE_PORT: "Attendre qu'un port réponde",
    WAIT_MODE_EXIT: "Attendre la fermeture",
}

CLOSE_ACTION_MINIMIZE = "minimize_to_tray"
CLOSE_ACTION_QUIT = "quit"

CLOSE_ACTIONS = (
    CLOSE_ACTION_MINIMIZE,
    CLOSE_ACTION_QUIT,
)

CLOSE_ACTION_LABELS = {
    CLOSE_ACTION_MINIMIZE: "Fermer en minimisant dans la zone de notification",
    CLOSE_ACTION_QUIT: "Fermer en quittant l'application",
}


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


@dataclass(slots=True)
class ActionStep:
    id: str = field(default_factory=lambda: new_id("step"))
    action_type: str = ACTION_LAUNCH_APP
    command: str = ""
    arguments: str = ""
    working_directory: str = ""
    shell: bool = False
    wait_mode: str = WAIT_MODE_NONE
    wait_timeout_s: float = 5.0
    wait_host: str = "127.0.0.1"
    wait_port: int = 0
    url: str = ""
    method: str = "POST"
    headers_json: str = "{}"
    body: str = ""
    mac_address: str = ""
    broadcast_ip: str = "255.255.255.255"
    seconds: float = 1.0
    local_sequence_id: str = ""
    remote_peer_id: str = ""
    remote_peer_name: str = ""
    remote_sequence_id: str = ""
    remote_sequence_name: str = ""
    home_assistant_domain: str = HOME_ASSISTANT_DOMAIN_LIGHT
    home_assistant_entity_id: str = ""
    home_assistant_action: str = HOME_ASSISTANT_ACTION_ON

    def display_name(self) -> str:
        return ACTION_LABELS.get(self.action_type, "Étape")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action_type": self.action_type,
            "command": self.command,
            "arguments": self.arguments,
            "working_directory": self.working_directory,
            "shell": self.shell,
            "wait_mode": self.wait_mode,
            "wait_timeout_s": self.wait_timeout_s,
            "wait_host": self.wait_host,
            "wait_port": self.wait_port,
            "url": self.url,
            "method": self.method,
            "headers_json": self.headers_json,
            "body": self.body,
            "mac_address": self.mac_address,
            "broadcast_ip": self.broadcast_ip,
            "seconds": self.seconds,
            "local_sequence_id": self.local_sequence_id,
            "remote_peer_id": self.remote_peer_id,
            "remote_peer_name": self.remote_peer_name,
            "remote_sequence_id": self.remote_sequence_id,
            "remote_sequence_name": self.remote_sequence_name,
            "home_assistant_domain": self.home_assistant_domain,
            "home_assistant_entity_id": self.home_assistant_entity_id,
            "home_assistant_action": self.home_assistant_action,
        }

    def clone(self) -> "ActionStep":
        return self.from_dict(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActionStep":
        if not isinstance(data, dict):
            return cls()
        action_type = str(data.get("action_type") or ACTION_LAUNCH_APP)
        command = str(data.get("command") or "")
        arguments = str(data.get("arguments") or "")
        if action_type not in ACTION_TYPES:
            action_type = ACTION_LAUNCH_APP
        try:
            seconds = float(data.get("seconds", 1.0))
        except Exception:
            seconds = 1.0
        wait_mode = str(data.get("wait_mode") or "").strip()
        if wait_mode not in WAIT_MODES:
            wait_mode = WAIT_MODE_EXIT if bool(data.get("wait_for_exit", False)) else WAIT_MODE_NONE
        try:
            wait_timeout_s = float(data.get("wait_timeout_s", 5.0))
        except Exception:
            wait_timeout_s = 5.0
        try:
            wait_port = int(data.get("wait_port", 0))
        except Exception:
            wait_port = 0
        home_assistant_domain = str(data.get("home_assistant_domain") or HOME_ASSISTANT_DOMAIN_LIGHT).strip().lower()
        if home_assistant_domain not in HOME_ASSISTANT_DOMAINS:
            home_assistant_domain = HOME_ASSISTANT_DOMAIN_LIGHT
        home_assistant_action = str(data.get("home_assistant_action") or HOME_ASSISTANT_ACTION_ON).strip().lower()
        if home_assistant_action not in HOME_ASSISTANT_ACTIONS:
            home_assistant_action = HOME_ASSISTANT_ACTION_ON
        return cls(
            id=str(data.get("id") or new_id("step")),
            action_type=action_type,
            command=command,
            arguments=arguments,
            working_directory=str(data.get("working_directory") or ""),
            shell=False,
            wait_mode=wait_mode,
            wait_timeout_s=max(0.5, wait_timeout_s),
            wait_host=str(data.get("wait_host") or "127.0.0.1"),
            wait_port=max(0, wait_port),
            url=str(data.get("url") or ""),
            method=str(data.get("method") or "POST").upper(),
            headers_json=str(data.get("headers_json") or "{}"),
            body=str(data.get("body") or ""),
            mac_address=str(data.get("mac_address") or ""),
            broadcast_ip=str(data.get("broadcast_ip") or "255.255.255.255"),
            seconds=max(0.0, seconds),
            local_sequence_id=str(data.get("local_sequence_id") or ""),
            remote_peer_id=str(data.get("remote_peer_id") or ""),
            remote_peer_name=str(data.get("remote_peer_name") or ""),
            remote_sequence_id=str(data.get("remote_sequence_id") or ""),
            remote_sequence_name=str(data.get("remote_sequence_name") or ""),
            home_assistant_domain=home_assistant_domain,
            home_assistant_entity_id=str(data.get("home_assistant_entity_id") or ""),
            home_assistant_action=home_assistant_action,
        )


@dataclass(slots=True)
class LaunchSequence:
    id: str = field(default_factory=lambda: new_id("sequence"))
    name: str = "Nouvelle séquence"
    run_on_app_start: bool = False
    run_once_on_boot: bool = False
    last_boot_run_id: str = ""
    steps: list[ActionStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "run_on_app_start": self.run_on_app_start,
            "run_once_on_boot": self.run_once_on_boot,
            "last_boot_run_id": self.last_boot_run_id,
            "steps": [step.to_dict() for step in self.steps],
        }

    def clone(self) -> "LaunchSequence":
        return self.from_dict(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LaunchSequence":
        if not isinstance(data, dict):
            return cls()
        steps_raw = data.get("steps") if isinstance(data.get("steps"), list) else []
        run_on_app_start = bool(data.get("run_on_app_start", False))
        legacy_run_on_boot = bool(data.get("run_on_boot", False))
        run_once_on_boot = bool(data.get("run_once_on_boot", False) or data.get("run_only_once_on_boot", False))
        return cls(
            id=str(data.get("id") or new_id("sequence")),
            name=str(data.get("name") or "Nouvelle séquence"),
            run_on_app_start=run_on_app_start or legacy_run_on_boot,
            run_once_on_boot=run_once_on_boot,
            last_boot_run_id=str(data.get("last_boot_run_id") or ""),
            steps=[ActionStep.from_dict(item) for item in steps_raw if isinstance(item, dict)],
        )


@dataclass(slots=True)
class AppSettings:
    node_id: str = field(default_factory=lambda: new_id("node"))
    node_name: str = "Mon poste"
    api_port: int = 8765
    discovery_port: int = 8766
    discovery_interval_s: float = 2.0
    peer_expiry_s: float = 8.0
    peer_refresh_interval_s: float = 5.0
    start_minimized: bool = False
    start_with_windows: bool = False
    close_action: str = CLOSE_ACTION_MINIMIZE
    home_assistant_url: str = ""
    home_assistant_token: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_name": self.node_name,
            "api_port": self.api_port,
            "discovery_port": self.discovery_port,
            "discovery_interval_s": self.discovery_interval_s,
            "peer_expiry_s": self.peer_expiry_s,
            "peer_refresh_interval_s": self.peer_refresh_interval_s,
            "start_minimized": self.start_minimized,
            "start_with_windows": self.start_with_windows,
            "close_action": self.close_action,
            "home_assistant_url": self.home_assistant_url,
            "home_assistant_token": self.home_assistant_token,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        if not isinstance(data, dict):
            return cls()
        try:
            api_port = int(data.get("api_port", 8765))
        except Exception:
            api_port = 8765
        try:
            discovery_port = int(data.get("discovery_port", 8766))
        except Exception:
            discovery_port = 8766
        try:
            discovery_interval_s = float(data.get("discovery_interval_s", 2.0))
        except Exception:
            discovery_interval_s = 2.0
        try:
            peer_expiry_s = float(data.get("peer_expiry_s", 8.0))
        except Exception:
            peer_expiry_s = 8.0
        try:
            peer_refresh_interval_s = float(data.get("peer_refresh_interval_s", 5.0))
        except Exception:
            peer_refresh_interval_s = 5.0
        close_action = str(data.get("close_action") or CLOSE_ACTION_MINIMIZE)
        if close_action not in CLOSE_ACTIONS:
            close_action = CLOSE_ACTION_MINIMIZE
        return cls(
            node_id=str(data.get("node_id") or new_id("node")),
            node_name=str(data.get("node_name") or "Mon poste"),
            api_port=max(1, api_port),
            discovery_port=max(1, discovery_port),
            discovery_interval_s=max(0.5, discovery_interval_s),
            peer_expiry_s=max(2.0, peer_expiry_s),
            peer_refresh_interval_s=max(2.0, peer_refresh_interval_s),
            start_minimized=bool(data.get("start_minimized", False)),
            start_with_windows=bool(data.get("start_with_windows", False)),
            close_action=close_action,
            home_assistant_url=str(data.get("home_assistant_url") or ""),
            home_assistant_token=str(data.get("home_assistant_token") or ""),
        )


@dataclass(slots=True)
class AppConfig:
    version: int = 1
    settings: AppSettings = field(default_factory=AppSettings)
    sequences: list[LaunchSequence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "settings": self.settings.to_dict(),
            "sequences": [sequence.to_dict() for sequence in self.sequences],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        if not isinstance(data, dict):
            return cls()
        raw_sequences = data.get("sequences") if isinstance(data.get("sequences"), list) else []
        return cls(
            version=int(data.get("version", 1)),
            settings=AppSettings.from_dict(data.get("settings") if isinstance(data.get("settings"), dict) else {}),
            sequences=[LaunchSequence.from_dict(item) for item in raw_sequences if isinstance(item, dict)],
        )


@dataclass(slots=True)
class PeerSequenceSummary:
    id: str
    name: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "name": self.name}


@dataclass(slots=True)
class PeerInfo:
    node_id: str
    name: str
    host: str
    port: int
    version: int
    last_seen: float = field(default_factory=monotonic)
    sequences: list[PeerSequenceSummary] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "version": self.version,
            "last_seen": self.last_seen,
            "sequences": [sequence.to_dict() for sequence in self.sequences],
        }
