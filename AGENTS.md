# Agent entrypoint

Butler Core owns provider-neutral contracts and execution foundations.

## Read before feature design

Use the public Butler documentation hub in `keriol/Iot-home-automation` as the
canonical ecosystem map:

1. `docs/agent/index.md`
2. `docs/agent/source-of-truth.md`
3. `docs/agent/feature-design.md`
4. relevant API/architecture/ADR/milestone pages



## This repository owns

- tool/registry contracts;
- deterministic resolution contracts;
- execution and policy primitives;
- async job contracts;
- tracing contracts;
- domain/capability contribution contracts;

## This repository does not own

- client transport;
- cross-Butler routing;
- Butler identity;
- Home Assistant integration;
- runtime plugin loading;
- frontend rendering;

## Sources of truth

- GitHub Issues: tasks, priorities, dependencies and active status;
- this repository's `main`: merged implementation and versioned local docs;
- tags/releases/workflows: release evidence;
- live systems: deployed/runtime behavior.

Do not infer release or runtime state from this file.

## Development rule

Before proposing code:

1. identify the owning layer;
2. search existing issues and PRs;
3. define interfaces, failure semantics and public/private scope;
4. define tests and E2E/observable evidence where relevant;
5. follow Issue -> branch -> commit -> main -> close.

Keep this file short. Full architecture belongs in canonical docs, not here.
