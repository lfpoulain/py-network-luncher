import threading
import time

import pytest

from py_network_launcher.executor import OUTCOME_FAILED, OUTCOME_STOPPED, OUTCOME_SUCCESS, SequenceExecutor
from py_network_launcher.models import ACTION_DELAY, ACTION_LOCAL_SEQUENCE, ACTION_SHELL_COMMAND, WAIT_MODE_EXIT, ActionStep, AppConfig, LaunchSequence
from tests.conftest import RecordingListener


def delay(seconds: float = 0.0, **kwargs) -> ActionStep:
    return ActionStep(action_type=ACTION_DELAY, seconds=seconds, **kwargs)


def failing(**kwargs) -> ActionStep:
    return ActionStep(action_type=ACTION_SHELL_COMMAND, command="exit 1", wait_mode=WAIT_MODE_EXIT, **kwargs)


def call(sequence: LaunchSequence) -> ActionStep:
    return ActionStep(action_type=ACTION_LOCAL_SEQUENCE, local_sequence_id=sequence.id)


def make_executor(*sequences: LaunchSequence) -> tuple[SequenceExecutor, RecordingListener]:
    config = AppConfig(sequences=list(sequences))
    listener = RecordingListener()
    executor = SequenceExecutor(
        resolve_sequence=config.find_sequence,
        run_remote=lambda step, stop: None,
        home_assistant_settings=lambda: ("", ""),
        listener=listener,
    )
    return executor, listener


def test_successful_run_reports_every_step() -> None:
    sequence = LaunchSequence(steps=[delay(), delay()])
    executor, listener = make_executor(sequence)
    assert executor.start_sequence(sequence.id)
    assert listener.wait(sequence.id) == (OUTCOME_SUCCESS, None)
    finished = [event for event in listener.events if event[0] == "step_finished"]
    assert [event[2] for event in finished] == [step.id for step in sequence.steps]
    deadline = time.monotonic() + 2
    while executor.is_running(sequence.id) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not executor.is_running(sequence.id)


def test_failure_stops_the_sequence_and_names_the_step() -> None:
    sequence = LaunchSequence(steps=[delay(), failing(), delay()])
    executor, listener = make_executor(sequence)
    executor.start_sequence(sequence.id)
    outcome, error = listener.wait(sequence.id)
    assert outcome == OUTCOME_FAILED
    assert error is not None and error.startswith("Étape 2")
    assert ("step_started", sequence.id, sequence.steps[2].id) not in listener.events


def test_continue_on_error_and_disabled_steps() -> None:
    sequence = LaunchSequence(steps=[failing(continue_on_error=True), failing(enabled=False), delay()])
    executor, listener = make_executor(sequence)
    executor.start_sequence(sequence.id)
    assert listener.wait(sequence.id)[0] == OUTCOME_SUCCESS
    started = [event[2] for event in listener.events if event[0] == "step_started"]
    assert started == [sequence.steps[0].id, sequence.steps[2].id]


def test_a_running_sequence_cannot_be_started_twice() -> None:
    sequence = LaunchSequence(steps=[delay(1.0)])
    executor, listener = make_executor(sequence)
    assert executor.start_sequence(sequence.id)
    assert not executor.start_sequence(sequence.id)
    executor.stop_sequence(sequence.id)
    assert listener.wait(sequence.id)[0] == OUTCOME_STOPPED


def test_stop_interrupts_a_long_delay() -> None:
    sequence = LaunchSequence(steps=[delay(30)])
    executor, listener = make_executor(sequence)
    executor.start_sequence(sequence.id)
    threading.Timer(0.2, executor.stop_sequence, args=(sequence.id,)).start()
    assert listener.wait(sequence.id, timeout=5)[0] == OUTCOME_STOPPED


def test_nested_sequence_runs_inline_and_propagates_errors() -> None:
    child = LaunchSequence(name="enfant", steps=[failing()])
    parent = LaunchSequence(name="parent", steps=[call(child), delay()])
    executor, listener = make_executor(parent, child)
    executor.start_sequence(parent.id)
    outcome, error = listener.wait(parent.id)
    assert outcome == OUTCOME_FAILED
    assert "enfant" in (error or "")
    assert listener.finished[child.id][0] == OUTCOME_FAILED


def test_cycles_between_sequences_are_detected() -> None:
    first = LaunchSequence(name="A")
    second = LaunchSequence(name="B", steps=[call(first)])
    first.steps.append(call(second))
    executor, listener = make_executor(first, second)
    executor.start_sequence(first.id)
    outcome, error = listener.wait(first.id)
    assert outcome == OUTCOME_FAILED
    assert "Boucle" in (error or "")


def test_unknown_sequence_raises() -> None:
    executor, _ = make_executor()
    with pytest.raises(ValueError):
        executor.start_sequence("sequence-inconnue")


def test_single_step_test_reports_result() -> None:
    executor, _ = make_executor()
    results: list = []
    done = threading.Event()

    def on_done(error):
        results.append(error)
        done.set()

    executor.run_single_step(failing(), on_done)
    assert done.wait(10)
    assert results[0] and "code 1" in results[0]
