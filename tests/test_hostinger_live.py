"""Offline socket/TLS fixtures only. No test contacts Hostinger or resolves DNS."""
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import socket
import ssl
import stat
import tempfile
import unittest
from unittest.mock import patch

from control_tower import hostinger_live as live
from control_tower.hostinger_probe import PreparedRequest, prepare_request, probe
from scripts import jarvis_hostinger as cli


TOKEN = "OFFLINE_FIXTURE_TOKEN_NOT_A_REAL_CREDENTIAL"
ADDRESS = (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("192.0.2.1", 443))


def http_response(body=b"[]", *, status=200, headers=None, content_length=True):
    rows = [("Content-Type", "application/json")]
    if content_length:
        rows.append(("Content-Length", str(len(body))))
    rows.extend(headers or [])
    wire = f"HTTP/1.1 {status} Fixture\r\n".encode()
    wire += b"".join(f"{key}: {value}\r\n".encode() for key, value in rows)
    return wire + b"\r\n" + body


class FakeSocket:
    def __init__(self, wire=b"", *, chunk=4096):
        self.wire = io.BytesIO(wire)
        self.chunk = chunk
        self.timeouts = []
        self.addresses = []
        self.sent = []
        self.read_sizes = []
        self.received = 0
        self.closed = False
        self.tcp = None
        self.connect_error = None
        self.handshake_error = None
        self.on_receive = None

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def connect(self, address):
        self.addresses.append(address)
        if self.connect_error:
            raise self.connect_error

    def do_handshake(self):
        if self.handshake_error:
            raise self.handshake_error

    def selected_alpn_protocol(self):
        return "http/1.1"

    def sendall(self, value):
        self.sent.append(value)

    def recv_into(self, buffer, amount):
        self.read_sizes.append(amount)
        if self.on_receive:
            self.on_receive()
        value = self.wire.read(min(amount, self.chunk))
        buffer[:len(value)] = value
        self.received += len(value)
        return len(value)

    def close(self):
        self.closed = True
        if self.tcp:
            self.tcp.close()


class FakeContext:
    def __init__(self, tls_socket):
        self.tls_socket = tls_socket
        self.wraps = []
        self.loaded = []
        self.alpn = None

    def load_default_certs(self, purpose):
        self.loaded.append(purpose)

    def set_alpn_protocols(self, protocols):
        self.alpn = protocols

    def wrap_socket(self, tcp_socket, **kwargs):
        self.wraps.append(kwargs)
        self.tls_socket.tcp = tcp_socket
        return self.tls_socket


@contextmanager
def network_fixture(wire, *, chunk=4096):
    tcp = FakeSocket()
    tls = FakeSocket(wire, chunk=chunk)
    context = FakeContext(tls)
    with patch.object(live.socket, "getaddrinfo", return_value=[ADDRESS]) as dns, \
         patch.object(live.socket, "socket", return_value=tcp) as socket_factory, \
         patch.object(live.ssl, "SSLContext", return_value=context) as context_factory:
        yield tcp, tls, context, dns, socket_factory, context_factory


