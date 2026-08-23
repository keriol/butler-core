from __future__ import annotations

import unittest

from butler_core import (
    NullTracer,
    TraceContext,
    TraceEvent,
    TraceLevel,
    TraceSeverity,
    TraceStatus,
    current_trace_context,
    safe_emit,
    trace_context,
    traced_span,
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


class TracingTests(unittest.TestCase):
    def test_child_preserves_trace_and_parent(self) -> None:
        root = TraceContext.root()
        child = root.child()

        self.assertEqual(child.trace_id, root.trace_id)
        self.assertEqual(child.parent_span_id, root.span_id)
        self.assertNotEqual(child.span_id, root.span_id)

    def test_context_manager_sets_and_resets_context(self) -> None:
        root = TraceContext.root()
        self.assertIsNone(current_trace_context())

        with trace_context(root):
            self.assertEqual(current_trace_context(), root)

        self.assertIsNone(current_trace_context())

    def test_context_round_trip_through_job_metadata(self) -> None:
        root = TraceContext.root()
        restored = TraceContext.from_metadata(root.to_metadata())

        self.assertEqual(restored, root)

    def test_invalid_metadata_is_ignored(self) -> None:
        self.assertIsNone(
            TraceContext.from_metadata(
                {"butler_trace": {"trace_id": "only-trace"}}
            )
        )

    def test_trace_level_order_is_cumulative(self) -> None:
        self.assertTrue(TraceLevel.DEBUG.includes(TraceLevel.DEBUG))
        self.assertTrue(TraceLevel.DEBUG.includes(TraceLevel.RELEASE))
        self.assertTrue(
            TraceLevel.DIAGNOSTIC.includes(TraceLevel.ACTIVITY)
        )
        self.assertTrue(
            TraceLevel.ACTIVITY.includes(TraceLevel.OPERATIONAL)
        )
        self.assertTrue(
            TraceLevel.OPERATIONAL.includes(TraceLevel.RELEASE)
        )
        self.assertFalse(
            TraceLevel.RELEASE.includes(TraceLevel.OPERATIONAL)
        )
        self.assertFalse(
            TraceLevel.ACTIVITY.includes(TraceLevel.DIAGNOSTIC)
        )

    def test_critical_event_is_promoted_to_release(self) -> None:
        event = TraceEvent(
            context=TraceContext.root(),
            component="runtime",
            operation="critical.operation",
            message="Critical failure",
            level=TraceLevel.DEBUG,
            status=TraceStatus.ERROR,
            severity=TraceSeverity.CRITICAL,
        )

        self.assertEqual(event.level, TraceLevel.RELEASE)
        self.assertEqual(event.severity, TraceSeverity.CRITICAL)

    def test_non_critical_event_keeps_declared_level(self) -> None:
        event = TraceEvent(
            context=TraceContext.root(),
            component="runtime",
            operation="diagnostic.operation",
            message="Diagnostic detail",
            level=TraceLevel.DIAGNOSTIC,
            severity=TraceSeverity.DEGRADED,
        )

        self.assertEqual(event.level, TraceLevel.DIAGNOSTIC)

    def test_traced_span_emits_success(self) -> None:
        tracer = RecordingTracer()
        root = TraceContext.root()

        with trace_context(root):
            with traced_span(
                tracer,
                component="execution",
                operation="tool.execute",
                message="Executed tool",
            ) as span:
                self.assertEqual(span.trace_id, root.trace_id)
                self.assertEqual(span.parent_span_id, root.span_id)

        self.assertEqual(len(tracer.events), 1)
        event = tracer.events[0]
        self.assertEqual(event.status, TraceStatus.SUCCESS)
        self.assertEqual(event.severity, TraceSeverity.NORMAL)
        self.assertEqual(event.level, TraceLevel.ACTIVITY)
        self.assertEqual(event.component, "execution")
        self.assertEqual(event.context.trace_id, root.trace_id)
        self.assertGreaterEqual(event.duration_ms or 0, 0)

    def test_traced_span_emits_error_and_reraises(self) -> None:
        tracer = RecordingTracer()

        with self.assertRaisesRegex(RuntimeError, "boom"):
            with traced_span(
                tracer,
                component="execution",
                operation="tool.execute",
                message="Executed tool",
            ):
                raise RuntimeError("boom")

        self.assertEqual(len(tracer.events), 1)
        event = tracer.events[0]
        self.assertEqual(event.status, TraceStatus.ERROR)
        self.assertEqual(event.severity, TraceSeverity.DEGRADED)
        self.assertEqual(event.level, TraceLevel.ACTIVITY)
        self.assertEqual(event.attributes["error_type"], "RuntimeError")

    def test_traced_span_can_mark_error_critical(self) -> None:
        tracer = RecordingTracer()

        with self.assertRaises(RuntimeError):
            with traced_span(
                tracer,
                component="runtime",
                operation="critical.operation",
                message="Critical operation failed",
                level=TraceLevel.DEBUG,
                error_severity=TraceSeverity.CRITICAL,
            ):
                raise RuntimeError("boom")

        event = tracer.events[0]
        self.assertEqual(event.severity, TraceSeverity.CRITICAL)
        self.assertEqual(event.level, TraceLevel.RELEASE)

    def test_safe_emit_contains_tracer_failure(self) -> None:
        emitted = safe_emit(
            BrokenTracer(),
            TraceEvent(
                context=TraceContext.root(),
                component="test",
                operation="broken-tracer",
                message="ignored failure",
            ),
        )

        self.assertFalse(emitted)

    def test_tracer_failure_does_not_change_successful_span(self) -> None:
        reached = False

        with traced_span(
            BrokenTracer(),
            component="execution",
            operation="tool.execute",
            message="Executed tool",
        ):
            reached = True

        self.assertTrue(reached)

    def test_original_exception_survives_tracer_failure(self) -> None:
        with self.assertRaisesRegex(ValueError, "original failure"):
            with traced_span(
                BrokenTracer(),
                component="execution",
                operation="tool.execute",
                message="Executed tool",
            ):
                raise ValueError("original failure")

    def test_null_tracer_is_safe_noop(self) -> None:
        NullTracer().emit(
            TraceEvent(
                context=TraceContext.root(),
                component="test",
                operation="noop",
                message="ignored",
            )
        )


if __name__ == "__main__":
    unittest.main()
