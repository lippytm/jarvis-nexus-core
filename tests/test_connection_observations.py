from datetime import datetime, timezone
import unittest
import json
from copy import deepcopy
from hashlib import sha256
from control_tower.connections import (read_observation, connector_report,
    verify_github_commit_response, validate_destination_registry)
from control_tower.network_contract import TARGETS

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
