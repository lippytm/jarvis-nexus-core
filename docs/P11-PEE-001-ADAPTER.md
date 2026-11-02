# Prompt #11 Adapter — P11-PEE-001 v0.1

This branch introduces a **reference-only, fail-closed** adapter between `jarvis-nexus-core` and the canonical `lippytm/Prompt-11-` repository.

## What it does

- validates Prompt #11 module metadata;
- requires the canonical Prompt #11 repository;
- accepts only `approved` prompt-module state;
- requires explicit HumanApprovalGate evidence;
- produces an immutable reference object for downstream use.

## What it deliberately does not do

- fetch remote Prompt #11 content;
- inject Prompt #11 into Jarvis-Hub system prompts;
- modify Jarvis-Flow workflow generation;
- deploy or restart services;
- synchronize repositories;
- claim that Prompt #11 or P11-PEE-001 is approved.

This keeps current Jarvis behavior unchanged while giving the next implementation step a deterministic governance boundary.

## Test

Run:

```sh
node prompt11-policy-adapter.test.js
```

The test verifies:

1. production prompt injection is disabled;
2. a review-ready/unapproved module is rejected;
3. a non-canonical repository is rejected;
4. an approved fixture produces a reference-only module descriptor.

The approved fixture is test data only and is not evidence that any real Prompt #11 module has passed HumanApprovalGate.

## Next step after review

Once an actual Prompt #11 module is approved and its exact version/ref is recorded, add an opt-in Jarvis-Hub integration that composes the approved module with the selected persona prompt. That change should remain disabled by default until integration and regression tests pass.
