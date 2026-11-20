"""Synthetic diary records only; no owner records, source fetches or model calls."""
from copy import deepcopy
import json
import unittest

from control_tower.diary import (build_diary_briefing, diary_entry_digest,
                                  validate_diary_entry)
from control_tower.network_contract import MAX_PACKET_BYTES, canonical, digest
from control_tower.portfolio import INITIATIVES


def entry(entry_id="synthetic-entry", visibility="public_candidate", date="2026-10-22"):
    return {"schema_version": 1, "kind": "jarvis.diary_entry", "entry_id": entry_id,
            "date": date, "timezone": "America/Los_Angeles", "initiative_id": "jarvis-tools",
            "title": "Synthetic project note", "visibility": visibility,
            "summary": "This is a synthetic test fixture, not a report of completed work.",
            "observations": [{"observation_id": "observation-01", "text": "A planned synthetic check.",
                              "evidence_state": "planned", "source_ids": []}],
            "sources": [], "next_action": "Review the synthetic fixture.",
            "media_notes": {"audience": "", "visual_style": "", "audio_style": "",
                            "learning_goal": "", "call_to_action": ""}}


def sourced_entry():
    value = entry()
    value["sources"] = [{"source_id": "source-01", "title": "Synthetic documentation reference",
                         "url": "https://example.org/documentation"}]
    value["observations"][0].update(evidence_state="source_linked", source_ids=["source-01"])
    return value


