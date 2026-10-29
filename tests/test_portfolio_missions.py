from copy import deepcopy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from control_tower.campaigns import CHANNEL_FORMATS, campaign_briefs, daily_campaign_briefs
from control_tower.funnels import DESTINATIONS
from control_tower.handoffs import HandoffLedger
from control_tower.missions import (TIMEBOXES, compile_mission, export_role_draft,
                                     validate_mission, validate_mission_request)
from control_tower.network_contract import canonical, digest, load_packet, validate_draft
from control_tower.portfolio import INITIATIVES, initiative, portfolio_catalog
from control_tower.portfolio_demo import demonstrate_portfolio
from scripts.jarvis_portfolio import _write, main

ROOT = Path(__file__).resolve().parents[1]
REVISION = "a67e743e8b32e552ccddd9e16a2108fe2f816274"


def request(initiative_id="jarvis-tools", **updates):
    return {"schema_version": 1, "kind": "jarvis.mission_request", "initiative_id": initiative_id,
            "target": "gemini", "objective": "Prepare one clearly scoped, reviewable improvement.",
            "timebox_minutes": 30, **updates}


def mission(initiative_id="jarvis-tools", **updates):
    return compile_mission(request(initiative_id, **updates), mission_id="sample-mission", source_revision=REVISION)


class CatalogTests(unittest.TestCase):
    def test_daily_media_assignments_are_bounded_distinct_and_round_trip(self):
        source = mission(target="codex")
        original = deepcopy(source)
        result = daily_campaign_briefs(source, editorial_date="2026-10-29")
        self.assertEqual(source, original)
        self.assertEqual(result, json.loads(canonical(result)))
        self.assertEqual(result["briefs_sha256"], digest({k:v for k,v in result.items() if k != "briefs_sha256"}))
        channels = {"facebook", "linkedin", "youtube", "instagram", "threads", "substack"}
        self.assertEqual(24, len(result["posts"]))
        self.assertEqual(channels, {b["channel"] for b in result["source_briefs"]})
        for channel in channels:
            posts = [p for p in result["posts"] if p["channel"] == channel]
            self.assertEqual({1, 2, 3, 4}, {p["slot"] for p in posts})
            self.assertEqual(4, len({p["draft"]["text"] for p in posts}))
            brief = next(b for b in result["source_briefs"] if b["channel"] == channel)
            for post in posts:
                self.assertEqual(digest(brief), post["source_brief_sha256"])
                self.assertEqual("codex", validate_draft(post["draft"])["target"])
        self.assertIsNone(result["publication_schedule"])
        self.assertIsNone(result["actual_metrics"])
        self.assertEqual(0, result["external_actions"])
        result["posts"][0]["draft"]["text"] = "Caller edit"
        self.assertNotEqual(result, daily_campaign_briefs(source, editorial_date="2026-10-29"))

    def test_daily_media_keeps_customer_partner_destinations_and_rejects_stale_input(self):
        for kind in ("funding-customers", "referral-partners"):
            source = mission(kind)
            result = daily_campaign_briefs(source, editorial_date="2026-10-29", destination_index=1)
            expected = campaign_briefs(source, destination_index=1)
            self.assertTrue(all(b in expected["briefs"] for b in result["source_briefs"]))
        source["request"]["objective"] = "Unreviewed tampering"
        with self.assertRaises(ValueError):
            daily_campaign_briefs(source, editorial_date="2026-10-29")
        for value in (None, "2026-02-30", "20261029", "2026-10-29T12:00:00"):
            with self.subTest(date=value), self.assertRaises(ValueError):
                daily_campaign_briefs(mission(), editorial_date=value)

    def test_catalog_and_tracked_browser_snapshot_match(self):
        catalog = portfolio_catalog()
        self.assertEqual(12, len(catalog["initiatives"]))
        self.assertEqual(7, len({item["project_id"] for item in catalog["initiatives"]}))
        self.assertEqual(catalog, load_packet(ROOT / "examples/portfolio/catalog.json"))
        self.assertIsNone(catalog["live_metrics"])
        record = {k: v for k, v in catalog.items() if k != "catalog_sha256"}
        self.assertEqual(digest(record), catalog["catalog_sha256"])

    def test_catalog_is_defensive_and_internal_records_immutable(self):
        item = initiative("website-learning")
        item["destination"]["urls"].clear()
        self.assertTrue(initiative("website-learning")["destination"]["urls"])
        with self.assertRaises(TypeError):
            INITIATIVES["fake"] = None
        with self.assertRaises(AttributeError):
            INITIATIVES["jarvis-tools"].title = "changed"

    def test_ready_examples_match_catalog_requests_and_compiler(self):
        root = ROOT / "examples/portfolio"
        index = load_packet(root / "mission_index.json")
        self.assertEqual(set(INITIATIVES), {entry["initiative_id"] for entry in index["missions"]})
        self.assertEqual("synthetic planning examples", index["scope"])
        for entry in index["missions"]:
            key = entry["initiative_id"]
            self.assertEqual(key + ".request.json", entry["request_file"])
            self.assertEqual(key + ".mission.json", entry["mission_file"])
            loaded = validate_mission(load_packet(root / entry["mission_file"]))
            self.assertEqual(load_packet(root / entry["request_file"]), loaded["request"])
            self.assertEqual(entry["mission_sha256"], loaded["mission_sha256"])
            self.assertEqual(entry["project_id"], loaded["initiative"]["project_id"])
            if key in {"funding-customers", "referral-partners"}:
                self.assertEqual(campaign_briefs(loaded, destination_index=1), load_packet(root / (key + ".campaign.json")))

    def test_separate_destinations_and_journey_intents(self):
        self.assertEqual("member", initiative("website-learning")["journey_kind"])
        self.assertEqual([], initiative("affiliate-builder")["destination"]["urls"])
        for initiative_id, kind in (("funding-customers", "funding_customer"), ("referral-partners", "funding_partner")):
            item = initiative(initiative_id)
            self.assertEqual(kind, item["journey_kind"])
            self.assertEqual(list(DESTINATIONS[kind]), item["destination"]["urls"])


