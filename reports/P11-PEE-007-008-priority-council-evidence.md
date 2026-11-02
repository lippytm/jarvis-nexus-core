# P11-PEE-007 / P11-PEE-008 — Priority and AI Council Regression Evidence

**Date:** 2026-11-01  
**Branch:** `p011-pee-001-adapter`  
**Runtime activation:** disabled

## P11-PEE-007 priority engine

Commands:

```sh
node --check priority-engine.js
node --check priority-engine.test.js
node priority-engine.test.js
```

Result:

```text
P11-PEE-007 priority engine tests passed
```

Verified:
- RED -> STOP_AND_ESCALATE;
- open incident -> ROUTE_TO_FAILURE_FORENSICS;
- failed required regression -> REPAIR_REGRESSION;
- missing rollback -> COMPLETE_ROLLBACK;
- ORANGE -> QUARANTINE;
- evidence < 90 -> COLLECT_EVIDENCE;
- missing required red-team -> RUN_RED_TEAM;
- model disagreement -> RESOLVE_MODEL_DISAGREEMENT;
- YELLOW -> RUN_COMPARATIVE_EVAL;
- GREEN + approval pending -> PREPARE_OWNER_REVIEW;
- GREEN + approved -> PREPARE_CANARY;
- recommendations never execute actions or activate production.

## P11-PEE-008 AI Council resolver

Commands:

```sh
node --check ai-council-resolver.js
node --check ai-council-resolver.test.js
node ai-council-resolver.test.js
```

Result:

```text
P11-PEE-008 AI Council resolver tests passed
```

Verified:
- unanimous evidence-backed positions + deterministic tests -> VERIFIED_CONSENSUS;
- unanimous evidence-backed positions without deterministic tests -> PROVISIONAL_CONSENSUS;
- unanimous positions without evidence -> COLLECT_EVIDENCE;
- factual disagreement -> authoritative evidence/test;
- risk disagreement -> conservative risk state + red-team;
- critical policy disagreement -> BLOCKED_DISAGREEMENT / STOP_AND_ESCALATE;
- majority vote is never used to establish truth;
- minority positions are preserved;
- duplicate council member IDs are rejected;
- production activation remains false;
- HumanApprovalGate remains required.

## SHA-256

- `priority-engine.js`: `c479d024067e27a5e72bc2f4251cdb6e9ee493a968b6ddb137e97f7b193a7dc4`
- `priority-engine.test.js`: `3bf211c885753312ed449e7676f83326987e0a543752ff90a49ae65baf622146`
- `ai-council-resolver.js`: `73194e8cd3027e2f71e09d313626c19c6aa19d9235868e776aec5dd0213cdd50`
- `ai-council-resolver.test.js`: `a2b81fba588c8b2c8e260b8066d65d83d57546d648206ada26e4d1819c9a27d6`

Hashes identify the tested local source copies; they do not establish authorship or deployment.

## Integration rule

P11-PEE-008 outcomes feed P11-PEE-007 as advisory state:
- BLOCKED_DISAGREEMENT -> STOP_AND_ESCALATE;
- factual/evidence disagreement -> COLLECT_EVIDENCE or deterministic test;
- risk disagreement -> RUN_RED_TEAM / conservative state;
- noncritical split decision -> RESOLVE_MODEL_DISAGREEMENT / comparative eval;
- verified consensus -> PREPARE_OWNER_REVIEW, never autonomous release.
