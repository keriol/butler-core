from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from time import monotonic_ns
from typing import Any, Protocol

from butler_core.execution import validate_arguments
from butler_core.registry import ToolRegistry


class PlannerProvider(Protocol):
    def __call__(
        self,
        message: str,
        system_prompt: str,
        tools: list[dict[str, Any]],
    ) -> str:
        ...


class PlannerStatus(str, Enum):
    SUCCESS = "success"
    DISABLED = "disabled"
    PROVIDER_ERROR = "provider_error"
    INVALID_RESPONSE = "invalid_response"
    UNKNOWN_TOOL = "unknown_tool"
    INVALID_ARGUMENTS = "invalid_arguments"


@dataclass(frozen=True)
class ToolPlan:
    tool_name: str | None
    arguments: Mapping[str, Any] = field(
        default_factory=dict
    )
    confidence: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class PlannerResult:
    status: PlannerStatus
    duration_ms: float
    plan: ToolPlan | None = None
    model: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    validation_errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status is PlannerStatus.SUCCESS


class ButlerPlanner:
    def __init__(
        self,
        registry: ToolRegistry,
        *,
        provider: PlannerProvider,
        system_prompt: str,
        model: str | None = None,
        enabled: bool = True,
    ) -> None:
        self._registry = registry
        self._provider = provider
        self._system_prompt = system_prompt.strip()
        self._model = model
        self._enabled = enabled

    def is_available(self) -> bool:
        return self._enabled

    def describe_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "category": tool.category,
                "permission": tool.permission.value,
                "parameters": tool.parameters,
            }
            for tool in self._registry.list_tools()
        ]

    def plan(self, message: str) -> PlannerResult:
        started = monotonic_ns()

        if not self.is_available():
            return self._result(
                started,
                PlannerStatus.DISABLED,
                error_code="planner_disabled",
                error_message="Planner is disabled.",
            )

        try:
            raw_response = self._provider(
                message,
                self._system_prompt,
                self.describe_tools(),
            )
        except Exception as exc:
            return self._result(
                started,
                PlannerStatus.PROVIDER_ERROR,
                error_code="provider_error",
                error_message=str(exc),
            )

        if not isinstance(raw_response, str):
            return self._result(
                started,
                PlannerStatus.INVALID_RESPONSE,
                error_code="non_string_response",
                error_message=(
                    "Planner provider must return a string."
                ),
            )

        try:
            payload = json.loads(raw_response.strip())
        except json.JSONDecodeError:
            return self._result(
                started,
                PlannerStatus.INVALID_RESPONSE,
                error_code="invalid_json",
                error_message=(
                    "Planner provider returned invalid JSON."
                ),
            )

        parsed = self._parse_plan(payload)

        if isinstance(parsed, PlannerResult):
            return self._result(
                started,
                parsed.status,
                error_code=parsed.error_code,
                error_message=parsed.error_message,
            )

        if parsed.tool_name is None:
            return self._result(
                started,
                PlannerStatus.SUCCESS,
                plan=parsed,
            )

        tool = self._registry.get(parsed.tool_name)

        if tool is None:
            return self._result(
                started,
                PlannerStatus.UNKNOWN_TOOL,
                error_code="unknown_tool",
                error_message=(
                    f"Tool not registered: {parsed.tool_name}"
                ),
            )

        errors = validate_arguments(
            tool,
            parsed.arguments,
        )

        if errors:
            return self._result(
                started,
                PlannerStatus.INVALID_ARGUMENTS,
                error_code="invalid_arguments",
                error_message=(
                    "Planned arguments failed validation."
                ),
                validation_errors=errors,
            )

        return self._result(
            started,
            PlannerStatus.SUCCESS,
            plan=parsed,
        )

    def _parse_plan(
        self,
        payload: Any,
    ) -> ToolPlan | PlannerResult:
        if not isinstance(payload, dict):
            return self._invalid(
                "non_object_response",
                "Planner response must be a JSON object.",
            )

        required = {
            "tool_name",
            "arguments",
            "confidence",
            "reason",
        }

        missing = sorted(required - payload.keys())

        if missing:
            return self._invalid(
                "missing_fields",
                "Missing fields: " + ", ".join(missing),
            )

        tool_name = payload["tool_name"]
        arguments = payload["arguments"]
        confidence = payload["confidence"]
        reason = payload["reason"]

        if (
            tool_name is not None
            and not isinstance(tool_name, str)
        ):
            return self._invalid(
                "invalid_tool_name",
                "tool_name must be a string or null.",
            )

        if not isinstance(arguments, dict):
            return self._invalid(
                "invalid_arguments_type",
                "arguments must be a JSON object.",
            )

        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1
        ):
            return self._invalid(
                "invalid_confidence",
                "confidence must be between 0 and 1.",
            )

        if not isinstance(reason, str):
            return self._invalid(
                "invalid_reason",
                "reason must be a string.",
            )

        if tool_name is None and arguments:
            return self._invalid(
                "arguments_without_tool",
                "arguments must be empty without a tool.",
            )

        return ToolPlan(
            tool_name=tool_name,
            arguments=arguments,
            confidence=float(confidence),
            reason=reason,
        )

    @staticmethod
    def _invalid(
        code: str,
        message: str,
    ) -> PlannerResult:
        return PlannerResult(
            status=PlannerStatus.INVALID_RESPONSE,
            duration_ms=0.0,
            error_code=code,
            error_message=message,
        )

    def _result(
        self,
        started: int,
        status: PlannerStatus,
        *,
        plan: ToolPlan | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        validation_errors: tuple[str, ...] = (),
    ) -> PlannerResult:
        return PlannerResult(
            status=status,
            duration_ms=round(
                (monotonic_ns() - started) / 1_000_000,
                3,
            ),
            plan=plan,
            model=self._model,
            error_code=error_code,
            error_message=error_message,
            validation_errors=validation_errors,
        )
