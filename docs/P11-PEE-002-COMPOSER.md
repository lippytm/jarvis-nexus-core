# P11-PEE-002 Reference-Only Composer

This component creates an immutable Prompt #11 composition manifest from already-validated module descriptors.

It deliberately performs **no network fetch, no prompt-text injection, no model call, and no runtime integration**.

## Purpose

The composer establishes a deterministic module order and provenance record before any future Jarvis-Hub composition feature is considered.

## Guarantees

- duplicate module IDs are rejected;
- required provenance and approval references must be nonempty strings;
- composition order is explicit;
- output and nested module descriptors are frozen;
- activation state is always `inactive`;
- production/runtime flags remain false.

## Test

```sh
node prompt11-composer.test.js
```

Synthetic fixtures are used only to test behavior. They do not represent real HumanApprovalGate records.