class MissionRequestTests(unittest.TestCase):
    def test_exact_shape_and_preserved_text(self):
        r = request(objective="  One idea\nwith a second line.\t ")
        self.assertEqual(r, validate_mission_request(r))
        for update in ({"extra": 1}, {"schema_version": True}, {"kind": "mission"},
                       {"initiative_id": []}, {"initiative_id": "unknown"}, {"target": []},
                       {"target": "unlisted"}, {"timebox_minutes": True}, {"timebox_minutes": 30.0},
                       {"timebox_minutes": 31}, {"objective": None}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                validate_mission_request({**r, **update})
        incomplete = dict(r)
        incomplete.pop("objective")
        with self.assertRaises(ValueError):
            validate_mission_request(incomplete)

    def test_unicode_and_objective_byte_boundary(self):
        self.assertEqual("🙂" * 500, validate_mission_request(request(objective="🙂" * 500))["objective"])
        for value in ("🙂" * 501, "x" * 2001, "\ud800", "\udfff", "", "\u0085", " \n\t"):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                validate_mission_request(request(objective=value))
        for i in range(32):
            text = "x" + chr(i)
            if chr(i) in "\n\t\r":
                self.assertEqual(text, validate_mission_request(request(objective=text))["objective"])
            else:
                with self.subTest(control=i), self.assertRaises(ValueError):
                    validate_mission_request(request(objective=text))


class MissionCompilerTests(unittest.TestCase):
    def test_portfolio_demo_remains_synthetic_and_metrics_unavailable(self):
        report = demonstrate_portfolio()
        self.assertEqual((12, 7, 60), (report["initiative_count"], report["project_count"], report["inactive_role_drafts"]))
        self.assertEqual(0, report["model_calls"])
        self.assertEqual(0, report["external_actions"])
        self.assertEqual(0, report["external_agents_started"])
        self.assertIsNone(report["live_metrics"])
        self.assertTrue(all(x["referral_parameter_preserved"] for x in report["campaign_samples"]))

    def test_every_initiative_has_five_inactive_valid_role_drafts(self):
        for key in INITIATIVES:
            with self.subTest(initiative=key):
                result = mission(key)
                self.assertEqual(result, validate_mission(result))
                self.assertEqual("inactive_mission", result["state"])
                self.assertEqual(5, len(result["tasks"]))
                self.assertEqual(0, result["external_actions"])
                self.assertEqual(0, result["model_calls"])
                self.assertEqual([], result["resume_bookmark"]["completed_work"])
                self.assertEqual([], result["resume_bookmark"]["verified_outcomes"])
                for task in result["tasks"]:
                    self.assertEqual(task["draft"], validate_draft(task["draft"]))
                    self.assertEqual("planned", task["state"])
                    self.assertIn(task["assistant_id"], {a["assistant_id"] for a in result["swarm"]["assistants"]})
                self.assertLessEqual(len(canonical(result)) + 1, 65536)

    def test_planned_dependencies_and_time_allocation(self):
        for timebox in TIMEBOXES:
            result = mission(timebox_minutes=timebox)
            self.assertEqual(timebox, sum(t["planned_minutes"] for t in result["tasks"]))
            prior = []
            for task in result["tasks"]:
                self.assertEqual(prior, task["depends_on"])
                prior = [task["task_id"]]
            self.assertTrue(result["planning_limits"]["time_is_estimate_not_runtime_enforcement"])

    def test_deterministic_integrity_with_fresh_copies(self):
        original = mission()
        self.assertEqual(original, mission())
        copied = validate_mission(original)
        copied["tasks"][0]["acceptance"].clear()
        self.assertTrue(original["tasks"][0]["acceptance"])
        altered = mission(objective="A different scoped objective.")
        self.assertNotEqual(original["mission_sha256"], altered["mission_sha256"])

    def test_tampering_rejected_even_with_recomputed_digest(self):
        for mutate in (
            lambda x: x["tasks"][0].update(state="completed"),
            lambda x: x["planning_limits"].update(model_call_budget=1),
            lambda x: x.update(schema_version=True),
            lambda x: x["swarm"].update(max_depth=2),
            lambda x: x["initiative"]["destination"].update(urls=["https://example.org"]),
            lambda x: x["resume_bookmark"]["completed_work"].append("all work"),
            lambda x: x["tasks"][1]["depends_on"].clear(),
        ):
            changed = mission()
            mutate(changed)
            changed["mission_sha256"] = digest({k: v for k, v in changed.items() if k != "mission_sha256"})
            with self.assertRaises(ValueError):
                validate_mission(changed)

    def test_identifier_and_source_revision_bounds(self):
        for bad in ("x", "../path", "x" * 49, [], None):
            with self.subTest(id=bad), self.assertRaises(ValueError):
                compile_mission(request(), mission_id=bad, source_revision=REVISION)
        for bad in ("main", "0" * 39, "F" * 40, None):
            with self.subTest(revision=bad), self.assertRaises(ValueError):
                compile_mission(request(), mission_id="valid-id", source_revision=bad)

    def test_worst_case_requests_fit_loader_and_serialize_without_loss(self):
        for objective in ("🙂" * 500, "字" * 666, "\\" * 2000, '"' * 2000, "x" + "\n" * 1999):
            with self.subTest(objective_type=repr(objective[:8])), tempfile.TemporaryDirectory() as directory:
                result = mission("funding-customers", objective=objective)
                path = Path(directory) / "mission.json"
                _write(path, result)
                self.assertEqual(result, validate_mission(load_packet(path)))

    def test_selected_role_enters_existing_ledger_and_requires_review(self):
        result = mission()
        builder = next(t for t in result["tasks"] if t["role"] == "builder")
        exported = export_role_draft(result, "builder")
        with tempfile.TemporaryDirectory() as directory:
            with HandoffLedger(Path(directory) / "ledger.sqlite") as ledger:
                staged = ledger.stage(exported, result["swarm"], assistant_id=builder["assistant_id"], handoff_id="one-builder-task")
                self.assertEqual("pending_review", staged["state"])
                with self.assertRaises(ValueError):
                    ledger.export("one-builder-task", expected_sha256=staged["handoff_sha256"])
                ledger.review("one-builder-task", reviewer_id="local-reviewer", expected_sha256=staged["handoff_sha256"])
                packet = ledger.export("one-builder-task", expected_sha256=staged["handoff_sha256"])
                self.assertEqual(exported, packet["handoff"]["draft"])
                self.assertEqual(0, packet["external_actions"])
        with self.assertRaises(ValueError):
            export_role_draft(result, "operator")


class CampaignTests(unittest.TestCase):
    def test_all_seven_channels_keep_handoff_provider_separate(self):
        result = campaign_briefs(mission())
        self.assertEqual(set(CHANNEL_FORMATS), {b["channel"] for b in result["briefs"]})
        self.assertEqual(7, len(result["briefs"]))
        self.assertIsNone(result["actual_metrics"])
        self.assertEqual("unpublished_drafts", result["state"])
        for brief in result["briefs"]:
            self.assertEqual("gemini", brief["draft"]["target"])
            self.assertEqual(brief["draft"], validate_draft(brief["draft"]))
            self.assertIn(brief["channel"], brief["draft"]["text"])

    def test_referral_parameters_and_customer_partner_routes_preserved(self):
        for key, kind in (("funding-customers", "funding_customer"), ("referral-partners", "funding_partner")):
            for index, destination in enumerate(DESTINATIONS[kind]):
                packet = campaign_briefs(mission(key), destination_index=index)
                self.assertEqual(destination, packet["destination"])
                self.assertEqual(kind, packet["journey_kind"])
                base = urlsplit(destination)
                for brief in packet["briefs"]:
                    parsed = urlsplit(brief["candidate_url"])
                    self.assertEqual((base.scheme, base.netloc, base.path), (parsed.scheme, parsed.netloc, parsed.path))
                    query = parse_qs(parsed.query)
                    for name, values in parse_qs(base.query).items():
                        self.assertEqual(values, query[name])
                    self.assertEqual([brief["channel"]], query["utm_source"])
                    self.assertEqual(["organic"], query["utm_medium"])
                    self.assertEqual("unverified", brief["url_status"])

    def test_unassigned_affiliate_platform_has_no_invented_education_cta(self):
        packet = campaign_briefs(mission("affiliate-builder"))
        self.assertIsNone(packet["destination"])
        for brief in packet["briefs"]:
            self.assertIsNone(brief["candidate_url"])
            self.assertEqual("unassigned", brief["url_status"])
            self.assertNotIn("https://aievolutionaryevolutions.com", brief["draft"]["text"])

    def test_destination_validation_and_complete_packet_bounds(self):
        for bad in (-1, True, 0.0, 2, "0"):
            with self.subTest(index=bad), self.assertRaises(ValueError):
                campaign_briefs(mission("funding-customers"), destination_index=bad)
        for key in INITIATIVES:
            for objective in ("🙂" * 500, "\\" * 2000, "x" + "\n" * 1999):
                packet = campaign_briefs(mission(key, objective=objective))
                self.assertLessEqual(len(canonical(packet)) + 1, 65536)
                self.assertEqual(0, packet["external_actions"])


class PortfolioCLITests(unittest.TestCase):
    def call(self, *args):
        with patch("sys.stdout", new_callable=io.StringIO) as out, patch("sys.stderr", new_callable=io.StringIO) as err:
            code = main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_cli_plan_export_role_and_swarm_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "request.json").write_text(json.dumps(request()))
            common = ("--root", directory)
            code, _, err = self.call(*common, "plan", "--request", "request.json", "--mission", "cli-example", "--source-revision", REVISION, "--out", "plan.json")
            self.assertEqual(0, code, err)
            for command, filename, extra in (("export-role", "draft.json", ("--role", "builder")), ("export-swarm", "swarm.json", ()), ("campaign", "campaign.json", ())):
                code, _, err = self.call(*common, command, "--mission-file", "plan.json", *extra, "--out", filename)
                self.assertEqual(0, code, err)
            self.assertEqual("jarvis.draft", load_packet(root / "draft.json")["kind"])
            self.assertEqual("jarvis.swarm", load_packet(root / "swarm.json")["kind"])
            self.assertEqual(7, len(load_packet(root / "campaign.json")["briefs"]))

    def test_cli_rejects_escape_existing_output_and_malformed_request(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "saved.json").write_text("keep")
            for output in ("../outside.json", "/tmp/outside-jarvis.json", "saved.json"):
                code, _, _ = self.call("--root", directory, "catalog", "--out", output)
                self.assertEqual(1, code)
            self.assertEqual("keep", (root / "saved.json").read_text())
            (root / "bad.json").write_text('{"kind":"first","kind":"second"}')
            code, _, _ = self.call("--root", directory, "plan", "--request", "bad.json", "--mission", "bad-mission", "--source-revision", REVISION, "--out", "result.json")
            self.assertEqual(1, code)
            self.assertFalse((root / "result.json").exists())

    def test_atomic_failure_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            with patch("scripts.jarvis_portfolio.os.link", side_effect=OSError("private path detail")):
                with self.assertRaises(OSError):
                    _write(path, {"ok": True})
            self.assertEqual([], list(Path(directory).iterdir()))
            _write(path, {"ok": True})
            with self.assertRaises(FileExistsError):
                _write(path, {"changed": True})
            self.assertEqual({"ok": True}, load_packet(path))

    def test_cyclic_symlink_paths_return_sanitized_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            loop = root / "private-cycle-name"
            try:
                loop.symlink_to(loop.name)
            except (NotImplementedError, OSError):
                self.skipTest("symlink creation is not available")
            commands = (
                ("--root", directory, "catalog", "--out", loop.name + "/output.json"),
                ("--root", str(loop), "catalog", "--out", "output.json"),
                ("--root", directory, "plan", "--request", loop.name, "--mission", "cycle-test", "--source-revision", REVISION, "--out", "output.json"),
            )
            for command in commands:
                code, _, error = self.call(*command)
                self.assertEqual(1, code)
                self.assertNotIn(loop.name, error)
                self.assertEqual(0, json.loads(error)["external_actions"])
            self.assertFalse((root / "output.json").exists())

    def test_cli_process_runs_catalog_without_external_operations(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(ROOT / "scripts/jarvis_portfolio.py"), "--root", directory,
                                     "catalog", "--out", "catalog.json"], capture_output=True, text=True, timeout=5)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(0, json.loads(result.stdout)["external_actions"])
            self.assertEqual(12, len(load_packet(Path(directory) / "catalog.json")["initiatives"]))


if __name__ == "__main__":
    unittest.main()
