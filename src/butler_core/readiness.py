from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable


class AvailabilityState(str, Enum):
    """Provider-neutral evaluated operational state."""

    USABLE = "usable"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AvailabilityResult:
    """Immutable readiness/availability result returned by an observational probe.

    ``reason_code`` is intentionally opaque to Core beyond basic validation so
    concrete runtimes/providers can own their diagnostic vocabulary.
    """

    state: AvailabilityState
    reason_code: str | None = None
    diagnostic: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.state, AvailabilityState):
            raise TypeError("Availability state must be an AvailabilityState value.")
        if self.reason_code is not None and not self.reason_code.strip():
            raise ValueError("Availability reason_code cannot be empty.")

    @property
    def usable(self) -> bool:
        return self.state in {
            AvailabilityState.USABLE,
            AvailabilityState.DEGRADED,
        }

    @classmethod
    def usable_result(cls, diagnostic: str = "") -> "AvailabilityResult":
        return cls(AvailabilityState.USABLE, diagnostic=diagnostic)

    @classmethod
    def unknown_result(
        cls,
        reason_code: str = "probe_not_declared",
        diagnostic: str = "No readiness probe is declared.",
    ) -> "AvailabilityResult":
        return cls(
            AvailabilityState.UNKNOWN,
            reason_code=reason_code,
            diagnostic=diagnostic,
        )


AvailabilityProbe = Callable[[], AvailabilityResult]


def evaluate_availability_probe(
    probe: AvailabilityProbe | None,
) -> AvailabilityResult:
    """Evaluate one observational probe with safe failure semantics.

    Missing probes deliberately evaluate to UNKNOWN rather than UNAVAILABLE.
    This preserves backwards compatibility for older declarations while making
    the absence of evidence explicit to consumers.
    """

    if probe is None:
        return AvailabilityResult.unknown_result()

    try:
        result = probe()
    except Exception as exc:  # pragma: no cover - exact provider exception is opaque
        return AvailabilityResult(
            AvailabilityState.ERROR,
            reason_code="probe_failed",
            diagnostic=f"Availability probe failed: {type(exc).__name__}: {exc}",
        )

    if not isinstance(result, AvailabilityResult):
        return AvailabilityResult(
            AvailabilityState.ERROR,
            reason_code="invalid_probe_result",
            diagnostic=(
                "Availability probe returned "
                f"{type(result).__name__}, expected AvailabilityResult."
            ),
        )

    return result


def aggregate_availability(
    results: Iterable[AvailabilityResult],
) -> AvailabilityResult:
    """Derive a pure package summary from evaluated capability results."""

    values = tuple(results)
    if not values:
        return AvailabilityResult.unknown_result(
            reason_code="no_capability_results",
            diagnostic="No capability availability results were supplied.",
        )

    if not all(isinstance(item, AvailabilityResult) for item in values):
        raise TypeError("Availability aggregation requires AvailabilityResult values.")

    states = {item.state for item in values}

    if states == {AvailabilityState.USABLE}:
        return AvailabilityResult.usable_result(
            "All evaluated capabilities are usable."
        )

    if any(item.usable for item in values):
        return AvailabilityResult(
            AvailabilityState.DEGRADED,
            reason_code="partial_availability",
            diagnostic="Some evaluated capabilities are not fully usable.",
        )

    if AvailabilityState.ERROR in states:
        return AvailabilityResult(
            AvailabilityState.ERROR,
            reason_code="capability_probe_error",
            diagnostic="At least one capability availability probe failed.",
        )

    if states == {AvailabilityState.UNAVAILABLE}:
        return AvailabilityResult(
            AvailabilityState.UNAVAILABLE,
            reason_code="all_capabilities_unavailable",
            diagnostic="All evaluated capabilities are unavailable.",
        )

    return AvailabilityResult(
        AvailabilityState.UNKNOWN,
        reason_code="capability_state_unknown",
        diagnostic="No evaluated capability is usable and readiness is not conclusive.",
    )


__all__ = [
    "AvailabilityProbe",
    "AvailabilityResult",
    "AvailabilityState",
    "aggregate_availability",
    "evaluate_availability_probe",
]
