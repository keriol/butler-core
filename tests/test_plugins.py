from dataclasses import dataclass

import pytest

from butler_core.plugins import (
    ButlerPlugin,
    PluginRegistry,
)


@dataclass
class FakePlugin:
    name: str
    capabilities: frozenset[str]


def test_structural_plugin_contract() -> None:
    plugin: ButlerPlugin = FakePlugin(
        name="sample",
        capabilities=frozenset({
            "output.dispatch",
        }),
    )

    assert plugin.name == "sample"
    assert plugin.capabilities == frozenset({
        "output.dispatch",
    })


def test_registry_round_trip() -> None:
    registry = PluginRegistry()

    plugin = FakePlugin(
        name="sample",
        capabilities=frozenset({
            "output.dispatch",
        }),
    )

    registry.register(plugin)

    assert registry.get("sample") is plugin
    assert registry.names() == ("sample",)
    assert registry.list_plugins() == (plugin,)


def test_registry_names_are_deterministic() -> None:
    registry = PluginRegistry()

    registry.register(
        FakePlugin(
            name="zeta",
            capabilities=frozenset(),
        )
    )
    registry.register(
        FakePlugin(
            name="alpha",
            capabilities=frozenset(),
        )
    )

    assert registry.names() == (
        "alpha",
        "zeta",
    )

    assert tuple(
        plugin.name
        for plugin in registry.list_plugins()
    ) == (
        "alpha",
        "zeta",
    )


def test_registry_rejects_duplicate_name() -> None:
    registry = PluginRegistry()

    registry.register(
        FakePlugin(
            name="sample",
            capabilities=frozenset(),
        )
    )

    with pytest.raises(
        ValueError,
        match="Plugin already registered: sample",
    ):
        registry.register(
            FakePlugin(
                name="sample",
                capabilities=frozenset({
                    "other",
                }),
            )
        )


def test_registry_rejects_empty_name() -> None:
    registry = PluginRegistry()

    with pytest.raises(
        ValueError,
        match="Plugin name cannot be empty",
    ):
        registry.register(
            FakePlugin(
                name="   ",
                capabilities=frozenset(),
            )
        )


def test_registry_discovers_plugins_by_capability() -> None:
    registry = PluginRegistry()

    output = FakePlugin(
        name="output",
        capabilities=frozenset({
            "output.dispatch",
        }),
    )

    media = FakePlugin(
        name="media",
        capabilities=frozenset({
            "media.resolve",
        }),
    )

    multi = FakePlugin(
        name="multi",
        capabilities=frozenset({
            "media.resolve",
            "output.dispatch",
        }),
    )

    registry.register(output)
    registry.register(media)
    registry.register(multi)

    assert registry.plugins_for(
        "output.dispatch"
    ) == (
        multi,
        output,
    )


def test_missing_plugin_returns_none() -> None:
    registry = PluginRegistry()

    assert registry.get("missing") is None


def test_plugin_contract_is_exported_from_package() -> None:
    from butler_core import (
        ButlerPlugin as PublicButlerPlugin,
        PluginRegistry as PublicPluginRegistry,
    )

    assert PublicButlerPlugin is ButlerPlugin
    assert PublicPluginRegistry is PluginRegistry
