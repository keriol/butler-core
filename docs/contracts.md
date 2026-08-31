# Butler Core public contracts

This page is a compact map of the public contract families exported by `butler_core` in the 0.2 line.

## Tools

`ToolDefinition` describes an executable tool and its parameters, timeout and `ToolPermission`. `ToolRegistry` owns registration and lookup.

Permissions are explicit:

- `READ`: observation/read-only operation;
- `ACTION`: state-changing operation subject to host policy;
- `DANGEROUS`: elevated operation disabled or confirmed according to execution policy.

## Planner

The planner contracts describe provider-neutral planning boundaries. Core defines the interface and structured results; selection and configuration of a concrete planning provider remain host concerns.

## Resolution

`ResolverDefinition` gives a deterministic resolver a stable name and callable handler.

Resolvers return `ResolutionResult` with one of three states:

- `HANDLED`
- `NOT_HANDLED`
- `ERROR`

`DeterministicResolutionPipeline` runs resolvers in declared order and supports an optional injected fallback. Fallback use is represented explicitly in the returned result.

## Execution

`ExecutionRequest` identifies a registered tool, arguments, confirmation state and execution ID.

`ExecutionEngine`:

1. finds the tool;
2. validates arguments;
3. applies `ExecutionPolicy`;
4. executes the handler with its timeout;
5. returns a structured `ExecutionResult`;
6. emits an optional trace event.

Argument validation supports the JSON-schema-like subset implemented by Core, including primitive types, objects, arrays, required properties, enums and additional-property control.

## Jobs

`JobRequest` represents work completed later and has a generated `job_id`, operation, arguments and metadata.

`JobStatus` includes queued, running, succeeded, failed and cancelled states. `JobResult` exposes terminal/ok helpers and a serializable representation.

`JobStore` and `JobRunner` are protocols, keeping persistence and concrete job execution outside Core.

`JobRequest.with_trace_context()` and `with_current_trace()` allow the originating trace context to be carried through metadata.

## Tracing

`TraceContext` carries `trace_id`, `span_id` and an optional `parent_span_id`.

`TraceEvent` is storage-agnostic and contains:

- component and operation;
- message;
- `TraceLevel`;
- `TraceStatus`;
- `TraceSeverity`;
- optional duration;
- structured scalar attributes.

`Tracer` is the consumer protocol. `NullTracer` disables observability without requiring conditional execution code. `safe_emit()` ensures tracer failures remain observational failures.

`traced_span()` creates correlated child spans and emits a terminal success/error event.

## Domain and capability contributions

`DomainDefinition` declares a provider-neutral domain identity.

`CapabilityDefinition` declares behavior owned by a domain and may include deterministic `ResolverDefinition` entries. Its stable identity is `<domain>.<capability>`.

`PluginDefinition` aggregates a self-contained domain contribution:

- domains;
- capabilities;
- tool-registration callable;
- verification expectations.

The name "plugin" describes the contribution contract only. Core does not provide discovery, a plugin registry, loading or lifecycle management.

`GoalExpectation` declares a deterministic verification expectation associated with a capability and tool.

`validate_plugin_definition()` and `assert_plugin_conforms()` validate structural conformance, including ownership relationships and verification references to tools actually registered by the contribution.

## Output

`OutputRequest` represents provider-neutral output intent with kind and priority. `OutputAdapter` is the concrete-provider boundary.

`OutputDeliveryStatus.ACCEPTED` means dispatch was accepted but not positively verified. `DELIVERED` is reserved for providers that can confirm delivery.

Concrete rendering, provider selection, routing and delivery remain outside Core.
