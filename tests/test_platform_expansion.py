"""Regression checks for portable targets, review boundaries and copied drafts."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from control_tower.connections import connector_report
from control_tower.handoffs import HandoffLedger
from control_tower.injective_marketing import injective_campaign
from control_tower.network_contract import TARGETS, digest, load_packet, validate_draft
from control_tower.provider_catalog import provider_catalog, provider_details
from control_tower.swarm_factory import build_swarm
from control_tower.validation import json_record_errors

REVISION = "e7c99a44933f14532fde05070bedb4b6ce049a52"
NEW_TARGETS = ("slack", "zapier", "claude-cowork", "perplexity")


class PlatformExpansionTests(unittest.TestCase):
    def test_all_targets_share_catalog_contract_and_readiness(self):
        catalog = provider_catalog()
        self.assertEqual(set(catalog), set(TARGETS))
        self.assertEqual(len(TARGETS), 16)
        report = connector_report()
        for target in NEW_TARGETS:
            self.assertIn(target, TARGETS)
            self.assertEqual(report[target]["status"], "unverified")
            self.assertEqual(report[target]["runtime_available"], "unknown")
            self.assertEqual(report[target]["write_gate"], "owner_review")
            self.assertEqual(catalog[target]["reviewed_on"], "2026-10-27")
            self.assertEqual(catalog[target]["live_api_adapter"], "not_implemented")

    def test_new_targets_keep_manual_review_and_return_bindings(self):
        for target in NEW_TARGETS:
            with self.subTest(target=target), TemporaryDirectory() as directory:
                manifest = build_swarm("ai-jarvis", [target], swarm_id="expanded",
                                       source_revision=REVISION)
                original = {"schema_version": 1, "kind": "jarvis.draft",
                            "project_id": "ai-jarvis", "target": target,
                            "text": "Synthetic local fixture only; no provider call or message."}
                self.assertEqual(validate_draft(original), original)
                self.assertEqual(manifest["model_calls"], 0)
                with HandoffLedger(Path(directory) / "ledger.sqlite3") as ledger:
                    record = ledger.stage(original, manifest, assistant_id="expanded.builder",
                                          handoff_id="expanded-first")
                    checksum = record["handoff_sha256"]
                    with self.assertRaises(ValueError):
                        ledger.export("expanded-first", expected_sha256=checksum)
                    ledger.review("expanded-first", reviewer_id="owner-review-label",
                                  expected_sha256=checksum)
                    exported = ledger.export("expanded-first", expected_sha256=checksum)
                    self.assertEqual(exported["mode"], "manual_handoff")
                    packet = {"schema_version": 1, "kind": "jarvis.return",
                              "return_id": "expanded-return", "handoff_id": "expanded-first",
                              "handoff_sha256": checksum, "source_provider": target,
                              "text": "Synthetic fixture response, not received from a provider.",
                              "evidence_urls": []}
                    wrong = {**packet, "source_provider": "github"}
                    with self.assertRaises(ValueError):
                        ledger.import_return(wrong)
                    result = ledger.import_return(packet)
                    self.assertEqual(result["state"], "returned_unverified")
                    self.assertEqual(result["sender_authentication"], "not_established")
                with HandoffLedger(Path(directory) / "ledger.sqlite3") as reopened:
                    self.assertEqual(reopened.status()["return_count"], 1)
                    self.assertTrue(reopened.import_return(packet)["duplicate"])

    def test_all_six_media_targets_and_requested_workspaces_are_retained(self):
        requested = {"github", "youtube", "facebook", "linkedin", "instagram",
                     "hostinger", "slack", "zapier", "threads", "substack",
                     "claude", "claude-cowork", "gemini", "perplexity"}
        manifest = build_swarm("ai-jarvis", sorted(requested), swarm_id="complete",
                               source_revision=REVISION)
        self.assertEqual(set(manifest["targets"]), requested)
        self.assertEqual(len(manifest["assistants"]), 5)
        self.assertTrue(all(item["state"] == "inactive_proposal"
                            for item in manifest["assistants"]))

    def test_nested_catalog_edits_do_not_enable_or_change_other_targets(self):
        for target in NEW_TARGETS:
            row = provider_details(target)
            row["handoff_modes"]["live_api"] = "enabled"
            row["documentation_urls"].clear()
            fresh = provider_details(target)
            self.assertEqual(fresh["handoff_modes"]["live_api"], "not_implemented")
            self.assertTrue(fresh["documentation_urls"])

    def test_unknown_target_does_not_fall_back_to_a_provider(self):
        for target in ("cowork", "Claude Cowork", "slack/channel", "https://example.com"):
            with self.assertRaises(ValueError):
                validate_draft({"schema_version": 1, "kind": "jarvis.draft",
                                "project_id": "ai-jarvis", "target": target, "text": "draft"})


class DraftReliabilityTests(unittest.TestCase):
    def test_utf8_packet_below_limit_survives_file_load(self):
        record = {"text": "😀" * 6000}
        self.assertLess(len(json.dumps(record, ensure_ascii=False).encode("utf-8")), 65536)
        self.assertGreater(len(json.dumps(record, ensure_ascii=True)), 65536)
        self.assertEqual(json_record_errors(record), [])
        with TemporaryDirectory() as directory:
            path = Path(directory) / "unicode.json"
            path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(load_packet(path), record)

    def test_utf8_over_limit_and_invalid_surrogates_rejected(self):
        self.assertIn("record exceeds 64 KiB", json_record_errors({"text": "😀" * 17000}))
        self.assertTrue(json_record_errors({"text": "\ud800"}))
        self.assertTrue(json_record_errors({"text": float("nan")}))
        cyclic = {}
        cyclic["loop"] = cyclic
        self.assertTrue(json_record_errors(cyclic))

    def test_editing_a_campaign_does_not_change_other_campaigns_or_digest(self):
        first = injective_campaign("education-membership", "facebook")
        saved = deepcopy(first)
        first["theme"]["name"] = "Edited in one draft"
        first["membership"]["destination"] = "https://example.invalid"
        later = injective_campaign("education-membership", "facebook")
        self.assertEqual(later, saved)
        body = {key: value for key, value in later.items() if key != "campaign_sha256"}
        self.assertEqual(later["campaign_sha256"], digest(body))


if __name__ == "__main__":
    unittest.main()
