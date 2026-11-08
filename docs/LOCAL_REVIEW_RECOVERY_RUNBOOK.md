# Draft local review and export recovery

**Proposed procedure — independent and owner review pending.** Prepared against
source `1b702e9357ab78892527f7759d107873fa587dbf` and master memory revision 172.
Inspection template updated against source
`6a24084c5b5a1eaec65e9f3bc450be14f285bd89` and master memory revision 178.
Export reconciliation added against source
`e4800d7fdac5691c607266265af6e00089205c38` and master memory revision 195.
Registry-inspection receipt reuse added against source
`2583a09358690c5e8a9ee37b878485bbb1567b5b` and master memory revision 209.
Platform-selected queue rechecks added against source
`31709ff09208c8c2fcdfbd1fbfcf4a2b70100ec6` and master memory revision 213.
This is navigation for the existing local ledger, not an accepted operating
policy, authenticated approval or permission to release work.

Use this when `review-context --include-receipt --context-revision N --out ...`
fails or when a retained receipt needs checking after restart. The review commits
before file publication. An I/O error can therefore leave a committed review
with either no receipt file or a complete file that was not acknowledged.
An interruption after SQLite completes a commit can likewise prevent the review
receipt from returning to the caller. Cleanup rollback cannot undo that completed
commit. Do not infer database rollback from the CLI exit code, an exception or an
absent receipt, and do not replay blindly. A deterministic regression commits a
real synthetic SQLite review and injects an interrupt before acknowledgement;
read-only reopen observes the review while execution holds remain intact. This
models the boundary, not an actual owner incident or runtime outage.

## Retain the same mission and scope

Read the last work receipt before acting. Preserve its project, mission, handoff,
asset/platform, source and memory revisions, expected context revision, output
locator and recorded errors. Retrieve only the authorized evidence needed for
that mission. A mission ID and handoff ID are separate selectors; do not assume
they are equal. Do not create a replacement mission to evade duplicate handling.

For a coding task, first perform and record one harmless command in the intended
Codex environment. A failed command leaves the task `execution_blocked`; passing
GitHub CI does not prove that context recovered. Only an actual later successful
command can establish availability. This procedure neither restarts a server nor
changes the separately paused Studio cycle or newsletter schedule.

The commands below are templates, not executed work receipts. Fill variables
from the actual retained record before use. `TASK_ROOT` must be an existing
authorized absolute workspace root. `LEDGER` and every file locator are relative
to that root. Use fresh output names on each authorized observation; the writer
refuses overwrite. Never put credentials in these values or evidence records.

## Keep the digests distinct

| Value | Meaning | Where used |
|---|---|---|
| `CONTEXT_SHA256` | Exact canonical saved context digest | `inspect-recovery --digest` |
| `RECEIPT_SHA256` | Receipt body digest, excluding its own checksum | `check-review-receipt --receipt-digest` |
| `QUEUE_REPORT_SHA256` | Selected queue report body digest, excluding its own checksum | Queue `--expected-report-digest` |
| File byte SHA-256 | Exact serialized bytes, including whitespace | External artifact retention; not `--receipt-digest` |
| `REGISTRY_SHA256` | Entire canonical proposed registry, including unselected entries | `inspect-registry --digest` |
| `INSPECTION_SHA256` | Selected inspection receipt, excluding its own checksum | `inspect-registry --expected-receipt-digest` |

`CONTEXT_REVISION` is the stored ledger revision. `MEMORY_REVISION` belongs to the
context profile. Neither replaces `SOURCE_REVISION`, the recorded source SHA.

## Prepare and reuse a selective registry inspection

**Proposed addition — independent and owner review pending.** This preflight
does not open or change a ledger, accept a registry or contact a provider. Use
only the authorized private registry for the selected mission. Keep its exact
source/revision and whole-registry digest from the retained work record;
`REGISTRY_FILE` is relative to `TASK_ROOT`. The seven source project keys and
seventeen portable target IDs are separate from the seventeen business areas.

Prepare a fresh owner-private summary with both selectors explicit:

```sh
python scripts/jarvis_network.py --root "$TASK_ROOT" --read-only inspect-registry --file "$REGISTRY_FILE" --digest "$REGISTRY_SHA256" --source-revision "$REGISTRY_SOURCE_REVISION" --registry-revision "$REGISTRY_REVISION" --project "$PROJECT_ID" --platform "$PLATFORM_ID" --out reports/registry-selection-001.json
```

