"""Offline, bounded AI-building-AI task orchestration; never executes generated code."""
from dataclasses import dataclass
from typing import FrozenSet, Tuple
from math import isfinite
from control_tower.validation import valid_identifier

AUTHORIZED_ROLES = frozenset({"researcher", "architect", "builder", "evaluator", "reporter"})

@dataclass(frozen=True)
class AgentPassport:
    agent_id: str
    capabilities: FrozenSet[str]
    max_tasks: int = 3
    max_depth: int = 1
    budget_usd: float = 0.0
    role: str = "builder"

@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    requested_capability: str
    target: str
    approval_state: str = "pending"
    evidence_ref: str = ""
    depth: int = 0

FORBIDDEN_TARGETS = frozenset({
    "production_deploy", "send_marketing", "collect_credit_application",
    "transfer_money", "modify_permissions", "spawn_unbounded",
})

def plan(passport: AgentPassport, proposals: Tuple[Proposal, ...]):
    """Return reviewable decisions; does not call LLMs, cloud services or runtimes."""
    accepted, rejected = [], []
    if not isinstance(passport, AgentPassport) or not valid_identifier(passport.agent_id):
        raise ValueError("invalid agent passport")
    if not isinstance(passport.role, str) or passport.role not in AUTHORIZED_ROLES:
        raise ValueError("invalid agent role")
    if not isinstance(passport.capabilities, frozenset) or any(not valid_identifier(c) for c in passport.capabilities):
        raise ValueError("capabilities must be an explicit immutable set")
    try:
        finite_budget = type(passport.budget_usd) in (int, float) and isfinite(passport.budget_usd)
    except (OverflowError, ValueError):
        finite_budget = False
    if (type(passport.max_tasks) is not int or not 0 <= passport.max_tasks <= 50
        or type(passport.max_depth) is not int or not 0 <= passport.max_depth <= 5
        or not finite_budget or passport.budget_usd < 0):
        raise ValueError("invalid agent budgets")
    if not isinstance(proposals, (list, tuple)) or len(proposals) > 100:
        raise ValueError("at most 100 proposals are accepted")
    seen = set()
    for proposal in proposals:
        if not isinstance(proposal, Proposal) or not valid_identifier(proposal.proposal_id):
            rejected.append((None, "invalid proposal"))
            continue
        if proposal.proposal_id in seen:
            rejected.append((proposal.proposal_id, "duplicate proposal"))
            continue
        seen.add(proposal.proposal_id)
        if not valid_identifier(proposal.requested_capability) or not isinstance(proposal.target, str):
            rejected.append((proposal.proposal_id, "invalid proposal fields"))
        elif type(proposal.depth) is not int or not 0 <= proposal.depth <= passport.max_depth:
            rejected.append((proposal.proposal_id, "depth budget reached"))
        elif len(accepted) >= passport.max_tasks:
            rejected.append((proposal.proposal_id, "task budget reached"))
        elif proposal.target in FORBIDDEN_TARGETS:
            rejected.append((proposal.proposal_id, "prohibited action"))
        elif proposal.requested_capability not in passport.capabilities:
            rejected.append((proposal.proposal_id, "missing capability"))
        elif proposal.target != "sandbox":
            rejected.append((proposal.proposal_id, "sandbox only"))
        elif not isinstance(proposal.approval_state, str) or proposal.approval_state not in {"pending", "approved"}:
            rejected.append((proposal.proposal_id, "invalid approval state"))
        elif not isinstance(proposal.evidence_ref, str) or not proposal.evidence_ref.strip() or len(proposal.evidence_ref) > 2048:
            rejected.append((proposal.proposal_id, "missing provenance"))
        else:
            accepted.append(proposal)
    return {"proposed_sandbox_tasks": accepted, "rejected": rejected,
            "executed": False, "authorization": "proposal_only"}
