"""Plan a PhoneCommand into a runnable ProcessGraph.

`ProcessGraphBuilder` is the pre-flight stage of execution: it validates a
PhoneCommand and produces a `ProcessGraph` — a plain description of each
step's stdin source, capture flag, and forwarding edge. The builder never
touches the OS; turning the plan into processes is the executor's job.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from xumret.executor.models import PhoneCommand

FdName = Literal["stdout", "stderr"]


class GraphValidationError(ValueError):
    """The PhoneCommand cannot be turned into a valid process graph."""


class StdinSource(BaseModel):
    """A step's stdin is fed by another step's stdout/stderr."""

    src_step_index: int
    src_fd: FdName


class FdPlan(BaseModel):
    """What happens to one outgoing fd of one step.

    `capture` and `forward_to` are orthogonal — the executor tees when both
    are set. If neither is set the stream is dropped (read and discarded).
    """

    mode: Literal["lines", "binary"]
    capture: bool
    forward_to: int | None


class StepPlan(BaseModel):
    step_index: int
    argv: list[str]
    stdin_from: StdinSource | None
    stdout: FdPlan
    stderr: FdPlan


class ProcessGraph(BaseModel):
    """A validated, ready-to-spawn plan derived from a PhoneCommand."""

    steps: list[StepPlan]
    timeout: float | None
    slug: str | None
    mutex_by_slug: bool


class ProcessGraphBuilder:
    """Validate a PhoneCommand and produce a ProcessGraph.

    Stateless — one instance can be reused across calls.
    """

    def build(self, pc: PhoneCommand) -> ProcessGraph:
        edges = self._validate(pc)
        return self._plan(pc, edges)

    # ── validation ──────────────────────────────────────────────────

    def _validate(self, pc: PhoneCommand) -> list[tuple[int, FdName, int]]:
        n = len(pc.steps)
        if n == 0:
            raise GraphValidationError("PhoneCommand must have at least one step")

        for i, step in enumerate(pc.steps):
            if not step.argv:
                raise GraphValidationError(f"step {i}: argv must be non-empty")

        self._validate_run_option(pc)
        edges = self._collect_edges(pc)
        self._reject_self_loops(edges)
        self._reject_stdin_collisions(edges)
        self._reject_cycles(n, edges)
        return edges

    def _validate_run_option(self, pc: PhoneCommand) -> None:
        ro = pc.run_option
        if ro.mutex_by_slug and ro.slug is None:
            raise GraphValidationError("mutex_by_slug requires slug to be set")
        if ro.timeout is not None and ro.timeout <= 0:
            raise GraphValidationError(f"timeout must be > 0, got {ro.timeout}")

    def _collect_edges(self, pc: PhoneCommand) -> list[tuple[int, FdName, int]]:
        n = len(pc.steps)
        edges: list[tuple[int, FdName, int]] = []
        for i, step in enumerate(pc.steps):
            streams: list[tuple[FdName, StreamConfig]] = [
                ("stdout", step.stdout_stream),
                ("stderr", step.stderr_stream),
            ]
            for fd_name, cfg in streams:
                dst = cfg.forward_dest_process_idx
                if dst is None:
                    continue
                if not (0 <= dst < n):
                    raise GraphValidationError(
                        f"step {i} {fd_name}: forward_dest_process_idx={dst} "
                        f"out of range [0, {n})"
                    )
                edges.append((i, fd_name, dst))
        return edges

    def _reject_self_loops(self, edges: list[tuple[int, FdName, int]]) -> None:
        for src, fd, dst in edges:
            if src == dst:
                raise GraphValidationError(
                    f"step {src} {fd}: cannot forward to itself"
                )

    def _reject_stdin_collisions(
        self, edges: list[tuple[int, FdName, int]]
    ) -> None:
        seen: dict[int, tuple[int, FdName]] = {}
        for src, fd, dst in edges:
            if dst in seen:
                prev_src, prev_fd = seen[dst]
                raise GraphValidationError(
                    f"step {dst} stdin has multiple sources: "
                    f"step {prev_src} {prev_fd} and step {src} {fd}"
                )
            seen[dst] = (src, fd)

    def _reject_cycles(
        self, n: int, edges: list[tuple[int, FdName, int]]
    ) -> None:
        # Kahn's algorithm: a DAG empties out; a cyclic graph leaves residue.
        adj: list[list[int]] = [[] for _ in range(n)]
        indeg = [0] * n
        for src, _fd, dst in edges:
            adj[src].append(dst)
            indeg[dst] += 1
        queue = [i for i in range(n) if indeg[i] == 0]
        visited = 0
        while queue:
            node = queue.pop()
            visited += 1
            for child in adj[node]:
                indeg[child] -= 1
                if indeg[child] == 0:
                    queue.append(child)
        if visited != n:
            raise GraphValidationError("forwarding graph contains a cycle")

    # ── plan ────────────────────────────────────────────────────────

    def _plan(
        self,
        pc: PhoneCommand,
        edges: list[tuple[int, FdName, int]],
    ) -> ProcessGraph:
        inbound: dict[int, StdinSource] = {
            dst: StdinSource(src_step_index=src, src_fd=fd)
            for src, fd, dst in edges
        }

        steps = [
            StepPlan(
                step_index=i,
                argv=list(step.argv),
                stdin_from=inbound.get(i),
                stdout=FdPlan(
                    mode=step.stdout_stream.mode,
                    capture=step.stdout_stream.capture,
                    forward_to=step.stdout_stream.forward_dest_process_idx,
                ),
                stderr=FdPlan(
                    mode=step.stderr_stream.mode,
                    capture=step.stderr_stream.capture,
                    forward_to=step.stderr_stream.forward_dest_process_idx,
                ),
            )
            for i, step in enumerate(pc.steps)
        ]

        return ProcessGraph(
            steps=steps,
            timeout=pc.run_option.timeout,
            slug=pc.run_option.slug,
            mutex_by_slug=pc.run_option.mutex_by_slug,
        )
