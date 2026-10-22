"""Bounded, pure-memory reconciliation of synthetic membership/referral fixtures.

No network, payment, storage, login, message or entitlement action occurs here.
This is a one-payment, full-refund model, not a subscription billing engine.
"""
from datetime import datetime
import re

from control_tower.funnels import DESTINATIONS


MAX_EVENTS = 1000
_ID = re.compile(r"synthetic-[a-z0-9][a-z0-9_-]{0,71}\Z")
_SOURCES = {"direct", "test", "simulator", "facebook", "instagram", "threads",
            "linkedin", "substack", "hostinger"}
_KINDS = {"member", "funding_customer", "funding_partner"}
_BASE = {"event_id", "journey_id", "kind", "event_type", "occurred_at", "source", "synthetic"}
_CONSENT = {"service_consent", "marketing_opt_in"}
_PAYMENT = {"payment_id", "provider_event_id", "confirmation_kind", "amount_minor", "currency"}
_FIELDS = {
    "member_signup": _CONSENT,
    "member_payment_confirmed": _PAYMENT,
    "member_access_granted": {"payment_id", "entitlement_id"},
    "member_cancelled": set(),
    "member_refunded": _PAYMENT,
    "funding_referral_click": _CONSENT | {"referral_provider"},
    "funding_partner_signup": _CONSENT | {"referral_provider"},
    "marketing_preference_updated": {"marketing_opt_in"},
}
_PROVIDERS = {
    "funding_customer": {"getbizfunds": DESTINATIONS["funding_customer"][0],
                         "7figures_customer": DESTINATIONS["funding_customer"][1]},
    "funding_partner": {"lendtrack_partner": DESTINATIONS["funding_partner"][0],
                        "7figures_partner": DESTINATIONS["funding_partner"][1]},
}


def _synthetic_id(value):
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _timestamp(value):
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo is not None and result.utcoffset() is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def validate_journey_event(event):
    """Return sanitized error codes; only an explicit flat fixture contract is accepted.

    Nested dictionaries/lists, unknown fields and free-text customer data are forbidden.
    The synthetic marker is an input constraint, not proof of an external provider.
    """
    if not isinstance(event, dict):
        return ["event_must_be_object"]
    if len(event) > 20:
        return ["too_many_fields"]
    if any(not isinstance(key, str) for key in event):
        return ["field_names_must_be_strings"]
    if any(type(value) not in (str, bool, int) for value in event.values()):
        return ["only_flat_scalar_fields_allowed"]
    if any(isinstance(value, str) and len(value) > 128 for value in event.values()):
        return ["field_value_too_long"]
    errors = []
    event_type = event.get("event_type")
    if event_type not in _FIELDS:
        return ["unsupported_event_type"]
    if set(event) - (_BASE | _FIELDS[event_type]):
        errors.append("unsupported_fields")
    if not _BASE.issubset(event):
        errors.append("missing_envelope_fields")
    if event.get("synthetic") is not True:
        errors.append("synthetic_true_required")
    for field in ("event_id", "journey_id"):
        if not _synthetic_id(event.get(field)):
            errors.append("invalid_" + field)
    if event.get("kind") not in _KINDS:
        errors.append("unsupported_journey_kind")
    if event.get("source") not in _SOURCES:
        errors.append("unsupported_source")
    if _timestamp(event.get("occurred_at")) is None:
        errors.append("timezone_aware_timestamp_required")
    if event_type.startswith("member_") and event.get("kind") != "member":
        errors.append("event_kind_mismatch")
    if event_type == "funding_referral_click" and event.get("kind") != "funding_customer":
        errors.append("event_kind_mismatch")
    if event_type == "funding_partner_signup" and event.get("kind") != "funding_partner":
        errors.append("event_kind_mismatch")
    if event_type in {"member_signup", "funding_referral_click", "funding_partner_signup"}:
        if event.get("service_consent") is not True:
            errors.append("service_consent_required")
    if "marketing_opt_in" in event and type(event["marketing_opt_in"]) is not bool:
        errors.append("marketing_opt_in_must_be_boolean")
    if event_type == "marketing_preference_updated" and "marketing_opt_in" not in event:
        errors.append("marketing_preference_required")
    if event_type in {"member_payment_confirmed", "member_refunded"}:
        if event.get("confirmation_kind") != "simulated_provider":
            errors.append("simulated_provider_confirmation_required")
        if type(event.get("amount_minor")) is not int or not 0 < event["amount_minor"] <= 100_000_000:
            errors.append("positive_bounded_integer_amount_required")
        if event.get("currency") != "USD":
            errors.append("only_usd_supported")
        for field in ("payment_id", "provider_event_id"):
            if not _synthetic_id(event.get(field)):
                errors.append("invalid_" + field)
    if event_type == "member_access_granted":
        for field in ("payment_id", "entitlement_id"):
            if not _synthetic_id(event.get(field)):
                errors.append("invalid_" + field)
    if event_type.startswith("funding_"):
        providers = _PROVIDERS.get(event.get("kind"), {})
        if event.get("referral_provider") not in providers:
            errors.append("referral_provider_kind_mismatch")
    return errors


