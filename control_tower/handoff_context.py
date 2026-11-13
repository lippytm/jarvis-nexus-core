"""Bounded HFM context alongside strict v1 handoffs, with no execution authority.

Context is proposed metadata and selectively referenced evidence. Visibility and
review labels are caller-supplied classifications, not access authentication or
a sensitive-text detector. Hosted adapters must supply actual access control.
"""
from copy import deepcopy

from control_tower.network_contract import (digest, require_identifier,
    require_record, require_text)
from control_tower.validation import valid_https_url


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("integer outside context bounds")


def validate_context(profile, handoff):
    if not isinstance(profile, dict):
        raise ValueError("context must be a record")
    version = profile.get("schema_version")
    if type(version) is not int or version not in (1, 2, 3):
        raise ValueError("unsupported context schema")
    keys = {
        "schema_version", "kind", "handoff_id", "handoff_sha256", "project_id",
        "mission_id", "source_revision", "asset_id", "platform", "configuration_version",
        "memory_revision", "visibility", "allowed_actions", "context_refs", "evidence_refs",
        "budget", "execution"}
    require_record(profile, keys | ({"control"} if version >= 2 else set())
                   | ({"destination_id"} if version == 3 else set()))
    if version == 3:
        require_identifier(profile["destination_id"], "destination ID")
    if version >= 2:
        control = profile["control"]
        require_record(control, {"state", "actor_id", "reason"})
        if control["state"] not in ("active", "paused", "cancelled"):
            raise ValueError("invalid handoff control state")
        require_identifier(control["actor_id"], "local controller label")
        require_text(control["reason"])
    if profile["kind"] != "jarvis.handoff_context":
        raise ValueError("unsupported context schema")
    binding = {"handoff_id": handoff["handoff_id"], "handoff_sha256": digest(handoff),
               "project_id": handoff["draft"]["project_id"], "source_revision": handoff["source_revision"],
               "asset_id": handoff["assistant_id"], "platform": handoff["draft"]["target"]}
    if any(profile[k] != v for k, v in binding.items()):
        raise ValueError("context does not bind to its handoff")
    require_identifier(profile["mission_id"], "mission ID")
    require_identifier(profile["configuration_version"], "configuration version")
    _integer(profile["memory_revision"], 1, 2147483647)
    if profile["visibility"] not in ("owner_private", "public_candidate"):
        raise ValueError("invalid context visibility")
    # Existing assistant templates have only prepare_draft; context cannot grant tools.
    if profile["allowed_actions"] != ["prepare_draft"]:
        raise ValueError("context cannot expand the existing assistant capabilities")
    for field in ("context_refs", "evidence_refs"):
        refs = profile[field]
        if not isinstance(refs, list) or len(refs) > 8:
            raise ValueError("at most eight references per class")
        seen = set()
        for ref in refs:
            require_record(ref, {"url", "revision", "visibility"})
            if not valid_https_url(ref["url"]):
                raise ValueError("invalid context reference URL")
            _integer(ref["revision"], 1, 2147483647)
            if ref["visibility"] not in ("owner_private", "public_candidate"):
                raise ValueError("invalid reference visibility")
            if profile["visibility"] == "public_candidate" and ref["visibility"] != "public_candidate":
                raise ValueError("private reference cannot enter a public context")
            if ref["url"] in seen:
                raise ValueError("duplicate reference")
            seen.add(ref["url"])
    budget = profile["budget"]
    require_record(budget, {"max_attempts", "time_limit_seconds", "paid_execution_authorized"})
    _integer(budget["max_attempts"], 1, 3)
    _integer(budget["time_limit_seconds"], 1, 3600)
    if budget["paid_execution_authorized"] is not False:
        raise ValueError("paid execution is not authorized")
    execution = profile["execution"]
    require_record(execution, {"state", "context_id", "attempts", "checkpoint_ref", "detail"})
    if execution["state"] not in ("pending", "execution_blocked", "outcome_unknown"):
        raise ValueError("unsupported execution state; no executor is installed")
    require_identifier(execution["context_id"], "execution context ID")
    _integer(execution["attempts"], 0, budget["max_attempts"])
    require_text(execution["detail"])
    if execution["checkpoint_ref"] is not None and not valid_https_url(execution["checkpoint_ref"]):
        raise ValueError("invalid checkpoint reference")
    return deepcopy(profile)
