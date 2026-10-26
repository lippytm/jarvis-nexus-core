import unittest
from control_tower.affiliate_universe import OPPORTUNITY_WORLDS
from control_tower.injective_marketing import MEMBERSHIP_LADDER, ROUTES
from control_tower.organic_marketing import FREE_CHANNELS, PRODUCTS
from control_tower.portfolio import portfolio_catalog
from control_tower.space_alien_comedy_affiliate import (
    PROGRAM, PRODUCT_ROUTE_MAP, newsletter_program_map, portfolio_injection_map,
    product_campaign, product_campaign_family, program_registry,
)

class SpaceAlienComedyAffiliateTests(unittest.TestCase):
    def test_registry_covers_every_current_registry_without_claiming_metrics(self):
        registry=program_registry()
        self.assertEqual(set(PRODUCTS),set(registry['registered_products']))
        self.assertEqual(set(OPPORTUNITY_WORLDS),set(registry['registered_opportunity_worlds']))
        self.assertEqual(set(MEMBERSHIP_LADDER),set(registry['registered_memberships']))
        self.assertEqual(set(ROUTES),set(registry['registered_injective_routes']))
        self.assertEqual({i['id'] for i in portfolio_catalog()['initiatives']},set(registry['registered_portfolio_initiatives']))
        self.assertIsNone(registry['actual_metrics'])
        self.assertEqual(0,registry['external_actions'])

    def test_every_registered_product_maps_to_one_route(self):
        self.assertEqual(set(PRODUCTS),set(PRODUCT_ROUTE_MAP))
        for p,r in PRODUCT_ROUTE_MAP.items():
            self.assertIn(r,ROUTES)

    def test_every_product_builds_for_all_active_channels_only(self):
        for product_id in PRODUCTS:
            family=product_campaign_family(product_id)
            self.assertEqual(len(FREE_CHANNELS),family['campaign_count'])
            self.assertNotIn('tiktok',{x['channel'] for x in family['campaigns']})
            self.assertEqual(0,family['publishing_actions'])
            self.assertIsNone(family['actual_metrics'])

    def test_funding_and_partner_claim_controls_survive_comedy_overlay(self):
        funding=product_campaign('funding-7figures','facebook')
        partner=product_campaign('partner-7figures','facebook')
        self.assertIn('guaranteed approval',funding['prohibited_claims'])
        self.assertIn('guaranteed earnings',partner['prohibited_claims'])
        self.assertNotEqual(funding['route_id'],partner['route_id'])

    def test_comedy_program_has_reality_boundary(self):
        self.assertIn('do not imply',PROGRAM['reality_rule'].lower())
        packet=product_campaign('jarvis-ai-building-ai','linkedin',comedy_format='roast_and_rebuild')
        self.assertTrue(any('fiction/comedy/satire' in x.lower() for x in packet['prompt_11_gate']))
        self.assertEqual('unpublished_draft',packet['state'])

    def test_portfolio_map_covers_all_current_initiatives_without_inventing_destinations(self):
        packet=portfolio_injection_map()
        self.assertEqual(len(portfolio_catalog()['initiatives']),len(packet['initiatives']))
        self.assertTrue(all(x['injection_state']=='creative_overlay_candidate' for x in packet['initiatives']))
        self.assertTrue(all('destination' not in x for x in packet['initiatives']))

    def test_newsletter_map_covers_all_registered_products(self):
        packet=newsletter_program_map()
        self.assertEqual(set(PRODUCTS),{x['product_id'] for x in packet['sections']})
        self.assertTrue(all(x['state']=='unpublished_newsletter_candidate' for x in packet['sections']))
        self.assertEqual(0,packet['external_actions'])

if __name__=='__main__': unittest.main()
