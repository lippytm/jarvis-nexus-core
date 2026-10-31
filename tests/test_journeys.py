"""Behavior checks for the offline one-payment journey model."""
import copy
import json
from pathlib import Path
import unittest

from control_tower.journeys import reconcile_journeys, validate_journey_event


def event(event_type, number, journey="synthetic-member-1", kind="member", **extra):
    fixture = {
        "event_id": f"synthetic-event-{number}", "journey_id": journey,
        "kind": kind, "event_type": event_type,
        "occurred_at": f"2026-10-22T12:{number:02d}:00-07:00",
        "source": "test", "synthetic": True,
    }
    fixture.update(extra)
    return fixture


def signup(number=1, **extra):
    return event("member_signup", number, service_consent=True, marketing_opt_in=False, **extra)


def payment(number=2, **extra):
    fields = {"provider_event_id": f"synthetic-provider-{number}",
              "payment_id": "synthetic-payment-1", "amount_minor": 500, "currency": "USD",
              "confirmation_kind": "simulated_provider"}
    fields.update(extra)
    return event("member_payment_confirmed", number, **fields)


def access(number=3, **extra):
    fields = {"payment_id": "synthetic-payment-1", "entitlement_id": "synthetic-access-1"}
    fields.update(extra)
    return event("member_access_granted", number, **fields)


def refund(number=5, **extra):
    fixture = payment(number, **extra)
    fixture["event_type"] = "member_refunded"
    return fixture


