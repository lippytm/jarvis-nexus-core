import unittest
from control_tower.orchestrator import AgentPassport, Proposal, plan
from control_tower.attribution import aggregate
from control_tower.briefing import project_summary

class ControlTowerExtensionsTests(unittest.TestCase):
    def test_builder_proposal_is_sandbox_only(self):
        passport = AgentPassport("builder", frozenset({"write_code"}))
        tasks = (Proposal("p1", "write_code", "sandbox", evidence_ref="issue-2"),
                 Proposal("p2", "write_code", "production_deploy", approval_state="approved", evidence_ref="issue-2"))
        result = plan(passport, tasks)
        self.assertEqual(len(result["proposed_sandbox_tasks"]), 1)
        self.assertEqual(result["rejected"][0][1], "prohibited action")

    def test_budget_caps_tasks(self):
        passport = AgentPassport("builder", frozenset({"write_code"}), max_tasks=1)
        tasks = tuple(Proposal(str(n), "write_code", "sandbox", evidence_ref="evidence") for n in range(3))
        self.assertEqual(len(plan(passport, tasks)["rejected"]), 2)

    def test_unknown_capability_rejected(self):
        passport = AgentPassport("builder", frozenset({"read_docs"}))
        self.assertEqual(plan(passport, (Proposal("p1", "write_code", "sandbox", evidence_ref="e"),))["rejected"][0][1], "missing capability")

    def test_missing_evidence_rejected(self):
        passport = AgentPassport("builder", frozenset({"write_code"}))
        self.assertEqual(plan(passport, (Proposal("p1", "write_code", "sandbox"),))["rejected"][0][1], "missing provenance")

    def test_optin_attribution_no_duplicate(self):
        events = [
            {"event_id": "v1", "utm_source": "linkedin", "event_type": "campaign_visit"},
            {"event_id": "v1", "utm_source": "linkedin", "event_type": "campaign_visit"},
            {"event_id": "s1", "utm_source": "linkedin", "event_type": "member_signup", "consent_status": "opted_in"},
            {"event_id": "s2", "utm_source": "facebook", "event_type": "member_signup", "consent_status": "opted_out"},
        ]
        result = aggregate(events)
        self.assertEqual(result[("linkedin", "visits")], 1)
        self.assertEqual(result[("linkedin", "member_signup")], 1)
        self.assertNotIn(("facebook", "member_signup"), result)

    def test_verified_requires_evidence(self):
        self.assertEqual(project_summary([{"name": "Hostinger", "status": "verified"}]), "Hostinger: unknown")

if __name__ == "__main__":
    unittest.main()
