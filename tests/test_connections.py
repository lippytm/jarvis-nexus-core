import unittest
from control_tower.connections import connector_report

class ConnectionRegistryTests(unittest.TestCase):
    def test_unverified_sources_not_reported_connected(self):
        report = connector_report()
        for name in ("hostinger", "gemini", "claude", "facebook", "instagram",
                     "threads", "linkedin", "substack"):
            self.assertEqual(report[name]["status"], "unverified")
    def test_registry_is_immutable_to_callers(self):
        report = connector_report()
        report["hostinger"]["status"] = "connected"
        self.assertEqual(connector_report()["hostinger"]["status"], "unverified")

if __name__ == "__main__":
    unittest.main()
