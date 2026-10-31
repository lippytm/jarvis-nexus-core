# Reconciliation of the recovered v1.0 candidate

Date: October 22, 2026. Scope: source comparison and offline verification.

The recovered `jarvis_v10_control_tower_candidate.zip` is a separate local
candidate, not the source of the existing PR #5 branch. It contains four modules,
four test files, an empty package initializer, a README, and historical evidence.

Archive SHA-256:
`9ea1636315dab47fee162b165a1045ef501cb15a8923fcd5a3329d0f728a3f13`

All **9 of 9** source/test hashes in the archive's manifest matched after recovery.
After source inspection, the recovered suite was run again: **24 tests passed**.
The starting GitHub branch was independently tested: **27 tests passed** at
`b304e0864cd01993957b2e9b6cf252babb7cc4aa`. These are different suites, not
competing counts for the same revision, and must never be added together to
claim one test result.

## Integration decisions

| Recovered feature | Canonical location and decision |
| --- | --- |
| Membership activation/cancellation/refund model | `control_tower/journeys.py` replaces the weaker Boolean `provider_verified` convention with explicitly synthetic confirmation records, payment references, replay checks, and a documented one-payment/full-refund scope. |
| Consent-check and synthetic-count tool templates | Added to the existing `builder.py` template registry. The evaluator requires an exact declared template and digest. Generated source remains unexecuted. |
| Bounded roles and handoff proposals | Integrated into the existing `orchestrator.py`: allowlisted roles, strict task/depth budgets, duplicate rejection and explicit proposal-only status. A passport is data, not authentication. |
| Connection readiness registry | Expanded the existing `connections.py` with HubSpot and Airtable plans and bounded recorded-read observations. No connector claims credentials are absent or that current access exists without an observation. |
| Six-channel and three-journey pipeline | Kept the current routing/attribution modules, added the stronger journey model to `demo.py`, and hardened malformed-input/duplicate handling. No parallel second `control_tower` implementation was installed. |

The old candidate remains historical evidence. The existing PR branch is the
review target for this update. The new source, tests, workflow and verification
record provide the reproducible implementation; the `v1.0` archive label alone
does not establish a release, deployment or live integration.

## Remaining boundaries

- The code generator produces allowlisted draft source, not autonomous code execution.
- Tests and static evaluation are not a human security audit or a secure runtime.
- Synthetic payment confirmations do not authenticate a real provider.
- The source checks do not establish demand, customer revenue, Linux compatibility,
  robotics readiness, or cross-platform synchronization.
- Hostinger editing, production billing and provider-specific API access remain
  separate integration tasks requiring actual supported access and runtime evidence.
