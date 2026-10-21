import unittest
from control_tower.demo import demonstrate

class DemoTests(unittest.TestCase):
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