Compare the receipt's registry/source/revision/configuration identity, project,
platform, count and visibility with the intended scope. The saved file is
mode 0600 and refuses overwrite; it omits resource/destination mappings. Counts
describe supplied specifications, not connected agents or completed work. Retain
the summary as proposed evidence. A known empty scope is a zero-count summary,
not a failed command or a verified connection.

For subsequent reuse, `INSPECTION_SHA256` must be the `receipt_sha256` retained
with the exact reviewed selection. A file's byte hash is different. Reading a
self-declared digest from an arbitrary file does not establish independent
provenance, authenticated review or owner approval. When no trusted review/pin
exists, label the first summary unpinned; do not claim a successful pinned check.

Reinspect with the same explicit selectors and a fresh output name:

```sh
python scripts/jarvis_network.py --root "$TASK_ROOT" --read-only inspect-registry --file "$REGISTRY_FILE" --digest "$REGISTRY_SHA256" --source-revision "$REGISTRY_SOURCE_REVISION" --registry-revision "$REGISTRY_REVISION" --project "$PROJECT_ID" --platform "$PLATFORM_ID" --expected-receipt-digest "$INSPECTION_SHA256" --out reports/registry-selection-002.json
```

| Observed result | Bounded next action |
| --- | --- |
| Exact receipt matches | Retain both files and the actual command receipt; matching bytes do not authorize dispatch or establish authentication. |
| Registry/source/revision or inspection digest mismatches | Preserve the failed check and intended pin; reconcile changed data or selectors. Do not remove a guard merely to obtain success. |
| Output already exists | Preserve it and inspect the prior receipt. Existing-file preflight may reject before registry inspection; do not infer which later check would pass. |
| Missing/unreadable input or uncertain I/O | Preserve unfinished work and the error; do not initialize a ledger, invent acceptance or overlap retries. |

The optional guard adds no receipt fields: aggregate v1, project-only v2 and
platform-selected v3 formats remain distinct. Omitting a selector changes the
selected receipt and may invalidate its pin even when counts happen to match.
Full-registry guards remain required. No check changes review state, execution
holds, permissions, schedules or external-action limits, and it does not freeze
the registry for a future write. A real authorized authenticated storage/delivery
receipt is still needed before claiming operational shared connections.

## Observe the existing mission privately

From the repository root, select metadata for the actual project, mission and
portable target. `PLATFORM_ID` must be the exact retained target, such as `codex`;
it is separate from ChatGPT, the OpenAI API and GitHub:

```sh
python scripts/jarvis_network.py --root "$TASK_ROOT" --database "$LEDGER" --read-only queue-report --project "$PROJECT_ID" --mission "$MISSION_ID" --platform "$PLATFORM_ID" --include-review-state --out reports/queue-observation-001.json
```

This does not modify the ledger. The private report may contain project and
destination identifiers; retain it within its authorized audience. A local
review flag is not authenticated identity, owner approval or a completed mission.
Seven source project keys and seventeen portable targets do not replace the
master Page's seventeen business areas.

Retain the version-4 report's project, mission, platform, source/memory/context
revisions, local review flags and `report_sha256` with the work receipt. Set
`QUEUE_REPORT_SHA256` from that exact retained selection for a subsequent check;
the file's byte digest is different. A pin taken from a synthetic or unreviewed
file exercises consistency only, not independent provenance or approval.

Recheck the same selection in a fresh read-only process and output file:

```sh
python scripts/jarvis_network.py --root "$TASK_ROOT" --database "$LEDGER" --read-only queue-report --project "$PROJECT_ID" --mission "$MISSION_ID" --platform "$PLATFORM_ID" --include-review-state --expected-report-digest "$QUEUE_REPORT_SHA256" --out reports/queue-observation-002.json
```

| Observed result | Bounded next action |
| --- | --- |
| Exact selected report matches | Retain both private files and the command receipt. Read-only inspection changes no attempts, reviews or holds. |
| Scope, selected membership, context/revision, state or local review changes | Preserve the stale-check refusal and intended pin; retrieve fresh authorized metadata for review. Do not remove selectors or guards to manufacture a match. |
| Valid record on another platform changes | The selected snapshot may remain identical. That match says nothing about the other platform's current state. |
| Selected scope is empty | Record zero matching handoffs, not mission completion or a connected/ready agent. |
| Output exists or ledger is missing/unreadable | Retain existing evidence and the error. Do not overwrite it, initialize a replacement ledger or overlap retries. |

