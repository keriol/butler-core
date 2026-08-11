# Butler Core

Butler Core provides the small, provider-neutral runtime contracts shared by
Butler implementations.

The initial public surface contains:

- `ToolPermission`
- `ToolDefinition`
- `ToolRegistry`

Butler Core does not own device integrations, application routing, AI provider
configuration, user interfaces, or deployment-specific behavior.

The core is intentionally small. Higher-level runtimes build on these
contracts rather than becoming dependencies of the core.

## Output contracts

Butler Core defines provider-neutral contracts for delivering output without
owning a concrete speech, notification, sound or display provider.

The public output surface includes:

- `OutputKind`
- `OutputPriority`
- `OutputRequest`
- `OutputAdapter`
- `OutputDeliveryStatus`
- `OutputDeliveryResult`

Applications and integrations own rendering, routing and concrete delivery.
Butler Core does not depend on a device platform, voice system or transport.
