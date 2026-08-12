from __future__ import annotations

from butler_core import (
    OutputAdapter,
    OutputDeliveryResult,
    OutputDeliveryStatus,
    OutputKind,
    OutputPriority,
    OutputRequest,
)


class RecordingAdapter:
    def __init__(self) -> None:
        self.requests: list[OutputRequest] = []

    @property
    def supported_kinds(self) -> frozenset[OutputKind]:
        return frozenset(
            {
                OutputKind.SPEECH,
                OutputKind.NOTIFICATION,
            }
        )

    def deliver(
        self,
        request: OutputRequest,
    ) -> OutputDeliveryResult:
        self.requests.append(request)
        return OutputDeliveryResult(
            status=OutputDeliveryStatus.DELIVERED
        )


def test_output_kinds_are_provider_neutral() -> None:
    assert {kind.value for kind in OutputKind} == {
        "speech",
        "notification",
        "sound",
        "display",
    }


def test_request_defaults_are_neutral() -> None:
    request = OutputRequest(
        content="Hello.",
        kind=OutputKind.SPEECH,
    )

    assert request.content == "Hello."
    assert request.kind is OutputKind.SPEECH
    assert request.target is None
    assert request.priority is OutputPriority.NORMAL
    assert request.locale is None
    assert request.metadata == {}
    assert request.correlation_id is None


def test_request_carries_delivery_context() -> None:
    request = OutputRequest(
        content="Laundry complete.",
        kind=OutputKind.NOTIFICATION,
        target="kitchen",
        priority=OutputPriority.HIGH,
        locale="en-GB",
        metadata={"source": "workflow"},
        correlation_id="job-42",
    )

    assert request.target == "kitchen"
    assert request.priority is OutputPriority.HIGH
    assert request.locale == "en-GB"
    assert request.metadata == {"source": "workflow"}
    assert request.correlation_id == "job-42"


def test_delivery_result_normalizes_outcomes() -> None:
    accepted = OutputDeliveryResult(
        status=OutputDeliveryStatus.ACCEPTED
    )
    delivered = OutputDeliveryResult(
        status=OutputDeliveryStatus.DELIVERED
    )
    unsupported = OutputDeliveryResult(
        status=OutputDeliveryStatus.UNSUPPORTED,
        error_code="unsupported_kind",
    )
    failed = OutputDeliveryResult(
        status=OutputDeliveryStatus.FAILED,
        error_code="delivery_failed",
        error_message="Provider unavailable.",
    )

    assert accepted.accepted is True
    assert accepted.delivered is False
    assert accepted.ok is True

    assert delivered.accepted is True
    assert delivered.delivered is True
    assert delivered.ok is True

    assert unsupported.accepted is False
    assert unsupported.delivered is False
    assert unsupported.ok is False

    assert failed.accepted is False
    assert failed.delivered is False
    assert failed.ok is False


def test_adapter_protocol_is_structural() -> None:
    adapter: OutputAdapter = RecordingAdapter()

    request = OutputRequest(
        content="Hello.",
        kind=OutputKind.SPEECH,
    )

    result = adapter.deliver(request)

    assert result.ok is True
    assert OutputKind.SPEECH in adapter.supported_kinds
    assert adapter.requests == [request]
