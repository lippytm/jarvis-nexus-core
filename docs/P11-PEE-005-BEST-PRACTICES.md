# P11-PEE-005 Best-Practice Attestation Checker

This deterministic component checks whether a Prompt #11 work packet records the global best-practice gates needed for promotion review.

It does not decide whether a practice was substantively executed well. It only verifies the attestation structure and blocks promotion when:
- a required critical gate is not true;
- production activation is asserted;
- required human approval has not occurred;
- approval is asserted without approver/audit evidence.

No model calls, deployment, or runtime integration are performed.
