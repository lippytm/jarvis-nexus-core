"""One fixed, read-only Hostinger HTTPS request using the Python standard library.

Only explicit read_inventory_from_environment(live=True) may start a live read.
The operating-system DNS resolver is outside the five-second socket/I/O budget.
Tests replace socket/TLS boundaries; their success is not live account evidence.
"""
from datetime import datetime, timezone
import http.client
import io
import os
import socket
import ssl
import time

from control_tower.hostinger_probe import (
    ENDPOINT, MAX_RESPONSE_BYTES, TIMEOUT_SECONDS, PreparedRequest, ProbeResponse,
    prepare_request, probe,
)


TOKEN_ENV = "HOSTINGER_API_TOKEN"
HOST = "developers.hostinger.com"
PORT = 443
PATH = "/api/horizons/v1/websites"
MAX_METADATA_BYTES = 16 * 1024
MAX_HTTP_BYTES = MAX_RESPONSE_BYTES + MAX_METADATA_BYTES + 1
MAX_READ_BYTES = 4096


class HostingerTransportError(RuntimeError):
    """Fixed message only; never wraps provider data or a credential in its text."""


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("hostinger_io_deadline")
    return min(TIMEOUT_SECONDS, remaining)


def _verified_context():
    # SSLContext does not enable SSLKEYLOGFILE automatically. create_default_context
    # would honor that debug variable, so construct the verified client explicitly.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.keylog_filename = None
    context.load_default_certs(ssl.Purpose.SERVER_AUTH)
    context.set_alpn_protocols(["http/1.1"])
    return context


class _DeadlineReader(io.RawIOBase):
    def __init__(self, tls_socket, deadline):
        super().__init__()
        self._socket = tls_socket
        self._deadline = deadline
        self._remaining_bytes = MAX_HTTP_BYTES

    def readable(self):
        return True

    def readinto(self, buffer):
        if not buffer:
            return 0
        if self._remaining_bytes <= 0:
            raise ValueError("http_response_limit")
        amount = min(len(buffer), MAX_READ_BYTES, self._remaining_bytes)
        self._socket.settimeout(_remaining(self._deadline))
        received = self._socket.recv_into(memoryview(buffer)[:amount], amount)
        if type(received) is not int or not 0 <= received <= amount:
            raise ValueError("invalid_socket_read")
        self._remaining_bytes -= received
        return received


class _MetadataReader(io.BufferedReader):
    """Bound all status/header/chunk-metadata lines consumed by http.client."""
    def __init__(self, raw):
        super().__init__(raw, buffer_size=MAX_READ_BYTES)
        self._metadata_remaining = MAX_METADATA_BYTES

    def readline(self, size=-1):
        limit = self._metadata_remaining + 1
        if size >= 0:
            limit = min(size, limit)
        line = super().readline(limit)
        if len(line) > self._metadata_remaining:
            raise ValueError("http_metadata_limit")
        self._metadata_remaining -= len(line)
        return line


class _ResponseSocket:
    """Give the stdlib parser a bounded reader without transferring socket ownership."""
    def __init__(self, tls_socket, deadline):
        self._socket = tls_socket
        self._deadline = deadline

    def makefile(self, mode):
        if mode != "rb":
            raise ValueError("unexpected_response_mode")
        return _MetadataReader(_DeadlineReader(self._socket, self._deadline))


def _single_header(response, name, default=""):
    values = response.headers.get_all(name, [])
    if len(values) > 1:
        raise ValueError("duplicate_response_header")
    return values[0].strip() if values else default


def _request_bytes(request):
    if (type(request) is not PreparedRequest or request.method != "GET" or request.url != ENDPOINT
            or request.timeout_seconds != TIMEOUT_SECONDS or request.max_response_bytes != MAX_RESPONSE_BYTES
            or request.follow_redirects is not False):
        raise ValueError("fixed_request_required")
    authorization = request.headers_for_transport()["Authorization"]
    if type(authorization) is not str or not authorization.startswith("Bearer "):
        raise ValueError("invalid_authorization")
    # PreparedRequest's public constructor can be used directly; revalidate the
    # token at this boundary before any DNS lookup or transmission.
    prepare_request(authorization[7:])
    return (f"GET {PATH} HTTP/1.1\r\nHost: {HOST}\r\n"
            f"Authorization: {authorization}\r\nAccept: application/json\r\n"
            "Content-Type: application/json\r\nAccept-Encoding: identity\r\n"
            "User-Agent: Jarvis-Hostinger-ReadOnly/1\r\nConnection: close\r\n\r\n").encode("ascii")


def _close_quietly(resource):
    if resource is not None:
        try:
            resource.close()
        except Exception:
            pass


