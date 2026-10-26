import unittest
from urllib.parse import parse_qs, urlsplit

from control_tower.organic_marketing import (
    BLOCKED_CHANNELS, FREE_CHANNELS, PRODUCTS, campaign_packet, free_market_registry,
    newsletter_packet, product_record,
)


class OrganicMarketingTests(unittest.TestCase):
    def test_registry_has_thirteen_active_markets_and_tiktok_is_blocked(self):
        registry = free_market_registry()
        self.assertEqual(13, len(registry["channels"]))
        self.assertNotIn("tiktok", registry["channels"])
        self.assertEqual("blocked_for_owner", registry["blocked_channels"]["tiktok"]["state"])
        self.assertEqual(BLOCKED_CHANNELS["tiktok"], registry["blocked_channels"]["tiktok"])
        self.assertEqual(0, registry["external_actions"])
        self.assertEqual(0, registry["live_connections"])
        self.assertEqual(64, len(registry["registry_sha256"]))

    def test_every_product_gets_one_unpublished_brief_per_channel(self):
        for product_id in PRODUCTS:
            packet = campaign_packet(product_id, campaign_id="qa-campaign")
            self.assertEqual(set(FREE_CHANNELS), {b["channel"] for b in packet["briefs"]})
            self.assertEqual(13, len(packet["briefs"]))
            self.assertNotIn("tiktok", {b["channel"] for b in packet["briefs"]})
            self.assertEqual(0, packet["external_actions"])
            self.assertEqual(0, packet["publishing_actions"])
            self.assertIsNone(packet["actual_metrics"])
            self.assertTrue(all(b["state"] == "unpublished_draft_brief" for b in packet["briefs"]))

    def test_referral_parameters_are_preserved_and_utm_is_added(self):
        for product_id in ("funding-7figures", "partner-7figures", "partner-lendtrack"):
            product = product_record(product_id)
            base_query = parse_qs(urlsplit(product["destination"]).query)
            packet = campaign_packet(product_id, campaign_id="organic-qa")
            for brief in packet["briefs"]:
                query = parse_qs(urlsplit(brief["candidate_url"]).query)
                for key, value in base_query.items():
                    self.assertEqual(value, query[key])
                self.assertEqual([brief["channel"]], query["utm_source"])
                self.assertEqual(["organic"], query["utm_medium"])
                self.assertEqual(["organic-qa"], query["utm_campaign"])

    def test_customer_and_partner_routes_stay_separate(self):
        customer = campaign_packet("funding-7figures")
        partner = campaign_packet("partner-7figures")
        self.assertEqual("funding_customer", customer["product"]["journey_kind"])
        self.assertEqual("funding_partner", partner["product"]["journey_kind"])
        self.assertNotEqual(customer["product"]["destination"], partner["product"]["destination"])
        self.assertIn("approval", " ".join(customer["product"]["prohibited_claims"]))
        self.assertIn("earnings", " ".join(partner["product"]["prohibited_claims"]))

    def test_unreleased_book_incubator_has_no_invented_destination(self):
        packet = campaign_packet("book-incubator")
        self.assertIsNone(packet["product"]["destination"])
        self.assertTrue(all(b["candidate_url"] is None for b in packet["briefs"]))
        self.assertTrue(all(b["url_status"] == "unassigned" for b in packet["briefs"]))

    def test_newsletter_packet_connects_all_products_without_claiming_publication(self):
        packet = newsletter_packet()
        self.assertEqual(len(PRODUCTS), len(packet["sections"]))
        self.assertEqual("unpublished_draft", packet["publication_state"])
        self.assertEqual(0, packet["external_actions"])
        self.assertTrue(all(section["state"] == "newsletter_candidate_unpublished" for section in packet["sections"]))

    def test_unknown_product_and_duplicate_newsletter_ids_fail_closed(self):
        with self.assertRaises(ValueError):
            campaign_packet("missing")
        with self.assertRaises(ValueError):
            newsletter_packet(["education-hub", "education-hub"])


if __name__ == "__main__":
    unittest.main()
