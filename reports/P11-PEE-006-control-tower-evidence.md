# P11-PEE-006 — Control Tower Regression Evidence

**Date:** 2026-11-01  
**Branch:** `p011-pee-001-adapter`  
**Runtime activation:** disabled

## Scope

Deterministic validation of the P11-PEE-006 Control Tower traffic-light rules. No model call, network call, deployment, or production activation occurred.

## Commands

```sh
node --check control-tower-scoreboard.js
node --check control-tower-scoreboard.test.js
node control-tower-scoreboard.test.js
```

## Result

```text
Control Tower scoreboard tests passed
```

## Behaviors verified

- GREEN when critical gates pass, evidence >= 90, best-practice score >= 90, no unresolved high/critical risk, no high-severity regression failure, rollback ready;
- GREEN still blocks promotion while HumanApprovalGate is pending;
- YELLOW for incomplete evidence;
- YELLOW for unresolved model disagreement;
- ORANGE for unresolved high risk;
- ORANGE for failed high-severity regression;
- RED for failed critical gate;
- RED for unresolved critical risk;
- numeric score cannot override critical-gate failure;
- production activation remains false.

## Local SHA-256

- `control-tower-scoreboard.js`: `f7411a6ef633cc1f6721bd7a1903135971815a531ddd940f87d12bdedc747348`
- `control-tower-scoreboard.test.js`: `4dc3bbf7e73f7357fed15ac2d8620e7a998f18ebec185e48daf8b31dabfdbf48`

These hashes identify the locally tested source copies. They do not establish authorship or production deployment.

## Known unresolved item

The Prompt #11 IF sandbox example still needs to be updated to include the newly required prompt module ID/version fields. A connector mutation attempt was blocked; the schema itself already requires those provenance fields.
