# Jarvis Life and Business Diary data contract

The diary records supplied text, evidence labels, source references and proposed next actions. Its Python core validates entries, stores local revision history, and compiles a deterministic daily briefing. It does not fetch sources, call a model, infer personal events, authenticate an author, publish content, or establish revenue, sales or completion of a plan.

Implementation: [diary.py](../control_tower/diary.py), [diary_store.py](../control_tower/diary_store.py). The [workbench](../web/jarvis-diary.html), [local CLI](../scripts/jarvis_diary.py) and media exporters use the same entry contract. The CLI and media exporters have their own output and format checks.

## Entry schema, version 1

An entry is a JSON object with exactly these 13 keys. Unknown or missing fields fail validation, including inside nested objects. All Python types must be exact built-in JSON types: for example, `true` and `1.0` do not satisfy the integer schema version.

| Field | Required value or bound |
| --- | --- |
| `schema_version` | Integer `1` |
| `kind` | String `jarvis.diary_entry` |
| `entry_id` | Identifier of 2–48 ASCII characters, matching `[a-z][a-z0-9_.-]{1,47}` |
| `date` | ASCII `YYYY-MM-DD`, a valid Gregorian date in years 0001–9999 |
| `timezone` | Exactly `America/Los_Angeles` |
| `initiative_id` | One of the 12 registered portfolio initiative IDs below |
| `title` | Nonblank string, at most 180 UTF-8 bytes |
| `visibility` | `private`, `internal`, or `public_candidate` |
| `summary` | Nonblank string, at most 3,000 UTF-8 bytes |
| `observations` | List of 1–8 observation objects |
| `sources` | List of 0–5 source objects |
| `next_action` | Nonblank string, at most 1,500 UTF-8 bytes |
| `media_notes` | Exact five-field object described below |

The initiative IDs come from [portfolio.py](../control_tower/portfolio.py): `jarvis-tools`, `website-learning`, `affiliate-builder`, `funding-customers`, `referral-partners`, `publishing-library`, `interactive-video`, `linux-learning`, `robotics-simulation`, `wearables-research`, `business-operations`, and `personal-workflow`. Choosing an initiative assigns a local record to that project; it does not imply an account connection or activity in an external service.

Every string must encode as valid UTF-8. Lone Unicode surrogates and C0 control characters are rejected, except tab, carriage return and line feed. Nonblank means that Python's Unicode-aware `str.strip()` leaves at least one character. Text is preserved exactly: validation does not trim it, normalize Unicode, redact it, or rewrite claims. Byte limits count encoded UTF-8, so a four-byte character consumes four bytes. The canonical JSON representation of the complete entry must not exceed 65,536 bytes, including JSON escaping and field names.

### Observations and evidence

Each observation has exactly `observation_id`, `text`, `evidence_state`, and `source_ids`.

| Field | Required value or bound |
| --- | --- |
| `observation_id` | Same identifier rule as `entry_id`; unique among this entry's observations |
| `text` | Nonblank string, at most 1,000 UTF-8 bytes |
| `evidence_state` | One of the four labels in the following table |
| `source_ids` | List of at most five unique source IDs, all present in this entry's `sources` |

| Evidence label | Meaning retained by the tools |
| --- | --- |
| `source_linked` | The author attached one or more source references. Accuracy and support for the claim still require review. At least one `source_id` is required. |
| `owner_reported` | Supplied as an owner report, without independent verification by these tools. |
| `planned` | A plan or intended action, not evidence of completed work. |
| `fictional` | An explicitly fictional record, not a factual event. |

The last three labels may have zero or more valid source references. Attaching a reference does not change the evidence label. A summary remains supplied editorial context; individual observations carry the evidence labels. Neither the entry digest nor the briefing digest upgrades a label to “verified.”

### Sources and media notes

Each source has exactly `source_id`, `title`, and `url`. Source IDs use the same identifier rule and must be unique within the entry. Source titles are nonblank strings of at most 200 UTF-8 bytes.

A source URL is at most 1,000 UTF-8 bytes and must pass the shared [`valid_https_url`](../control_tower/validation.py) boundary: HTTPS, a nonempty parsed hostname, no credentials, no whitespace or C0 characters, no backslashes, and a port that is absent or 443. The original string is retained. This is URL-shape validation, not a fetch, host reputation check, content verification, or guarantee that a destination is public. No DNS lookup occurs. A URL can still contain sensitive text in its path or query; visibility selection does not perform a sensitive-data scan.

`media_notes` has exactly `audience`, `visual_style`, `audio_style`, `learning_goal`, and `call_to_action`. Each is a string of at most 600 UTF-8 bytes and may be blank. These are supplied creative instructions, not evidence that a video, course, advert or other product exists.

