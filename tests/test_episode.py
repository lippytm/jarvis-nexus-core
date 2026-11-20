"""Offline synthetic plans and the public pilot; no private records or provider calls."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from control_tower import episode as module
from control_tower.diary import diary_entry_digest
from control_tower.episode import build_episode, validate_episode
from control_tower.network_contract import MAX_PACKET_BYTES, canonical, digest, load_packet
from control_tower.portfolio import INITIATIVES


REVISION = "a" * 40


def entry(*states, visibility="public_candidate"):
    states = states or ("planned",)
    return {"schema_version": 1, "kind": "jarvis.diary_entry", "entry_id": "synthetic-diary",
            "date": "2026-10-22", "timezone": "America/Los_Angeles", "initiative_id": "jarvis-tools",
            "title": "Synthetic episode source", "visibility": visibility,
            "summary": "Synthetic supplied context, not a report of actual activity.",
            "observations": [{"observation_id": f"observation-{index:02d}",
                "text": f"Synthetic record {index}; this fixture describes no real project result.",
                "evidence_state": state, "source_ids": ["source-01"] if state == "source_linked" else []}
                for index, state in enumerate(states, 1)],
            "sources": [{"source_id": "source-01", "title": "Synthetic reference", "url": "https://example.org/reference"}],
            "next_action": "Review the synthetic plan before choosing a real next step.",
            "media_notes": {"audience": "", "visual_style": "", "audio_style": "",
                            "learning_goal": "", "call_to_action": ""}}


def episode(value=None, **kwargs):
    return build_episode(value if value is not None else entry(), source_revision=REVISION,
                         episode_id="synthetic-episode", **kwargs)


def rehash(value):
    value["episode_sha256"] = digest({key: item for key, item in value.items() if key != "episode_sha256"})
    return value


class EpisodeBuildTests(unittest.TestCase):
    def test_shipped_public_pilot_matches_its_source_and_current_compiler(self):
        root = Path(__file__).resolve().parents[1]
        source = load_packet(root / "examples/episodes/public-diary-source.json")
        pilot = validate_episode(load_packet(root / "examples/episodes/jarvis-diary-pilot.json"))
        self.assertEqual(source["visibility"], "public_candidate")
        self.assertEqual((pilot["audience"], pilot["source_visibility"]), ("public", "public_candidate"))
        self.assertEqual(pilot, build_episode(source, source_revision=pilot["source_context_revision"],
                                             episode_id=pilot["episode_id"]))

    def test_deterministic_digest_and_source_binding(self):
        source = entry("source_linked", "planned", "fictional")
        first = episode(source)
        second = episode(dict(reversed(list(source.items()))))
        self.assertEqual(first, second)
        self.assertEqual(len(first), 21)
        self.assertEqual(first["kind"], "jarvis.rpg_episode")
        self.assertEqual(first["source_entry_sha256"], diary_entry_digest(source))
        self.assertEqual(first["source_context_revision"], REVISION)
        expected = digest({key: value for key, value in first.items() if key != "episode_sha256"})
        self.assertEqual(first["episode_sha256"], expected)
        self.assertEqual(first["date"], source["date"])
        self.assertEqual(first["title"], source["title"])

    def test_input_and_template_objects_are_not_modified_or_shared(self):
        source = entry("source_linked")
        original = deepcopy(source)
        first = episode(source)
        first["scenes"][1]["source_ids"].clear()
        first["sources"][0]["title"] = "changed caller copy"
        first["quests"][0]["status"] = "completed"
        first["worlds"][0]["title"] = "changed caller world"
        self.assertEqual(source, original)
        later = episode(source)
        self.assertEqual(later["scenes"][1]["source_ids"], ["source-01"])
        self.assertEqual(later["quests"][0]["status"], "planned")
        self.assertEqual(later["worlds"][0]["title"], "The Lantern Archive")

    def test_default_public_rejects_private_and_internal_before_hashing(self):
        for visibility in ("private", "internal"):
            private = entry(visibility=visibility)
            private["title"] = "SYNTHETIC_PRIVATE_TITLE"
            private["observations"][0]["text"] = "SYNTHETIC_PRIVATE_RECORD"
            with self.subTest(visibility=visibility), patch.object(module, "diary_entry_digest") as source_hash, \
                 patch.object(module, "digest") as output_hash:
                with self.assertRaisesRegex(ValueError, "public_candidate") as caught:
                    episode(private)
                source_hash.assert_not_called()
                output_hash.assert_not_called()
                self.assertNotIn("SYNTHETIC_PRIVATE", str(caught.exception))
                self.assertNotIn(private["entry_id"], str(caught.exception))

    def test_explicit_owner_preserves_audience_and_source_visibility(self):
        for visibility in ("private", "internal", "public_candidate"):
            source = entry("owner_reported", visibility=visibility)
            source["observations"][0]["text"] = "SYNTHETIC_OWNER_RECORD"
            owner = episode(source, audience="owner")
            self.assertEqual(owner["audience"], "owner")
            self.assertEqual(owner["source_visibility"], visibility)
            self.assertIn("SYNTHETIC_OWNER_RECORD", owner["scenes"][1]["voiceover"])
            self.assertEqual(owner["publication_approval"], "not_granted")
            self.assertEqual(validate_episode(owner), owner)
        self.assertNotEqual(episode()["episode_sha256"], episode(audience="owner")["episode_sha256"])

    def test_invalid_audience_is_not_an_owner_shortcut(self):
        for audience in (None, True, "", "internal", "PUBLIC", "owner "):
            with self.subTest(audience=audience), self.assertRaises(ValueError):
                episode(entry(visibility="private"), audience=audience)

    def test_each_record_retains_label_and_original_source_ids(self):
        states = ("source_linked", "owner_reported", "planned", "fictional")
        for state in states:
            source = entry(state)
            source["observations"][0]["source_ids"] = ["source-01"]
            record = episode(source)["scenes"][1]
            self.assertEqual(record["evidence_state"], state)
            self.assertEqual(record["source_ids"], ["source-01"])
            self.assertIn("From the diary:", record["voiceover"])
            self.assertIn(module._RECORD_LABELS[state][0], record["voiceover"])
        mixed = episode(entry("source_linked", "planned", "fictional"))
        self.assertEqual([row["evidence_state"] for row in mixed["scenes"][1:4]],
                         ["source_linked", "planned", "fictional"])
        self.assertNotIn("mixed", [row["evidence_state"] for row in mixed["scenes"]])

    def test_scene_budget_and_explicit_omitted_record_count(self):
        for count in range(1, 9):
            source = entry(*(["fictional"] * count))
            built = episode(source)
            self.assertEqual(len(built["scenes"]), 6 if count == 1 else 7)
            records = [row for row in built["scenes"] if row["scene_id"].startswith("record-")]
            self.assertEqual(len(records), min(3, count))
            self.assertEqual(built["observations_omitted"], max(0, count - 3))
            self.assertEqual(records[-1]["title"], "Diary record: observation-" + f"{min(3, count):02d}")
            ids = [row["scene_id"] for row in built["scenes"]]
            self.assertEqual("briefing-revenue-plan" in ids, count >= 3)
            self.assertEqual("revenue-experiment" in ids, count < 3)

    def test_fictional_worlds_and_fixed_quests_never_award_completion_or_money(self):
        built = episode(entry("source_linked", "owner_reported"))
        self.assertEqual([row["world_id"] for row in built["worlds"]], ["archive", "forge", "observatory"])
        self.assertTrue(all("fictional" in row["description"] for row in built["worlds"]))
        self.assertEqual([(q["quest_id"], q["world_id"]) for q in built["quests"]],
                         [("hostinger-connection", "observatory"), ("ai-building-cycle", "forge"), ("media-review", "archive")])
        for quest in built["quests"]:
            self.assertEqual(quest["status"], "planned")
            self.assertEqual(quest["evidence_state"], "planned")
            self.assertEqual(quest["source_ids"], [])
            self.assertNotIn("xp", quest)
            self.assertNotIn("money", quest)
            self.assertNotIn("completed", quest)
        self.assertEqual(built["scenes"][0]["evidence_state"], "fictional")
        self.assertEqual(built["scenes"][-1]["evidence_state"], "fictional")
        self.assertTrue(built["scenes"][0]["voiceover"].startswith(module.FICTIONAL_FRAMING))

    def test_news_and_release_status_are_explicit_not_inferred(self):
        source = entry("source_linked")
        source["observations"][0]["text"] = "A synthetic supplied assertion, not independently verified by the compiler."
        built = episode(source)
        self.assertEqual(built["news_status"], "not_included_in_this_project_pilot")
        self.assertEqual(built["publication_approval"], "not_granted")
        self.assertEqual(built["external_actions"], 0)
        self.assertEqual(built["model_calls"], 0)
        for row in built["scenes"]:
            if row["scene_id"] not in {"opening", "closing"} and not row["scene_id"].startswith("record-"):
                self.assertEqual(row["evidence_state"], "planned")
        self.assertNotIn("verified_news", built)

    def test_all_initiatives_have_valid_bounded_fictional_world_placement(self):
        for identifier in INITIATIVES:
            source = entry()
            source["initiative_id"] = identifier
            built = episode(source)
            self.assertIn(INITIATIVES[identifier].title, built["scenes"][0]["voiceover"])
            self.assertIn(built["scenes"][1]["world_id"], module.WORLD_IDS)

    def test_long_unicode_and_escape_heavy_sources_remain_bounded(self):
        for content in ("x" * 1000, "😀" * 250, '"' * 1000, "line\n" * 200):
            source = entry("source_linked", "planned", "fictional")
            source["title"] = "😀" * 45
            source["next_action"] = "é" * 750
            for observation in source["observations"]:
                observation["text"] = content
            built = episode(source)
            for scene in built["scenes"]:
                self.assertLessEqual(len(scene["voiceover"]), 500)
                self.assertLessEqual(len(scene["screen_text"]), 180)
                scene["voiceover"].encode("utf-8")
            self.assertLessEqual(len(canonical(built)), MAX_PACKET_BYTES)
        source = entry()
        source["observations"][0]["text"] = "x" * 1000
        self.assertTrue(episode(source)["scenes"][1]["voiceover"].endswith("…"))

    def test_unused_editorial_and_media_text_is_not_invented_as_narration(self):
        source = entry()
        source["summary"] = "SYNTHETIC_UNUSED_EDITORIAL_TEXT"
        source["media_notes"]["visual_style"] = "SYNTHETIC_UNUSED_PRIVATE_STYLE"
        built = episode(source)
        wire = json.dumps(built)
        self.assertNotIn("SYNTHETIC_UNUSED_EDITORIAL_TEXT", wire)
        self.assertNotIn("SYNTHETIC_UNUSED_PRIVATE_STYLE", wire)
        self.assertEqual(built["source_entry_sha256"], diary_entry_digest(source))

    def test_build_parameters_and_original_diary_must_validate(self):
        for revision in ("a" * 39, "A" * 40, "g" * 40, True):
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                build_episode(entry(), source_revision=revision, episode_id="valid-id")
        for identifier in ("x", "a" * 49, "Bad-ID", "../filename", True):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                build_episode(entry(), source_revision=REVISION, episode_id=identifier)
        invalid = entry()
        invalid["observations"][0]["evidence_state"] = "verified"
        with self.assertRaises(ValueError):
            episode(invalid)


class EpisodeValidationTests(unittest.TestCase):
    def test_validator_returns_deep_defensive_copy(self):
        original = episode(entry("source_linked"))
        clean = validate_episode(original)
        clean["scenes"][1]["source_ids"].clear()
        clean["sources"][0]["url"] = "https://example.org/changed"
        self.assertEqual(original["scenes"][1]["source_ids"], ["source-01"])
        self.assertEqual(original["sources"][0]["url"], "https://example.org/reference")

    def test_content_change_or_wrong_hash_is_rejected(self):
        for field, value in (("title", "Changed title"), ("episode_sha256", "0" * 64),
                             ("source_entry_sha256", "0" * 64)):
            changed = episode()
            changed[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "hash mismatch"):
                validate_episode(changed)
        changed = episode()
        changed["scenes"][1]["voiceover"] += " changed"
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            validate_episode(changed)

    def test_owner_packet_cannot_be_mislabeled_public_without_candidate_visibility(self):
        for visibility in ("private", "internal"):
            changed = episode(entry(visibility=visibility), audience="owner")
            changed["audience"] = "public"
            with self.assertRaisesRegex(ValueError, "public_candidate"):
                validate_episode(rehash(changed))
        changed = episode()
        changed["source_visibility"] = "private"
        with self.assertRaisesRegex(ValueError, "public_candidate"):
            validate_episode(rehash(changed))

    def test_exact_fields_and_integer_types(self):
        original = episode()
        for key in original:
            changed = deepcopy(original)
            del changed[key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                validate_episode(changed)
        for field, value in (("schema_version", True), ("schema_version", 1.0), ("model_calls", False),
                             ("external_actions", True), ("observations_omitted", False),
                             ("timezone", "UTC"), ("kind", "another.kind"),
                             ("news_status", "five_items_verified"), ("publication_approval", "approved")):
            changed = deepcopy(original)
            changed[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_episode(rehash(changed))
        for collection in (None, "scenes", "quests", "worlds", "sources"):
            changed = deepcopy(original)
            target = changed if collection is None else changed[collection][0]
            target["unexpected"] = "synthetic extra data"
            with self.assertRaises(ValueError):
                validate_episode(rehash(changed))

    def test_scene_sequence_duplicate_ids_and_unknown_world_are_rejected(self):
        for mutation in ("short", "long", "duplicate", "reordered", "unknown-world", "unknown-record"):
            changed = episode(entry("planned", "fictional"))
            if mutation == "short":
                changed["scenes"] = changed["scenes"][:5]
            elif mutation == "long":
                changed["scenes"].append(deepcopy(changed["scenes"][-1]))
            elif mutation == "duplicate":
                changed["scenes"][2]["scene_id"] = changed["scenes"][1]["scene_id"]
            elif mutation == "reordered":
                changed["scenes"][1], changed["scenes"][2] = changed["scenes"][2], changed["scenes"][1]
            elif mutation == "unknown-world":
                changed["scenes"][1]["world_id"] = "secret-world"
            else:
                changed["scenes"][1]["scene_id"] = "record-99"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_episode(rehash(changed))

    def test_framing_and_planned_steps_cannot_be_reclassified_as_achievements(self):
        for scene_index in (0, -1, -2, -3):
            changed = episode(entry("source_linked"))
            changed["scenes"][scene_index]["evidence_state"] = "source_linked"
            changed["scenes"][scene_index]["source_ids"] = ["source-01"]
            with self.assertRaises(ValueError):
                validate_episode(rehash(changed))
        changed = episode()
        changed["scenes"][1]["evidence_state"] = "mixed"
        with self.assertRaises(ValueError):
            validate_episode(rehash(changed))

    def test_source_reference_shape_and_supported_urls(self):
        for references in ([], ["missing-source"], ["source-01", "source-01"], ("source-01",)):
            changed = episode(entry("source_linked"))
            changed["scenes"][1]["source_ids"] = references
            with self.subTest(references=references), self.assertRaises(ValueError):
                validate_episode(rehash(changed))
        for url in ("http://example.org", "https://user:password@example.org", "https://example.org:444", "https://example.org/a b"):
            changed = episode()
            changed["sources"][0]["url"] = url
            with self.assertRaises(ValueError):
                validate_episode(rehash(changed))
        changed = episode()
        changed["sources"].append(deepcopy(changed["sources"][0]))
        with self.assertRaises(ValueError):
            validate_episode(rehash(changed))

    def test_quest_completion_rewards_extra_fields_and_reordering_fail(self):
        mutations = (("status", "completed"), ("evidence_state", "source_linked"), ("world_id", "forge"),
                     ("quest_id", "unknown-quest"), ("xp", 100), ("money", 1000), ("source_ids", ["source-01"]))
        for field, value in mutations:
            changed = episode()
            changed["quests"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_episode(rehash(changed))
        for quests in ([], episode()["quests"] * 2, list(reversed(episode()["quests"]))):
            changed = episode()
            changed["quests"] = quests
            with self.assertRaises(ValueError):
                validate_episode(rehash(changed))

    def test_world_catalog_and_omission_bounds_are_checked(self):
        for worlds in ([], list(reversed(episode()["worlds"])), episode()["worlds"] * 2):
            changed = episode()
            changed["worlds"] = worlds
            with self.assertRaises(ValueError):
                validate_episode(rehash(changed))
        for omitted in (-1, 1, 6):
            changed = episode()
            changed["observations_omitted"] = omitted
            with self.assertRaises(ValueError):
                validate_episode(rehash(changed))

    def test_text_codepoint_limits_unicode_and_control_rules(self):
        for field, limit in (("voiceover", 500), ("screen_text", 180), ("title", 80)):
            changed = episode()
            changed["scenes"][1][field] = "😀" * limit
            validate_episode(rehash(changed))
            changed["scenes"][1][field] += "x"
            with self.assertRaises(ValueError):
                validate_episode(rehash(changed))
        for value in ("\u0085", "bad\x00text", "bad\x0btext", "\ud800"):
            changed = episode()
            changed["scenes"][1]["voiceover"] = value
            with self.assertRaises(ValueError):
                validate_episode(changed)
        changed = episode()
        changed["quests"][0]["objective"] = "x" * 401
        with self.assertRaises(ValueError):
            validate_episode(rehash(changed))

    def test_duplicate_keys_and_raw_size_are_checked_by_shared_loader(self):
        packet = canonical(episode()).decode("utf-8")
        duplicate = packet.replace('"schema_version":1', '"schema_version":1,"schema_version":1')
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic-episode.json"
            path.write_text(packet)
            self.assertEqual(validate_episode(load_packet(path)), episode())
            for data in (duplicate.encode(), b" " * (MAX_PACKET_BYTES + 1), b"\xff"):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    load_packet(path)


if __name__ == "__main__":
    unittest.main()
