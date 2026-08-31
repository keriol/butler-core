# Butler Core

Butler Core is the provider-neutral foundation shared by Butler runtimes.

It defines the contracts for describing tools, resolving requests, executing operations, representing asynchronous work, emitting structured traces, declaring reusable domain capabilities, and handing output to external delivery providers.

Core deliberately does **not** own application routing, plugin discovery, concrete integrations, AI providers, user interfaces, delivery providers, or deployment-specific behavior. Higher-level runtimes compose Core contracts without becoming dependencies of Core.

## Install

Published releases provide a Python wheel and source distribution on the GitHub Releases page. Download the wheel for the desired version and install it locally:

```bash
python -m pip install ./butler_core-0.2.0-py3-none-any.whl
```

Python 3.10 or newer is required.

## Public contract families

Butler Core 0.2 exposes these main contract families:

- **Tools and registry**: `ToolPermission`, `ToolDefinition`, `ToolRegistry`
- **Planning**: `ButlerPlanner`, `PlannerProvider`, `PlannerResult`, `PlannerStatus`, `ToolPlan`
- **Deterministic resolution**: `ResolverDefinition`, `RequestResolver`, `ResolutionResult`, `ResolutionStatus`, `DeterministicResolutionPipeline`
- **Execution**: `ExecutionRequest`, `ExecutionResult`, `ExecutionStatus`, `ExecutionPolicy`, `ExecutionEngine`
- **Asynchronous jobs**: `JobRequest`, `JobResult`, `JobStatus`, `JobStore`, `JobRunner`
- **Tracing**: `TraceContext`, `TraceEvent`, `TraceLevel`, `TraceStatus`, `TraceSeverity`, `Tracer`, `NullTracer`
- **Domain contributions**: `DomainDefinition`, `CapabilityDefinition`, `PluginDefinition`, `GoalExpectation` and conformance helpers
- **Output**: `OutputRequest`, `OutputKind`, `OutputPriority`, `OutputAdapter`, `OutputDeliveryStatus`, `OutputDeliveryResult`

See [Architecture](docs/architecture.md) for ownership boundaries and [Public contracts](docs/contracts.md) for how these families compose.

## Design principles

### Provider neutral

Core models behavior and boundaries, not concrete services. A tool may eventually call Home Assistant, another home-automation platform, a local process, a cloud API or something else entirely; Core does not need to know.

The public [Home Assistant Plugin](https://github.com/keriol/home-assistant-plugin) is a useful ecosystem example of this rule. Home Assistant-specific authentication, transport, state reads and actions belong in that plugin, while Core keeps only reusable contracts. The same architecture is intended to allow another home-automation manager to be integrated by implementing another plugin rather than by adding platform-specific concepts to Core.

The Home Assistant Plugin was initially created as a real proving example around Wilfred and is now being evolved toward a consumer-neutral Butler plugin that can be consumed independently by sibling runtimes. That ongoing migration is implementation work outside Core; this README does not claim it is already part of the current Core 0.2 release contract.

### Deterministic before fallback

`DeterministicResolutionPipeline` runs ordered deterministic resolvers first. The first resolver that returns `HANDLED` wins. An optional fallback can be injected by the host, but Core makes no assumption that the fallback is AI-backed.

### Policy before execution

`ExecutionEngine` validates tool arguments and applies permission policy before invoking a tool. `READ`, `ACTION` and `DANGEROUS` operations remain explicit contracts rather than frontend conventions.

### Observable boundaries

Tracing is optional and storage-agnostic. Trace context can cross execution and asynchronous-job boundaries while tracer failures are prevented from changing execution outcomes.

### Domains declare, runtimes host

Domain packages can declare domains, capabilities, deterministic resolvers, tools and verification expectations through Core contracts. Discovery, loading, lifecycle and runtime verification remain responsibilities of higher-level runtimes.

A reusable integration package can therefore be shared by more than one runtime without making those runtimes depend on each other. The intended dependency shape is contracts downward, composition upward:

```text
              Butler Core
              /         \
        Runtime A     Runtime B
              \         /
          reusable plugin
```

The concrete loader/registry topology belongs to the runtimes and plugins involved, not to Core itself.

## Output semantics

Core defines output delivery contracts without owning speech, notification, sound or display providers.

For asynchronous providers, `OutputDeliveryStatus.ACCEPTED` means the provider accepted the dispatch request but delivery has not been positively verified. `DELIVERED` is reserved for delivery an adapter can confirm.

## Project status

Butler Core is pre-1.0. The 0.2 line establishes the shared execution, observability and domain-contribution baseline intended for reuse by Butler runtimes.

Release-specific changes are documented under [`docs/releases/`](docs/releases/).