def _transition(event, previous, payment_owners):
    """Compute a new state without modifying an existing accepted state."""
    event_type = event["event_type"]
    if previous is None:
        if event_type not in {"member_signup", "funding_referral_click", "funding_partner_signup"}:
            return None, "initial_request_required"
        state = {"kind": event["kind"], "source": event["source"],
                 "service_consent": True, "marketing_opt_in": event.get("marketing_opt_in", False),
                 "last_occurred_at": event["occurred_at"]}
        if event_type == "member_signup":
            state.update(status="signed_up", access_active=False,
                         confirmed_amount_minor=0, refunded_amount_minor=0, currency="USD")
        else:
            state.update(status="customer_redirect_recorded" if event["kind"] == "funding_customer"
                         else "partner_request_recorded",
                         referral_provider=event["referral_provider"],
                         destination=_PROVIDERS[event["kind"]][event["referral_provider"]],
                         provider_completion="unverified", commission="unavailable")
        return state, None
    if event["kind"] != previous["kind"]:
        return None, "journey_kind_cannot_change"
    if _timestamp(event["occurred_at"]) < _timestamp(previous["last_occurred_at"]):
        return None, "out_of_order_event"
    state = dict(previous)
    if event_type == "marketing_preference_updated":
        state["marketing_opt_in"] = event["marketing_opt_in"]
    elif event_type == "member_payment_confirmed":
        if state["status"] != "signed_up":
            return None, "payment_requires_unpaid_active_signup"
        if event["payment_id"] in payment_owners:
            return None, "payment_receipt_already_used"
        state.update(status="paid", payment_id=event["payment_id"],
                     confirmed_amount_minor=event["amount_minor"])
    elif event_type == "member_access_granted":
        if state["status"] != "paid" or event["payment_id"] != state.get("payment_id"):
            return None, "access_requires_matching_confirmed_payment"
        state.update(status="active", access_active=True, entitlement_id=event["entitlement_id"])
    elif event_type == "member_cancelled":
        if state["status"] in {"cancelled", "refunded"}:
            return None, "membership_already_terminal"
        state.update(status="cancelled", access_active=False)
    elif event_type == "member_refunded":
        if (not state.get("payment_id") or state["status"] == "refunded"
                or event["payment_id"] != state["payment_id"]
                or event["amount_minor"] != state["confirmed_amount_minor"]
                or event["currency"] != state["currency"]):
            return None, "full_refund_requires_matching_payment"
        state.update(status="refunded", access_active=False,
                     refunded_amount_minor=event["amount_minor"])
    else:
        return None, "initial_request_already_recorded"
    state["last_occurred_at"] = event["occurred_at"]
    return state, None


def reconcile_journeys(events):
    """Reconcile at most 1,000 synthetic events in supplied delivery order.

    Event/provider ID replays are idempotent; conflicting ID reuse is rejected.
    Other events that predate the last accepted event in their journey are rejected.
    Rejected events never change state or reserve payment/provider IDs. Cancellation
    revokes access immediately in this fixture model; production policy is unresolved.
    """
    if not isinstance(events, (list, tuple)) or len(events) > MAX_EVENTS:
        raise ValueError("events must be a list or tuple of at most 1000 fixtures")
    states, event_ids, provider_ids, payment_owners = {}, {}, {}, {}
    records = []
    counts = {"accepted": 0, "duplicate": 0, "rejected": 0}
    for index, event in enumerate(events):
        errors = validate_journey_event(event)
        event_id = event.get("event_id") if isinstance(event, dict) else None
        record = {"index": index, "event_id": event_id if _synthetic_id(event_id) else None}
        status = "rejected"
        if not errors:
            replay = event_ids.get(event_id)
            provider_id = event.get("provider_event_id")
            provider_payload = {key: value for key, value in event.items() if key != "event_id"}
            if replay is not None:
                status = "duplicate" if replay == event else "rejected"
                errors = [] if status == "duplicate" else ["conflicting_event_id"]
            elif provider_id in provider_ids:
                status = "duplicate" if provider_ids[provider_id] == provider_payload else "rejected"
                errors = [] if status == "duplicate" else ["conflicting_provider_event_id"]
                if status == "duplicate":
                    event_ids[event_id] = dict(event)
            else:
                state, error = _transition(event, states.get(event["journey_id"]), payment_owners)
                if error:
                    errors = [error]
                else:
                    status = "accepted"
                    states[event["journey_id"]] = state
                    event_ids[event_id] = dict(event)
                    if provider_id:
                        provider_ids[provider_id] = provider_payload
                    if event["event_type"] == "member_payment_confirmed":
                        payment_owners[event["payment_id"]] = event["journey_id"]
        counts[status] += 1
        records.append(dict(record, status=status, errors=errors))
    members = {key: value for key, value in states.items() if value["kind"] == "member"}
    referrals = {key: value for key, value in states.items() if value["kind"] != "member"}
    confirmed = sum(value["confirmed_amount_minor"] for value in members.values())
    refunded = sum(value["refunded_amount_minor"] for value in members.values())
    return {
        "mode": "synthetic_only", "status": "reconciled_with_rejections" if counts["rejected"] else "reconciled",
        "external_actions": 0, "records": records, "counts": counts,
        "members": members, "referrals": referrals,
        "synthetic_metrics": {
            "active_access_count": sum(value["access_active"] for value in members.values()),
            "confirmed_amount_minor": confirmed, "refunded_amount_minor": refunded,
            "net_amount_minor": confirmed - refunded, "currency": "USD",
            "customer_redirect_count": sum(value["kind"] == "funding_customer" for value in referrals.values()),
            "partner_request_count": sum(value["kind"] == "funding_partner" for value in referrals.values()),
        },
        "live_memberships": "unavailable", "live_revenue": "unavailable",
        "live_commissions": "unavailable", "provider_authentication": "not_performed",
    }
