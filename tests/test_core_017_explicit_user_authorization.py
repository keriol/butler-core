from __future__ import annotations

import json

import pytest

from butler_core import (
    ButlerPlanner,
    ToolPlan,
    ToolRegistry,
)


def test_tool_plan_is_unauthorized_by_default() -> None:
    plan = ToolPlan(tool_name="demo")

    assert plan.user_authorized is False


def test_trusted_code_can_construct_authorized_plan() -> None:
    plan = ToolPlan(
        tool_name="demo",
        user_authorized=True,
    )

    assert plan.user_authorized is True


def test_authorization_flag_requires_a_real_bool() -> None:
    with pytest.raises(TypeError, match="user_authorized"):
        ToolPlan(
            tool_name="demo",
            user_authorized=1,  # type: ignore[arg-type]
        )


def test_provider_cannot_self_authorize_plan() -> None:
    payload = {
        "tool_name": None,
        "arguments": {},
        "confidence": 0.0,
        "reason": "No tool required.",
        "user_authorized": True,
    }

    result = ButlerPlanner(
        ToolRegistry(),
        provider=lambda *_: json.dumps(payload),
        system_prompt="Generic.",
    ).plan("do something")

    assert result.ok is True
    assert result.plan is not None
    assert result.plan.user_authorized is False
