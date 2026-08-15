from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Protocol


class ResolutionStatus(str, Enum):
    HANDLED = "handled"
    NOT_HANDLED = "not_handled"
    ERROR = "error"


@dataclass(frozen=True)
class ResolutionResult:
    status: ResolutionStatus
    value: Any = None
    resolver_name: str | None = None
    used_fallback: bool = False
    error_code: str | None = None
    error_message: str | None = None

    @property
    def handled(self) -> bool:
        return self.status is ResolutionStatus.HANDLED

    @classmethod
    def handled_result(
        cls,
        value: Any = None,
    ) -> ResolutionResult:
        return cls(
            status=ResolutionStatus.HANDLED,
            value=value,
        )

    @classmethod
    def not_handled_result(
        cls,
    ) -> ResolutionResult:
        return cls(
            status=ResolutionStatus.NOT_HANDLED,
        )


class RequestResolver(Protocol):
    def __call__(
        self,
        request: Any,
        /,
    ) -> ResolutionResult:
        ...


@dataclass(frozen=True)
class ResolverDefinition:
    name: str
    handler: RequestResolver

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError(
                "Resolver name must not be empty."
            )

        if not callable(self.handler):
            raise TypeError(
                "Resolver handler must be callable."
            )


class DeterministicResolutionPipeline:
    """
    Resolve requests through ordered deterministic resolvers.

    The first resolver returning HANDLED wins.

    NOT_HANDLED continues to the next resolver. If every resolver
    declines the request, an optional injected fallback is invoked.

    Butler Core does not know whether the fallback is an AI planner,
    another deterministic mechanism, or any other implementation.

    Resolver failures are returned as structured ERROR results and
    do not silently fall through to another resolver or fallback.
    """

    def __init__(
        self,
        resolvers: Iterable[ResolverDefinition] = (),
        *,
        fallback: RequestResolver | None = None,
    ) -> None:
        self._resolvers = tuple(resolvers)
        self._fallback = fallback

    def resolve(
        self,
        request: Any,
    ) -> ResolutionResult:
        for resolver in self._resolvers:
            result = self._call_resolver(
                resolver,
                request,
            )

            if result.status is ResolutionStatus.NOT_HANDLED:
                continue

            return result

        if self._fallback is None:
            return ResolutionResult.not_handled_result()

        return self._call_fallback(request)

    def _call_resolver(
        self,
        resolver: ResolverDefinition,
        request: Any,
    ) -> ResolutionResult:
        try:
            result = resolver.handler(request)
        except Exception as exc:
            return ResolutionResult(
                status=ResolutionStatus.ERROR,
                resolver_name=resolver.name,
                error_code="resolver_exception",
                error_message=str(exc),
            )

        if not isinstance(result, ResolutionResult):
            return ResolutionResult(
                status=ResolutionStatus.ERROR,
                resolver_name=resolver.name,
                error_code="invalid_resolver_result",
                error_message=(
                    "Resolver must return ResolutionResult."
                ),
            )

        return replace(
            result,
            resolver_name=resolver.name,
            used_fallback=False,
        )

    def _call_fallback(
        self,
        request: Any,
    ) -> ResolutionResult:
        assert self._fallback is not None

        try:
            result = self._fallback(request)
        except Exception as exc:
            return ResolutionResult(
                status=ResolutionStatus.ERROR,
                used_fallback=True,
                error_code="fallback_exception",
                error_message=str(exc),
            )

        if not isinstance(result, ResolutionResult):
            return ResolutionResult(
                status=ResolutionStatus.ERROR,
                used_fallback=True,
                error_code="invalid_fallback_result",
                error_message=(
                    "Fallback must return ResolutionResult."
                ),
            )

        return replace(
            result,
            used_fallback=True,
        )
