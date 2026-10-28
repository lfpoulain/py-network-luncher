from __future__ import annotations

import socket
from dataclasses import dataclass, field, fields
from time import monotonic
from typing import Any
from uuid import uuid4

CONFIG_VERSION = 2

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
    ACTION_WAKE_ON_LAN: "Wake-on-LAN",
    ACTION_DELAY: "Délai",
    ACTION_LOCAL_SEQUENCE: "Séquence locale",
    ACTION_REMOTE_SEQUENCE: "Séquence distante",
    ACTION_HOME_ASSISTANT: "Home Assistant",
}

HOME_ASSISTANT_ACTION_ON = "on"
HOME_ASSISTANT_ACTION_OFF = "off"
HOME_ASSISTANT_ACTION_TOGGLE = "toggle"

HOME_ASSISTANT_ACTION_LABELS = {
    HOME_ASSISTANT_ACTION_ON: "Allumer",
    HOME_ASSISTANT_ACTION_OFF: "Éteindre",
    HOME_ASSISTANT_ACTION_TOGGLE: "Basculer",
}

HOME_ASSISTANT_SERVICES = {
    HOME_ASSISTANT_ACTION_ON: "turn_on",
    HOME_ASSISTANT_ACTION_OFF: "turn_off",
    HOME_ASSISTANT_ACTION_TOGGLE: "toggle",
}

WAIT_MODE_NONE = "none"
WAIT_MODE_OPENED = "opened"
WAIT_MODE_STARTED = "started"
WAIT_MODE_PORT = "port"
WAIT_MODE_EXIT = "exit"

WAIT_MODE_LABELS = {
    WAIT_MODE_NONE: "Ne pas attendre",
    WAIT_MODE_OPENED: "Vérifier que l'application s'ouvre",
    WAIT_MODE_STARTED: "Vérifier qu'elle reste ouverte pendant le délai",
    WAIT_MODE_PORT: "Attendre qu'un port TCP réponde",
    WAIT_MODE_EXIT: "Attendre la fin du processus",
}

WEBHOOK_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")

TRIGGER_MANUAL = "manual"
TRIGGER_APP_START = "app_start"
TRIGGER_ONCE_PER_SESSION = "once_per_session"

TRIGGER_LABELS = {
    TRIGGER_MANUAL: "Manuel uniquement",
    TRIGGER_APP_START: "À chaque démarrage de l'application",
    TRIGGER_ONCE_PER_SESSION: "Une fois par session Windows",
}

CLOSE_ACTION_MINIMIZE = "minimize_to_tray"
CLOSE_ACTION_QUIT = "quit"

CLOSE_ACTION_LABELS = {
    CLOSE_ACTION_MINIMIZE: "Réduire dans la zone de notification",
    CLOSE_ACTION_QUIT: "Quitter l'application",
}

DEFAULT_API_PORT = 8765
DEFAULT_DISCOVERY_PORT = 8766


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def default_node_name() -> str:
    try:
        return socket.gethostname() or "Mon poste"
    except OSError:
        return "Mon poste"


def _coerce(value: Any, default: Any) -> Any:
    """Convertit une valeur JSON vers le type de `default`, ou renvoie `default`."""
    if value is None:
        return default
    try:
        if isinstance(default, bool):
            if isinstance(value, str):
                return value.strip().lower() in ("1", "true", "yes", "on")
            return bool(value)
        if isinstance(default, int):
            return int(value)
        if isinstance(default, float):
            return float(value)
        if isinstance(default, str):
            return str(value)
    except (TypeError, ValueError):
        return default
    return value


def _load_fields(cls: type, data: dict[str, Any]) -> dict[str, Any]:
    """Lit chaque champ simple d'une dataclass depuis `data` en conservant son type."""
    template = cls()
    values: dict[str, Any] = {}
    for item in fields(cls):
        default = getattr(template, item.name)
        if isinstance(default, (list, dict)):
            continue
        values[item.name] = _coerce(data.get(item.name), default)
    return values


def _dump_fields(instance: Any) -> dict[str, Any]:
    return {item.name: getattr(instance, item.name) for item in fields(instance)}


