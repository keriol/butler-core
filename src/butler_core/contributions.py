from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable, Mapping

from butler_core.models import ToolDefinition
from butler_core.readiness import AvailabilityProbe
from butler_core.registry import ToolRegistry
from butler_core.resolution import ResolverDefinition


_PUBLIC_NAME_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*")


def _validate_public_name(kind: str, value: str) -> None:
    if _PUBLIC_NAME_PATTERN.fullmatch(value) is None:
        raise ValueError(f"Invalid {kind} name: {value!r}")


@dataclass(frozen=True)
class DomainDefinition:
    """Provider-neutral identity and metadata for one Butler domain."""

    name: str
    description: str = ""

    def __post_init__(self) -> None:
        _validate_public_name("domain", self.name)

    @property
    def identity(self) -> str:
        return self.name


@dataclass(frozen=True)
class CapabilityDefinition:
    """Provider-neutral declaration of behavior owned by one domain.

    ``availability_probe`` is optional and observational only. A missing probe
    carries no negative implication; consumers evaluate it as UNKNOWN rather
    than persisting a mutable availability flag.
    """

    name: str
    domain: str
    description: str = ""
    resolvers: tuple[ResolverDefinition, ...] = ()
    availability_probe: AvailabilityProbe | None = None

    def __post_init__(self) -> None:
        _validate_public_name("capability", self.name)
        _validate_public_name("domain", self.domain)

        if self.availability_probe is not None and not callable(
            self.availability_probe
        ):
            raise TypeError("Capability availability_probe must be callable.")

        resolvers = tuple(self.resolvers)
        if not all(isinstance(item, ResolverDefinition) for item in resolvers):
            raise TypeError(
                "Capability resolvers must contain ResolverDefinition values."
            )

        names = [item.name for item in resolvers]
        duplicates = sorted(name for name in set(names) if names.count(name) > 1)
        if duplicates:
            raise ValueError(
                f"Capability {self.identity!r} declares duplicate resolvers: "
                f"{', '.join(duplicates)}"
            )

        object.__setattr__(self, "resolvers", resolvers)

    @property
    def identity(self) -> str:
        return f"{self.domain}.{self.name}"


@dataclass(frozen=True)
class GoalExpectation:
    """Declarative deterministic expectation attached to one capability."""

    identity: str
    goal: str
    capability: str
    tool_name: str
    expected_arguments: Mapping[str, object] | None = None
    expected_value: object | None = None
    verify_value: bool = False

    def __post_init__(self) -> None:
        for field_name, value in (
            ("identity", self.identity),
            ("goal", self.goal),
            ("capability", self.capability),
            ("tool_name", self.tool_name),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} cannot be empty.")

        if self.expected_arguments is not None:
            object.__setattr__(
                self,
                "expected_arguments",
                dict(self.expected_arguments),
            )


PluginRegistrar = Callable[[ToolRegistry], None]


@dataclass(frozen=True)
class PluginDefinition:
    """Provider-neutral declaration contributed by one domain package.

    Discovery, loading and lifecycle deliberately remain runtime concerns.
    ``readiness_probe`` is optional and observational only; hosts own when and
    how it is evaluated, cached or presented.
    """

    name: str
    register: PluginRegistrar
    description: str = ""
    version: str = "0.1.0"
    domains: tuple[DomainDefinition, ...] = ()
    capabilities: tuple[CapabilityDefinition, ...] = ()
    verification: tuple[GoalExpectation, ...] = ()
    readiness_probe: AvailabilityProbe | None = None

    def __post_init__(self) -> None:
        _validate_public_name("plugin", self.name)
        if not self.version.strip():
            raise ValueError("Plugin version cannot be empty.")
        if not callable(self.register):
            raise TypeError("Plugin register must be callable.")
        if self.readiness_probe is not None and not callable(self.readiness_probe):
            raise TypeError("Plugin readiness_probe must be callable.")

        domains = tuple(self.domains)
        capabilities = tuple(self.capabilities)
        verification = tuple(self.verification)

        if not all(isinstance(item, DomainDefinition) for item in domains):
            raise TypeError("Plugin domains must contain DomainDefinition values.")
        if not all(isinstance(item, CapabilityDefinition) for item in capabilities):
            raise TypeError(
                "Plugin capabilities must contain CapabilityDefinition values."
            )
        if not all(isinstance(item, GoalExpectation) for item in verification):
            raise TypeError(
                "Plugin verification must contain GoalExpectation values."
            )

        _reject_duplicate_identities(self.name, "domains", domains)
        _reject_duplicate_identities(self.name, "capabilities", capabilities)
        _reject_duplicate_identities(
            self.name,
            "verification expectations",
            verification,
        )

        owned_domains = {item.identity for item in domains}
        owned_capabilities = {item.identity for item in capabilities}

        for capability in capabilities:
            if capability.domain not in owned_domains:
                raise ValueError(
                    f"Plugin {self.name!r} capability {capability.identity!r} "
                    f"references undeclared domain {capability.domain!r}."
                )

        for expectation in verification:
            if expectation.capability not in owned_capabilities:
                raise ValueError(
                    f"Plugin {self.name!r} verification expectation "
                    f"{expectation.identity!r} references undeclared capability "
                    f"{expectation.capability!r}."
                )

        object.__setattr__(
            self,
            "domains",
            tuple(sorted(domains, key=lambda item: item.identity)),
        )
        object.__setattr__(
            self,
            "capabilities",
            tuple(sorted(capabilities, key=lambda item: item.identity)),
        )
        object.__setattr__(
            self,
            "verification",
            tuple(sorted(verification, key=lambda item: item.identity)),
        )


def _reject_duplicate_identities(
    plugin_name: str,
    kind: str,
    values: tuple[object, ...],
) -> None:
    identities = [getattr(item, "identity") for item in values]
    duplicates = sorted(
        identity
        for identity in set(identities)
        if identities.count(identity) > 1
    )
    if duplicates:
        raise ValueError(
            f"Plugin {plugin_name!r} declares duplicate {kind}: "
            f"{', '.join(duplicates)}"
        )


def validate_plugin_definition(plugin: PluginDefinition) -> None:
    """Validate cross-reference conformance not requiring a host runtime."""

    declared_tools: set[str] = set()

    class RecordingRegistry(ToolRegistry):
        def register(self, tool: ToolDefinition) -> None:
            super().register(tool)
            declared_tools.add(tool.name)

    recording_registry = RecordingRegistry()
    plugin.register(recording_registry)

    for expectation in plugin.verification:
        if expectation.tool_name not in declared_tools:
            raise ValueError(
                f"Plugin {plugin.name!r} verification expectation "
                f"{expectation.identity!r} references undeclared tool "
                f"{expectation.tool_name!r}."
            )


def assert_plugin_conforms(plugin: PluginDefinition) -> PluginDefinition:
    """Reusable testkit helper returning the validated declaration."""

    validate_plugin_definition(plugin)
    return plugin


__all__ = [
    "CapabilityDefinition",
    "DomainDefinition",
    "GoalExpectation",
    "PluginDefinition",
    "PluginRegistrar",
    "assert_plugin_conforms",
    "validate_plugin_definition",
]
