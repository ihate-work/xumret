from __future__ import annotations

import pytest

from xumret.executor.models import (
    CommandStep,
    PhoneCommand,
    RunOption,
    StreamConfig,
)
from xumret.executor.process_graph import (
    GraphValidationError,
    ProcessGraphBuilder,
)


def _pc(steps: list[CommandStep], *, run_option: RunOption | None = None) -> PhoneCommand:
    return PhoneCommand(
        name="t",
        steps=steps,
        run_option=run_option or RunOption(),
    )


def test_single_step_minimal() -> None:
    pc = _pc([CommandStep(argv=["echo", "hi"])])
    g = ProcessGraphBuilder().build(pc)
    assert len(g.steps) == 1
    assert g.steps[0].argv == ["echo", "hi"]
    assert g.steps[0].stdin_from is None
    assert g.steps[0].stdout.forward_to is None
    assert g.steps[0].stdout.capture is False


def test_linear_pipeline_stdout_forward() -> None:
    pc = _pc([
        CommandStep(
            argv=["echo", "hi"],
            stdout_stream=StreamConfig(forward_dest_process_idx=1),
        ),
        CommandStep(argv=["tr", "a-z", "A-Z"]),
    ])
    g = ProcessGraphBuilder().build(pc)
    assert g.steps[0].stdout.forward_to == 1
    assert g.steps[1].stdin_from is not None
    assert g.steps[1].stdin_from.src_step_index == 0
    assert g.steps[1].stdin_from.src_fd == "stdout"


def test_stderr_can_forward() -> None:
    pc = _pc([
        CommandStep(
            argv=["sh", "-c", "echo err 1>&2"],
            stderr_stream=StreamConfig(forward_dest_process_idx=1),
        ),
        CommandStep(argv=["cat"]),
    ])
    g = ProcessGraphBuilder().build(pc)
    assert g.steps[0].stderr.forward_to == 1
    assert g.steps[1].stdin_from is not None
    assert g.steps[1].stdin_from.src_fd == "stderr"


def test_capture_and_forward_coexist() -> None:
    pc = _pc([
        CommandStep(
            argv=["echo", "hi"],
            stdout_stream=StreamConfig(capture=True, forward_dest_process_idx=1),
        ),
        CommandStep(argv=["cat"]),
    ])
    g = ProcessGraphBuilder().build(pc)
    assert g.steps[0].stdout.capture is True
    assert g.steps[0].stdout.forward_to == 1


def test_run_option_propagates() -> None:
    pc = _pc(
        [CommandStep(argv=["echo", "hi"])],
        run_option=RunOption(timeout=10.0, slug="s1", mutex_by_slug=True),
    )
    g = ProcessGraphBuilder().build(pc)
    assert g.timeout == 10.0
    assert g.slug == "s1"
    assert g.mutex_by_slug is True


def test_reject_empty_steps() -> None:
    pc = _pc([])
    with pytest.raises(GraphValidationError, match="at least one step"):
        ProcessGraphBuilder().build(pc)


def test_reject_empty_argv() -> None:
    pc = _pc([CommandStep(argv=[])])
    with pytest.raises(GraphValidationError, match="argv must be non-empty"):
        ProcessGraphBuilder().build(pc)


def test_reject_forward_out_of_range() -> None:
    pc = _pc([
        CommandStep(
            argv=["echo", "hi"],
            stdout_stream=StreamConfig(forward_dest_process_idx=5),
        ),
    ])
    with pytest.raises(GraphValidationError, match="out of range"):
        ProcessGraphBuilder().build(pc)


def test_reject_self_loop() -> None:
    pc = _pc([
        CommandStep(
            argv=["cat"],
            stdout_stream=StreamConfig(forward_dest_process_idx=0),
        ),
    ])
    with pytest.raises(GraphValidationError, match="cannot forward to itself"):
        ProcessGraphBuilder().build(pc)


def test_reject_stdin_collision() -> None:
    pc = _pc([
        CommandStep(
            argv=["echo", "a"],
            stdout_stream=StreamConfig(forward_dest_process_idx=2),
        ),
        CommandStep(
            argv=["echo", "b"],
            stdout_stream=StreamConfig(forward_dest_process_idx=2),
        ),
        CommandStep(argv=["cat"]),
    ])
    with pytest.raises(GraphValidationError, match="multiple sources"):
        ProcessGraphBuilder().build(pc)


def test_reject_cycle() -> None:
    # 0.stdout -> 1, 1.stdout -> 0
    pc = _pc([
        CommandStep(
            argv=["cat"],
            stdout_stream=StreamConfig(forward_dest_process_idx=1),
        ),
        CommandStep(
            argv=["cat"],
            stdout_stream=StreamConfig(forward_dest_process_idx=0),
        ),
    ])
    with pytest.raises(GraphValidationError, match="cycle"):
        ProcessGraphBuilder().build(pc)


def test_reject_mutex_without_slug() -> None:
    pc = _pc(
        [CommandStep(argv=["echo", "hi"])],
        run_option=RunOption(mutex_by_slug=True),
    )
    with pytest.raises(GraphValidationError, match="mutex_by_slug requires slug"):
        ProcessGraphBuilder().build(pc)


def test_reject_cache_for_without_slug() -> None:
    pc = _pc(
        [CommandStep(argv=["echo", "hi"])],
        run_option=RunOption(cache_for=10),
    )
    with pytest.raises(GraphValidationError, match="cache_for requires slug"):
        ProcessGraphBuilder().build(pc)


def test_reject_non_positive_timeout() -> None:
    pc = _pc(
        [CommandStep(argv=["echo", "hi"])],
        run_option=RunOption(timeout=0),
    )
    with pytest.raises(GraphValidationError, match="timeout must be > 0"):
        ProcessGraphBuilder().build(pc)


def test_dropped_stream_has_no_forward_no_capture() -> None:
    pc = _pc([CommandStep(argv=["echo", "hi"])])
    g = ProcessGraphBuilder().build(pc)
    # both fds default to dropped
    assert g.steps[0].stdout.forward_to is None
    assert g.steps[0].stdout.capture is False
    assert g.steps[0].stderr.forward_to is None
    assert g.steps[0].stderr.capture is False
