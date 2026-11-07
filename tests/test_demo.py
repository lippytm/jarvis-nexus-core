import unittest
from control_tower.demo import demonstrate

class DemoTests(unittest.TestCase):
    def test_membership_journey_preserves_marketing_choice(self):
        from control_tower.demo import demonstrate
        journey = demonstrate()["membership_journey"]
        self.assertEqual(journey["synthetic_metrics"]["active_access_count"], 1)
        self.assertEqual(journey["live_revenue"], "unavailable")
        self.assertFalse(journey["members"]["synthetic-member-1"]["marketing_opt_in"])
        self.assertEqual(journey["external_actions"], 0)
    def test_seven_workflow_simulation(self):
        result = demonstrate()
        self.assertEqual(result["mode"], "synthetic_only")
        self.assertEqual(len(result["routes"]), 3)
        self.assertEqual(result["roundtrip"]["accepted_count"], 3)
        self.assertEqual(result["external_actions"], 0)
        self.assertTrue(result["static_evaluation"]["passed"], result["static_evaluation"]["errors"])
        self.assertEqual(result["dashboard"]["metrics"]["verified_commissions_usd"], "unavailable")
        self.assertEqual(result["connectors"]["hostinger"]["status"], "unverified")
        self.assertEqual(result["roundtrip"]["deployment"], "not_deployed")

if __name__ == "__main__":
    unittest.main()
