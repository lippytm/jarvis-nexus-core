# P11-PEE-009 — Evidence Arbitration & Sandbox Communications Evidence

**Date:** 2026-11-01  
**Branch:** `p011-pee-001-adapter`  
**Runtime activation:** disabled

## Sandbox communications

Commands:

```sh
node --check sandbox-communications.js
node --check sandbox-communications.test.js
node sandbox-communications.test.js
```

Result:

```text
P11-PEE-009 sandbox communications tests passed
```

Verified:
- FIRST_PASS requires independence_preserved=true;
- production activation is rejected;
- duplicate recipients are rejected;
- Prompt #11 semantic versioning is required;
- envelopes are immutable;
- ChatGPT, ChatGPT Business, Claude, Gemini, GitHub, Jarvis specialists, and deterministic tools have explicit sender classes.

## Evidence arbitration

Commands:

```sh
node --check evidence-arbitrator.js
node --check evidence-arbitrator.test.js
node evidence-arbitrator.test.js
```

Result:

```text
P11-PEE-009 evidence arbitrator tests passed
```

Verified:
- deterministic + primary independent evidence can reach VERIFIED_SUPPORT;
- model-only agreement is treated as CIRCULAR_EVIDENCE / COLLECT_INDEPENDENT_EVIDENCE;
- factual conflict routes to authoritative evidence or deterministic test;
- risk conflict routes to DONT_DO_THAT and red-team;
- policy conflict routes to STOP_AND_ESCALATE;
- stale evidence routes to REFRESH_EVIDENCE;
- production activation remains false;
- HumanApprovalGate remains required.

## SHA-256

- `sandbox-communications.js`: `41698640dda00264ffa3de03c5949f0b4b8bcb30e966a43bdc11b073682c316d`
- `sandbox-communications.test.js`: `88ce5a749e328be022f4cc181e5869cae5d020d0ad344eab9fce4d7090a85f42`
- `evidence-arbitrator.js`: `51aa601977d28bf4afddce3e87f8d75722d183cef004d770d4c6259929977b4d`
- `evidence-arbitrator.test.js`: `9cec24d68460746bfc2a601812c6ea7365bacceed68b2c2a98b3ab8af3f063db`

Hashes identify locally tested source copies; they do not establish authorship or deployment.

## Performance interpretation

The communications workflow is expected to improve reasoning quality and operational efficiency by preserving independent first-pass analysis, exchanging only disputed claims/evidence instead of full conversations, attaching provenance to every message, and preventing circular model validation. Actual cost, latency, and quality improvements still require measurement.
