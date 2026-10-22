import json
import unittest
from urllib.parse import urlsplit

from control_tower.provider_catalog import (
    DISTRIBUTION_CHANNELS, PROVIDERS, provider_catalog, provider_details,
)


class ProviderCatalogTests(unittest.TestCase):
    def test_seven_requested_distribution_channels_and_distinct_ai_products(self):
        self.assertEqual(set(DISTRIBUTION_CHANNELS),
                         {"facebook", "linkedin", "substack", "instagram", "threads", "youtube", "github"})
        self.assertTrue(set(DISTRIBUTION_CHANNELS).issubset(PROVIDERS))
        self.assertTrue({"chatgpt", "openai", "gemini", "claude", "hostinger"}.issubset(PROVIDERS))
        self.assertNotEqual(PROVIDERS["chatgpt"]["category"], PROVIDERS["openai"]["category"])

    def test_export_availability_never_means_live_permission(self):
        for record in provider_catalog().values():
            self.assertEqual(record["handoff_modes"]["manual_draft_export"], "available")
            self.assertEqual(record["handoff_delivery"], "human_transfer_required")
            self.assertEqual(record["connection_status"], "unverified")
            self.assertEqual(record["live_api_adapter"], "not_implemented")
            self.assertEqual(record["write_operations"], "not_implemented")

    def test_nested_copy_mutation_cannot_change_future_catalog_or_constants(self):
        catalog = provider_catalog()
        catalog["hostinger"]["connection_status"] = "connected"
        catalog["hostinger"]["documentation_urls"].clear()
        catalog["hostinger"]["handoff_modes"]["live_api"] = "connected"
        catalog.clear()
        fresh = provider_catalog()
        self.assertTrue(fresh["hostinger"]["documentation_urls"])
        self.assertEqual(fresh["hostinger"]["connection_status"], "unverified")
        self.assertEqual(fresh["hostinger"]["handoff_modes"]["live_api"], "not_implemented")
        with self.assertRaises(TypeError):
            PROVIDERS["hostinger"]["connection_status"] = "connected"
        with self.assertRaises(TypeError):
            PROVIDERS["hostinger"]["handoff_modes"]["live_api"] = "connected"

    def test_unknown_and_malformed_lookup_cannot_become_a_url_or_fallback(self):
        for target in (None, [], {}, 0, True, "", "Hostinger", " hostinger", "https://attacker.invalid", "github/../../", "x" * 65):
            with self.assertRaisesRegex(ValueError, "unknown_provider"):
                provider_details(target)
        details = provider_details("github")
        details["required_configuration"].clear()
        self.assertTrue(provider_details("github")["required_configuration"])

    def test_documentation_is_official_https_and_catalog_is_json_serializable(self):
        allowed = {"learn.chatgpt.com", "developers.openai.com", "ai.google.dev", "platform.claude.com",
                   "docs.hostinger.com", "www.hostinger.com", "developers.facebook.com", "learn.microsoft.com",
                   "support.substack.com", "developers.google.com", "docs.github.com"}
        catalog = provider_catalog()
        json.dumps(catalog, allow_nan=False)
        for row in catalog.values():
            self.assertTrue(row["documentation_urls"])
            self.assertTrue(row["required_configuration"])
            for url in row["documentation_urls"]:
                parsed = urlsplit(url)
                self.assertEqual(parsed.scheme, "https")
                self.assertIn(parsed.hostname, allowed)
                self.assertIsNone(parsed.username)

    def test_substack_readonly_mcp_is_distinct_from_publication(self):
        row = provider_details("substack")
        self.assertEqual(row["api_documentation_status"], "read_only_mcp_documented")
        self.assertEqual(row["write_operations"], "not_implemented")
        self.assertTrue(any("cannot publish" in text for text in row["boundaries"]))


if __name__ == "__main__":
    unittest.main()