@dataclass(slots=True)
class ActionStep:
    id: str = field(default_factory=lambda: new_id("step"))
    action_type: str = ACTION_LAUNCH_APP
    enabled: bool = True
    continue_on_error: bool = False
    command: str = ""
    arguments: str = ""
    working_directory: str = ""
    show_console: bool = False
    wait_mode: str = WAIT_MODE_NONE
    wait_timeout_s: float = 10.0
    wait_host: str = "127.0.0.1"
    wait_port: int = 0
    url: str = ""
    method: str = "POST"
    headers_json: str = ""
    body: str = ""
    mac_address: str = ""
    broadcast_ip: str = "255.255.255.255"
    seconds: float = 1.0
    local_sequence_id: str = ""
    remote_peer_id: str = ""
    remote_peer_name: str = ""
    remote_sequence_id: str = ""
    remote_sequence_name: str = ""
    home_assistant_entity_id: str = ""
    home_assistant_action: str = HOME_ASSISTANT_ACTION_ON

    @property
    def label(self) -> str:
        return ACTION_LABELS.get(self.action_type, "Étape")

    def to_dict(self) -> dict[str, Any]:
        return _dump_fields(self)

    def clone(self, *, new_identity: bool = False) -> ActionStep:
        copy = ActionStep.from_dict(self.to_dict())
        if new_identity:
            copy.id = new_id("step")
        return copy

    @classmethod
    def from_dict(cls, data: Any) -> ActionStep:
        if not isinstance(data, dict):
            return cls()
        values = _load_fields(cls, data)
        values["id"] = str(data.get("id") or "").strip() or new_id("step")
        if values["action_type"] not in ACTION_TYPES:
            values["action_type"] = ACTION_LAUNCH_APP
        if data.get("wait_mode") not in WAIT_MODE_LABELS:
            # Format v0.0 : booléen `wait_for_exit`.
            values["wait_mode"] = WAIT_MODE_EXIT if _coerce(data.get("wait_for_exit"), False) else WAIT_MODE_NONE
        action = values["home_assistant_action"].strip().lower()
        values["home_assistant_action"] = action if action in HOME_ASSISTANT_ACTION_LABELS else HOME_ASSISTANT_ACTION_ON
        method = values["method"].strip().upper()
        values["method"] = method if method in WEBHOOK_METHODS else "POST"
        if values["headers_json"].strip() == "{}":
            values["headers_json"] = ""
        values["wait_timeout_s"] = max(0.5, values["wait_timeout_s"])
        values["wait_port"] = min(65535, max(0, values["wait_port"]))
        values["seconds"] = max(0.0, values["seconds"])
        return cls(**values)