Changing or omitting platform, mission or review-state selection changes the
report contract and can invalidate the pin even when counts coincide. Existing
v1/v2/v3 reports remain available when their opt-ins are omitted. Malformed
context elsewhere in the selected project still rejects before platform
filtering. A successful snapshot check is point-in-time: it neither freezes a
future write nor permits dispatch, unpause, retry or release. Private report
identifiers still require authorized storage; omitted profile text is not ACL
isolation or authenticated shared memory.

## Check a receipt that actually exists

If its canonical receipt digest was retained independently:

```sh
python scripts/jarvis_network.py --root "$TASK_ROOT" --database "$LEDGER" --read-only check-review-receipt --handoff "$HANDOFF_ID" --file receipts/review.json --receipt-digest "$RECEIPT_SHA256" --out reports/receipt-check-001.json
```

The checker always opens the existing ledger read-only, even without the explicit
flag. It checks receipt integrity and the current exact context/reviewer binding.
The output contains check metadata, not the raw profile. A substituted receipt
rejects before ledger open when the independent expected digest differs.

If no independently retained digest exists, omit only `--receipt-digest` and label
the observation **unpinned**. Do not copy the current file's self-declared digest
and describe that as independent provenance. A valid rehashed timestamp can pass
the default consistency check because timestamps are not archived or attested.

## Reconcile the observed outcome

| Observation | Bounded next action |
|---|---|
| Complete receipt passes current check | Retain original file and check report. Do not overwrite it or rerun review merely to obtain success output. |
| Complete receipt fails pinned digest | Preserve the discrepancy and both references. Reconcile which receipt was intended; do not discard the pin to claim success. |
| Receipt fails current revision/content/reviewer binding | Treat it as historical. Retrieve current authorized selectors and request review of that exact revision when required. |
| No receipt, but current metadata shows local review | Record that review may have committed. There is no receipt archive to recover the original timestamp from. A new receipt would require a separate explicit exact-revision local review; it is not reconstruction of the lost receipt. |
| Missing/unreadable ledger or uncertain I/O result | Preserve the unfinished task and observed error. Do not initialize a replacement database, overlap retries or manufacture a completion receipt. |

When exact context selectors are available, inspect recovery holds separately:

```sh
python scripts/jarvis_network.py --root "$TASK_ROOT" --database "$LEDGER" --read-only inspect-recovery --handoff "$HANDOFF_ID" --digest "$CONTEXT_SHA256" --source-revision "$SOURCE_REVISION" --memory-revision "$MEMORY_REVISION" --context-revision "$CONTEXT_REVISION" --out reports/recovery-inspection-001.json
```

Use the selected stored revision from the retained record, not the profile's
memory revision. The revision guard rejects an old request after content changes
and is restored to the same digest at a later stored revision. On mismatch,
preserve the failed observation and retrieve the current authorized metadata;
do not discard the guard merely to obtain output. This check is atomic with the
inspection read, but it does not freeze future state or authorize a later write.

Keep paused/cancelled, blocked and unknown-outcome state intact. Consistency is
point-in-time: a successful read does not freeze later edits or gate a later
write. No command here authorizes dispatch, retry, unpause, publishing, merge,
deployment, spending or live trading. Trading Bots remains research/backtesting/
paper-only; RoboParty remains deferred.

## Reconcile a failed manual envelope export

For `export-context --context-revision N --out ...` I/O failures, preserve the
same ledger, selected revisions, output locator and error. The export transaction
commits before the file writer runs. `export_prepared` records preparation, not
successful file publication, provider delivery or mission completion. An absent
file does not prove that the ledger rolled back. Do not invoke `export-context`
again merely to inspect the outcome, and never import an envelope as a review
receipt: `check-review-receipt` accepts a different record kind.

