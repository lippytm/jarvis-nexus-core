# Hostinger: bounded read-only connection runbook

**Prepared:** October 22, 2026.  
**Starting revision:** `a67e743e8b32e552ccddd9e16a2108fe2f816274`.  
**Implemented:** one fixed HTTPS inventory read, an explicit command, and offline tests.  
**Live validation:** not performed while implementing this milestone.

## Exact capability

The command can issue this single request after explicit `--live` selection:

```text
GET https://developers.hostinger.com/api/horizons/v1/websites
```

The [Hostinger API overview](https://docs.hostinger.com/api-reference/overview), [website-list operation](https://docs.hostinger.com/api-reference/endpoints/horizons/websites/get-website-list) and [official OpenAPI specification](https://developers.hostinger.com/openapi/openapi.json) document this Horizons inventory endpoint and bearer authentication. The existing `hostinger_probe` validates its response array and produces aggregate counts plus a SHA-256 digest. The new `hostinger_live` module supplies a real Python standard-library transport. No provider SDK or new dependency is installed.

The endpoint inventories **Horizons projects**. A successful read does not establish that an existing manual-mode Hostinger Website Builder site is a Horizons project or is editable through the Horizons API. In particular, compatibility with `aievolutionaryevolutions.com` remains unverified. An empty inventory cannot establish that the account has no Website Builder sites. Hostinger separately documents [AI Builder API capabilities](https://docs.hostinger.com/ai-builder/integrations) and [manual-mode custom-code embeds](https://www.hostinger.com/support/6463152-hostinger-ai-builder-manual-mode-how-to-embed-custom-code/).

The transport does not edit, create, publish, clone or delete projects. It does not contact affiliate providers, test payment flows, modify memberships or post on social channels. API draft delivery remains unimplemented. Catalog account status remains `unverified` until separately supported by trustworthy runtime evidence.

## Runtime prerequisites

Use a trusted runtime with Python **3.11 or later**, its normal CA trust store, and permitted outbound HTTPS to `developers.hostinger.com:443`. The output writer requires POSIX directory-descriptor support and `O_NOFOLLOW`; it fails closed on platforms without them. The implementation uses APIs available in Python 3.11. Local execution was verified on Python 3.12.14; the repository CI is configured for Python 3.11, with exact-revision CI results requiring separate confirmation.

An authorized operator must provision the credential as the runtime environment variable **`HOSTINGER_API_TOKEN`**, using the runtime's secret configuration. Do not put the token in a command argument, URL, source file, report, chat message or shell-history assignment. This command has no token flag, token-file option, automatic login or credential-discovery fallback. It does not inspect other token variables. Hostinger documents that an API token inherits its owner's permissions; the GET-only code restricts this command's behavior, not the token's broader account privileges.

Create an output directory before invocation. Output paths must be relative to `--root`, use simple ASCII filename components, end in `.json`, contain at most six components and fit within 256 characters. Parent directories must already exist. Symlink parents and existing final filenames are rejected. Each report is created with mode `0600`; choose a new name for every run.

## First: offline presence check

After the runtime has been configured, this command checks only whether the named variable has a nonempty value:

```bash
python3 scripts/jarvis_hostinger.py --root . --out reports/hostinger/config-2026-10-22-01.json --check-config
```

It does not validate token format, authenticate, resolve DNS or open a socket. A malformed but nonempty value still reports `credential_present: true`. No secret is echoed. Exit code `0` means present; `2` means missing or empty. Both outcomes save a presence-only report. Path or command failures return `1` and a fixed sanitized error.

The output file is exclusively reserved before the variable is inspected. If `reports/hostinger` does not exist, create it inside the intended workspace before retrying with a fresh filename. A successful presence check does not prove API access or compatibility with the user's website.

## Then: one authorized live read

After the operator has confirmed the target runtime and authorization, the explicit command is:

```bash
python3 scripts/jarvis_hostinger.py --root . --out reports/hostinger/read-2026-10-22-01.json --live
```

No live invocation was performed during this implementation. `--live` is mutually exclusive with `--check-config`; omitting both fails before any output reservation or network work. The library entry point likewise requires `read_inventory_from_environment(live=True)`.

The command reserves a fresh, writable report file before calling the live entry point. It then validates the token's header-safe form and makes at most one TCP connection attempt and one GET request. There is no retry or alternate-address fallback. A failed first resolved address therefore fails the read, even if another address might have worked.

Exit code `0` for a live command means the returned response passed the fixed endpoint/status/JSON/schema checks. Other live outcomes return `1`. Saved records contain fixed status fields, aggregate counts when available, response digests and timestamps. They omit tokens, raw bodies, site identifiers, domains, descriptions, headers and raw exceptions. The console prints only a small sanitized summary. Disk or filesystem errors can still occur after a read; incomplete files owned by this command are removed when possible, and an error summary is returned.

## Network and parsing limits

| Boundary | Behavior |
|---|---|
| Destination | Fixed HTTPS host, port 443 and exact Horizons path; caller URLs and proxy configuration are not accepted. |
| Method | One GET with no request body; no mutation method exists. |
| TLS | `PROTOCOL_TLS_CLIENT`, required certificate verification, hostname checking with `developers.hostinger.com`, minimum TLS 1.2, HTTP/1.1 ALPN and normal trust roots. No insecure override or TLS key logging. |
| Resolution | One operating-system `getaddrinfo` call; only the first TCP address is attempted. |
| TCP/TLS/I/O time | A shared five-second monotonic budget starts **after DNS returns**. The remaining budget is installed before connection, handshake, sending and each socket read. |
| HTTP reads | Reads request at most 4 KiB at a time; aggregate HTTP bytes are capped at 64 KiB + 16 KiB + 1 byte. This cap counts decrypted HTTP data, not encrypted TLS framing. |
| Response body | At most 64 KiB. A one-byte lookahead detects an oversized body when its size is not supplied in advance. |
| Metadata | At most 16 KiB across status, header and chunk-metadata lines; Python's additional HTTP parser limits also apply. |
| Redirects/retries | No redirect is followed, no alternative host is contacted, and no request is retried. Error/redirect bodies and locations are not retained. |
| Framing | Duplicate critical headers, conflicting length/chunked framing, unsupported transfer encoding, compression and mismatched fixed lengths fail closed. |
| JSON/schema | Existing strict probe rejects duplicate JSON keys, nonfinite values, malformed UTF-8, unexpected fields/shapes and duplicate website identities. |
| Local report | Fresh descriptor opened exclusively before network work; existing files are never overwritten; report size at most 16 KiB. |

**DNS timing limitation:** Python's [`getaddrinfo`](https://docs.python.org/3.11/library/socket.html#socket.getaddrinfo) wraps the system resolver and has no per-call timeout argument. Socket timeouts do not supply a hard wall-clock limit for that resolution step. The five-second budget covers the subsequent TCP/TLS/HTTP operations. A process supervisor is required if the deployment needs a hard overall wall-clock deadline including a stalled resolver; this command does not create a background resolver thread or subprocess to claim that guarantee.

The TLS policy follows the Python [`SSLContext` client-verification documentation](https://docs.python.org/3.11/library/ssl.html#ssl.PROTOCOL_TLS_CLIENT). Python documents [handshake timing](https://docs.python.org/3.11/library/ssl.html#ssl.SSLSocket.do_handshake) and [socket timeouts](https://docs.python.org/3.11/library/socket.html#notes-on-socket-timeouts). The response framing uses the standard [`http.client.HTTPResponse`](https://docs.python.org/3.11/library/http.client.html#httpresponse-objects) parser with a bounded reader. TLS and certificate trust depend on the integrity of the selected runtime and its CA store.

## Interpreting evidence

Both offline fixtures and a live command use the same parser. A fixture can produce `response_validated`, so that status or a digest alone does not prove a real account was contacted. Results deliberately retain `connection_status: unverified` and `live_access_verified: false`, with `runtime_provenance: operator_verification_required`. The observation candidate identifies the fixed HTTPS collector while preserving that provenance limitation.

For an actual authorized run, retain the command's source revision, runtime provenance, run time, exit status and sanitized report. A reviewer may then record that a specific inventory read occurred at that time. Such a read still does not establish current availability, write permission, full account health, membership/checkout correctness or Website Builder compatibility. This milestone does not automatically import a receipt into the shared connector ledger or mark an account connected.

Useful outcomes include `invalid_configuration` before transport, `authorization_failed` for 401/403, `rate_limited` for 429, `rejected` for redirects, `provider_error` for other non-200 responses, `transport_error` for sanitized TLS/socket/framing/limit failures, and `invalid_response` for schema failures. Errors intentionally do not expose provider diagnostics. Inspect trusted runtime configuration and rerun only after choosing a fresh output path; there is no automatic retry.

## Offline verification

```bash
python3 -m py_compile control_tower/hostinger_live.py scripts/jarvis_hostinger.py tests/test_hostinger_live.py control_tower/provider_catalog.py tests/test_provider_catalog.py
python3 -m unittest discover -s tests -p test_hostinger_live.py -v
python3 -m unittest discover -s tests -p test_hostinger_probe.py -v
python3 -m unittest discover -s tests -p test_provider_catalog.py -v
```

The tests replace DNS, sockets and TLS boundaries. They exercise exact destination/method, verification configuration, disabled key logging, invalid-request rejection before DNS, certificate failure before credential transmission, no retries/redirects, body/header limits, chunked and incomplete responses, deadline checks, explicit DNS-limit semantics, named-variable presence checks, output reservation before live entry, symlink/traversal rejection, existing-file protection, and sanitized error handling. Test success establishes these local behaviors; live access remains untested.

Authoring result on **Python 3.12.14**: source syntax passed; **18 transport/CLI tests, 11 existing probe tests and 7 catalog tests passed (36 total)**. Python 3.11 grammar parsing and review against the official 3.11 API documentation also passed. A Python 3.11 interpreter was not available locally, so these checks do not constitute execution under 3.11. The repository's Python 3.11 CI must confirm this revision after publication. The integrated repository suite and an authorized runtime presence check are separate root-level steps.