@dataclass(slots=True)
class LaunchSequence:
    id: str = field(default_factory=lambda: new_id("sequence"))
    name: str = "Nouvelle séquence"
    trigger: str = TRIGGER_MANUAL
    last_session_id: str = ""
    steps: list[ActionStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = _dump_fields(self)
        data["steps"] = [step.to_dict() for step in self.steps]
        return data

    def clone(self, *, new_identity: bool = False) -> LaunchSequence:
        copy = LaunchSequence.from_dict(self.to_dict())
        if new_identity:
            copy.id = new_id("sequence")
            copy.last_session_id = ""
            for step in copy.steps:
                step.id = new_id("step")
        return copy

    def find_step(self, step_id: str) -> ActionStep | None:
        return next((step for step in self.steps if step.id == step_id), None)

    def index_of(self, step_id: str) -> int:
        return next((index for index, step in enumerate(self.steps) if step.id == step_id), -1)

    @classmethod
    def from_dict(cls, data: Any) -> LaunchSequence:
        if not isinstance(data, dict):
            return cls()
        values = _load_fields(cls, data)
        values["id"] = str(data.get("id") or "").strip() or new_id("sequence")
        values["name"] = values["name"].strip() or "Nouvelle séquence"
        if data.get("trigger") not in TRIGGER_LABELS:
            # Formats v0.1 : booléens `run_on_app_start` / `run_on_boot` / `run_once_on_boot`.
            if _coerce(data.get("run_on_app_start"), False) or _coerce(data.get("run_on_boot"), False):
                values["trigger"] = TRIGGER_APP_START
            elif _coerce(data.get("run_once_on_boot"), False) or _coerce(data.get("run_only_once_on_boot"), False):
                values["trigger"] = TRIGGER_ONCE_PER_SESSION
            else:
                values["trigger"] = TRIGGER_MANUAL
        raw_steps = data.get("steps")
        steps = [ActionStep.from_dict(item) for item in raw_steps if isinstance(item, dict)] if isinstance(raw_steps, list) else []
        return cls(steps=steps, **values)


@dataclass(slots=True)
class AppSettings:
    node_id: str = field(default_factory=lambda: new_id("node"))
    node_name: str = field(default_factory=default_node_name)
    api_port: int = DEFAULT_API_PORT
    discovery_port: int = DEFAULT_DISCOVERY_PORT
    discovery_interval_s: float = 2.0
    peer_expiry_s: float = 8.0
    peer_refresh_interval_s: float = 5.0
    start_with_windows: bool = False
    start_minimized: bool = False
    close_action: str = CLOSE_ACTION_MINIMIZE
    home_assistant_url: str = ""
    home_assistant_token: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _dump_fields(self)

    @classmethod
    def from_dict(cls, data: Any) -> AppSettings:
        if not isinstance(data, dict):
            return cls()
        values = _load_fields(cls, data)
        values["node_id"] = str(data.get("node_id") or "").strip() or new_id("node")
        values["node_name"] = values["node_name"].strip() or default_node_name()
        values["api_port"] = values["api_port"] if 1 <= values["api_port"] <= 65535 else DEFAULT_API_PORT
        values["discovery_port"] = values["discovery_port"] if 1 <= values["discovery_port"] <= 65535 else DEFAULT_DISCOVERY_PORT
        values["discovery_interval_s"] = max(0.5, values["discovery_interval_s"])
        values["peer_expiry_s"] = max(2.0, values["peer_expiry_s"])
        values["peer_refresh_interval_s"] = max(2.0, values["peer_refresh_interval_s"])
        values["start_minimized"] = values["start_minimized"] and values["start_with_windows"]
        if values["close_action"] not in CLOSE_ACTION_LABELS:
            values["close_action"] = CLOSE_ACTION_MINIMIZE
        values["home_assistant_url"] = values["home_assistant_url"].strip().rstrip("/")
        values["home_assistant_token"] = values["home_assistant_token"].strip()
        return cls(**values)


@dataclass(slots=True)
class AppConfig:
    version: int = CONFIG_VERSION
    settings: AppSettings = field(default_factory=AppSettings)
    sequences: list[LaunchSequence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": CONFIG_VERSION,
            "settings": self.settings.to_dict(),
            "sequences": [sequence.to_dict() for sequence in self.sequences],
        }

    def find_sequence(self, sequence_id: str) -> LaunchSequence | None:
        return next((sequence for sequence in self.sequences if sequence.id == sequence_id), None)

    def sequences_referencing(self, sequence_id: str) -> list[LaunchSequence]:
        return [
            sequence
            for sequence in self.sequences
            if sequence.id != sequence_id
            and any(step.action_type == ACTION_LOCAL_SEQUENCE and step.local_sequence_id == sequence_id for step in sequence.steps)
        ]

    @classmethod
    def from_dict(cls, data: Any) -> AppConfig:
        if not isinstance(data, dict):
            return cls()
        raw_sequences = data.get("sequences")
        sequences = [LaunchSequence.from_dict(item) for item in raw_sequences if isinstance(item, dict)] if isinstance(raw_sequences, list) else []
        return cls(settings=AppSettings.from_dict(data.get("settings")), sequences=sequences)


@dataclass(slots=True)
class PeerSequenceSummary:
    id: str
    name: str


@dataclass(slots=True)
class PeerInfo:
    node_id: str
    name: str
    host: str
    port: int
    version: int = 1
    app_version: str = ""
    last_seen: float = field(default_factory=monotonic)
    sequences: list[PeerSequenceSummary] = field(default_factory=list)
    sequences_loaded: bool = False
    reachable: bool = True

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"

    def find_sequence(self, sequence_id: str) -> PeerSequenceSummary | None:
        return next((item for item in self.sequences if item.id == sequence_id), None)
