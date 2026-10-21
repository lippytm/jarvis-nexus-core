import unittest
from control_tower.funnels import route_lead
from control_tower.dashboard import build_dashboard

class FunnelDashboardTests(unittest.TestCase):
    def test_funding_customer_vs_partner(self):
        customer = route_lead({"kind":"funding_customer","consent":True,"utm_source":"linkedin"})
        partner = route_lead({"kind":"funding_partner","consent":True,"utm_source":"threads"})
        self.assertNotEqual(customer["destinations"], partner["destinations"])
        self.assertEqual(customer["source"], "linkedin")
    def test_consent_is_required(self):
        self.assertEqual(route_lead({"kind":"member","consent":False})["status"], "rejected")
    def test_sensitive_data_is_rejected(self):
        self.assertEqual(route_lead({"kind":"funding_customer","consent":True,"ssn":"fake"})["status"], "rejected")
    def test_missing_metrics_are_unavailable(self):
        model = build_dashboard([{"name":"Hostinger","status":"verified"}], {})
        self.assertEqual(model["projects"][0]["status"], "unknown")
        self.assertEqual(model["metrics"]["verified_commissions_usd"], "unavailable")

if __name__ == "__main__":
    unittest.main()
