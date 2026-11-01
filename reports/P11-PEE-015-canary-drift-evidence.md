# P11-PEE-015 — Canary Telemetry & Drift Evidence

**Date:** 2026-11-01
**Branch:** `p011-pee-001-adapter`
**Production activation:** disabled

## Commands

```sh
node --check canary-drift-comparator.js
node --check canary-drift-comparator.test.js
node canary-drift-comparator.test.js
node --check post-canary-verifier.js
node --check post-canary-verifier.test.js
node post-canary-verifier.test.js
```

## Results

```text
P11-PEE-015 canary drift comparator tests passed
P11-PEE-014 post-canary verification tests passed
```

## Verified behavior

- no telemetry change => NO_DRIFT;
- better success and lower failure without quality/regression degradation => IMPROVEMENT;
- small noncritical variation => ACCEPTABLE_DRIFT;
- >=10 point success/schema/evidence degradation => MATERIAL_DRIFT;
- increased critical errors or high-severity regressions => CRITICAL_DRIFT;
- MATERIAL_DRIFT => ROLLBACK recommendation;
- CRITICAL_DRIFT => ROLLBACK recommendation;
- INSUFFICIENT_DATA => HOLD;
- security/privacy or rollback-verification failure => ESCALATE;
- improvement never bypasses owner review;
- no automatic production activation or rollback occurs.

## SHA-256

- `canary-drift-comparator.js`: `f512d629679525755b2cbb104d6ae74ca5a365ce195833a74c21c320aefb2867`
- `canary-drift-comparator.test.js`: `5981d77235b204ec554f8affed9395492c74f19cfc0f894e90ee409cf06c781f`
- `post-canary-verifier.js`: `b2bd9b040622ffb0c88e79d9f23e6884a3160eb980d5365671fd0b00629b69a1`
- `post-canary-verifier.test.js`: `c0b084366b8ff76ea6fca09afd0354a833e7a83f6e4e5d0abe3bad3bb5f7d7b1`

These hashes identify the tested local copies and do not establish live deployment.