def _https_transport(request):
    """Transport for the existing probe; no URL, proxy, TLS or timeout overrides.

    DNS is a single OS getaddrinfo call. Only the first returned TCP address is
    attempted: no fallback, HTTP retry, redirect, upload or account enumeration.
    All TCP/TLS/send/receive work shares a five-second budget after DNS returns.
    """
    tcp_socket = tls_socket = response = None
    try:
        payload = _request_bytes(request)
        context = _verified_context()
        addresses = socket.getaddrinfo(HOST, PORT, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
        if not addresses:
            raise ValueError("no_address")
        family, socktype, protocol, _, address = addresses[0]
        if family not in (socket.AF_INET, socket.AF_INET6) or socktype != socket.SOCK_STREAM:
            raise ValueError("unexpected_address")
        deadline = time.monotonic() + TIMEOUT_SECONDS
        tcp_socket = socket.socket(family, socktype, protocol)
        tcp_socket.settimeout(_remaining(deadline))
        tcp_socket.connect(address)
        tls_socket = context.wrap_socket(tcp_socket, server_hostname=HOST, do_handshake_on_connect=False)
        tcp_socket = None  # TLS wrapper now owns the underlying descriptor.
        tls_socket.settimeout(_remaining(deadline))
        tls_socket.do_handshake()
        if tls_socket.selected_alpn_protocol() not in (None, "http/1.1"):
            raise ValueError("unexpected_protocol")
        tls_socket.settimeout(_remaining(deadline))
        tls_socket.sendall(payload)
        response = http.client.HTTPResponse(_ResponseSocket(tls_socket, deadline), method="GET")
        response.begin()
        if response.status != 200:
            # Error and redirect bodies/locations never become retained evidence.
            return ProbeResponse(response.status, b"")
        content_type = _single_header(response, "Content-Type")
        content_encoding = _single_header(response, "Content-Encoding", "identity").lower()
        if content_type.split(";", 1)[0].strip().lower() != "application/json" or content_encoding not in ("", "identity"):
            raise ValueError("unexpected_content")
        length = _single_header(response, "Content-Length")
        transfer = _single_header(response, "Transfer-Encoding").lower()
        if transfer not in ("", "chunked") or (length and transfer):
            raise ValueError("ambiguous_response_framing")
        expected = None
        if length:
            if len(length) > 6 or not length.isascii() or not length.isdecimal():
                raise ValueError("invalid_content_length")
            expected = int(length)
            if expected > MAX_RESPONSE_BYTES:
                raise ValueError("response_size_limit")
        body = bytearray()
        while True:
            _remaining(deadline)
            part = response.read1(min(MAX_READ_BYTES, MAX_RESPONSE_BYTES + 1 - len(body)))
            if not part:
                break
            body.extend(part)
            if len(body) > MAX_RESPONSE_BYTES:
                raise ValueError("response_size_limit")
        if expected is not None and len(body) != expected:
            raise ValueError("incomplete_response")
        return ProbeResponse(200, bytes(body), content_type=content_type, content_encoding=content_encoding)
    except Exception:
        raise HostingerTransportError("hostinger_transport_failed") from None
    finally:
        _close_quietly(response)
        _close_quietly(tls_socket)
        _close_quietly(tcp_socket)


def check_configuration():
    """Inspect only the named variable's presence; no validation or network call."""
    return {"provider": "hostinger", "mode": "check_config", "status": "configuration_checked",
            "credential_environment_variable": TOKEN_ENV,
            "credential_present": bool(os.environ.get(TOKEN_ENV)),
            "credential_validation": "presence_only", "connection_status": "unverified",
            "live_access_verified": False, "transport_calls": 0, "writes_requested": 0}


def read_inventory_from_environment(*, live=False):
    """Explicit live entry point. Never accepts a plaintext token argument.

    Results retain the probe's unverified status. A real invocation can supply a
    point-in-time read candidate, but saved JSON and hashes alone do not establish
    whether this runtime used real sockets or test replacements.
    """
    if live is not True:
        return {"provider": "hostinger", "status": "live_flag_required",
                "connection_status": "unverified", "live_access_verified": False,
                "transport_calls": 0, "writes_requested": 0}
    result = probe(_https_transport, os.environ.get(TOKEN_ENV))
    result.update(mode="live_read", transport_implementation="stdlib_fixed_https",
                  observed_at=datetime.now(timezone.utc).isoformat(),
                  credential_environment_variable=TOKEN_ENV,
                  runtime_provenance="operator_verification_required")
    if "observation" in result:
        result["observation"]["provenance"] = "stdlib_https_collector_runtime_unverified"
    return result
