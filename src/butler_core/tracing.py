from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from enum import Enum
from time import monotonic_ns
from typing import Any, Iterator, Protocol
from uuid import uuid4


_TRACE_METADATA_KEY = "butler_trace"


class TraceStatus(str, Enum):
    """Provider-neutral outcome classification for trace events."""

    NORMAL = "normal"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class TraceSeverity(str, Enum):
    """Operational impact classification independent from event status."""

    NORMAL = "normal"
    DEGRADED = "degraded"
    CRITICAL = "critical"


TraceAttribute = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class TraceContext:
    """Correlation context shared across Butler execution boundaries."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None

    @classmethod
    def root(cls) -> "TraceContext":
        return cls(
            trace_id=str(uuid4()),
            span_id=str(uuid4()),
        )

    def child(self) -> "TraceContext":
        return TraceContext(
            trace_id=self.trace_id,
            span_id=str(uuid4()),
            parent_span_id=self.span_id,
        )

    def to_metadata(self) -> dict[str, dict[str, str | None]]:
        return {
            _TRACE_METADATA_KEY: {
                "trace_id": self.trace_id,
                "span_id": self.span_id,
                "parent_span_id": self.parent_span_id,
            }
        }

    @classmethod
    def from_metadata(
        cls,
        metadata: Mapping[str, Any] | None,
    ) -> "TraceContext | None":
        if not isinstance(metadata, Mapping):
            return None

        raw = metadata.get(_TRACE_METADATA_KEY)
        if not isinstance(raw, Mapping):
            return None

        trace_id = raw.get("trace_id")
        span_id = raw.get("span_id")
        parent_span_id = raw.get("parent_span_id")

        if not isinstance(trace_id, str) or not trace_id.strip():
            return None
        if not isinstance(span_id, str) or not span_id.strip():
            return None
        if parent_span_id is not None and not isinstance(
            parent_span_id,
            str,
        ):
            return None

        return cls(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
        )


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """A storage-agnostic structured event in one Butler trace."""

    context: TraceContext
    component: str
    operation: str
    message: str
    status: TraceStatus = TraceStatus.NORMAL
    severity: TraceSeverity = TraceSeverity.NORMAL
    duration_ms: float | None = None
    attributes: Mapping[str, TraceAttribute] = field(
        default_factory=dict
    )


class Tracer(Protocol):
    """Storage-agnostic consumer of Butler trace events."""

    def emit(self, event: TraceEvent) -> None:
        ...


class NullTracer:
    """Default no-op tracer used when observability is disabled."""

    def emit(self, event: TraceEvent) -> None:
        del event


def safe_emit(tracer: Tracer, event: TraceEvent) -> bool:
    """Emit an event without allowing observability to break execution.

    Tracer implementations are external consumers from Core's perspective.
    Their failures must therefore remain observational failures rather than
    becoming Butler execution failures.
    """

    try:
        tracer.emit(event)
    except Exception:
        return False

    return True


_current_trace_context: ContextVar[TraceContext | None] = ContextVar(
    "butler_trace_context",
    default=None,
)


def current_trace_context() -> TraceContext | None:
    return _current_trace_context.get()


def set_trace_context(context: TraceContext | None) -> Token:
    return _current_trace_context.set(context)


def reset_trace_context(token: Token) -> None:
    _current_trace_context.reset(token)


@contextmanager
def trace_context(
    context: TraceContext,
) -> Iterator[TraceContext]:
    token = set_trace_context(context)
    try:
        yield context
    finally:
        reset_trace_context(token)


@contextmanager
def traced_span(
    tracer: Tracer,
    *,
    component: str,
    operation: str,
    message: str,
    attributes: Mapping[str, TraceAttribute] | None = None,
    context: TraceContext | None = None,
    error_severity: TraceSeverity = TraceSeverity.DEGRADED,
) -> Iterator[TraceContext]:
    """Create a child span and emit its terminal event.

    The helper intentionally emits only the terminal event. Consumers that
    need explicit start events can emit them themselves without changing the
    Core contract. Tracer failures are swallowed through ``safe_emit`` so
    instrumentation cannot change the observed execution outcome.
    """

    parent = context or current_trace_context()
    span = parent.child() if parent is not None else TraceContext.root()
    started = monotonic_ns()

    with trace_context(span):
        try:
            yield span
        except Exception as exc:
            safe_emit(
                tracer,
                TraceEvent(
                    context=span,
                    component=component,
                    operation=operation,
                    message=message,
                    status=TraceStatus.ERROR,
                    severity=error_severity,
                    duration_ms=_elapsed_ms(started),
                    attributes={
                        **dict(attributes or {}),
                        "error_type": type(exc).__name__,
                    },
                ),
            )
            raise
        else:
            safe_emit(
                tracer,
                TraceEvent(
                    context=span,
                    component=component,
                    operation=operation,
                    message=message,
                    status=TraceStatus.SUCCESS,
                    severity=TraceSeverity.NORMAL,
                    duration_ms=_elapsed_ms(started),
                    attributes=dict(attributes or {}),
                ),
            )


def _elapsed_ms(started: int) -> float:
    return round(
        max((monotonic_ns() - started) / 1_000_000, 0.0),
        3,
    )
