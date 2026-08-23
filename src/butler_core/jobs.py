from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Protocol
from uuid import uuid4

from butler_core.tracing import TraceContext, current_trace_context


class JobStatus(str, Enum):
    """Lifecycle state for work completed asynchronously."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in {
            JobStatus.SUCCEEDED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        }


@dataclass(frozen=True)
class JobRequest:
    """Provider-neutral request for work completed later."""

    operation: str
    arguments: Mapping[str, Any] = field(
        default_factory=dict
    )
    metadata: Mapping[str, Any] = field(
        default_factory=dict
    )
    job_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    @property
    def trace_context(self) -> TraceContext | None:
        """Restore the originating Butler trace when metadata carries one."""

        return TraceContext.from_metadata(self.metadata)

    def with_trace_context(
        self,
        context: TraceContext | None,
    ) -> JobRequest:
        """Return a copy carrying ``context`` without altering other metadata."""

        if context is None:
            return self

        metadata = dict(self.metadata)
        metadata.update(context.to_metadata())
        return replace(self, metadata=metadata)

    def with_current_trace(self) -> JobRequest:
        """Capture the current Butler trace for later asynchronous execution."""

        return self.with_trace_context(current_trace_context())


@dataclass(frozen=True)
class JobResult:
    """Observable lifecycle state and eventual result."""

    job_id: str
    operation: str
    status: JobStatus
    value: Any = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: float | None = None
    updated_at: float | None = None
    metadata: Mapping[str, Any] = field(
        default_factory=dict
    )

    @property
    def done(self) -> bool:
        return self.status.terminal

    @property
    def ok(self) -> bool:
        return self.status is JobStatus.SUCCEEDED

    def to_dict(self) -> dict[str, Any]:
        error = None

        if self.error_code is not None:
            error = {
                "code": self.error_code,
                "message": self.error_message,
            }

        return {
            "job_id": self.job_id,
            "operation": self.operation,
            "status": self.status.value,
            "done": self.done,
            "ok": self.ok,
            "value": self.value,
            "error": error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }


class JobStore(Protocol):
    """Persistence boundary for asynchronous jobs."""

    def create(
        self,
        request: JobRequest,
    ) -> JobResult:
        ...

    def get(
        self,
        job_id: str,
    ) -> JobResult | None:
        ...

    def update(
        self,
        result: JobResult,
    ) -> JobResult:
        ...


class JobRunner(Protocol):
    """Execution boundary for asynchronous jobs."""

    def submit(
        self,
        request: JobRequest,
    ) -> JobResult:
        ...

    def get(
        self,
        job_id: str,
    ) -> JobResult | None:
        ...

    def cancel(
        self,
        job_id: str,
    ) -> JobResult:
        ...
