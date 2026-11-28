from copy import deepcopy
import unittest

from control_tower.affiliate_universe import (
    AFFILIATE_UNIVERSE, OPPORTUNITY_WORLDS, ROUTE_CLASSES, opportunity_matrix,
    opportunity_world, universe_registry,
)


class AffiliateUniverseTests(unittest.TestCase):
    def test_registry_edits_preserve_other_records_and_guardrails(self):
        theme = deepcopy(AFFILIATE_UNIVERSE)
        worlds = deepcopy(OPPORTUNITY_WORLDS)
        routes = deepcopy(ROUTE_CLASSES)
        baseline = deepcopy(universe_registry())
        matrix = opportunity_matrix()
        packets = {wid: opportunity_world(wid) for wid in worlds}
        try:
            edited = universe_registry()
            independent = universe_registry()
            edited["theme"]["reality_label"] = "Caller-only change"
            edited["opportunity_worlds"]["business-funding-referrals"]["guardrails"].clear()
            edited["opportunity_worlds"]["education-memberships"]["examples"].append("Caller-only example")
            del edited["opportunity_worlds"]["ai-tools-software"]
            edited["route_classes"]["affiliate_referral"] = "Caller-only route"
            self.assertEqual(independent, baseline)
            self.assertEqual(universe_registry(), baseline)
            self.assertEqual(AFFILIATE_UNIVERSE, theme)
            self.assertEqual(OPPORTUNITY_WORLDS, worlds)
            self.assertEqual(ROUTE_CLASSES, routes)
            self.assertEqual(opportunity_matrix(), matrix)
            for wid, packet in packets.items():
                with self.subTest(world=wid):
                    self.assertEqual(opportunity_world(wid), packet)
        finally:
            # Preserve isolation when reproducing the unfixed shared-state bug.
            for shared, original in ((AFFILIATE_UNIVERSE, theme), (OPPORTUNITY_WORLDS, worlds), (ROUTE_CLASSES, routes)):
                shared.clear()
                shared.update(original)

    def test_registry_contains_twelve_worlds_without_claiming_actual_program_count(self):
        registry = universe_registry()
        self.assertEqual(12, len(registry["opportunity_worlds"]))
        self.assertIsNone(registry["actual_program_count"])
        self.assertIsNone(registry["actual_revenue"])
        self.assertEqual(0, registry["external_actions"])
        self.assertEqual(64, len(registry["registry_sha256"]))

    def test_unlimited_language_has_reality_boundary(self):
        self.assertIn("Unlimited Possibilities", AFFILIATE_UNIVERSE["creative_tagline"])
        self.assertIn("no earnings", AFFILIATE_UNIVERSE["reality_label"].lower())
        matrix = opportunity_matrix()
        self.assertIn("Aspirational", matrix["reality_boundary"])

    def test_every_world_has_guardrails_and_prompt_11_review(self):
        for world_id, raw in OPPORTUNITY_WORLDS.items():
            with self.subTest(world_id=world_id):
                self.assertTrue(raw["guardrails"])
                packet = opportunity_world(world_id)
                self.assertTrue(packet["prompt_11_review"])
                self.assertEqual(0, packet["external_actions"])
                self.assertEqual(64, len(packet["world_sha256"]))

    def test_business_funding_world_separates_approval_and_earnings_guarantees(self):
        packet = opportunity_world("business-funding-referrals")
        text = " ".join(packet["guardrails"])
        self.assertIn("no guaranteed approval", text)
        self.assertIn("no guaranteed earnings", text)

    def test_fiction_world_remains_labeled_fiction(self):
        packet = opportunity_world("space-alien-entertainment")
        self.assertEqual("fictional_brand_world", packet["state"])
        self.assertTrue(any("fiction" in x.lower() for x in packet["guardrails"]))

    def test_matrix_is_planning_only_and_has_scale_gate(self):
        matrix = opportunity_matrix(["ai-tools-software", "newsletter-community"])
        self.assertEqual("planning_only", matrix["state"])
        self.assertEqual(2, len(matrix["worlds"]))
        self.assertIn("verify one real offer", matrix["next_step"])
        self.assertIsNone(matrix["actual_metrics"])

    def test_invalid_or_duplicate_worlds_fail_closed(self):
        with self.assertRaises(ValueError):
            opportunity_world("missing")
        with self.assertRaises(ValueError):
            opportunity_matrix([])
        with self.assertRaises(ValueError):
            opportunity_matrix(["newsletter-community", "newsletter-community"])


if __name__ == "__main__":
    unittest.main()
