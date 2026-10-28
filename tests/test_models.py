from py_network_launcher.models import (
    ACTION_DELAY,
    ACTION_LAUNCH_APP,
    ACTION_LOCAL_SEQUENCE,
    CLOSE_ACTION_MINIMIZE,
    TRIGGER_APP_START,
    TRIGGER_MANUAL,
    TRIGGER_ONCE_PER_SESSION,
    WAIT_MODE_EXIT,
    WAIT_MODE_NONE,
    ActionStep,
    AppConfig,
    AppSettings,
    LaunchSequence,
)


def test_config_round_trip() -> None:
    config = AppConfig(
        settings=AppSettings(node_name="PC-1", api_port=9000),
        sequences=[LaunchSequence(name="Stream", trigger=TRIGGER_APP_START, steps=[ActionStep(action_type=ACTION_DELAY, seconds=2.5)])],
    )
    restored = AppConfig.from_dict(config.to_dict())
    assert restored.to_dict() == config.to_dict()


def test_legacy_v01_triggers_are_migrated() -> None:
    assert LaunchSequence.from_dict({"run_on_app_start": True}).trigger == TRIGGER_APP_START
    assert LaunchSequence.from_dict({"run_on_boot": True}).trigger == TRIGGER_APP_START
    assert LaunchSequence.from_dict({"run_once_on_boot": True}).trigger == TRIGGER_ONCE_PER_SESSION
    assert LaunchSequence.from_dict({"name": "x"}).trigger == TRIGGER_MANUAL
    assert LaunchSequence.from_dict({"trigger": TRIGGER_ONCE_PER_SESSION, "run_on_app_start": True}).trigger == TRIGGER_ONCE_PER_SESSION


def test_legacy_step_fields_are_migrated() -> None:
    assert ActionStep.from_dict({"wait_for_exit": True}).wait_mode == WAIT_MODE_EXIT
    assert ActionStep.from_dict({}).wait_mode == WAIT_MODE_NONE
    step = ActionStep.from_dict({"headers_json": "{}", "shell": True, "home_assistant_domain": "light"})
    assert step.headers_json == ""
    assert "shell" not in step.to_dict()


def test_invalid_values_fall_back_to_defaults() -> None:
    step = ActionStep.from_dict(
        {"action_type": "nope", "seconds": "abc", "wait_port": 99999, "wait_timeout_s": 0, "method": "trace", "home_assistant_action": "explode"}
    )
    assert step.action_type == ACTION_LAUNCH_APP
    assert step.seconds == 1.0
    assert step.wait_port == 65535
    assert step.wait_timeout_s == 0.5
    assert step.method == "POST"
    assert step.home_assistant_action == "on"
    settings = AppSettings.from_dict({"api_port": "70000", "close_action": "bogus", "start_minimized": True, "home_assistant_url": " http://ha:8123/ "})
    assert settings.api_port == 8765
    assert settings.close_action == CLOSE_ACTION_MINIMIZE
    assert settings.start_minimized is False  # n'a de sens qu'avec le démarrage Windows
    assert settings.home_assistant_url == "http://ha:8123"


def test_garbage_input_never_raises() -> None:
    assert AppConfig.from_dict(None).sequences == []
    assert AppConfig.from_dict({"sequences": "oops", "settings": []}).sequences == []
    assert LaunchSequence.from_dict({"steps": [1, "x", None, {"action_type": ACTION_DELAY}]}).steps[0].action_type == ACTION_DELAY


def test_clone_with_new_identity() -> None:
    sequence = LaunchSequence(name="A", last_session_id="logon-1", steps=[ActionStep(), ActionStep()])
    copy = sequence.clone(new_identity=True)
    assert copy.id != sequence.id
    assert copy.last_session_id == ""
    assert {step.id for step in copy.steps}.isdisjoint({step.id for step in sequence.steps})
    assert sequence.clone().id == sequence.id


def test_sequences_referencing() -> None:
    target = LaunchSequence(name="cible")
    caller = LaunchSequence(name="appelante", steps=[ActionStep(action_type=ACTION_LOCAL_SEQUENCE, local_sequence_id=target.id)])
    config = AppConfig(sequences=[target, caller])
    assert config.sequences_referencing(target.id) == [caller]
    assert config.sequences_referencing(caller.id) == []
