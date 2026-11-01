# P11-PEE-001 Jarvis Adapter — Test Evidence

**Date:** 2026-11-01  
**Branch:** `p011-pee-001-adapter`  
**Scope:** reference-only Prompt #11 governance adapter; no production injection

## Source checks

- `node --check prompt11-policy-adapter.js` — PASS
- `node --check prompt11-policy-adapter.test.js` — PASS

## Behavior test

Command:

```sh
node prompt11-policy-adapter.test.js
```

Result:

```text
Prompt #11 adapter tests passed
```

Verified behaviors:

1. production prompt injection remains disabled;
2. review-ready/unapproved Prompt #11 modules are rejected;
3. non-canonical Prompt #11 repository metadata is rejected;
4. an approved test fixture produces a reference-only immutable descriptor.

The approved fixture is synthetic test data only. It is not evidence that a real Prompt #11 module has passed HumanApprovalGate.

## SHA-256 evidence

- `prompt11-policy-adapter.js`: `68fdaf75a79a0a2092ec7ededf95bbf2015f9c22970cc2a31633e1a4fbdc0970`
- `prompt11-policy.json`: `c65fdb8bda0efa2b5c2c417630524c1fb7620b00bc99960b3833ad60b33900f3`
- `prompt11-policy-adapter.test.js`: `4f6fc4307b689394720b1262d02d47a672776cca35d4d55b242e95c834d8fa62`

## Environment limitation

The execution container could not resolve `github.com` for a direct clone. Source was therefore fetched from the connected GitHub repository branch through the authorized connector, materialized locally, and tested with Node. This does not affect the source-level or behavior checks above.

## Release boundary

This evidence supports review of the adapter only. It does not prove deployment, service restart, remote prompt fetching, Prompt #11 approval, or production integration.