JSON-compatible Unicode is not automatically compatible with every export format. In particular, the media exporter rejects U+FFFE and U+FFFF before producing XML-based files. The original diary record and history remain unchanged; the core does not silently delete or replace those characters.

## Validation and deterministic daily briefings

```python
from control_tower.diary import (
    validate_diary_entry,
    diary_entry_digest,
    build_diary_briefing,
)

validated = validate_diary_entry(entry)
entry_hash = diary_entry_digest(validated)
public_briefing = build_diary_briefing(
    entries, diary_date="2026-10-22", audience="public"
)
```

`validate_diary_entry(entry)` returns a deep defensive copy. It does not modify the input. `diary_entry_digest(entry)` validates first and returns SHA-256 over canonical JSON: sorted keys, compact separators, original Unicode encoded as UTF-8, and no nonfinite numbers. This full-entry hash includes all fields and is owner-local metadata unless the associated entry has been deliberately selected for export. It is a content-integrity value, not a signature or publication authorization.

`build_diary_briefing(entries, *, diary_date, audience="public")` accepts a list or tuple of at most 1,000 entries. It validates every supplied entry and rejects duplicate entry IDs before selecting the requested date. Invalid hidden entries produce a fixed validation error that does not echo their content. A public briefing includes only `public_candidate` entries. An explicit `audience="owner"` includes all three visibilities for that date. Other audience values are rejected.

The function sorts selected entries by `entry_id` and rejects more than seven eligible entries. It does not silently drop eligible entries to meet the daily limit. An empty selection produces `status="no_eligible_entry"` and an empty `entries` list. No hidden-entry count, private entry ID, full hidden-entry hash, or hidden text is included in a successful public result. Adding or editing valid private/internal records, or records on another date, leaves the public result and its digest unchanged, provided the supplied input remains within the validation bounds.

The briefing is a short projection, not a complete record export:

| Included field | Projection rule |
| --- | --- |
| Entry ID, initiative, title, visibility | Retained for selected entries |
| Summary | First 400 UTF-8 bytes, ending at a complete code point; explicit truncation flag |
| Proposed next action | First 240 UTF-8 bytes; explicit truncation flag |
| Observations | First three in supplied order, with ID, evidence label, source IDs, and at most 160 UTF-8 bytes of text each |
| Omitted observations | Explicit count within the selected entry |
| Evidence labels | Sorted unique labels from all observations, including any omitted observation |
| Sources | All source IDs and complete original URLs; title excerpts of at most 80 UTF-8 bytes with truncation flags |
| Media notes and full-entry hash | Omitted |

Truncation flags identify excerpts that require the original record for complete context. A briefing must not be treated as a full verification of an excerpted claim. All source URLs are retained intact. In the unusual case that seven valid entries with long or heavily escaped URLs exceed the final 65,536-byte briefing bound, the function rejects the briefing; use fewer entries or shorten the supplied records deliberately.

The output has kind `jarvis.diary_briefing`, the selected date and timezone, audience, status, entries, eligible `entry_count`, `publication_approval="not_granted"`, `source_verification="not_performed"`, and `external_actions=0`. `briefing_sha256` hashes that audience-filtered output before the hash field itself is added. No current timestamp or hidden-record metadata contributes to it. Identical selected inputs produce identical canonical output.

`public_candidate` means that the owner selected an entry for a possible local public-facing draft. It does not approve publication, consent to marketing, or authorize any account action. Free text is not automatically checked for personal information, credentials, intellectual-property permission, or factual accuracy.

## Local revision store

```python
from control_tower.diary_store import DiaryStore

with DiaryStore("reports/diary/diary.sqlite3") as diary:
    created = diary.save(entry)
    current = diary.get(entry["entry_id"])
    current["next_action"] = "Review the next synthetic draft."
    updated = diary.save(current, expected_sha256=created["sha256"])
    revision_metadata = diary.history(entry["entry_id"])
```

The default path is `reports/diary/diary.sqlite3`, relative to the caller's current working directory. `reports/` is ignored by this repository. The CLI anchors its default under the repository root. Store methods never derive filenames from entry IDs.

| Method | Result and behavior |
| --- | --- |
| `save(entry, expected_sha256=None)` | Validates and saves; returns only `entry_id`, `revision`, `sha256`, and `status` (`created`, `updated`, or `unchanged`). |
| `get(entry_id)` | Returns an independent validated current entry, or `None` if the ID does not exist. |
| `entries_for_date(date)` | Returns current entries for a valid date in entry-ID order. This is an owner-local read and includes all visibilities. |
| `history(entry_id)` | Returns revision metadata in revision order; unknown ID returns an empty list. |
| `list_metadata()` | Returns metadata for current entries in entry-ID order. |
| `close()` / context manager | Releases SQLite and retained filesystem descriptors. |