class DiaryContractTests(unittest.TestCase):
    def test_validation_returns_deep_copy_and_canonical_digest(self):
        original = sourced_entry()
        clean = validate_diary_entry(original)
        self.assertEqual(clean, original)
        clean["observations"][0]["source_ids"].clear()
        clean["media_notes"]["audience"] = "changed"
        self.assertEqual(original["observations"][0]["source_ids"], ["source-01"])
        self.assertEqual(original["media_notes"]["audience"], "")
        self.assertEqual(diary_entry_digest(original), digest(original))
        self.assertEqual(diary_entry_digest(original), diary_entry_digest(dict(reversed(list(original.items())))))

    def test_all_portfolio_ids_are_accepted(self):
        self.assertEqual(len(INITIATIVES), 12)
        for initiative_id in INITIATIVES:
            value = entry()
            value["initiative_id"] = initiative_id
            self.assertEqual(validate_diary_entry(value)["initiative_id"], initiative_id)

    def test_exact_record_keys_and_types(self):
        fixtures = []
        for key in entry():
            value = entry()
            del value[key]
            fixtures.append(value)
        for key, invalid in (("schema_version", True), ("schema_version", 1.0), ("schema_version", 2),
                             ("kind", "other"), ("title", 10), ("observations", ()),
                             ("sources", ()), ("media_notes", []), ("initiative_id", True)):
            value = entry()
            value[key] = invalid
            fixtures.append(value)
        for nested in ("entry", "observation", "source", "media"):
            value = sourced_entry()
            target = {"entry": value, "observation": value["observations"][0],
                      "source": value["sources"][0], "media": value["media_notes"]}[nested]
            target["unexpected"] = "synthetic hidden value"
            fixtures.append(value)
        class TextSubclass(str):
            pass
        value = entry()
        value["title"] = TextSubclass("synthetic subclass")
        fixtures.append(value)
        for value in fixtures:
            with self.subTest(case=str(value.keys())):
                with self.assertRaises(ValueError):
                    validate_diary_entry(value)

    def test_identifiers_have_exact_ascii_boundary(self):
        for valid in ("aa", "a" * 48, "entry-01_v1.2"):
            value = entry(valid)
            self.assertEqual(validate_diary_entry(value)["entry_id"], valid)
        for invalid in ("a", "a" * 49, "Upper", "bad id", "bad\n", "éa", "a/../b", True):
            with self.subTest(invalid=repr(invalid)), self.assertRaises(ValueError):
                validate_diary_entry(entry(invalid))
        for key, location in (("observation_id", "observations"), ("source_id", "sources")):
            value = sourced_entry()
            value[location][0][key] = "a" * 49
            with self.assertRaises(ValueError):
                validate_diary_entry(value)

    def test_dates_are_ascii_gregorian_and_timezone_fixed(self):
        for valid in ("0001-01-01", "9999-12-31", "2000-02-29", "2024-02-29"):
            self.assertEqual(validate_diary_entry(entry(date=valid))["date"], valid)
        for invalid in ("0000-01-01", "1900-02-29", "2026-02-29", "2026-2-01", "2026-10-22Z",
                        "２０２６-10-22", "2026-13-01", "2026-04-31", None):
            with self.subTest(date=invalid), self.assertRaises(ValueError):
                validate_diary_entry(entry(date=invalid))
        for key, value in (("timezone", "UTC"), ("initiative_id", "unknown-project"),
                           ("visibility", "public")):
            invalid = entry()
            invalid[key] = value
            with self.assertRaises(ValueError):
                validate_diary_entry(invalid)

    def test_text_is_bounded_by_utf8_bytes(self):
        for field, limit in (("title", 180), ("summary", 3000), ("next_action", 1500)):
            value = entry()
            value[field] = "é" * (limit // 2)
            validate_diary_entry(value)
            value[field] += "é"
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_diary_entry(value)
        value = entry()
        value["observations"][0]["text"] = "😀" * 250
        validate_diary_entry(value)
        value["observations"][0]["text"] += "x"
        with self.assertRaises(ValueError):
            validate_diary_entry(value)
        value = entry()
        value["media_notes"]["audience"] = "é" * 301
        with self.assertRaises(ValueError):
            validate_diary_entry(value)

    def test_unicode_and_blank_rules_do_not_mutate_content(self):
        for invalid in ("", " \t\n\r", "\u0085", "\u2003", "a\x00b", "a\x0bb", "\ud800"):
            value = entry()
            value["summary"] = invalid
            with self.subTest(invalid=repr(invalid)), self.assertRaises(ValueError):
                validate_diary_entry(value)
        for valid in ("a\t\n\rb", "é😀", "a\ufffeb\uffffc"):
            value = entry()
            value["summary"] = valid
            self.assertEqual(validate_diary_entry(value)["summary"], valid)
        for invalid in ("", "\u0085", "é" * 101):
            value = sourced_entry()
            value["sources"][0]["title"] = invalid
            with self.assertRaises(ValueError):
                validate_diary_entry(value)

    def test_sources_use_existing_https_boundary(self):
        for url in ("https://example.org/", "HTTPS://EXAMPLE.ORG:443/path?q=value#anchor",
                    "https://example.org/café", "https://[::1]:443/reference"):
            value = sourced_entry()
            value["sources"][0]["url"] = url
            self.assertEqual(validate_diary_entry(value)["sources"][0]["url"], url)
        for url in ("http://example.org", "https://", "https://user:secret@example.org", "https://@example.org",
                    "https://example.org:444", "https://example.org:bad", "https://example.org/a b",
                    "https://example.org/\tpath", "https://example.org/\u0085", "https://example.org\\bad",
                    "https://example.org/" + "é" * 500):
            value = sourced_entry()
            value["sources"][0]["url"] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_diary_entry(value)

    def test_source_references_and_labels_are_validated_not_verified(self):
        value = sourced_entry()
        self.assertEqual(validate_diary_entry(value)["observations"][0]["evidence_state"], "source_linked")
        for references in ([], ["missing-source"], ["source-01", "source-01"], ("source-01",), [True]):
            value = sourced_entry()
            value["observations"][0]["source_ids"] = references
            with self.subTest(references=references), self.assertRaises(ValueError):
                validate_diary_entry(value)
        value = entry()
        value["observations"][0]["evidence_state"] = "verified"
        with self.assertRaises(ValueError):
            validate_diary_entry(value)
        for state in ("planned", "fictional", "owner_reported"):
            value = entry()
            value["observations"][0]["evidence_state"] = state
            validate_diary_entry(value)

    def test_collection_cardinality_and_duplicate_identifiers(self):
        for count in (0, 9):
            value = entry()
            value["observations"] = [{"observation_id": f"item-{i}", "text": "Synthetic.",
                                      "evidence_state": "fictional", "source_ids": []} for i in range(count)]
            with self.assertRaises(ValueError):
                validate_diary_entry(value)
        for collection in ("sources", "observations"):
            value = sourced_entry()
            value[collection].append(deepcopy(value[collection][0]))
            with self.assertRaises(ValueError):
                validate_diary_entry(value)
        value = sourced_entry()
        value["sources"] = [{"source_id": f"source-{i}", "title": "Synthetic", "url": "https://example.org"}
                            for i in range(6)]
        with self.assertRaises(ValueError):
            validate_diary_entry(value)


class DiaryBriefingTests(unittest.TestCase):
    def test_date_visibility_and_stable_order(self):
        rows = [entry("public-b"), entry("private-a", "private"), entry("internal-a", "internal"),
                entry("public-a"), entry("other-date", date="2026-10-21")]
        public = build_diary_briefing(rows, diary_date="2026-10-22")
        self.assertEqual([row["entry_id"] for row in public["entries"]], ["public-a", "public-b"])
        self.assertEqual(public, build_diary_briefing(list(reversed(rows)), diary_date="2026-10-22"))
        owner = build_diary_briefing(rows, diary_date="2026-10-22", audience="owner")
        self.assertEqual([row["entry_id"] for row in owner["entries"]], ["internal-a", "private-a", "public-a", "public-b"])
        self.assertEqual(public["publication_approval"], "not_granted")
        self.assertEqual(public["source_verification"], "not_performed")
        self.assertEqual(public["external_actions"], 0)
        claimed = public.pop("briefing_sha256")
        self.assertEqual(claimed, digest(public))

    def test_hidden_records_do_not_contribute_ids_text_counts_or_digest(self):
        candidate = sourced_entry()
        expected = build_diary_briefing([candidate], diary_date="2026-10-22")
        hidden = [entry("private-marker", "private"), entry("internal-marker", "internal"),
                  entry("other-date-marker", date="2026-10-21")]
        for row in hidden:
            row["title"] = "HIDDEN_SYNTHETIC_TEXT"
            row["summary"] = "HIDDEN_SYNTHETIC_TEXT"
        actual = build_diary_briefing([candidate] + hidden, diary_date="2026-10-22")
        self.assertEqual(actual, expected)
        for marker in ("HIDDEN_SYNTHETIC_TEXT", "private-marker", "internal-marker", "other-date-marker"):
            self.assertNotIn(marker, json.dumps(actual))
        hidden[0]["summary"] = "CHANGED_HIDDEN_TEXT"
        self.assertEqual(build_diary_briefing([candidate] + hidden, diary_date="2026-10-22"), expected)

    def test_empty_date_has_explicit_status_and_no_hidden_count(self):
        empty = build_diary_briefing([], diary_date="2026-10-22")
        hidden = build_diary_briefing([entry("private-only", "private")], diary_date="2026-10-22")
        self.assertEqual(hidden, empty)
        self.assertEqual(empty["status"], "no_eligible_entry")
        self.assertEqual(empty["entry_count"], 0)
        self.assertEqual(empty["entries"], [])

    def test_all_inputs_are_validated_before_filtering_and_error_is_redacted(self):
        bad = entry("private-record", "private")
        bad["summary"] = "PRIVATE_SYNTHETIC_SECRET\x00"
        with self.assertRaises(ValueError) as error:
            build_diary_briefing([entry(), bad], diary_date="2026-10-22")
        self.assertNotIn("PRIVATE_SYNTHETIC_SECRET", str(error.exception))
        for kwargs in ({"diary_date": "2026-02-30"}, {"diary_date": "2026-10-22", "audience": "internal"},
                       {"diary_date": "2026-10-22", "audience": True}):
            with self.assertRaises(ValueError):
                build_diary_briefing([], **kwargs)
        for values in ({}, iter([]), [entry(), entry()]):
            with self.assertRaises(ValueError):
                build_diary_briefing(values, diary_date="2026-10-22")

    def test_eligible_daily_limit_and_input_limit(self):
        rows = [entry(f"public-{i}") for i in range(7)]
        self.assertEqual(build_diary_briefing(rows + [entry("hidden-one", "private")],
                                            diary_date="2026-10-22")["entry_count"], 7)
        with self.assertRaises(ValueError):
            build_diary_briefing(rows + [entry("public-extra")], diary_date="2026-10-22")
        with self.assertRaises(ValueError):
            build_diary_briefing(rows + [entry("hidden-one", "private")], diary_date="2026-10-22", audience="owner")
        with self.assertRaises(ValueError):
            build_diary_briefing([entry()] * 1001, diary_date="2026-10-22")

    def test_excerpts_keep_unicode_sources_and_all_evidence_labels(self):
        value = sourced_entry()
        value["summary"] = "😀" * 150
        value["next_action"] = "é" * 200
        value["sources"][0]["title"] = "é" * 100
        value["observations"][0]["text"] = "😀" * 100
        for i, state in enumerate(("planned", "owner_reported", "fictional")):
            value["observations"].append({"observation_id": f"observation-{i + 2}", "text": "Synthetic label.",
                                           "evidence_state": state, "source_ids": []})
        result = build_diary_briefing([value], diary_date="2026-10-22")
        brief = result["entries"][0]
        self.assertEqual(brief["summary_excerpt"], "😀" * 100)
        self.assertTrue(brief["summary_truncated"])
        self.assertEqual(brief["next_action_excerpt"], "é" * 120)
        self.assertTrue(brief["next_action_truncated"])
        self.assertTrue(brief["observations"][0]["text_truncated"])
        self.assertEqual(brief["observations_omitted"], 1)
        self.assertEqual(brief["evidence_states"], ["fictional", "owner_reported", "planned", "source_linked"])
        self.assertEqual(brief["sources"][0]["url"], value["sources"][0]["url"])
        self.assertTrue(brief["sources"][0]["title_truncated"])
        self.assertLessEqual(len(canonical(result)), MAX_PACKET_BYTES)
        self.assertNotIn("media_notes", brief)

    def test_packet_bound_includes_json_escaping(self):
        value = entry()
        value["title"] = "\t" * 179 + "x"
        value["summary"] = "\t" * 2999 + "x"
        value["next_action"] = "\t" * 1499 + "x"
        for key in value["media_notes"]:
            value["media_notes"][key] = "\t" * 600
        value["observations"] = [{"observation_id": f"observation-{i}", "text": "\t" * 999 + "x",
                                  "evidence_state": "fictional", "source_ids": []} for i in range(8)]
        self.assertLessEqual(len(canonical(validate_diary_entry(value))), MAX_PACKET_BYTES)
        rows = []
        for i in range(7):
            row = deepcopy(value)
            row["entry_id"] = f"entry-{i}"
            row["sources"] = [{"source_id": f"source-{j}", "title": "Synthetic", "url": "https://example.org/" + '"' * 980}
                              for j in range(5)]
            validate_diary_entry(row)
            rows.append(row)
        with self.assertRaisesRegex(ValueError, "briefing exceeds 64 KiB"):
            build_diary_briefing(rows, diary_date="2026-10-22")


if __name__ == "__main__":
    unittest.main()