| Observed output | Bounded reconciliation |
|---|---|
| No output file after a file-sync failure | Retain the error and observe the original ledger read-only. Record publication as unconfirmed; do not create a replacement mission or assume export state reverted. |
| Complete file after a directory-sync failure | Preserve its exact bytes and byte digest privately. A complete file may exist despite exit code 1; do not overwrite it or describe crash durability as verified. |
| Missing/unreadable ledger, partial/unreadable output or mismatched binding | Keep the discrepancy unresolved. Do not delete, overwrite or automatically replay; request exact-artifact review within the existing authority limits. |

Use fresh output names to observe the same project/mission and selected context:

```sh
python scripts/jarvis_network.py --root "$TASK_ROOT" --database "$LEDGER" --read-only queue-report --project "$PROJECT_ID" --mission "$MISSION_ID" --include-review-state --out reports/export-queue-001.json
python scripts/jarvis_network.py --root "$TASK_ROOT" --database "$LEDGER" --read-only inspect-recovery --handoff "$HANDOFF_ID" --digest "$CONTEXT_SHA256" --source-revision "$SOURCE_REVISION" --memory-revision "$MEMORY_REVISION" --context-revision "$CONTEXT_REVISION" --out reports/export-recovery-001.json
```

These separate snapshots do not freeze concurrent edits. Compare the handoff,
context digest/stored revision, source/memory revisions, local review and retained
execution/control state. On mismatch, retain both observations and retrieve fresh
authorized selectors. The inspection omits profile text and reference URLs but
still contains private identifiers. Neither command validates the exported file
or authenticates approval. Separately compare any retained envelope's original
handoff/context bindings and exact revision during authorized artifact review;
a file byte digest alone is not an independent signature or delivery receipt.

The POSIX regression in `tests/test_handoff_context_cli.py` injects file and
directory fsync failures into temporary ledgers. It observes committed export
state, absent versus complete private files and overwrite refusal. This is not
a real owner incident, a power/process-loss test or measured runtime recovery.
Retain blocked/paused/cancelled/unknown-outcome holds. This proposed procedure
authorizes no new export, retry, dispatch, unpause or release.

## Compare a retained backup's byte digest

When an expected `backup_sha256` was retained independently, compare that exact
file byte hash before considering a retained backup for further review:

```sh
python scripts/jarvis_network.py --root "$TASK_ROOT" --read-only check-backup-digest --file backups/retained.sqlite3 --digest "$BACKUP_SHA256" --out reports/backup-byte-check-001.json
```

This command opens no SQLite database and ignores `--database`. It reads one
regular file inside the workspace, with a 128 MiB limit and a ten-second budget
checked before and after each 64 KiB read, including EOF. A read finishing after
the deadline rejects; blocking operating-system I/O itself can exceed that budget.
Mismatch, invalid digest, missing/nonregular/oversized input or exhausted budget
rejects without a check report. Default output is metadata on stdout; optional
`--out` uses the existing private 0600, no-overwrite writer. Input bytes remain
unchanged. Report schema version 1 is `jarvis.backup_digest_check`, separate from
strict handoff packets and backup creation receipts.

A match means only that the bytes read have the expected digest. The command
deliberately accepts matching non-SQLite bytes and says `ledger_validation` is
`not_performed`. It does not inspect WAL sidecars, validate schema/records/holds,
authenticate the expected digest, attest crash durability or authorize restore,
retry or dispatch. Do not use an active/changing file as a frozen backup; this
read does not lock out writers or protect against concurrent path replacement.
Retain the expected digest separately rather than treating a newly computed
self-declared hash as independent provenance. A mismatch stays unresolved; do
not discard the expected hash or overwrite evidence to manufacture a match.

## Write back observations separately from decisions

Retain input source/memory revisions, actual execution context/result, exact
artifact locators/digests, check outputs, unresolved outcome, review status and
one next action. Keep accepted project facts/decisions, actual work receipts and
this proposed procedure distinguishable. Record observed failures or duplicates;
leave costs, recovery time and review effort unmeasured unless actually measured.
Do not infer a reliability improvement from this document or synthetic checks.

Local hashes and reviewer labels are not authentication. No accepted registry,
hosted worker, lease, failover or automatic reconciliation service is established.
See [the context contract](HANDOFF_CONTEXT_PROFILE.md),
[Codex readiness](CODEX_JARVIS_READINESS.md) and
[the Docker development path](DOCKER_RUNBOOK.md) for implementation boundaries.