class HostingerLiveTransportTests(unittest.TestCase):
    def test_exact_get_tls_verification_and_sanitized_inventory(self):
        body = json.dumps([{"website_id": "PRIVATE_SITE", "status": "active",
                            "created_at": "2026-10-22T12:00:00Z", "website_url": "https://private.example/",
                            "description": "PRIVATE_DESCRIPTION", "domain": "private.example"}]).encode()
        with network_fixture(http_response(body)) as (tcp, tls, context, dns, sockets, contexts):
            result = probe(live._https_transport, TOKEN)
        dns.assert_called_once_with(live.HOST, 443, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
        sockets.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        contexts.assert_called_once_with(ssl.PROTOCOL_TLS_CLIENT)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.minimum_version, ssl.TLSVersion.TLSv1_2)
        self.assertIsNone(context.keylog_filename)
        self.assertEqual(context.loaded, [ssl.Purpose.SERVER_AUTH])
        self.assertEqual(context.alpn, ["http/1.1"])
        self.assertEqual(context.wraps, [{"server_hostname": live.HOST, "do_handshake_on_connect": False}])
        self.assertEqual(len(tls.sent), 1)
        self.assertTrue(tls.sent[0].startswith(b"GET /api/horizons/v1/websites HTTP/1.1\r\n"))
        self.assertIn(b"Host: developers.hostinger.com\r\n", tls.sent[0])
        self.assertIn(("Authorization: Bearer " + TOKEN + "\r\n").encode(), tls.sent[0])
        self.assertTrue(all(0 < value <= 5 for value in tcp.timeouts + tls.timeouts))
        self.assertTrue(all(value <= live.MAX_READ_BYTES for value in tls.read_sizes))
        self.assertTrue(tcp.closed and tls.closed)
        self.assertEqual(result["website_count"], 1)
        self.assertEqual(result["response_sha256"], sha256(body).hexdigest())
        self.assertFalse(result["live_access_verified"])
        for value in (TOKEN, "PRIVATE_SITE", "PRIVATE_DESCRIPTION", "private.example"):
            self.assertNotIn(value, json.dumps(result))

    def test_real_context_keeps_verification_and_ignores_tls_keylog_variable(self):
        with tempfile.TemporaryDirectory() as temporary:
            keylog = Path(temporary) / "keys.log"
            with patch.dict(os.environ, {"SSLKEYLOGFILE": str(keylog)}):
                context = live._verified_context()
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)
            self.assertIsNone(context.keylog_filename)
            self.assertFalse(keylog.exists())

    def test_modified_descriptor_and_header_injection_fail_before_dns(self):
        changed = prepare_request(TOKEN)
        object.__setattr__(changed, "url", "https://untrusted.example/")
        requests = [changed, object(), PreparedRequest("Bearer bad\r\nInjected: yes")]
        with patch.object(live.socket, "getaddrinfo") as dns:
            for request in requests:
                with self.assertRaisesRegex(live.HostingerTransportError, "^hostinger_transport_failed$"):
                    live._https_transport(request)
        dns.assert_not_called()

    def test_certificate_error_prevents_credential_send_and_is_sanitized(self):
        with network_fixture(http_response()) as (_, tls, _, _, sockets, _):
            tls.handshake_error = ssl.SSLCertVerificationError(TOKEN + " private certificate details")
            result = probe(live._https_transport, TOKEN)
        self.assertEqual(result["status"], "transport_error")
        self.assertEqual(tls.sent, [])
        sockets.assert_called_once()
        self.assertTrue(tls.closed)
        self.assertNotIn(TOKEN, json.dumps(result))

    def test_first_address_failure_is_not_retried(self):
        with network_fixture(http_response()) as (tcp, tls, _, dns, sockets, _):
            dns.return_value = [ADDRESS, ADDRESS]
            tcp.connect_error = OSError(TOKEN + " private error")
            result = probe(live._https_transport, TOKEN)
        self.assertEqual(result["status"], "transport_error")
        sockets.assert_called_once()
        self.assertEqual(tcp.addresses, [ADDRESS[4]])
        self.assertEqual(tls.sent, [])
        self.assertTrue(tcp.closed)
        self.assertNotIn(TOKEN, json.dumps(result))

    def test_redirect_and_provider_errors_never_follow_or_return_body(self):
        for status, expected in ((302, "rejected"), (401, "authorization_failed"),
                                 (429, "rate_limited"), (500, "provider_error")):
            wire = http_response(TOKEN.encode(), status=status, headers=[("Location", "https://untrusted.example/" + TOKEN)])
            with network_fixture(wire) as (_, tls, _, dns, sockets, _):
                result = probe(live._https_transport, TOKEN)
            self.assertEqual(result["status"], expected)
            dns.assert_called_once()
            sockets.assert_called_once()
            self.assertEqual(len(tls.sent), 1)
            self.assertNotIn(TOKEN, json.dumps(result))

    def test_body_limit_handles_content_length_eof_and_chunked_responses(self):
        exact = b"[]" + b" " * (live.MAX_RESPONSE_BYTES - 2)
        fixtures = [(http_response(exact), "response_validated"),
                    (http_response(exact + b" "), "transport_error"),
                    (http_response(exact + b" ", content_length=False), "transport_error"),
                    (http_response(b"2\r\n[]\r\n0\r\n\r\n", headers=[("Transfer-Encoding", "chunked")], content_length=False), "response_validated"),
                    (http_response(b"2\r\n[", headers=[("Transfer-Encoding", "chunked")], content_length=False), "transport_error")]
        for wire, expected in fixtures:
            with network_fixture(wire) as (_, tls, _, _, _, _):
                result = probe(live._https_transport, TOKEN)
            self.assertEqual(result["status"], expected)
            self.assertLessEqual(tls.received, live.MAX_HTTP_BYTES)

    def test_header_budget_and_ambiguous_or_unsupported_framing_fail_closed(self):
        fixtures = [http_response(headers=[("X-Large", "x" * live.MAX_METADATA_BYTES)]),
                    http_response(headers=[("Content-Length", "2")]),
                    http_response(headers=[("Transfer-Encoding", "chunked")]),
                    http_response(headers=[("Content-Encoding", "gzip")]),
                    http_response(headers=[("Content-Type", "text/html")]),
                    http_response(content_length=False, headers=[("Content-Length", "9999999")]),
                    http_response(content_length=False, headers=[("Content-Length", "9")])]
        for wire in fixtures:
            with network_fixture(wire) as (_, tls, _, _, _, _):
                result = probe(live._https_transport, TOKEN)
            self.assertEqual(result["status"], "transport_error")
            self.assertLessEqual(tls.received, live.MAX_HTTP_BYTES)

    def test_deadline_is_rechecked_during_slow_response_reads(self):
        clock = [0.0]
        with network_fixture(http_response(), chunk=1) as (_, tls, _, _, _, _):
            tls.on_receive = lambda: clock.__setitem__(0, clock[0] + 2.0)
            with patch.object(live.time, "monotonic", side_effect=lambda: clock[0]):
                result = probe(live._https_transport, TOKEN)
        self.assertEqual(result["status"], "transport_error")
        self.assertLessEqual(len(tls.read_sizes), 3)
        self.assertTrue(tls.closed)

    def test_dns_time_is_explicitly_outside_socket_budget(self):
        clock = [0.0]
        with network_fixture(http_response()) as (tcp, _, _, dns, _, _):
            def resolve(*args, **kwargs):
                clock[0] = 123.0
                return [ADDRESS]
            dns.side_effect = resolve
            with patch.object(live.time, "monotonic", side_effect=lambda: clock[0]):
                result = probe(live._https_transport, TOKEN)
        self.assertEqual(result["status"], "response_validated")
        self.assertEqual(tcp.timeouts[0], 5.0)
        self.assertFalse(result["live_access_verified"])

    def test_environment_entry_requires_opt_in_and_invalid_token_never_resolves(self):
        with patch.dict(os.environ, {live.TOKEN_ENV: "bad\r\n" + TOKEN}, clear=True), \
             patch.object(live.socket, "getaddrinfo") as dns:
            self.assertEqual(live.read_inventory_from_environment()["status"], "live_flag_required")
            result = live.read_inventory_from_environment(live=True)
        dns.assert_not_called()
        self.assertEqual(result["status"], "invalid_configuration")
        self.assertEqual(result["transport_calls"], 0)
        self.assertNotIn(TOKEN, json.dumps(result))

    def test_check_config_presence_only_and_mocked_live_read_never_claims_access(self):
        with patch.dict(os.environ, {live.TOKEN_ENV: "invalid token with spaces"}, clear=True), \
             patch.object(live.socket, "getaddrinfo") as dns:
            result = live.check_configuration()
        dns.assert_not_called()
        self.assertTrue(result["credential_present"])
        self.assertEqual(result["credential_validation"], "presence_only")
        with network_fixture(http_response()), patch.dict(os.environ, {live.TOKEN_ENV: TOKEN}, clear=True):
            read = live.read_inventory_from_environment(live=True)
        self.assertEqual(read["status"], "response_validated")
        self.assertEqual(read["connection_status"], "unverified")
        self.assertFalse(read["live_access_verified"])
        self.assertEqual(read["runtime_provenance"], "operator_verification_required")
        self.assertNotIn(TOKEN, json.dumps(read))


