# Hermes Fabric MemPalace: local handoff context, versions 1 and 2

This development increment extends `HandoffLedger`; it does not introduce a
second memory store. The existing strict version-1 draft, handoff and return
packets remain unchanged. An optional `jarvis.handoff_context` record lives in
the same SQLite database. A `jarvis.context_envelope` export binds the original
handoff and its digest to the separately versioned context and its digest.

## Stored scope

- Project, mission, source commit, asset and platform identities bind to the
  existing handoff. Every one of the seventeen portable targets is supported,
  including distinct `codex`, `chatgpt`, `openai` and `github` IDs.
- A configuration version, memory revision, visibility, permitted action and
  bounded context/evidence references retain selected provenance.
- Execution context, attempt count, unfinished state and checkpoint reference
  survive a fresh process reading the database. `execution_blocked` and
  `outcome_unknown` remain unchanged on retrieval; no retry is dispatched.
- Budget metadata permits at most three attempts, 3,600 seconds and no paid
  execution. These are validated limits for a future worker, not an installed
  timer or supervisor. The only permitted action remains `prepare_draft`.

Keep secrets and unrelated diaries outside these records. Known sensitive
field names are rejected by the existing validator; ordinary strings and URLs
are not a complete sensitive-data detector. Reference visibility and review
labels are supplied classifications, not authenticated identities.

## Writes, reviews and retrieval

`save_context(profile, expected_revision=0)` creates context for an existing
handoff; later writes require the exact current local context revision.
SQLite `BEGIN IMMEDIATE` serializes the compare-and-swap and update. Identical
replays at the current revision are duplicates. Conflicting stale writes stop.
Memory revisions and recorded attempt counts cannot decrease; the mission ID
cannot change. The database stores proposed context, not accepted project facts.

`load_context` requires expected source and memory revisions and returns an
independent record. `audience="public_candidate"` rejects private profiles;
public profiles cannot contain references labelled private. This local audience
argument is **not authentication**. A hosted adapter must authenticate callers,
authorize project access and curate any public text before exposing this API.

`review_context` records a distinct local reviewer label bound to the context
digest. Every content change invalidates this context review, including an edit
to checkpoint text or configuration. `export_context` requires both original
handoff and context reviews plus exact source/memory revisions. Public envelope
export is denied because version-1 drafts have no visibility classification;
a public context label cannot declassify their text. Imported returns still bind
to the original handoff digest and target and remain unverified. No review label
here authorizes deployment, publishing, spending or permission changes.

## Unknown-outcome hold

For both supported profile versions, outcome_unknown blocks both legacy and
combined-envelope export, even after a matching local review or process restart.
An ordinary save-context update cannot clear that state, increase its attempt
count or replace the original execution context ID. It can retain additional
evidence references, checkpoint details and version-2 pause/cancel controls;
changed content still invalidates context review. Reads and identical duplicate
saves remain available. Unverified provider returns do not clear the hold.

There is no reconciliation/release operation in this increment. A future explicit
protocol must bind verified destination evidence and owner authority before a
retry or resolution can be enabled. Do not bypass the hold with a replacement
handoff ID, raw database edit or older application version. Use load-context for
private inspection; export is preparation for further manual handoff. These local
guards do not stop previously exported work or authenticate provider responses.

## Private recovery inspection

`inspect_recovery` and the `inspect-recovery` CLI command prepare a deterministic
metadata snapshot from this same ledger. They require the selected context's
exact SHA-256, source revision and memory revision. In one SQLite transaction,
the inspection captures the selected handoff and at most two ancestors, validates
stored handoff/context/return integrity, and records their current digests,
context revisions, execution/control states, local review status and unverified
return bindings. An ancestor without a context is explicitly shown as null.
Unrelated missions are excluded. The snapshot's inspection_sha256 hashes the
whole report except that checksum field; changed context or return bindings
produce a different snapshot. It is a current observation, not revision history.

The separate version-1 `jarvis.recovery_inspection` report does not change any
strict packet or database schema. It is always owner_private, including for
public-labelled contexts: identity and control metadata still need protection.
Draft/return text, execution detail, context/evidence URLs and checkpoint URLs
are omitted; the context digest binds those retained records for later selective
inspection. The report is not a public publishing export. Authentication is not
established by this local command or its checksum.

Inspection changes no handoff state, review, attempt count or context. It remains
available while unknown-outcome/pause/cancel holds prevent further exports.
`retry_authorized` is always false, including when the holds list is empty. That
list reports unknown-outcome and version-2 control/review holds, not complete
dispatch eligibility. Re-read the current ledger before any later decision;
this snapshot grants no authorization and cannot be imported as a return or
reconciliation approval. A future reconciliation proposal must bind current
inspection/context revisions to actual destination evidence and authenticated
owner approval. Verified resolution and hold release remain unimplemented.