class JourneyTests(unittest.TestCase):
    def test_signup_payment_access_without_marketing_consent(self):
        events = [signup(), payment(), access()]
        before = copy.deepcopy(events)
        report = reconcile_journeys(events)
        member = report["members"]["synthetic-member-1"]
        self.assertEqual(report["counts"], {"accepted": 3, "duplicate": 0, "rejected": 0})
        self.assertTrue(member["access_active"])
        self.assertFalse(member["marketing_opt_in"])
        self.assertEqual(report["synthetic_metrics"]["net_amount_minor"], 500)
        self.assertEqual(report["live_revenue"], "unavailable")
        self.assertEqual(report["provider_authentication"], "not_performed")
        self.assertEqual(events, before)

    def test_service_request_consent_is_separate_from_marketing(self):
        fixture = signup()
        fixture["service_consent"] = False
        fixture["marketing_opt_in"] = True
        self.assertIn("service_consent_required", validate_journey_event(fixture))
        fixture = signup()
        del fixture["marketing_opt_in"]
        result = reconcile_journeys([fixture])
        self.assertFalse(result["members"]["synthetic-member-1"]["marketing_opt_in"])

    def test_unpaid_access_and_payment_without_signup_are_rejected(self):
        self.assertEqual(reconcile_journeys([payment()])["counts"]["rejected"], 1)
        result = reconcile_journeys([signup(), access()])
        self.assertEqual(result["records"][-1]["errors"], ["access_requires_matching_confirmed_payment"])
        self.assertFalse(result["members"]["synthetic-member-1"]["access_active"])

    def test_wrong_payment_reference_cannot_grant_access(self):
        result = reconcile_journeys([signup(), payment(), access(payment_id="synthetic-other-payment")])
        self.assertEqual(result["counts"]["rejected"], 1)
        self.assertFalse(result["members"]["synthetic-member-1"]["access_active"])

    def test_provider_confirmation_must_be_explicitly_simulated(self):
        for value in ("provider_verified", "live", True):
            self.assertIn("simulated_provider_confirmation_required",
                          validate_journey_event(payment(confirmation_kind=value)))
        fixture = payment()
        del fixture["confirmation_kind"]
        self.assertTrue(validate_journey_event(fixture))

    def test_event_and_provider_replays_do_not_double_count(self):
        paid = payment()
        replay = dict(paid, event_id="synthetic-delivery-retry")
        result = reconcile_journeys([signup(), paid, copy.deepcopy(paid), replay, access()])
        self.assertEqual(result["counts"], {"accepted": 3, "duplicate": 2, "rejected": 0})
        self.assertEqual(result["synthetic_metrics"]["confirmed_amount_minor"], 500)

    def test_conflicting_event_id_and_provider_id_are_rejected(self):
        paid = payment()
        conflict = dict(paid, amount_minor=999)
        provider_conflict = dict(conflict, event_id="synthetic-different-delivery")
        result = reconcile_journeys([signup(), paid, conflict, provider_conflict])
        self.assertEqual(result["records"][2]["errors"], ["conflicting_event_id"])
        self.assertEqual(result["records"][3]["errors"], ["conflicting_provider_event_id"])
        self.assertEqual(result["synthetic_metrics"]["net_amount_minor"], 500)

    def test_provider_retry_alias_cannot_be_reused_for_another_event(self):
        replay = dict(payment(), event_id="synthetic-delivery-retry")
        conflict = event("member_cancelled", 4, event_id="synthetic-delivery-retry")
        result = reconcile_journeys([signup(), payment(), replay, conflict])
        self.assertEqual(result["records"][2]["status"], "duplicate")
        self.assertEqual(result["records"][3]["errors"], ["conflicting_event_id"])
        self.assertEqual(result["members"]["synthetic-member-1"]["status"], "paid")

    def test_one_receipt_cannot_fund_two_members(self):
        result = reconcile_journeys([
            signup(), payment(), signup(3, journey="synthetic-member-2"),
            payment(4, journey="synthetic-member-2"),
        ])
        self.assertEqual(result["records"][-1]["errors"], ["payment_receipt_already_used"])
        self.assertEqual(result["synthetic_metrics"]["confirmed_amount_minor"], 500)

    def test_second_payment_is_outside_single_payment_model(self):
        result = reconcile_journeys([signup(), payment(), payment(4, payment_id="synthetic-payment-2")])
        self.assertEqual(result["records"][-1]["errors"], ["payment_requires_unpaid_active_signup"])
        self.assertEqual(result["synthetic_metrics"]["confirmed_amount_minor"], 500)

    def test_cancellation_revokes_access_and_cannot_reactivate(self):
        result = reconcile_journeys([signup(), payment(), access(), event("member_cancelled", 4), access(5)])
        member = result["members"]["synthetic-member-1"]
        self.assertEqual(member["status"], "cancelled")
        self.assertFalse(member["access_active"])
        self.assertEqual(member["confirmed_amount_minor"], 500)
        self.assertEqual(member["refunded_amount_minor"], 0)
        self.assertEqual(result["counts"]["rejected"], 1)

    def test_full_refund_after_cancel_revokes_and_reconciles(self):
        refunded = refund()
        result = reconcile_journeys([
            signup(), payment(), access(), event("member_cancelled", 4), refunded, refunded, access(6),
        ])
        self.assertEqual(result["members"]["synthetic-member-1"]["status"], "refunded")
        self.assertEqual(result["synthetic_metrics"]["net_amount_minor"], 0)
        self.assertEqual(result["synthetic_metrics"]["active_access_count"], 0)
        self.assertEqual(result["counts"]["duplicate"], 1)
        self.assertEqual(result["counts"]["rejected"], 1)

    def test_refund_requires_exact_payment_and_full_amount(self):
        for extra in ({"amount_minor": 100}, {"amount_minor": 600}, {"payment_id": "synthetic-other"}):
            result = reconcile_journeys([signup(), payment(), access(), refund(**extra)])
            self.assertEqual(result["records"][-1]["errors"], ["full_refund_requires_matching_payment"])
            self.assertTrue(result["members"]["synthetic-member-1"]["access_active"])
            self.assertEqual(result["synthetic_metrics"]["refunded_amount_minor"], 0)

    def test_marketing_optout_does_not_cancel_paid_service(self):
        optin = event("marketing_preference_updated", 4, marketing_opt_in=True)
        optout = event("marketing_preference_updated", 5, marketing_opt_in=False)
        result = reconcile_journeys([signup(), payment(), access(), optin, optout])
        member = result["members"]["synthetic-member-1"]
        self.assertTrue(member["access_active"])
        self.assertFalse(member["marketing_opt_in"])
        self.assertTrue(member["service_consent"])

    def test_customer_and_partner_referrals_have_distinct_routes(self):
        customer = event("funding_referral_click", 1, journey="synthetic-customer-1", kind="funding_customer",
                         referral_provider="getbizfunds", service_consent=True)
        partner = event("funding_partner_signup", 2, journey="synthetic-partner-1", kind="funding_partner",
                        referral_provider="lendtrack_partner", service_consent=True, marketing_opt_in=False)
        result = reconcile_journeys([customer, partner, partner])
        self.assertEqual(result["synthetic_metrics"]["customer_redirect_count"], 1)
        self.assertEqual(result["synthetic_metrics"]["partner_request_count"], 1)
        self.assertEqual(result["live_commissions"], "unavailable")
        self.assertNotEqual(result["referrals"]["synthetic-customer-1"]["destination"],
                            result["referrals"]["synthetic-partner-1"]["destination"])
        self.assertEqual(result["referrals"]["synthetic-partner-1"]["provider_completion"], "unverified")
        partner["referral_provider"] = "getbizfunds"
        self.assertIn("referral_provider_kind_mismatch", validate_journey_event(partner))

    def test_out_of_order_delivery_does_not_change_state(self):
        late = event("member_cancelled", 1, event_id="synthetic-delayed-cancel")
        result = reconcile_journeys([signup(), payment(), access(), late])
        self.assertEqual(result["records"][-1]["errors"], ["out_of_order_event"])
        self.assertTrue(result["members"]["synthetic-member-1"]["access_active"])

    def test_sensitive_unknown_and_nested_data_are_rejected_without_echo(self):
        bad_values = ({"ssn": "DO_NOT_ECHO_1"}, [{"password": "DO_NOT_ECHO_2"}],
                      ({"token": "DO_NOT_ECHO_3"},))
        for value in bad_values:
            fixture = signup()
            fixture["payload"] = value
            result = reconcile_journeys([fixture])
            self.assertEqual(result["counts"]["rejected"], 1)
            self.assertNotIn("DO_NOT_ECHO", json.dumps(result))
        fixture = signup()
        fixture["email"] = "DO_NOT_ECHO@example.invalid"
        self.assertIn("unsupported_fields", validate_journey_event(fixture))
        cycle = {}
        cycle["cycle"] = cycle
        fixture["payload"] = cycle
        self.assertTrue(validate_journey_event(fixture))

    def test_amounts_booleans_timestamps_and_production_marker_fail_closed(self):
        for value in (True, 0, -1, 1.5, 100_000_001, "500"):
            self.assertTrue(validate_journey_event(payment(amount_minor=value)))
        for changes in ({"synthetic": False}, {"synthetic": "true"},
                        {"event_id": "real-customer@example.invalid"},
                        {"source": "arbitrary-free-text"}, {"occurred_at": "2026-10-22T12:00:00"},
                        {"event_type": []}, {"kind": {}}, {"marketing_opt_in": 1}):
            fixture = signup()
            fixture.update(changes)
            self.assertTrue(validate_journey_event(fixture))
        self.assertTrue(validate_journey_event({1: "bad-key"}))
        self.assertTrue(validate_journey_event(None))

    def test_bound_and_no_live_metrics_for_empty_input(self):
        with self.assertRaises(ValueError):
            reconcile_journeys([signup()] * 1001)
        with self.assertRaises(ValueError):
            reconcile_journeys(iter([]))
        result = reconcile_journeys([])
        self.assertEqual(result["external_actions"], 0)
        self.assertEqual(result["live_memberships"], "unavailable")
        self.assertEqual(result["live_revenue"], "unavailable")

    def test_documented_fixture_reconciles_without_external_actions(self):
        path = Path(__file__).resolve().parents[1] / "examples" / "membership_journey.json"
        result = reconcile_journeys(json.loads(path.read_text()))
        self.assertEqual(result["counts"], {"accepted": 7, "duplicate": 0, "rejected": 0})
        self.assertEqual(result["synthetic_metrics"]["net_amount_minor"], 0)
        self.assertEqual(result["synthetic_metrics"]["customer_redirect_count"], 1)
        self.assertEqual(result["synthetic_metrics"]["partner_request_count"], 1)
        self.assertEqual(result["external_actions"], 0)


if __name__ == "__main__":
    unittest.main()
