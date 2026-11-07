# Draft local review and export recovery

**Proposed procedure — independent and owner review pending.** Prepared against
source `1b702e9357ab78892527f7759d107873fa587dbf` and master memory revision 172.
Inspection template updated against source
`6a24084c5b5a1eaec65e9f3bc450be14f285bd89` and master memory revision 178.
Export reconciliation added against source
`e4800d7fdac5691c607266265af6e00089205c38` and master memory revision 195.
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
| Queue `report_sha256` | One selected metadata snapshot | Optional queue `--expected-report-digest` |
| File byte SHA-256 | Exact serialized bytes, including whitespace | External artifact retention; not `--receipt-digest` |

`CONTEXT_REVISION` is the stored ledger revision. `MEMORY_REVISION` belongs to the
context profile. Neither replaces `SOURCE_REVISION`, the recorded source SHA.

## Observe the existing mission privately

From the repository root, select metadata for the actual project and mission:

```sh
python scripts/jarvis_network.py --root "$TASK_ROOT" --database "$LEDGER" --read-only queue-report --project "$PROJECT_ID" --mission "$MISSION_ID" --include-review-state --out reports/queue-observation-001.json
```

This does not modify the ledger. The private report may contain project and
destination identifiers; retain it within its authorized audience. A local
review flag is not authenticated identity, owner approval or a completed mission.
Seven source project keys and seventeen portable targets do not replace the
master Page's seventeen business areas.

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
