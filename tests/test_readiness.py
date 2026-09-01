from __future__ import annotations

import pytest

from butler_core import (
    AvailabilityResult,
    AvailabilityState,
    CapabilityDefinition,
    DomainDefinition,
    PluginDefinition,
    aggregate_availability,
    evaluate_availability_probe,
)
from butler_core.registry import ToolRegistry


def _register_nothing(registry: ToolRegistry) -> None:
    del registry


def test_missing_probe_is_unknown_not_unavailable() -> None:
    result = evaluate_availability_probe(None)

    assert result.state is AvailabilityState.UNKNOWN
    assert result.reason_code == "probe_not_declared"
    assert result.usable is False


def test_probe_can_report_provider_owned_reason() -> None:
    result = evaluate_availability_probe(
        lambda: AvailabilityResult(
            AvailabilityState.UNAVAILABLE,
            reason_code="missing_server_identifier",
            diagnostic="Server identifier is not configured.",
        )
    )

    assert result.state is AvailabilityState.UNAVAILABLE
    assert result.reason_code == "missing_server_identifier"
    assert "not configured" in result.diagnostic


def test_probe_failure_is_error_not_unavailable() -> None:
    def broken_probe() -> AvailabilityResult:
        raise RuntimeError("provider exploded")

    result = evaluate_availability_probe(broken_probe)

    assert result.state is AvailabilityState.ERROR
    assert result.reason_code == "probe_failed"
    assert "RuntimeError" in result.diagnostic


def test_invalid_probe_result_is_error() -> None:
    result = evaluate_availability_probe(lambda: "ready")  # type: ignore[arg-type,return-value]

    assert result.state is AvailabilityState.ERROR
    assert result.reason_code == "invalid_probe_result"


def test_capability_and_plugin_accept_optional_probes() -> None:
    capability_probe = lambda: AvailabilityResult.usable_result()
    plugin_probe = lambda: AvailabilityResult.usable_result()

    capability = CapabilityDefinition(
        name="status",
        domain="system",
        availability_probe=capability_probe,
    )
    plugin = PluginDefinition(
        name="demo.system",
        register=_register_nothing,
        domains=(DomainDefinition(name="system"),),
        capabilities=(capability,),
        readiness_probe=plugin_probe,
    )

    assert capability.availability_probe is capability_probe
    assert plugin.readiness_probe is plugin_probe


def test_non_callable_probes_are_rejected() -> None:
    with pytest.raises(TypeError, match="availability_probe must be callable"):
        CapabilityDefinition(
            name="status",
            domain="system",
            availability_probe="yes",  # type: ignore[arg-type]
        )

    with pytest.raises(TypeError, match="readiness_probe must be callable"):
        PluginDefinition(
            name="demo.system",
            register=_register_nothing,
            readiness_probe="yes",  # type: ignore[arg-type]
        )


def test_all_usable_capabilities_aggregate_to_usable() -> None:
    result = aggregate_availability(
        [
            AvailabilityResult.usable_result(),
            AvailabilityResult.usable_result(),
        ]
    )

    assert result.state is AvailabilityState.USABLE


def test_partial_capability_availability_is_degraded() -> None:
    result = aggregate_availability(
        [
            AvailabilityResult.usable_result(),
            AvailabilityResult(
                AvailabilityState.UNAVAILABLE,
                reason_code="missing_optional_target",
            ),
        ]
    )

    assert result.state is AvailabilityState.DEGRADED
    assert result.reason_code == "partial_availability"
    assert result.usable is True


def test_all_unavailable_capabilities_aggregate_to_unavailable() -> None:
    result = aggregate_availability(
        [
            AvailabilityResult(AvailabilityState.UNAVAILABLE),
            AvailabilityResult(AvailabilityState.UNAVAILABLE),
        ]
    )

    assert result.state is AvailabilityState.UNAVAILABLE


def test_probe_error_wins_when_no_capability_is_usable() -> None:
    result = aggregate_availability(
        [
            AvailabilityResult(AvailabilityState.UNKNOWN),
            AvailabilityResult(AvailabilityState.ERROR),
        ]
    )

    assert result.state is AvailabilityState.ERROR
    assert result.reason_code == "capability_probe_error"


def test_empty_aggregation_is_unknown() -> None:
    result = aggregate_availability([])

    assert result.state is AvailabilityState.UNKNOWN
    assert result.reason_code == "no_capability_results"


def test_aggregation_rejects_non_results() -> None:
    with pytest.raises(TypeError, match="AvailabilityResult"):
        aggregate_availability([object()])  # type: ignore[list-item]