Before using an inspection in a later review, `check_recovery` can compare its
inspection_sha256 with a fresh transactional snapshot. The CLI equivalent is:

```sh
python scripts/jarvis_network.py --root /data --database handoffs.sqlite3 check-recovery --handoff YOUR-HANDOFF-ID --inspection-digest YOUR-INSPECTION-SHA256 --digest YOUR-CONTEXT-SHA256 --source-revision YOUR-40-CHAR-SOURCE-SHA --memory-revision 1
```

Use real values from inspect-recovery/load-context; these are placeholders. A
changed ancestor context, local review state or late return invalidates the old
inspection even if the selected context digest is unchanged. The check prints
only a small private receipt, not the lineage or source text. It changes no
ledger records and establishes only a current local observation. It is not a
lease: another process can change the ledger after the snapshot transaction.
Any future state-changing reconciliation must recheck the expected snapshot
atomically with its write and authenticate owner authority. A successful check
does not verify destination evidence, clear a hold or authorize a retry.

## Follow-up lineage controls

Staging a follow-up now checks its parent and ancestors for the same local hold
and review conditions used by export. Both export paths also recheck the complete
bounded lineage, including descendants staged before a later parent pause,
cancellation or unknown outcome. This applies even if a descendant has no context
record. The existing factory limit is two delegation levels (three records in a
lineage); cycles or excessive chains fail closed. Rejected staging leaves the
handoff budget and existing return evidence unchanged.

An explicit parent resume still needs fresh parent context review before a child
can be exported. Existing child records, their own reviews and private checkpoints
are retained. This is not global cancellation or a recall of exported work, and
does not prove a child result used the latest parent memory revision. A separately
staged root is not automatically recognized as the same mission; operators must
not allocate new IDs to evade a hold. Authenticated dispatch and evidence-bound
reconciliation remain unfinished.

## Version-2 per-handoff pause/cancel

Existing version-1 profiles remain unchanged and reject added fields. To opt in,
retain the entire profile, set schema_version to 2 and add:

```json
{"control":{"state":"paused","actor_id":"local-owner-label","reason":"Operator checkpoint before further export."}}
```

This is a field example, not a complete packet. Use the existing save-context
command and the exact current context revision; load-context returns the saved
control and revision. State is active, paused or cancelled. The actor is a local
label, not authenticated authority. All previous private/public, provenance,
budget and permitted-action checks still apply across all seventeen targets.

Both legacy export and export_context refuse paused/cancelled records, including
after process restart. A version-2 record cannot downgrade to version 1, and
cancellation cannot resume. A paused record can explicitly resume to active;
that edit invalidates context review, so both export paths require a fresh
context review for version-2 records. Cancellation does not recall prior exports or stop external work.
Late returns remain unverified evidence and never clear the control or resolve an
unknown execution outcome. Context reads and checkpoint updates remain available.

The current profile/revision is retained; this is not an append-only audit log.
These controls do not add a dispatcher, queue lease, global pause or authenticated
hosted service. Only this updated implementation enforces them. Do not run older
application code against controlled records; preserve private backups and review
controls explicitly before a rollback. No database-table migration is needed for
this envelope opt-in; SQLite user_version remains 2.

## Migration and rollback

Opening a supported version-1 ledger transactionally adds `handoff_contexts`
and sets SQLite `user_version=2`. Existing swarms, handoffs, reviews and returns
are not rewritten; legacy APIs remain usable. Unrelated databases and unknown
versions are rejected. Version-1 application code will reject a version-2 file.

Before first migration, stop the single worker and retain a SQLite online backup
using `Connection.backup` (or a closed-file copy). Keep the backup private. Roll
back code **and** restore that version-1 backup together; preserve the current
database separately so new context is not lost. Do not merely lower user_version
or delete tables. Tests also verify a version-2 backup restores context and the
original handoff together.

## Verification and remaining work

Run `python scripts/verify_control_tower.py` and
`node --test --test-reporter=tap tests/*.mjs`. The dedicated
`tests/test_handoff_context.py` uses synthetic local fixtures, including an actual
fresh Python process, a separate SQLite connection and backup restoration.
These checks do not prove authenticated provider delivery or deployed recovery.

This increment supplies persistent single-worker context/checkpoints and guarded
manual exports. Authenticated shared hosting, Sites storage integration, queue
leases, global cancellation/worker interruption, automatic retry/failover, connection credentials and live
dispatch are unfinished. No service is installed or deployed. Trading Bots stays
research/backtesting/paper only; RoboParty stays deferred. Owner release gates
and the full business portfolio remain in place.
