import unittest
from control_tower.creative_ad_foundry import CAMPAIGN_UNIVERSES, TONE_MODES, creative_blueprint, creative_campaign_family, newsletter_feature
from control_tower.organic_marketing import FREE_CHANNELS, PRODUCTS

class CreativeAdFoundryTests(unittest.TestCase):
    def test_entertainment_of_life_is_labeled_satire(self):
        bp = creative_blueprint('jarvis-ai-building-ai','entertainment-of-life','linkedin',tone='peace_through_wordplay')
        self.assertIn('satire', bp['story_label'].lower())
        self.assertIn('prevent warfare', ' '.join(bp['prompt_11_review']).lower())
        self.assertEqual(0,bp['external_actions'])

    def test_tiktok_fails_closed(self):
        with self.assertRaises(ValueError):
            creative_blueprint('education-hub','join-space-aliens','tiktok')

    def test_family_uses_all_active_channels_only(self):
        family=creative_campaign_family('book-incubator','entertainment-of-life',tone='cosmic_comedy')
        self.assertEqual(len(FREE_CHANNELS),family['active_channel_count'])
        self.assertNotIn('tiktok',{x['channel'] for x in family['blueprints']})
        self.assertEqual(0,family['publishing_actions'])

    def test_all_products_universes_tones_compile(self):
        for p in PRODUCTS:
            for u in CAMPAIGN_UNIVERSES:
                for tone in TONE_MODES:
                    bp=creative_blueprint(p,u,'threads',tone=tone)
                    self.assertEqual(p,bp['product_id'])
                    self.assertEqual(u,bp['campaign_universe'])
                    self.assertEqual(tone,bp['tone'])
                    self.assertEqual(64,len(bp['blueprint_sha256']))

    def test_funding_claim_controls_are_preserved(self):
        customer=creative_blueprint('funding-7figures','entertainment-of-life','facebook')
        partner=creative_blueprint('partner-7figures','entertainment-of-life','facebook')
        self.assertIn('guaranteed approval',customer['prohibited_claims'])
        self.assertIn('guaranteed earnings',partner['prohibited_claims'])
        self.assertNotEqual(customer['destination'],partner['destination'])

    def test_book_incubator_has_no_invented_destination(self):
        bp=creative_blueprint('book-incubator','entertainment-of-life','instagram')
        self.assertIsNone(bp['destination'])
        self.assertIn('release destination',bp['cta'])

    def test_newsletter_feature_has_comedy_structure(self):
        feature=newsletter_feature('education-hub','entertainment-of-life')
        self.assertEqual('unpublished_newsletter_candidate',feature['state'])
        self.assertTrue(any('joke' in x.lower() for x in feature['section_plan']))
        self.assertEqual(0,feature['external_actions'])

if __name__ == '__main__': unittest.main()
