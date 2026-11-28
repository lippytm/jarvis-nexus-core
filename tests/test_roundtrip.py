import unittest
from control_tower.roundtrip import run_synthetic_roundtrip

def event(event_id, kind, consent="not_applicable"):
    return {"event_id": event_id, "event_type": kind, "source": "linkedin",
            "utm_source": "linkedin", "occurred_at": "2026-10-21T09:30:00-07:00",
            "project_id": "test", "consent_status": consent,
            "approval_state": "pending", "payload": {"synthetic": True}}

class RoundtripTests(unittest.TestCase):
    def test_roundtrip(self):
        visit = event("v1", "campaign_visit")
        signup = event("s1", "member_signup", "opted_in")
        invalid = event("bad", "member_signup", "opted_out")
        result = run_synthetic_roundtrip([visit, visit, signup, invalid])
        self.assertEqual(result["accepted_count"], 2)
        self.assertEqual(len(result["rejected"]), 1)
        self.assertEqual(result["attribution"]["linkedin:visits"], 1)
        self.assertEqual(result["attribution"]["linkedin:member_signup"], 1)
        self.assertEqual(result["proposed_tasks"], ["candidate-1"])
        self.assertEqual(result["deployment"], "not_deployed")

    def test_hash_is_reproducible(self):
        events = [event("v2", "campaign_visit")]
        self.assertEqual(run_synthetic_roundtrip(events)["sha256"],
                         run_synthetic_roundtrip(events)["sha256"])

if __name__ == "__main__":
    unittest.main()