class HostingerCliTests(unittest.TestCase):
    def invoke(self, args):
        output, error = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            code = cli.main(args)
        return code, output.getvalue(), error.getvalue()

    def test_offline_config_writes_presence_only_without_socket_use(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {live.TOKEN_ENV: TOKEN}, clear=True), \
             patch.object(live.socket, "getaddrinfo") as dns, patch.object(live.socket, "socket") as sockets:
            code, output, error = self.invoke(["--root", root, "--out", "config.json", "--check-config"])
            saved = Path(root, "config.json").read_text()
            permissions = stat.S_IMODE(Path(root, "config.json").stat().st_mode)
        self.assertEqual(code, 0)
        dns.assert_not_called()
        sockets.assert_not_called()
        self.assertTrue(json.loads(saved)["credential_present"])
        self.assertEqual(permissions, 0o600)
        self.assertEqual(error, "")
        self.assertNotIn(TOKEN, saved + output)

    def test_missing_named_variable_does_not_search_alternatives(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {"OTHER_API_TOKEN": TOKEN}, clear=True), \
             patch.object(live.socket, "getaddrinfo") as dns:
            code, output, error = self.invoke(["--root", root, "--out", "config.json", "--check-config"])
        self.assertEqual(code, 2)
        self.assertFalse(json.loads(output)["credential_present"])
        dns.assert_not_called()
        self.assertNotIn(TOKEN, output + error)

    def test_output_is_reserved_before_live_entry_and_existing_receipt_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root, "read.json")
            def read(*, live):
                self.assertTrue(live)
                self.assertTrue(target.is_file())
                self.assertEqual(target.stat().st_size, 0)
                return {"status": "response_validated", "connection_status": "unverified",
                        "live_access_verified": False, "transport_calls": 1, "writes_requested": 0}
            with patch.object(cli, "read_inventory_from_environment", side_effect=read) as runner:
                code, _, _ = self.invoke(["--root", root, "--out", "read.json", "--live"])
                original = target.read_bytes()
                second, _, _ = self.invoke(["--root", root, "--out", "read.json", "--live"])
            self.assertEqual(target.read_bytes(), original)
        self.assertEqual(code, 0)
        self.assertEqual(second, 1)
        runner.assert_called_once_with(live=True)

    def test_unsafe_missing_and_symlink_paths_fail_before_live_entry(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            Path(root, "escape").symlink_to(outside, target_is_directory=True)
            Path(root, "dangling.json").symlink_to(Path(outside, "missing.json"))
            paths = ["../escape.json", "/absolute.json", "escape/read.json", "dangling.json",
                     "missing/read.json", "a\\b.json", "x\n.json", "a/" * 6 + "read.json", "x" * 101 + ".json"]
            with patch.object(cli, "read_inventory_from_environment") as runner:
                for value in paths:
                    code, _, _ = self.invoke(["--root", root, "--out", value, "--live"])
                    self.assertEqual(code, 1)
            runner.assert_not_called()
            self.assertFalse(Path(outside, "read.json").exists())

    def test_plaintext_token_arguments_and_missing_mode_never_echo_values(self):
        with tempfile.TemporaryDirectory() as root, patch.object(cli, "read_inventory_from_environment") as runner:
            for tail in ([], ["--check-config", "--live"], ["--live", "--token", TOKEN]):
                code, output, error = self.invoke(["--root", root, "--out", "read.json", *tail])
                self.assertEqual(code, 1)
                self.assertNotIn(TOKEN, output + error)
            runner.assert_not_called()
            self.assertFalse(Path(root, "read.json").exists())

    def test_unexpected_error_is_sanitized_and_owned_incomplete_receipt_removed(self):
        with tempfile.TemporaryDirectory() as root, \
             patch.object(cli, "read_inventory_from_environment", side_effect=RuntimeError(TOKEN)):
            code, output, error = self.invoke(["--root", root, "--out", "read.json", "--live"])
            self.assertFalse(Path(root, "read.json").exists())
        self.assertEqual(code, 1)
        self.assertNotIn(TOKEN, output + error)
        self.assertEqual(json.loads(error)["status"], "command_failed")


if __name__ == "__main__":
    unittest.main()
