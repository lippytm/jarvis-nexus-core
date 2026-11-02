# P11-PEE-013 / P11-PEE-014 — Canary and Post-Canary Evidence

**Date:** 2026-11-01
**Branch:** `p011-pee-001-adapter`
**Production activation:** disabled

## P11-PEE-013 Canary Manifest Validator

Commands:

```sh
node --check canary-manifest-validator.js
node --check canary-manifest-validator.test.js
node canary-manifest-validator.test.js
```

Result:

```text
P11-PEE-013 canary manifest validator tests passed
```

Verified:
- exact target, candidate ref, baseline ref, bounded scope required;
- nonempty success criteria, failure criteria, and stop conditions required;
- rollback target/procedure required;
- post-canary verification/evidence plans required;
- HumanApprovalGate evidence required;
- production_activation must remain false;
- validator never deploys.

SHA-256:
- canary-manifest-validator.js: `3f9928878ebf42ceba28825cbe74a80672972f52307ea22f3a7e075cb8b8f1df`
- canary-manifest-validator.test.js: `d716993927deebfac7bd820035d8d37619bb54324ebc4c020f8b9993eccb3cd3`

## P11-PEE-014 Post-Canary Verification

Commands:

```sh
node --check post-canary-verifier.js
node --check post-canary-verifier.test.js
node post-canary-verifier.test.js
```

Result:

```text
P11-PEE-014 post-canary verification tests passed
```

Verified:
- clean verified canary => CONTINUE recommendation;
- security/privacy violation => ESCALATE;
- rollback verification failure => ESCALATE;
- critical error => ROLLBACK recommendation;
- high-severity regression => ROLLBACK recommendation;
- incomplete evidence => HOLD;
- incomplete post-canary verification => HOLD;
- rollback is advisory only;
- owner review is always required;
- production activation remains false.

SHA-256:
- post-canary-verifier.js: `df660f1c4c19c65152bda67bc27e6c005fddfebbc3d1422e4cb591e434d9eeab`
- post-canary-verifier.test.js: `c041baf99a1e87be76305911a2901e8729cc696dcec73aaa690d2f0a207b46df`

Hashes identify the locally tested source copies; they do not establish authorship or live deployment.
