from datetime import datetime, timezone
import unittest
import json
from copy import deepcopy
from hashlib import sha256
from control_tower.connections import (read_observation, connector_report,
    verify_github_commit_response, validate_destination_registry, inspect_destination_registry)
from control_tower.network_contract import TARGETS, digest

NOW = datetime(2026, 10, 22, 20, tzinfo=timezone.utc)


def observed(**changes):
    kwargs = {"observed_at": "2026-10-22T19:00:00Z",
              "evidence_url": "https://github.com/lippytm/jarvis-nexus-core/pull/5",
              "response_sha256": "a" * 64, "scope": "pull request metadata", "source_revision": "b304e086"}
    kwargs.update(changes)
    return read_observation("github", **kwargs)


class ConnectionObservationTests(unittest.TestCase):
    def registry(self):
        return {"schema_version": 1, "kind": "jarvis.destination_registry", "registry_id": "local-test",
            "revision": 1, "source_revision": "a" * 40, "configuration_version": "read-config.v1",
            "visibility": "owner_private", "entries": [{"project_id": "ai-jarvis", "platform": target,
                "destination_id": "resource-one", "resource_id": "owner/repository" if target == "github" else "opaque-resource",
                "allowed_actions": ["read"]} for target in sorted(TARGETS)]}

    def test_destination_registry_retains_all_targets_and_independent_snapshots(self):
        registry = self.registry()
        restored = validate_destination_registry(json.loads(json.dumps(registry)))
        self.assertEqual(restored, registry)
        self.assertEqual({e["platform"] for e in restored["entries"]}, set(TARGETS))
        restored["entries"][0]["allowed_actions"].append("write")
        self.assertEqual(validate_destination_registry(registry), registry)
        other = deepcopy(registry)
        # Use another actual project ID without inventing a registry namespace.
        from control_tower.network_contract import PROJECTS
        other["entries"][0]["project_id"] = next(p for p in PROJECTS if p != "ai-jarvis")
        registry["entries"].append(other["entries"][0])
        self.assertEqual(len(validate_destination_registry(registry)["entries"]), len(TARGETS) + 1)

    def test_destination_registry_rejects_ambiguous_public_or_expanded_contracts(self):
        original = self.registry()
        invalid = [{**original, "schema_version": True}, {**original, "revision": True},
            {**original, "revision": 0}, {**original, "visibility": "public_candidate"},
            {**original, "source_revision": "main"}, {**original, "entries": []},
            {**original, "entries": original["entries"] * 101}, {**original, "extra": "field"},
            {**original, "entries": original["entries"] + [original["entries"][0]]}]
        for field, value in (("project_id", "unknown"), ("platform", []), ("destination_id", "../bad"),
                             ("resource_id", "../bad"), ("allowed_actions", ["read", "write"])):
            changed = deepcopy(original)
            changed["entries"][0][field] = value
            invalid.append(changed)
        for registry in invalid:
            with self.subTest(registry=registry), self.assertRaises(ValueError):
                validate_destination_registry(registry)

    def test_registry_inspection_retains_exact_identity_without_resource_mappings(self):
        registry = self.registry()
        args = dict(expected_sha256=digest(registry), expected_revision=1,
                    expected_source_revision=registry["source_revision"])
        result = inspect_destination_registry(registry, **args)
        self.assertEqual(result["registry_sha256"], digest(registry))
        self.assertEqual(result["platform_counts"], {target: 1 for target in TARGETS})
        self.assertEqual(result["entry_count"], len(TARGETS))
        self.assertEqual(result["visibility"], "owner_private")
        self.assertEqual(result["acceptance_state"], "proposed_unverified")
        self.assertFalse(result["dispatch_authorized"])
        self.assertEqual(result["sender_authentication"], "not_established")
        self.assertEqual(result["receipt_sha256"], digest({k: v for k, v in result.items() if k != "receipt_sha256"}))
        for private in ("owner/repository", "resource-one", "opaque-resource", "entries", "allowed_actions"):
            self.assertNotIn(private, json.dumps(result))
        result["platform_counts"].clear()
        self.assertEqual(len(inspect_destination_registry(registry, **args)["platform_counts"]), len(TARGETS))
        other = deepcopy(registry)
        other["registry_id"] = "independent-registry"
        self.assertNotEqual(inspect_destination_registry(other,
            **{**args, "expected_sha256": digest(other)})["receipt_sha256"],
            inspect_destination_registry(registry, **args)["receipt_sha256"])

    def test_registry_inspection_selects_project_with_explicit_version_two(self):
        from control_tower.network_contract import PROJECTS
        registry = self.registry()
        other = next(p for p in PROJECTS if p != "ai-jarvis")
        empty = next(p for p in PROJECTS if p not in ("ai-jarvis", other))
        registry["entries"].append({**deepcopy(registry["entries"][0]), "project_id": other})
        original = deepcopy(registry)
        args = dict(expected_sha256=digest(registry), expected_revision=1,
                    expected_source_revision=registry["source_revision"])
        legacy = inspect_destination_registry(registry, **args)
        self.assertEqual(legacy["schema_version"], 1)
        self.assertNotIn("project_id", legacy)
        self.assertEqual(legacy["entry_count"], len(TARGETS) + 1)
        for project, count in (("ai-jarvis", len(TARGETS)), (other, 1), (empty, 0)):
            selected = inspect_destination_registry(registry, **args, project_id=project)
            self.assertEqual(selected["schema_version"], 2)
            self.assertEqual(selected["project_id"], project)
            self.assertEqual(selected["entry_count"], count)
            self.assertEqual(sum(selected["platform_counts"].values()), count)
            self.assertEqual(selected["registry_sha256"], args["expected_sha256"])
            self.assertEqual(selected["acceptance_state"], "proposed_unverified")
            self.assertEqual(selected["sender_authentication"], "not_established")
            self.assertFalse(selected["dispatch_authorized"])
            self.assertEqual(selected["receipt_sha256"], digest({k:v for k,v in selected.items() if k != "receipt_sha256"}))
            self.assertNotIn("opaque-resource", json.dumps(selected))
            self.assertNotIn("entries", selected)
        for project in (True, [], "unknown"):
            with self.subTest(project=project), self.assertRaises(ValueError):
                inspect_destination_registry(registry, **args, project_id=project)
        changed_neighbor = deepcopy(registry)
        changed_neighbor["entries"][-1]["resource_id"] = "changed-neighbor-resource"
        with self.assertRaisesRegex(ValueError, "registry digest, source or revision mismatch"):
            inspect_destination_registry(changed_neighbor, **args, project_id="ai-jarvis")
        self.assertEqual(registry, original)
        self.assertEqual(inspect_destination_registry(registry, **args), legacy)

    def test_project_selection_cannot_hide_invalid_neighbor_entries(self):
        from control_tower.network_contract import PROJECTS
        original = self.registry()
        other = next(p for p in PROJECTS if p != "ai-jarvis")
        original["entries"].append({**deepcopy(original["entries"][0]), "project_id": other})
        invalid = []
        for key, value in (("allowed_actions", ["read", "write"]), ("platform", "unknown"),
                           ("project_id", "unknown"), ("destination_id", "../bad"),
                           ("resource_id", "../bad"), ("extra", "unsupported")):
            registry = deepcopy(original)
            registry["entries"][-1][key] = value
            invalid.append(registry)
        duplicate = deepcopy(original)
        duplicate["entries"].append(deepcopy(duplicate["entries"][-1]))
        invalid.append(duplicate)
        for index, registry in enumerate(invalid):
            before = deepcopy(registry)
            with self.subTest(case=index), self.assertRaises(ValueError):
                inspect_destination_registry(registry, expected_sha256=digest(registry),
                    expected_revision=1, expected_source_revision=registry["source_revision"],
                    project_id="ai-jarvis")
            self.assertEqual(registry, before)
        accepted = inspect_destination_registry(original, expected_sha256=digest(original),
            expected_revision=1, expected_source_revision=original["source_revision"], project_id="ai-jarvis")
        self.assertEqual(accepted["entry_count"], len(TARGETS))
        self.assertFalse(accepted["dispatch_authorized"])

    def test_registry_inspection_rejects_stale_digest_source_and_revision(self):
        registry = self.registry()
        before = deepcopy(registry)
        args = dict(expected_sha256=digest(registry), expected_revision=1,
                    expected_source_revision=registry["source_revision"])
        for change in (dict(expected_sha256="0" * 64), dict(expected_sha256="bad"),
                       dict(expected_revision=True), dict(expected_revision=2),
                       dict(expected_source_revision="b" * 40)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                inspect_destination_registry(registry, **{**args, **change})
        self.assertEqual(registry, before)
        public = {**registry, "visibility": "public_candidate"}
        with self.assertRaises(ValueError):
            inspect_destination_registry(public, **{**args, "expected_sha256": digest(public)})

    def test_github_commit_repository_names_preserve_resource_boundaries(self):
        source = "a" * 40
        def verify(repository):
            url = f"https://api.github.com/repos/{repository}/git/commits/{source}"
            content = json.dumps(dict(sha=source, url=url)).encode()
            record = observed(source_revision=source, evidence_url=url,
                              response_sha256=sha256(content).hexdigest())
            verify_github_commit_response(content, record, repository)
        for name in (".github", "-repo", "_repo", "repo..name", "a" * 100):
            with self.subTest(name=name):
                verify("owner/" + name)
        for name in (".", "..", "../repo", "repo/path", "repo\\path", "%2e%2e", "repo?query",
                     "repo#fragment", "", "a" * 101, "r\u00e9po"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                verify("owner/" + name)

    def test_github_commit_response_identity_and_exact_bytes(self):
        source = "a" * 40
        url = f"https://api.github.com/repos/lippytm/jarvis-nexus-core/git/commits/{source}"
        content = json.dumps(dict(sha=source, url=url)).encode()
        record = observed(source_revision=source, evidence_url=url, response_sha256=sha256(content).hexdigest())
        original = dict(record)
        verify_github_commit_response(content, record, "lippytm/jarvis-nexus-core")
        self.assertEqual(record, original)
        bad_content = [json.dumps(dict(sha="b" * 40, url=url)).encode(),
            json.dumps(dict(sha=source, url=url.replace("lippytm/", "other/"))).encode(),
            ('{"sha":"wrong","sha":"' + source + '","url":"' + url + '"}').encode(),
            b'[]', b'\xff', b'x' * 65537]
        for raw in bad_content:
            with self.subTest(content=raw[:60]), self.assertRaises(ValueError):
                verify_github_commit_response(raw, {**record, "response_sha256": sha256(raw).hexdigest()}, "lippytm/jarvis-nexus-core")
        for change in (dict(connector="codex"), dict(source_revision="main"),
                       dict(evidence_url=url + "?other=1"), dict(response_sha256="0" * 64)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                verify_github_commit_response(content, {**record, **change}, "lippytm/jarvis-nexus-core")
        for repository in ("other/repo", "../repo", "lippytm/repo/path", "https://github.com/lippytm/repo", None):
            with self.subTest(repository=repository), self.assertRaises(ValueError):
                verify_github_commit_response(content, record, repository)

    def test_configuration_does_not_imply_live_access(self):
        result = connector_report(now=NOW)
        self.assertTrue(all(row["status"] == "unverified" for row in result.values()))
        self.assertTrue(all(row["runtime_available"] == "unknown" for row in result.values()))

    def test_fresh_read_is_scoped_and_never_grants_write(self):
        result = connector_report([observed()], now=NOW)["github"]
        self.assertEqual(result["status"], "read_observed")
        self.assertEqual(result["write_gate"], "owner_review")
        self.assertEqual(result["runtime_available"], "unknown")
        self.assertEqual(result["observation_verification"], "integrity_only")

    def test_stale_read_does_not_show_recent_read_status(self):
        result = connector_report([observed(observed_at="2026-10-20T19:00:00Z")], now=NOW)["github"]
        self.assertEqual(result["status"], "unverified")

    def test_tampered_observation_rejected(self):
        record = observed(); record["connector"] = "hostinger"
        with self.assertRaises(ValueError):
            connector_report([record], now=NOW)

    def test_future_observation_rejected(self):
        with self.assertRaises(ValueError):
            connector_report([observed(observed_at="2026-10-23T19:00:00Z")], now=NOW)

    def test_malformed_or_sensitive_observation_rejected(self):
        for record in (None, {}, {"api_key": "synthetic"}, {**observed(), "operation": "write"}):
            with self.assertRaises(ValueError):
                connector_report([record], now=NOW)

    def test_latest_read_selected_independent_of_input_order(self):
        older = observed(observed_at="2026-10-21T19:00:00Z")
        result = connector_report([observed(), older], now=NOW)["github"]
        self.assertEqual(result["last_observation"]["observed_at"], "2026-10-22T19:00:00Z")


if __name__ == "__main__":
    unittest.main()
