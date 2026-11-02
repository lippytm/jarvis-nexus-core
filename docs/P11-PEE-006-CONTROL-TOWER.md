# P11-PEE-006 Control Tower Scoreboard

This deterministic component summarizes a Prompt #11 decision packet into GREEN, YELLOW, ORANGE, or RED.

Priority rules:
- failed critical gate or unresolved critical risk => RED;
- unresolved high risk, high-severity regression failure, missing rollback, or blocked best-practice attestation => ORANGE;
- incomplete evidence, sub-90 best-practice score, or unresolved model disagreement => YELLOW;
- otherwise => GREEN.

A GREEN state does not equal release approval. HumanApprovalGate remains separate, and promotion stays blocked until the required human approval is recorded.

The scorer performs no model calls, no network calls, and no production activation.
