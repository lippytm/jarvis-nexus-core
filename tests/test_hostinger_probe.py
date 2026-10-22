"""Offline transport tests only; no credentials, sockets or provider calls."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
import unittest

from control_tower.hostinger_probe import (
    ENDPOINT, MAX_RESPONSE_BYTES, TIMEOUT_SECONDS, ProbeResponse, prepare_request, probe,
)


TOKEN = "offline-fixture-token-not-a-real-credential"


def website(**changes):
    row = {"website_id": "fixture-website-id", "status": "active",
           "created_at": "2026-10-22T12:00:00Z", "website_url": "https://horizons.hostinger.com/fixture-website-id",
           "description": "PRIVATE_FIXTURE_DESCRIPTION", "domain": "private-fixture.example"}
    row.update(changes)
    return row


def respond(value, **changes):
    return ProbeResponse(200, json.dumps(value).encode(), **changes)


class HostingerProbeTests(unittest.TestCase):
    def test_fixed_get_descriptor_and_redacted_credential(self):
        request = prepare_request(TOKEN)
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.url, ENDPOINT)
        self.assertFalse(request.follow_redirects)
        self.assertEqual(request.timeout_seconds, 5.0)
        self.assertEqual(request.max_response_bytes, 65536)
        self.assertNotIn(TOKEN, repr(request))
        self.assertEqual(request.headers_for_transport()["Authorization"], "Bearer " + TOKEN)
        headers = request.headers_for_transport()
        headers["Authorization"] = "modified"
        self.assertEqual(request.headers_for_transport()["Authorization"], "Bearer " + TOKEN)
        with self.assertRaises(FrozenInstanceError):
            request.url = "https://untrusted.example"

    def test_invalid_token_never_reaches_transport(self):
        calls = []
        for token in (None, b"token", "", "x\r\nInjected: true", "has space", "x\0", "é", "a" * 4097):
            result = probe(lambda request: calls.append(request), token)
            self.assertEqual(result["reason"], "invalid_token")
            self.assertEqual(result["transport_calls"], 0)
        self.assertEqual(calls, [])

    def test_sanitized_count_and_digest_without_claim_of_live_connection(self):
        response = respond([website(), website(website_id="fixture-2", status="suspended")])
        calls = []
        def transport(request):
            calls.append(request)
            self.assertEqual(request.timeout_seconds, TIMEOUT_SECONDS)
            self.assertEqual(request.max_response_bytes, MAX_RESPONSE_BYTES)
            self.assertFalse(request.follow_redirects)
            return response
        result = probe(transport, TOKEN)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["status"], "response_validated")
        self.assertEqual(result["website_count"], 2)
        self.assertEqual(result["website_status_counts"]["active"], 1)
        self.assertEqual(result["website_status_counts"]["suspended"], 1)
        self.assertEqual(result["response_sha256"], sha256(response.body).hexdigest())
        self.assertEqual(result["connection_status"], "unverified")
        self.assertFalse(result["live_access_verified"])
        self.assertEqual(result["writes_requested"], 0)
        rendered = json.dumps(result)
        for private in (TOKEN, "fixture-website-id", "PRIVATE_FIXTURE_DESCRIPTION", "private-fixture.example"):
            self.assertNotIn(private, rendered)

    def test_empty_documented_array_is_valid_but_not_proof_of_live_access(self):
        result = probe(lambda request: respond([]), TOKEN)
        self.assertEqual(result["website_count"], 0)
        self.assertEqual(result["connection_status"], "unverified")

    def test_transport_failure_redacts_exception_and_does_not_retry(self):
        calls = []
        def transport(request):
            calls.append(request)
            raise RuntimeError(TOKEN + " PRIVATE_ERROR")
        result = probe(transport, TOKEN)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["status"], "transport_error")
        self.assertNotIn(TOKEN, json.dumps(result))
        self.assertNotIn("PRIVATE_ERROR", json.dumps(result))

    def test_redirects_and_foreign_final_urls_fail_closed(self):
        responses = [ProbeResponse(302, b"PRIVATE_LOCATION"),
                     respond([], final_url="https://untrusted.example/"),
                     respond([], final_url=ENDPOINT + "?token=PRIVATE"),
                     respond([], redirect_count=1), respond([], redirect_count=False)]
        for response in responses:
            result = probe(lambda request: response, TOKEN)
            self.assertEqual(result["reason"], "redirects_forbidden")
            self.assertNotIn("PRIVATE", json.dumps(result))

    def test_auth_rate_and_server_errors_do_not_return_body(self):
        for status, expected in ((401, "authorization_failed"), (403, "authorization_failed"),
                                 (429, "rate_limited"), (500, "provider_error"), (204, "provider_error")):
            response = ProbeResponse(status, b"PRIVATE_PROVIDER_ERROR")
            result = probe(lambda request: response, TOKEN)
            self.assertEqual(result["status"], expected)
            self.assertNotIn("PRIVATE_PROVIDER_ERROR", json.dumps(result))

    def test_max_body_boundary_and_no_implicit_decompression(self):
        body = b"[]" + b" " * (MAX_RESPONSE_BYTES - 2)
        valid = probe(lambda request: ProbeResponse(200, body), TOKEN)
        self.assertEqual(valid["status"], "response_validated")
        too_big = probe(lambda request: ProbeResponse(200, body + b" "), TOKEN)
        self.assertEqual(too_big["reason"], "body_type_or_size_limit")
        text_body = probe(lambda request: ProbeResponse(200, "[]"), TOKEN)
        self.assertEqual(text_body["reason"], "body_type_or_size_limit")
        for response in (respond([], content_type="text/html"), respond([], content_encoding="gzip")):
            self.assertEqual(probe(lambda request: response, TOKEN)["reason"], "unsupported_content_type_or_encoding")

    def test_strict_json_rejects_duplicate_keys_nonfinite_and_malformed_bodies(self):
        # Without duplicate-key rejection this otherwise valid resource would be
        # counted using only the final status value.
        duplicate_status = json.dumps([website()]).replace('"status": "active"',
                                                         '"status": "suspended", "status": "active"').encode()
        bodies = [duplicate_status, b'{"data": [], "data": []}', b"[NaN]", b"[Infinity]", b"null", b"false", b"{}",
                  b"[", b"\xff", b"[] trailing", b"[" * 1500 + b"]" * 1500]
        for body in bodies:
            result = probe(lambda request: ProbeResponse(200, body), TOKEN)
            self.assertEqual(result["reason"], "invalid_json_or_inventory_schema")

    def test_schema_mismatch_and_duplicate_sites_do_not_inflate_count(self):
        values = [[{}], [website(status="unexpected")], [website(status=[])], [website(created_at="2026-10-22")],
                  [website(website_url="http://unsafe.example")], [website(website_url="https://user:pass@example.com")],
                  [website(description={"ssn": "PRIVATE"})], [dict(website(), secret="PRIVATE")],
                  [website(), website()], {"data": [website()]}]
        for value in values:
            result = probe(lambda request: respond(value), TOKEN)
            self.assertEqual(result["status"], "invalid_response")
            self.assertNotIn("website_count", result)
            self.assertNotIn("PRIVATE", json.dumps(result))

    def test_transport_contract_is_explicit_and_no_default_sender_exists(self):
        self.assertEqual(probe(None, TOKEN)["reason"], "transport_required")
        for response in ({"status_code": 200, "body": b"[]"}, ProbeResponse(True, b"[]"), ProbeResponse(999, b"[]")):
            self.assertEqual(probe(lambda request: response, TOKEN)["reason"], "invalid_transport_response")


if __name__ == "__main__":
    unittest.main()
