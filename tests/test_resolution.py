import pytest

from butler_core import (
    DeterministicResolutionPipeline,
    ResolutionResult,
    ResolutionStatus,
    ResolverDefinition,
)


def test_first_handled_resolver_wins_in_order() -> None:
    calls: list[str] = []

    def first(request):
        calls.append("first")
        return ResolutionResult.not_handled_result()

    def second(request):
        calls.append("second")
        return ResolutionResult.handled_result(
            {"source": "second"}
        )

    def third(request):
        calls.append("third")
        return ResolutionResult.handled_result(
            {"source": "third"}
        )

    pipeline = DeterministicResolutionPipeline(
        [
            ResolverDefinition("first", first),
            ResolverDefinition("second", second),
            ResolverDefinition("third", third),
        ]
    )

    result = pipeline.resolve("hello")

    assert result.status is ResolutionStatus.HANDLED
    assert result.handled is True
    assert result.resolver_name == "second"
    assert result.value == {"source": "second"}
    assert result.used_fallback is False
    assert calls == ["first", "second"]


def test_all_resolvers_can_decline_request() -> None:
    pipeline = DeterministicResolutionPipeline(
        [
            ResolverDefinition(
                "first",
                lambda request:
                    ResolutionResult.not_handled_result(),
            ),
            ResolverDefinition(
                "second",
                lambda request:
                    ResolutionResult.not_handled_result(),
            ),
        ]
    )

    result = pipeline.resolve("hello")

    assert result.status is ResolutionStatus.NOT_HANDLED
    assert result.handled is False
    assert result.resolver_name is None
    assert result.used_fallback is False


def test_fallback_runs_after_all_resolvers_decline() -> None:
    calls: list[str] = []

    def resolver(request):
        calls.append("resolver")
        return ResolutionResult.not_handled_result()

    def fallback(request):
        calls.append("fallback")
        return ResolutionResult.handled_result(
            {"source": "fallback"}
        )

    pipeline = DeterministicResolutionPipeline(
        [
            ResolverDefinition(
                "deterministic",
                resolver,
            )
        ],
        fallback=fallback,
    )

    result = pipeline.resolve("hello")

    assert result.status is ResolutionStatus.HANDLED
    assert result.value == {"source": "fallback"}
    assert result.used_fallback is True
    assert result.resolver_name is None
    assert calls == ["resolver", "fallback"]


def test_fallback_is_not_called_when_request_is_handled() -> None:
    calls: list[str] = []

    def resolver(request):
        calls.append("resolver")
        return ResolutionResult.handled_result("done")

    def fallback(request):
        calls.append("fallback")
        return ResolutionResult.handled_result(
            "fallback"
        )

    pipeline = DeterministicResolutionPipeline(
        [
            ResolverDefinition(
                "deterministic",
                resolver,
            )
        ],
        fallback=fallback,
    )

    result = pipeline.resolve("hello")

    assert result.value == "done"
    assert result.used_fallback is False
    assert calls == ["resolver"]


def test_resolver_exception_is_structured_and_stops() -> None:
    calls: list[str] = []

    def broken(request):
        calls.append("broken")
        raise RuntimeError("boom")

    def later(request):
        calls.append("later")
        return ResolutionResult.handled_result("later")

    def fallback(request):
        calls.append("fallback")
        return ResolutionResult.handled_result(
            "fallback"
        )

    pipeline = DeterministicResolutionPipeline(
        [
            ResolverDefinition("broken", broken),
            ResolverDefinition("later", later),
        ],
        fallback=fallback,
    )

    result = pipeline.resolve("hello")

    assert result.status is ResolutionStatus.ERROR
    assert result.handled is False
    assert result.resolver_name == "broken"
    assert result.error_code == "resolver_exception"
    assert result.error_message == "boom"
    assert result.used_fallback is False
    assert calls == ["broken"]


def test_invalid_resolver_result_is_structured_error() -> None:
    def invalid(request):
        return {"handled": True}

    pipeline = DeterministicResolutionPipeline(
        [
            ResolverDefinition(
                "invalid",
                invalid,
            )
        ]
    )

    result = pipeline.resolve("hello")

    assert result.status is ResolutionStatus.ERROR
    assert result.resolver_name == "invalid"
    assert result.error_code == "invalid_resolver_result"


def test_fallback_exception_is_structured() -> None:
    def fallback(request):
        raise RuntimeError("fallback boom")

    pipeline = DeterministicResolutionPipeline(
        fallback=fallback,
    )

    result = pipeline.resolve("hello")

    assert result.status is ResolutionStatus.ERROR
    assert result.used_fallback is True
    assert result.error_code == "fallback_exception"
    assert result.error_message == "fallback boom"


def test_invalid_fallback_result_is_structured() -> None:
    def fallback(request):
        return "invalid"

    pipeline = DeterministicResolutionPipeline(
        fallback=fallback,
    )

    result = pipeline.resolve("hello")

    assert result.status is ResolutionStatus.ERROR
    assert result.used_fallback is True
    assert result.error_code == "invalid_fallback_result"


def test_empty_resolver_name_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Resolver name must not be empty",
    ):
        ResolverDefinition(
            "   ",
            lambda request:
                ResolutionResult.not_handled_result(),
        )


def test_request_is_forwarded_unchanged() -> None:
    request = {
        "message": "hello",
        "context": {"room": "kitchen"},
    }

    seen = []

    def resolver(received):
        seen.append(received)
        return ResolutionResult.handled_result("ok")

    pipeline = DeterministicResolutionPipeline(
        [
            ResolverDefinition(
                "capture",
                resolver,
            )
        ]
    )

    pipeline.resolve(request)

    assert seen == [request]
    assert seen[0] is request
