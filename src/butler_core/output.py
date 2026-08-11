from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


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


class OutputDeliveryStatus(str, Enum):
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
    def ok(self) -> bool:
        return self.status is OutputDeliveryStatus.DELIVERED


class OutputAdapter(Protocol):
    @property
    def supported_kinds(self) -> frozenset[OutputKind]:
        ...

    def deliver(
        self,
        request: OutputRequest,
    ) -> OutputDeliveryResult:
        ...
