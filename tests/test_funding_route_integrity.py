"""Funding journeys must preserve the selected product through route handoffs."""
import unittest

from control_tower.injective_marketing import (
    ROUTES, injective_campaign, newsletter_injective_map, route_record,
)
from control_tower.organic_marketing import FREE_CHANNELS, PRODUCTS
from control_tower.space_alien_comedy_affiliate import (
    PRODUCT_ROUTE_MAP, newsletter_program_map, product_campaign,
)

DESTINATIONS = {
    "funding-getbizfunds": "https://lippytmai.getbizfunds.com",
    "funding-7figures": "http://www.7figurescredit.com?a_aid=lippytm",
    "partner-7figures": "http://join.7figurespartners.com/?a_aid=lippytm",
    "partner-lendtrack": "http://lendtrack.ai/join/lippytmai",
}


class FundingRouteIntegrityTests(unittest.TestCase):
    def test_every_comedy_product_route_resolves_to_the_same_product(self):
        for product_id, route_id in PRODUCT_ROUTE_MAP.items():
            with self.subTest(product=product_id, route=route_id):
                self.assertEqual(ROUTES[route_id]["product_id"], product_id)

    def test_four_exact_destinations_survive_overlay_to_injective_handoff(self):
        self.assertEqual(len(set(DESTINATIONS.values())), 4)
        for product_id, destination in DESTINATIONS.items():
            for channel in FREE_CHANNELS:
                with self.subTest(product=product_id, channel=channel):
                    overlay = product_campaign(product_id, channel)
                    routed = injective_campaign(overlay["route_id"], channel)
                    self.assertEqual(overlay["destination"], destination)
                    self.assertEqual(routed["product_id"], product_id)
                    self.assertEqual(routed["destination"], destination)
                    self.assertEqual(routed["product_destination"], destination)
                    self.assertEqual(routed["audience"], PRODUCTS[product_id].audience)
                    self.assertEqual(routed["disclosure"], PRODUCTS[product_id].disclosure)
                    self.assertEqual(routed["external_actions"], 0)
                    self.assertEqual(routed["publishing_actions"], 0)
                    self.assertIsNone(routed["actual_metrics"])
                    if product_id.startswith("funding-"):
                        self.assertEqual(routed["route_kind"], "funding_customer")
                        self.assertIn("guaranteed approval", routed["prohibited_claims"])
                    else:
                        self.assertNotEqual(routed["route_kind"], "funding_customer")
                        self.assertIn("guaranteed earnings", routed["prohibited_claims"])

    def test_newsletter_handoff_preserves_each_funding_and_partner_journey(self):
        by_route = {row["route_id"]: row for row in newsletter_injective_map()["sections"]}
        by_product = {row["product_id"]: row for row in newsletter_program_map()["sections"]}
        for product_id, destination in DESTINATIONS.items():
            route_id = by_product[product_id]["route_id"]
            with self.subTest(product=product_id):
                self.assertEqual(ROUTES[route_id]["product_id"], product_id)
                self.assertEqual(by_route[route_id]["destination"], destination)
        self.assertNotEqual(by_product["funding-getbizfunds"]["route_id"],
                            by_product["funding-7figures"]["route_id"])

    def test_existing_route_ids_keep_their_original_providers(self):
        expected = {
            "funding-information": "funding-7figures",
            "affiliate-builder-membership": "partner-7figures",
            "referral-partner": "partner-lendtrack",
        }
        for route_id, product_id in expected.items():
            self.assertEqual(route_record(route_id)["product_id"], product_id)
        selected = route_record("funding-getbizfunds")
        selected["product_id"] = "changed locally"
        self.assertEqual(route_record("funding-getbizfunds")["product_id"],
                         "funding-getbizfunds")


if __name__ == "__main__":
    unittest.main()
