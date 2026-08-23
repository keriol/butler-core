from __future__ import annotations

from dataclasses import replace

from butler_core import (
    JobRequest,
    JobResult,
    JobRunner,
    JobStatus,
    JobStore,
    TraceContext,
    trace_context,
)


def test_job_request_generates_unique_id():
    first = JobRequest(operation="example")
    second = JobRequest(operation="example")

    assert first.job_id
    assert second.job_id
    assert first.job_id != second.job_id


def test_job_request_trace_context_round_trip():
    root = TraceContext.root()
    request = JobRequest(
        operation="example",
        metadata={"source": "test"},
    ).with_trace_context(root)

    assert request.trace_context == root
    assert request.metadata["source"] == "test"


def test_job_request_captures_current_trace():
    root = TraceContext.root()

    with trace_context(root):
        request = JobRequest(operation="example").with_current_trace()

    assert request.trace_context == root


def test_job_request_without_current_trace_stays_unlinked():
    request = JobRequest(
        operation="example",
        metadata={"source": "test"},
    ).with_current_trace()

    assert request.trace_context is None
    assert request.metadata == {"source": "test"}


def test_job_request_trace_handoff_preserves_identity():
    root = TraceContext.root()
    request = JobRequest(operation="example").with_trace_context(root)
    restored = request.trace_context

    assert restored is not None
    assert restored.trace_id == root.trace_id
    assert restored.span_id == root.span_id
    assert restored.parent_span_id == root.parent_span_id


def test_job_status_terminal_contract():
    assert JobStatus.QUEUED.terminal is False
    assert JobStatus.RUNNING.terminal is False

    assert JobStatus.SUCCEEDED.terminal is True
    assert JobStatus.FAILED.terminal is True
    assert JobStatus.CANCELLED.terminal is True


def test_success_result_contract():
    result = JobResult(
        job_id="job-1",
        operation="example",
        status=JobStatus.SUCCEEDED,
        value={"answer": 42},
        created_at=10.0,
        updated_at=20.0,
        metadata={"source": "test"},
    )

    assert result.done is True
    assert result.ok is True

    assert result.to_dict() == {
        "job_id": "job-1",
        "operation": "example",
        "status": "succeeded",
        "done": True,
        "ok": True,
        "value": {"answer": 42},
        "error": None,
        "created_at": 10.0,
        "updated_at": 20.0,
        "metadata": {"source": "test"},
    }


def test_failure_result_contract():
    result = JobResult(
        job_id="job-2",
        operation="example",
        status=JobStatus.FAILED,
        error_code="provider_error",
        error_message="boom",
    )

    assert result.done is True
    assert result.ok is False

    assert result.to_dict()["error"] == {
        "code": "provider_error",
        "message": "boom",
    }


def test_job_state_can_be_represented_immutably():
    queued = JobResult(
        job_id="job-3",
        operation="example",
        status=JobStatus.QUEUED,
    )

    running = replace(
        queued,
        status=JobStatus.RUNNING,
        updated_at=12.0,
    )

    succeeded = replace(
        running,
        status=JobStatus.SUCCEEDED,
        value="done",
        updated_at=15.0,
    )

    assert queued.done is False
    assert running.done is False
    assert succeeded.done is True
    assert succeeded.ok is True


def test_job_protocols_are_public():
    assert JobStore is not None
    assert JobRunner is not None
