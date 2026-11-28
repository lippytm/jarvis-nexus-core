from hashlib import sha256
import unittest

from control_tower.events import validate_event, ingest
from control_tower.roundtrip import run_synthetic_roundtrip
from control_tower.funnels import route_lead
from control_tower.attribution import aggregate
from control_tower.builder import ToolSpec, generate_candidate
from control_tower.evaluator import evaluate_candidate
from control_tower.orchestrator import AgentPassport, Proposal, plan


def fixture(**updates):
    event = {"event_id": "synthetic-1", "event_type": "campaign_visit", "source": "linkedin",
             "project_id": "demo", "occurred_at": "2026-10-22T12:00:00-07:00",
             "consent_status": "not_applicable", "approval_state": "pending",
             "utm_source": "linkedin", "payload": {"synthetic": True}}
    event.update(updates)
    return event


class InputHardeningTests(unittest.TestCase):
    def test_malformed_events_reject_without_crashing_or_mutating_seen(self):
        cases = [None, [], fixture(event_type=[]), fixture(event_id=[]), fixture(consent_status=[]),
                 fixture(approval_state={}), fixture(source=[]), fixture(project_id={}),
                 fixture(utm_source=[]), fixture(evidence_url="https://["), fixture(payload={1: "x"})]
        for case in cases:
            with self.subTest(case=case):
                seen = set()
                self.assertEqual(ingest(case, seen)[0], "rejected")
                self.assertEqual(seen, set())

    def test_non_json_cycles_depth_and_size_are_bounded(self):
        cycle = {}; cycle["again"] = cycle
        deep = {}; child = deep
        for _ in range(20):
            child["child"] = {}; child = child["child"]
        for payload in (cycle, deep, {"data": "x" * 70000}, {"n": float("nan")}, {"data": (1, 2)}):
            with self.subTest(kind=type(payload).__name__):
                self.assertTrue(validate_event(fixture(payload=payload)))

    def test_sensitive_key_variants_are_rejected_at_any_depth(self):
        for key in ("apiKey", "Access-Token", "card number", "Authorization", "private_key"):
            self.assertIn("disallowed sensitive field", validate_event(fixture(payload={"nested": [{key: "synthetic"}]})))
            self.assertEqual(route_lead({"kind": "member", "consent": True, "payload": {key: "synthetic"}})["status"], "rejected")

    def test_evidence_urls_reject_credentials_ports_and_control_characters(self):
        for url in ("https://user:password@example.com", "https://example.com:bad", "https://example.com\n/path", "https://"):
            self.assertTrue(validate_event(fixture(evidence_url=url)))

    def test_partner_signup_requires_explicit_consent(self):
        self.assertTrue(validate_event(fixture(event_type="funding_partner_signup")))
        self.assertEqual(validate_event(fixture(event_type="funding_partner_signup", consent_status="opted_in")), [])

    def test_roundtrip_rejects_nonfixtures_and_finishes_mixed_batch(self):
        result = run_synthetic_roundtrip([None, fixture(), fixture(), fixture(event_id="synthetic-2", payload={"synthetic": False})])
        self.assertEqual(result["accepted_count"], 1)
        self.assertEqual(result["duplicate_count"], 1)
        self.assertEqual(len(result["rejected"]), 2)
        self.assertTrue(result["fixture_only"])

    def test_conflicting_duplicate_does_not_change_attribution(self):
        changed = fixture(source="facebook", utm_source="facebook")
        result = run_synthetic_roundtrip([fixture(), changed])
        self.assertEqual(result["accepted_count"], 1)
        self.assertIn("conflicting duplicate event", result["rejected"][0]["errors"])
        self.assertNotIn("facebook:visits", result["attribution"])

    def test_rejected_ids_never_echo_malformed_payloads(self):
        result = run_synthetic_roundtrip([fixture(event_id={"api_key": "do-not-echo"})])
        self.assertIsNone(result["rejected"][0]["event_id"])
        self.assertNotIn("do-not-echo", str(result))

    def test_attribution_handles_malformed_direct_input(self):
        self.assertEqual(aggregate([None, fixture(event_id=[]), fixture(utm_source=[]), fixture(event_type=[])]), {})

    def test_source_templates_include_recovered_candidates_without_execution(self):
        for template in ("consent_check", "synthetic_count"):
            candidate = generate_candidate(ToolSpec("recovered_tool", template, "review only"))
            result = evaluate_candidate(candidate)
            self.assertTrue(result["passed"])
            self.assertEqual(result["execution"], "not_run")

    def test_matching_hash_cannot_approve_arbitrary_source(self):
        candidate = generate_candidate(ToolSpec("candidate_tool", "validation_tool", "test"))
        candidate["content"] = "while True:\n    pass\n"
        candidate["sha256"] = sha256(candidate["content"].encode()).hexdigest()
        self.assertFalse(evaluate_candidate(candidate)["passed"])

    def test_evaluator_rejects_malformed_candidate(self):
        for candidate in (None, [], {}, {"content": None}, {"content": "x" * 10001}):
            self.assertFalse(evaluate_candidate(candidate)["passed"])

    def test_unicode_source_and_evidence_fail_without_crashing(self):
        candidate = generate_candidate(ToolSpec("candidate_tool", "report_tool", "test"))
        candidate["content"] = "\ud800"
        self.assertFalse(evaluate_candidate(candidate)["passed"])
        self.assertTrue(validate_event(fixture(evidence_url="https://example.com/\ud800")))

    def test_overflow_budget_is_a_controlled_validation_error(self):
        with self.assertRaises(ValueError):
            plan(AgentPassport("agent", frozenset(), budget_usd=10 ** 400), ())

    def test_nonfinite_and_wrong_type_budgets_fail_closed(self):
        for value in (float("nan"), float("inf"), True, -1, 1.5, 51):
            with self.subTest(value=value), self.assertRaises(ValueError):
                plan(AgentPassport("agent", frozenset({"write_code"}), max_tasks=value), ())
        for value in (float("nan"), float("inf"), -1, True):
            with self.assertRaises(ValueError):
                plan(AgentPassport("agent", frozenset(), budget_usd=value), ())

    def test_string_capability_cannot_grant_substring_permission(self):
        with self.assertRaises(ValueError):
            plan(AgentPassport("agent", "write_code"), (Proposal("p1", "write", "sandbox", evidence_ref="test"),))

    def test_bounded_roles_depth_and_duplicate_handoffs(self):
        agent = AgentPassport("agent", frozenset({"read_docs"}), max_depth=1, role="researcher")
        first = Proposal("p1", "read_docs", "sandbox", evidence_ref="test")
        deep = Proposal("p2", "read_docs", "sandbox", evidence_ref="test", depth=2)
        result = plan(agent, (first, first, deep))
        self.assertEqual(len(result["proposed_sandbox_tasks"]), 1)
        self.assertEqual(len(result["rejected"]), 2)
        self.assertFalse(result["executed"])


if __name__ == "__main__":
    unittest.main()
