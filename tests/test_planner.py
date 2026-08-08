from __future__ import annotations

import json
import unittest

from butler_core.models import (
    ToolDefinition,
    ToolPermission,
)
from butler_core.planner import (
    ButlerPlanner,
    PlannerStatus,
)
from butler_core.registry import ToolRegistry


def make_registry(
    *,
    handler=None,
) -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(
        ToolDefinition(
            name="echo",
            description="Echo a message.",
            handler=handler or (
                lambda message: message
            ),
            parameters={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                    },
                },
                "required": ["message"],
                "additionalProperties": False,
            },
            category="test",
            permission=ToolPermission.READ,
        )
    )

    return registry


def provider_response(
    *,
    tool_name="echo",
    arguments=None,
    confidence=0.9,
    reason="Direct match.",
) -> str:
    if arguments is None:
        arguments = {"message": "hello"}

    return json.dumps(
        {
            "tool_name": tool_name,
            "arguments": arguments,
            "confidence": confidence,
            "reason": reason,
        }
    )


class ButlerPlannerTests(unittest.TestCase):
    def test_disabled_planner_does_not_call_provider(
        self,
    ) -> None:
        called = False

        def provider(*_args):
            nonlocal called
            called = True
            return provider_response()

        result = ButlerPlanner(
            ToolRegistry(),
            provider=provider,
            system_prompt="Generic.",
            enabled=False,
        ).plan("hello")

        self.assertFalse(result.ok)
        self.assertEqual(
            result.status,
            PlannerStatus.DISABLED,
        )
        self.assertFalse(called)

    def test_valid_plan_is_returned(self) -> None:
        result = ButlerPlanner(
            make_registry(),
            provider=lambda *_: provider_response(),
            system_prompt="Generic.",
            model="test-model",
        ).plan("say hello")

        self.assertTrue(result.ok)
        self.assertEqual(
            result.status,
            PlannerStatus.SUCCESS,
        )
        self.assertEqual(
            result.plan.tool_name,
            "echo",
        )
        self.assertEqual(
            result.plan.arguments,
            {"message": "hello"},
        )
        self.assertEqual(
            result.plan.confidence,
            0.9,
        )
        self.assertEqual(
            result.plan.reason,
            "Direct match.",
        )
        self.assertEqual(
            result.model,
            "test-model",
        )

    def test_tool_description_exposes_contract(
        self,
    ) -> None:
        planner = ButlerPlanner(
            make_registry(),
            provider=lambda *_: provider_response(),
            system_prompt="Generic.",
        )

        tool = planner.describe_tools()[0]

        self.assertEqual(tool["name"], "echo")
        self.assertEqual(
            tool["description"],
            "Echo a message.",
        )
        self.assertEqual(tool["category"], "test")
        self.assertEqual(
            tool["permission"],
            "READ",
        )
        self.assertIn(
            "properties",
            tool["parameters"],
        )
        self.assertNotIn("handler", tool)

    def test_no_tool_is_valid(self) -> None:
        result = ButlerPlanner(
            ToolRegistry(),
            provider=lambda *_: provider_response(
                tool_name=None,
                arguments={},
                confidence=0.0,
                reason="No match.",
            ),
            system_prompt="Generic.",
        ).plan("unsupported")

        self.assertTrue(result.ok)
        self.assertIsNone(result.plan.tool_name)
        self.assertEqual(result.plan.arguments, {})

    def test_invalid_json_is_rejected(self) -> None:
        result = ButlerPlanner(
            ToolRegistry(),
            provider=lambda *_: "not json",
            system_prompt="Generic.",
        ).plan("hello")

        self.assertEqual(
            result.status,
            PlannerStatus.INVALID_RESPONSE,
        )
        self.assertEqual(
            result.error_code,
            "invalid_json",
        )

    def test_unknown_tool_is_rejected(self) -> None:
        result = ButlerPlanner(
            ToolRegistry(),
            provider=lambda *_: provider_response(
                tool_name="ghost",
            ),
            system_prompt="Generic.",
        ).plan("hello")

        self.assertEqual(
            result.status,
            PlannerStatus.UNKNOWN_TOOL,
        )
        self.assertEqual(
            result.error_code,
            "unknown_tool",
        )

    def test_invalid_arguments_use_core_validator(
        self,
    ) -> None:
        result = ButlerPlanner(
            make_registry(),
            provider=lambda *_: provider_response(
                arguments={"message": 42},
            ),
            system_prompt="Generic.",
        ).plan("hello")

        self.assertEqual(
            result.status,
            PlannerStatus.INVALID_ARGUMENTS,
        )
        self.assertTrue(
            any(
                "expected string" in error
                for error in result.validation_errors
            )
        )

    def test_planner_never_executes_handler(
        self,
    ) -> None:
        calls = 0

        def handler(message):
            nonlocal calls
            calls += 1
            return message

        result = ButlerPlanner(
            make_registry(handler=handler),
            provider=lambda *_: provider_response(),
            system_prompt="Generic.",
        ).plan("hello")

        self.assertTrue(result.ok)
        self.assertEqual(calls, 0)

    def test_provider_failure_is_structured(
        self,
    ) -> None:
        def provider(*_args):
            raise RuntimeError("provider offline")

        result = ButlerPlanner(
            ToolRegistry(),
            provider=provider,
            system_prompt="Generic.",
        ).plan("hello")

        self.assertEqual(
            result.status,
            PlannerStatus.PROVIDER_ERROR,
        )
        self.assertEqual(
            result.error_code,
            "provider_error",
        )
        self.assertIn(
            "provider offline",
            result.error_message,
        )

    def test_invalid_confidence_is_rejected(
        self,
    ) -> None:
        for confidence in (-0.1, 1.1, True, "high"):
            with self.subTest(confidence=confidence):
                result = ButlerPlanner(
                    ToolRegistry(),
                    provider=lambda *_, c=confidence: (
                        provider_response(
                            tool_name=None,
                            arguments={},
                            confidence=c,
                        )
                    ),
                    system_prompt="Generic.",
                ).plan("hello")

                self.assertEqual(
                    result.error_code,
                    "invalid_confidence",
                )


    def test_non_object_response_is_rejected(
        self,
    ) -> None:
        result = ButlerPlanner(
            ToolRegistry(),
            provider=lambda *_: "[]",
            system_prompt="Generic.",
        ).plan("hello")

        self.assertEqual(
            result.status,
            PlannerStatus.INVALID_RESPONSE,
        )
        self.assertEqual(
            result.error_code,
            "non_object_response",
        )

    def test_missing_fields_are_rejected(
        self,
    ) -> None:
        result = ButlerPlanner(
            ToolRegistry(),
            provider=lambda *_: json.dumps(
                {"tool_name": None}
            ),
            system_prompt="Generic.",
        ).plan("hello")

        self.assertEqual(
            result.status,
            PlannerStatus.INVALID_RESPONSE,
        )
        self.assertEqual(
            result.error_code,
            "missing_fields",
        )

    def test_arguments_without_tool_are_rejected(
        self,
    ) -> None:
        result = ButlerPlanner(
            ToolRegistry(),
            provider=lambda *_: provider_response(
                tool_name=None,
                arguments={"message": "hello"},
                confidence=0.0,
            ),
            system_prompt="Generic.",
        ).plan("hello")

        self.assertEqual(
            result.status,
            PlannerStatus.INVALID_RESPONSE,
        )
        self.assertEqual(
            result.error_code,
            "arguments_without_tool",
        )

    def test_non_string_provider_response_is_rejected(
        self,
    ) -> None:
        result = ButlerPlanner(
            ToolRegistry(),
            provider=lambda *_: {},
            system_prompt="Generic.",
        ).plan("hello")

        self.assertEqual(
            result.status,
            PlannerStatus.INVALID_RESPONSE,
        )
        self.assertEqual(
            result.error_code,
            "non_string_response",
        )


if __name__ == "__main__":
    unittest.main()
