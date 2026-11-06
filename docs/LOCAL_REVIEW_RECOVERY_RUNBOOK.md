# Draft local review receipt recovery

**Proposed procedure — independent and owner review pending.** Prepared against
source `1b702e9357ab78892527f7759d107873fa587dbf` and master memory revision 172.
Inspection template updated against source
`6a24084c5b5a1eaec65e9f3bc450be14f285bd89` and master memory revision 178.
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
