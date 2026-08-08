"""Deterministic top-level worker sequence.

The supervisor makes no model-based routing decisions. Every enabled worker runs once in a
fixed order and an error stops downstream mutation, leaving an inspectable execution trace.
"""

from __future__ import annotations

import enum
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


class PipelineStage(enum.StrEnum):
    DOCUMENT_EXTRACTION = "document_extraction"
    VERIFICATION = "verification"
    REGISTRY = "registry"
    DIFF = "diff"
    IMPACT = "impact"
    REVIEW = "review"


PIPELINE_ORDER = tuple(PipelineStage)
Worker = Callable[[dict[str, Any]], dict[str, Any] | None]


@dataclass(frozen=True)
class StageExecution:
    stage: PipelineStage
    status: str
    output: dict[str, Any] | None = None
    error: str | None = None


@dataclass(frozen=True)
class PipelineExecution:
    context: dict[str, Any]
    stages: tuple[StageExecution, ...]
    completed: bool


def run_deterministic_pipeline(
    initial_context: Mapping[str, Any],
    workers: Mapping[PipelineStage, Worker],
) -> PipelineExecution:
    """Run configured real workers in fixed order; skipped stages are explicit."""
    context = dict(initial_context)
    executions: list[StageExecution] = []
    for stage in PIPELINE_ORDER:
        worker = workers.get(stage)
        if worker is None:
            executions.append(StageExecution(stage, "skipped"))
            continue
        try:
            output = worker(dict(context)) or {}
        except Exception as exc:
            executions.append(StageExecution(stage, "failed", error=str(exc)))
            return PipelineExecution(context, tuple(executions), False)
        context.update(output)
        executions.append(StageExecution(stage, "completed", output=output))
    return PipelineExecution(context, tuple(executions), True)
