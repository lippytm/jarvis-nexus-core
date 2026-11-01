# P11-PEE-009 Evidence Arbitration & Sandbox Communications

Two deterministic components:

1. `sandbox-communications.js` validates structured envelopes used by ChatGPT, ChatGPT Business, Claude, Gemini AI, GitHub, deterministic tools, and Jarvis specialists.
2. `evidence-arbitrator.js` compares evidence classes, freshness, verification state, independence groups, and conflict type.

Key guarantees:
- FIRST_PASS messages must preserve independence;
- production activation is always false;
- model-only agreement is not independent verification;
- stale evidence cannot verify a current claim;
- factual conflict routes to authoritative evidence/test;
- risk conflict routes to Don't Do That + red-team;
- policy conflict stops/escalates;
- verified support still routes to owner review rather than release.

GitHub is treated as evidence/change-control, not a reasoning model.