An identical-content retry is idempotent and does not append a revision. A well-formed but stale expected hash is permitted for that identical retry because it changes no content. Any malformed hash is rejected. Creating a new ID requires `expected_sha256=None`. Changing content under an existing ID requires the exact current lowercase 64-character SHA-256. Missing or stale hashes fail without changing either the current entry or its history.

Each successful change appends a numbered canonical revision with its hash, predecessor hash, date, visibility and UTC save timestamp, then moves the current-revision pointer in the same transaction. Revision numbers begin at 1 and are contiguous. Revision rows reject ordinary SQL updates and deletes through immutable-history triggers. A failed pointer update rolls back the newly inserted revision. Public reads use a single SQLite read transaction so a concurrent writer cannot create a false mismatch between the current pointer and the revision chain. Writes use `BEGIN IMMEDIATE`; the connection has a two-second SQLite busy timeout and no application retry loop.

Reading an entry validates the entire revision chain for that ID: JSON structure, duplicate keys, canonical representation, field bindings, content hashes, predecessor hashes, numbering and current pointer. Listings and date queries validate all current entries before returning results and also reject orphan revision rows. Corrupt stored data fails with a fixed integrity error, rather than exposing its raw contents. The store does not repair damaged history automatically.

History and listing metadata contain `entry_id`, `revision`, `sha256`, `date`, `visibility`, `saved_at` and `previous_sha256`. They exclude titles, summaries, observation text, source URLs and media notes. IDs, dates and hashes can still be sensitive; these owner-local listings are not public briefings.

The store caps current entries at 1,000 and revisions per entry at 256. Reaching a limit rejects a new write; it does not delete old entries or revisions. This version has no deletion, pruning, migration, synchronization or automated backup API.

## Storage protections and their limits

The implementation requires Python 3.11 or later and a POSIX environment with descriptor-relative filesystem operations and `O_NOFOLLOW`. It walks parent directories without following symlinks, creates missing directories with mode 0700, and creates the database with mode 0600, subject to the process umask. Existing database files must be regular files, owned by the current OS user, have one hard link, and have no group/other permission bits. The immediate parent must be owned by that user and must not be group/world writable. Symlinks, FIFOs, directories used as database files, hard links, unsafe existing permissions, memory databases and SQLite URI paths are rejected.

Before opening and before operations, the store checks the database identity and rejects unsafe SQLite journal/WAL/shared-memory sidecar paths. It retains file and directory descriptors for identity checks. Schema, application ID, version and the expected immutable-history triggers are checked when opening an existing database. Before any stored-row query, the connection sets SQLite's maximum string/blob/row length to 69,632 bytes: the 65,536-byte packet limit plus 4 KiB for fixed revision metadata. Oversized rows from an externally damaged database fail before JSON decoding. The configured journal mode is `DELETE`, with synchronous mode `FULL`. Fixed error messages omit SQLite error details, source text and database paths.

These safeguards reduce accidental disclosure and common local path hazards. They are not encryption, OS-user authentication, tamper-proof audit logging, or a sandbox against another process running as the same owner. SQLite opens a filename; a malicious same-user process able to race path replacement or rewrite the database is outside this protection boundary. Keep the store in a trusted local directory. Filesystem or disk failure can still lose data; revision history is not a backup. Public-candidate status does not remove private earlier revisions from the local database.

## Verification evidence

The focused standard-library tests use synthetic records and temporary databases only:

```bash
python -m py_compile control_tower/diary.py control_tower/diary_store.py tests/test_diary.py tests/test_diary_store.py
python -m unittest discover -s tests -p test_diary.py -v
python -m unittest discover -s tests -p test_diary_store.py -v
```

At implementation review, 17 core/briefing tests and 21 store tests passed locally. Coverage includes Unicode and byte boundaries, exact schemas, all 12 initiative IDs, source references, audience/digest isolation, deterministic excerpts and overflow rejection, durable reopen, idempotence, stale updates, immutable history, rollback, a real concurrent-reader/writer snapshot, corrupt and oversized stored data, unsafe file types/permissions, symlink sidecars and file replacement. These tests establish the stated local behaviors; they do not prove source accuracy, live provider integration, publication or storage resilience on every filesystem.

The [workbench fixtures](evidence/diary-workbench-fixtures.json) contain 12 actual JavaScript exports and 39 malformed entry objects. Python accepted the 12 exports unchanged and rejected all 39 malformed objects. Serialized JSON import is a separate boundary: callers should use the bounded [`load_packet`](../control_tower/network_contract.py) reader before validation, so duplicate JSON keys, invalid UTF-8 and oversized raw files are not normalized away by a permissive parser. All seven malformed serialized JSON fixtures were also rejected by `load_packet` plus `validate_diary_entry`. The validator accepts an already-decoded object; it cannot recover duplicate keys or original number syntax that a prior parser discarded.
