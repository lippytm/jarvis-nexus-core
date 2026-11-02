# P11-PEE-007 Deterministic Priority Engine

The priority engine converts a P11-PEE-006 Control Tower state into one advisory next action.

It never executes the action.

Priority is safety-first:
1. RED/failed critical gate -> STOP_AND_ESCALATE
2. open incident -> ROUTE_TO_FAILURE_FORENSICS
3. failed required regression -> REPAIR_REGRESSION
4. missing rollback -> COMPLETE_ROLLBACK
5. ORANGE -> QUARANTINE
6. evidence < 90 -> COLLECT_EVIDENCE
7. required red-team missing -> RUN_RED_TEAM
8. model disagreement -> RESOLVE_MODEL_DISAGREEMENT
9. YELLOW -> RUN_COMPARATIVE_EVAL
10. GREEN + approval pending -> PREPARE_OWNER_REVIEW
11. GREEN + approved -> PREPARE_CANARY

No direct production activation is permitted.
