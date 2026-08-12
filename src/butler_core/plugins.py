from __future__ import annotations

from typing import Protocol


class ButlerPlugin(Protocol):
    """Structural contract for a Butler subsystem plugin."""

    @property
    def name(self) -> str:
        ...

    @property
    def capabilities(self) -> frozenset[str]:
        ...


class PluginRegistry:
    """Deterministic registry for Butler subsystem plugins."""

    def __init__(self) -> None:
        self._plugins: dict[str, ButlerPlugin] = {}

    def register(
        self,
        plugin: ButlerPlugin,
    ) -> None:
        name = plugin.name.strip()

        if not name:
            raise ValueError(
                "Plugin name cannot be empty."
            )

        if name in self._plugins:
            raise ValueError(
                f"Plugin already registered: {name}"
            )

        self._plugins[name] = plugin

    def get(
        self,
        name: str,
    ) -> ButlerPlugin | None:
        return self._plugins.get(name)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._plugins))

    def list_plugins(
        self,
    ) -> tuple[ButlerPlugin, ...]:
        return tuple(
            self._plugins[name]
            for name in sorted(self._plugins)
        )

    def plugins_for(
        self,
        capability: str,
    ) -> tuple[ButlerPlugin, ...]:
        return tuple(
            plugin
            for plugin in self.list_plugins()
            if capability in plugin.capabilities
        )
