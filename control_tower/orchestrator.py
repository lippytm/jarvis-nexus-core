"""Offline, bounded AI-building-AI task orchestration; never executes generated code."""
from dataclasses import dataclass
from typing import FrozenSet, Tuple

@dataclass(frozen=True)
class AgentPassport:
    agent_id: str
    capabilities: FrozenSet[str]
    max_tasks: int = 3
    max_depth: int = 1
    budget_usd: float = 0.0

@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    requested_capability: str
    target: str
    approval_state: str = "pending"
    evidence_ref: str = ""

FORBIDDEN_TARGETS = frozenset({
    "production_deploy", "send_marketing", "collect_credit_application",
    "transfer_money", "modify_permissions", "spawn_unbounded",
})

def plan(passport: AgentPassport, proposals: Tuple[Proposal, ...]):
    """Return reviewable decisions; does not call LLMs, cloud services or runtimes."""
    accepted, rejected = [], []
    if passport.max_tasks < 0 or passport.max_depth < 0 or passport.budget_usd < 0:
        raise ValueError("invalid agent budgets")
    for proposal in proposals:
        if len(accepted) >= passport.max_tasks:
            rejected.append((proposal.proposal_id, "task budget reached"))
        elif proposal.target in FORBIDDEN_TARGETS:
            rejected.append((proposal.proposal_id, "prohibited action"))
        elif proposal.requested_capability not in passport.capabilities:
            rejected.append((proposal.proposal_id, "missing capability"))
        elif proposal.target != "sandbox":
            rejected.append((proposal.proposal_id, "sandbox only"))
        elif proposal.approval_state not in {"pending", "approved"}:
            rejected.append((proposal.proposal_id, "invalid approval state"))
        elif not proposal.evidence_ref:
            rejected.append((proposal.proposal_id, "missing provenance"))
        else:
            accepted.append(proposal)
    return {"proposed_sandbox_tasks": accepted, "rejected": rejected}
