from __future__ import annotations

from butler_core import (
    ToolDefinition,
    ToolPermission,
    ToolRegistry,
)


def test_tool_definition_defaults() -> None:
    tool = ToolDefinition(
        name="status",
        description="Return status.",
        handler=lambda: {"ok": True},
    )

    assert tool.category == "general"
    assert tool.permission is ToolPermission.READ
    assert tool.timeout_seconds == 10
    assert tool.parameters == {}


def test_registry_round_trip() -> None:
    registry = ToolRegistry()
    tool = ToolDefinition(
        name="status",
        description="Return status.",
        handler=lambda: {"ok": True},
    )

    registry.register(tool)

    assert registry.get("status") is tool
    assert registry.list_tools() == [tool]
    assert registry.names() == ["status"]


def test_registry_missing_tool() -> None:
    registry = ToolRegistry()

    assert registry.get("missing") is None


def test_duplicate_registration_is_rejected() -> None:
    registry = ToolRegistry()
    tool = ToolDefinition(
        name="status",
        description="Return status.",
        handler=lambda: None,
    )

    registry.register(tool)

    try:
        registry.register(tool)
    except ValueError as exc:
        assert str(exc) == "Tool already registered: status"
    else:
        raise AssertionError("duplicate tool registration accepted")


def test_permissions_are_stable_string_values() -> None:
    assert ToolPermission.READ.value == "READ"
    assert ToolPermission.ACTION.value == "ACTION"
    assert ToolPermission.DANGEROUS.value == "DANGEROUS"
