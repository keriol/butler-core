from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Protocol

from butler_core.tracing import TraceContext, current_trace_context


class OutputKind(str, Enum):
    SPEECH = "speech"
    NOTIFICATION = "notification"
    SOUND = "sound"
    DISPLAY = "display"


class OutputPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass(frozen=True)
class OutputRequest:
    content: str
    kind: OutputKind
    target: str | None = None
    priority: OutputPriority = OutputPriority.NORMAL
    locale: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None

    @property
    def trace_context(self) -> TraceContext | None:
        """Restore originating Butler trace context from output metadata."""

        return TraceContext.from_metadata(self.metadata)

    def with_trace_context(
        self,
        context: TraceContext,
    ) -> "OutputRequest":
        """Return an immutable copy carrying trace correlation metadata."""

        return replace(
            self,
            metadata={
                **dict(self.metadata),
                **context.to_metadata(),
            },
        )

    def with_current_trace(self) -> "OutputRequest":
        """Attach the current Butler trace when one exists."""

        context = current_trace_context()
        if context is None:
            return self

        return self.with_trace_context(context)


class OutputDeliveryStatus(str, Enum):
    ACCEPTED = "accepted"
    DELIVERED = "delivered"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


@dataclass(frozen=True)
class OutputDeliveryResult:
    status: OutputDeliveryStatus
    error_code: str | None = None
    error_message: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return self.status in {
            OutputDeliveryStatus.ACCEPTED,
            OutputDeliveryStatus.DELIVERED,
        }

    @property
    def delivered(self) -> bool:
        return self.status is OutputDeliveryStatus.DELIVERED

    @property
    def ok(self) -> bool:
        return self.accepted


class OutputAdapter(Protocol):
    @property
    def supported_kinds(self) -> frozenset[OutputKind]:
        ...

    def deliver(
        self,
        request: OutputRequest,
    ) -> OutputDeliveryResult:
        ...
