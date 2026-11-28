import unittest

from control_tower.injective_marketing import (
    INJECTION_POINTS, MEMBERSHIP_LADDER, ROUTES, injective_campaign,
    injective_funnel, newsletter_injective_map, route_record,
)
from control_tower.organic_marketing import FREE_CHANNELS


class InjectiveMarketingTests(unittest.TestCase):
    def test_tiktok_is_blocked(self):
        with self.assertRaises(ValueError):
            injective_campaign("newsletter", "tiktok")

    def test_all_routes_compile_for_all_active_channels(self):
        for route_id in ROUTES:
            for channel in FREE_CHANNELS:
                packet = injective_campaign(route_id, channel)
                self.assertEqual(route_id, packet["route_id"])
                self.assertEqual(channel, packet["channel"])
                self.assertEqual("unpublished_draft", packet["state"])
                self.assertEqual(0, packet["external_actions"])
                self.assertEqual(0, packet["publishing_actions"])
                self.assertIsNone(packet["actual_metrics"])

    def test_membership_pricing_is_not_invented(self):
        for membership in MEMBERSHIP_LADDER.values():
            self.assertIsNone(membership["price"])
        packet = injective_campaign("builder-membership", "substack")
        self.assertIsNone(packet["membership"]["price"])
        self.assertIn("review", packet["membership"]["price_rule"].lower())

    def test_funding_and_partner_routes_remain_separate(self):
        customer = injective_campaign("funding-information", "facebook")
        partner = injective_campaign("referral-partner", "facebook")
        self.assertEqual("funding_customer", customer["route_kind"])
        self.assertEqual("funding_partner", partner["route_kind"])
        self.assertNotEqual(customer["product_destination"], partner["product_destination"])
        self.assertIn("guaranteed approval", customer["prohibited_claims"])
        self.assertIn("guaranteed earnings", partner["prohibited_claims"])

    def test_one_route_preserves_fiction_fact_boundary(self):
        packet = injective_campaign("book-anima-universe", "instagram", injection_point="anima_rpg_quest")
        self.assertIsNone(packet["product_destination"])
        self.assertTrue(any("fiction" in rule.lower() for rule in packet["parallel_theme_rules"]))
        self.assertIn("fiction", packet["creative_label"].lower())

    def test_funnel_has_evidence_measurement_stage(self):
        funnel = injective_funnel("newsletter")
        self.assertEqual("planning_only", funnel["state"])
        self.assertEqual(["attention","interest","bridge","offer","action","measurement","evolution"],
                         [x["stage"] for x in funnel["stages"]])
        self.assertIn("separate evidenced events", funnel["stages"][5]["rule"])
        self.assertEqual(0, funnel["external_actions"])

    def test_newsletter_map_covers_every_route(self):
        packet = newsletter_injective_map()
        self.assertEqual(set(ROUTES), {x["route_id"] for x in packet["sections"]})
        self.assertTrue(all(x["state"] == "unpublished_newsletter_candidate" for x in packet["sections"]))
        self.assertEqual(0, packet["external_actions"])

    def test_invalid_route_and_injection_point_fail_closed(self):
        with self.assertRaises(ValueError):
            route_record("missing")
        with self.assertRaises(ValueError):
            injective_campaign("newsletter", "linkedin", injection_point="telepathy")
        self.assertIn("newsletter_feature", INJECTION_POINTS)


if __name__ == "__main__":
    unittest.main()
