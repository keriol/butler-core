# Butler Core architecture

Butler Core is the lowest reusable layer of the Butler architecture. Its job is to provide stable, provider-neutral contracts and small execution primitives that higher-level runtimes can compose.

## Ownership boundary

Core owns contracts and behavior that remain meaningful without knowing which runtime, frontend, integration or provider is using them.

Core owns:

- tool definitions, permissions and registration;
- provider-neutral planner interfaces;
- deterministic request-resolution contracts and pipeline behavior;
- validated and policy-governed tool execution;
- asynchronous job request/result boundaries;
- structured trace context and events;
- domain, capability and contribution declarations;
- provider-neutral output requests and delivery results.

Core does not own:

- plugin discovery, loading or lifecycle;
- conversation/application routing;
- concrete domain behavior;
- Home Assistant, Alexa or other service integrations;
- AI-provider configuration;
- UI or frontend rendering;
- logging, trace storage or trace viewers;
- concrete notification, speech, sound or display providers;
- deployment configuration or household-specific behavior.

This boundary is intentional. A higher-level runtime should be able to depend on Core without Core importing that runtime or its providers.

## Composition model

A typical host composes the contracts in roughly this direction:

1. Domain packages declare domains, capabilities, deterministic resolvers and tools.
2. A runtime discovers or otherwise loads those packages and registers their tools.
3. Ordered deterministic resolvers attempt to resolve a request.
4. A host-provided fallback may handle unresolved requests.
5. Resolved tool calls pass through argument validation and execution policy.
6. Work that continues asynchronously can be represented as jobs.
7. Output is handed to a provider through output contracts owned outside Core.
8. Trace context can correlate those boundaries without coupling Core to a logging backend.

The sequence is compositional, not a mandatory application framework. Core intentionally leaves orchestration choices to the host runtime.

## Deterministic resolution

`DeterministicResolutionPipeline` evaluates `ResolverDefinition` entries in order. `NOT_HANDLED` continues to the next resolver. `HANDLED` terminates resolution. Resolver failures become structured `ERROR` results and do not silently fall through.

If no deterministic resolver handles the request, the host may inject a fallback implementing the same resolver contract. Core does not define whether that fallback is an AI planner, another deterministic subsystem or something else.

## Execution and policy

`ExecutionEngine` resolves a registered tool, validates its arguments, applies permission policy and invokes its handler.

`ExecutionPolicy` keeps confirmation and dangerous-operation policy explicit. The engine produces structured result states such as success, confirmation required, denied, invalid arguments, tool not found, timeout and error.

Execution uses a copied Python context when invoking a tool in its worker thread, preserving context variables such as Butler trace context across that boundary.

## Asynchronous jobs

`JobRequest` and `JobResult` define provider-neutral asynchronous work and lifecycle state. `JobStore` and `JobRunner` are protocols: storage and execution implementations remain outside Core.

A job request can carry serialized `TraceContext` metadata, allowing a runtime to link later asynchronous work to the originating Butler operation.

## Tracing

Tracing is an observability contract, not a logging implementation.

`TraceContext` provides trace/span correlation. `TraceEvent` contains structured component, operation, status, severity, duration and safe scalar attributes. `Tracer` is the consumer protocol and `NullTracer` is the no-op default.

Trace emission is fail-safe: an external tracer failure does not become an execution failure. Core also defines ordered trace levels so hosts can choose their retained verbosity.

## Domain contributions

`PluginDefinition` is a declaration contributed by a domain package, not a runtime plugin loader. It can aggregate:

- `DomainDefinition` values;
- `CapabilityDefinition` values;
- capability-owned deterministic `ResolverDefinition` values;
- a callable that registers tools into `ToolRegistry`;
- `GoalExpectation` verification declarations.

Core validates ownership and references and provides reusable conformance helpers. Runtime discovery, loading, lifecycle and verification execution deliberately remain outside Core.
