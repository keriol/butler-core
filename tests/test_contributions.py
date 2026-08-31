from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from butler_core import (
    CapabilityDefinition,
    DomainDefinition,
    GoalExpectation,
    PluginDefinition,
    ResolverDefinition,
    ToolDefinition,
    ToolRegistry,
    assert_plugin_conforms,
    validate_plugin_definition,
)
from butler_core.resolution import ResolutionResult


def _register_echo(registry: ToolRegistry) -> None:
    registry.register(
        ToolDefinition(
            name="echo",
            description="Echo text.",
            handler=lambda text: text,
        )
    )


def _resolve_echo(request: object) -> ResolutionResult:
    return ResolutionResult.handled_result(request)


def test_domain_and_capability_have_stable_immutable_identity() -> None:
    domain = DomainDefinition(name="media")
    resolver = ResolverDefinition(name="media.search", handler=_resolve_echo)
    capability = CapabilityDefinition(
        name="search",
        domain="media",
        resolvers=(resolver,),
    )

    assert domain.identity == "media"
    assert capability.identity == "media.search"
    assert capability.resolvers == (resolver,)

    with pytest.raises(FrozenInstanceError):
        domain.name = "other"  # type: ignore[misc]


def test_invalid_public_identity_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid domain name"):
        DomainDefinition(name="Media Domain")

    with pytest.raises(ValueError, match="Invalid capability name"):
        CapabilityDefinition(name="Play Media", domain="media")


def test_duplicate_capability_resolvers_are_rejected() -> None:
    resolver = ResolverDefinition(name="media.search", handler=_resolve_echo)

    with pytest.raises(ValueError, match="duplicate resolvers"):
        CapabilityDefinition(
            name="search",
            domain="media",
            resolvers=(resolver, resolver),
        )


def test_plugin_aggregates_and_sorts_declarations() -> None:
    plugin = PluginDefinition(
        name="demo.media",
        register=_register_echo,
        domains=(DomainDefinition(name="system"), DomainDefinition(name="media")),
        capabilities=(
            CapabilityDefinition(name="status", domain="system"),
            CapabilityDefinition(name="search", domain="media"),
        ),
    )

    assert tuple(item.identity for item in plugin.domains) == ("media", "system")
    assert tuple(item.identity for item in plugin.capabilities) == (
        "media.search",
        "system.status",
    )


def test_plugin_rejects_inconsistent_ownership() -> None:
    with pytest.raises(ValueError, match="references undeclared domain"):
        PluginDefinition(
            name="demo.invalid",
            register=_register_echo,
            capabilities=(CapabilityDefinition(name="search", domain="media"),),
        )


def test_plugin_rejects_duplicate_declarations() -> None:
    domain = DomainDefinition(name="media")
    with pytest.raises(ValueError, match="duplicate domains: media"):
        PluginDefinition(
            name="demo.duplicate",
            register=_register_echo,
            domains=(domain, domain),
        )


def test_verification_expectation_must_reference_owned_capability() -> None:
    with pytest.raises(ValueError, match="references undeclared capability"):
        PluginDefinition(
            name="demo.invalid",
            register=_register_echo,
            domains=(DomainDefinition(name="media"),),
            verification=(
                GoalExpectation(
                    identity="demo.invalid.goal",
                    goal="echo hi",
                    capability="media.search",
                    tool_name="echo",
                ),
            ),
        )


def test_conformance_helper_rejects_unknown_tool_reference() -> None:
    plugin = PluginDefinition(
        name="demo.media",
        register=_register_echo,
        domains=(DomainDefinition(name="media"),),
        capabilities=(CapabilityDefinition(name="search", domain="media"),),
        verification=(
            GoalExpectation(
                identity="demo.media.search",
                goal="search media",
                capability="media.search",
                tool_name="missing",
            ),
        ),
    )

    with pytest.raises(ValueError, match="references undeclared tool 'missing'"):
        validate_plugin_definition(plugin)


def test_conformance_helper_accepts_self_contained_plugin() -> None:
    plugin = PluginDefinition(
        name="demo.media",
        register=_register_echo,
        domains=(DomainDefinition(name="media"),),
        capabilities=(CapabilityDefinition(name="search", domain="media"),),
        verification=(
            GoalExpectation(
                identity="demo.media.search",
                goal="search media",
                capability="media.search",
                tool_name="echo",
            ),
        ),
    )

    assert assert_plugin_conforms(plugin) is plugin
