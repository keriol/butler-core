from butler_core import (
    DeterministicResolutionPipeline,
    ResolutionResult,
    ResolverDefinition,
    TraceContext,
    TraceEvent,
    TraceLevel,
    TraceSeverity,
    TraceStatus,
    trace_context,
)


class RecordingTracer:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def emit(self, event: TraceEvent) -> None:
        self.events.append(event)


class BrokenTracer:
    def emit(self, event: TraceEvent) -> None:
        del event
        raise RuntimeError("tracer failed")


def test_resolution_reuses_current_trace_context() -> None:
    tracer = RecordingTracer()
    root = TraceContext.root()
    pipeline = DeterministicResolutionPipeline(
        fallback=lambda request: ResolutionResult.handled_result("ok"),
        tracer=tracer,
    )

    with trace_context(root):
        result = pipeline.resolve("hello")

    assert result.handled is True
    assert tracer.events
    assert all(event.context.trace_id == root.trace_id for event in tracer.events)


def test_decline_and_handled_resolver_are_reconstructable() -> None:
    tracer = RecordingTracer()
    pipeline = DeterministicResolutionPipeline(
        [
            ResolverDefinition(
                "first",
                lambda request: ResolutionResult.not_handled_result(),
            ),
            ResolverDefinition(
                "second",
                lambda request: ResolutionResult.handled_result("ok"),
            ),
        ],
        tracer=tracer,
    )

    result = pipeline.resolve("hello")

    assert result.handled is True
    operations = [event.operation for event in tracer.events]
    assert operations == [
        "resolver.attempt",
        "resolver.declined",
        "resolver.attempt",
        "resolver.handled",
    ]
    handled = tracer.events[-1]
    assert handled.level is TraceLevel.ACTIVITY
    assert handled.status is TraceStatus.SUCCESS
    assert handled.severity is TraceSeverity.NORMAL
    assert handled.attributes["resolver"] == "second"


def test_fallback_engagement_is_operational_and_visible() -> None:
    tracer = RecordingTracer()
    pipeline = DeterministicResolutionPipeline(
        [
            ResolverDefinition(
                "deterministic",
                lambda request: ResolutionResult.not_handled_result(),
            )
        ],
        fallback=lambda request: ResolutionResult.handled_result("fallback"),
        tracer=tracer,
    )

    result = pipeline.resolve("hello")

    assert result.used_fallback is True
    engaged = next(
        event for event in tracer.events if event.operation == "fallback.engaged"
    )
    handled = tracer.events[-1]
    assert engaged.level is TraceLevel.OPERATIONAL
    assert engaged.status is TraceStatus.WARNING
    assert handled.operation == "fallback.handled"
    assert handled.level is TraceLevel.OPERATIONAL
    assert handled.status is TraceStatus.SUCCESS


def test_resolver_failure_is_degraded_without_request_payload() -> None:
    tracer = RecordingTracer()

    def broken(request):
        raise RuntimeError("boom")

    pipeline = DeterministicResolutionPipeline(
        [ResolverDefinition("broken", broken)],
        tracer=tracer,
    )

    result = pipeline.resolve({"secret": "do-not-log"})

    assert result.error_code == "resolver_exception"
    event = tracer.events[-1]
    assert event.operation == "resolver.error"
    assert event.level is TraceLevel.OPERATIONAL
    assert event.status is TraceStatus.ERROR
    assert event.severity is TraceSeverity.DEGRADED
    assert event.attributes["error_code"] == "resolver_exception"
    assert "secret" not in event.attributes
    assert "do-not-log" not in event.message


def test_tracer_failure_does_not_change_resolution_result() -> None:
    pipeline = DeterministicResolutionPipeline(
        [
            ResolverDefinition(
                "winner",
                lambda request: ResolutionResult.handled_result("ok"),
            )
        ],
        tracer=BrokenTracer(),
    )

    result = pipeline.resolve("hello")

    assert result.handled is True
    assert result.value == "ok"
