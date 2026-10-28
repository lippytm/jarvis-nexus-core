# Hermes Fabric MemPalace: local handoff context, versions 1, 2 and 3

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

## Stored configuration integrity

The shared handoff read path validates the registered swarm through the existing
strict configuration validator, checks its saved identity/digest, and verifies
the handoff's manifest/source revision, assistant, project and target. Reviews,
exports, imported returns and context operations therefore reject inconsistent
stored scope before changing state. Backups reuse these checks rather than
maintaining a separate scope validator. Shared reads also require the stored handoff's exact version-1
kind, manual_export_only mode and integer zero external_actions, even when a
damaged record has a recalculated digest. Boolean substitutes are rejected.
These fixed contract checks do not change valid older records or install an
executor. These are integrity checks, not authentication, an adversarial-file
security boundary or proof of approval. Retain the damaged source for investigation instead of editing
raw records to bypass rejection. These read checks perform no automatic repair.

## Writes, reviews and retrieval

The CLI requires an existing database file for status, recovery, review and
context operations. A missing or mistyped path fails instead of creating an
empty ledger and reporting no pending work. Stage may initialize a new
ledger from valid draft/manifest packets. Alternatively, init-ledger explicitly
creates a checked empty version-2 ledger through atomic no-overwrite publication;
it refuses existing ledgers/files, including when another writer wins publication.
It does not alter packet schemas or establish authenticated storage.
An existing valid empty ledger can
still report an empty queue. This path check is not file-access authentication
or protection against concurrent filesystem replacement; retain backups and
control access before use.

For an optional audit, place --read-only before the command (for example,
python scripts/jarvis_network.py --root /data --database handoffs.sqlite3 --read-only status).
It uses SQLite mode=ro, skips schema setup/migration and uses read transactions.
Only inspection and backup commands are accepted; export, review, initialization
and other ledger writes are refused. Inspection may still save a requested
private output file. An existing version-2 or version-3 ledger is required; retain a backup
and use the normal writable path separately for a version-1 migration. Defaults
and valid old records are unchanged. This protects against database writes
through this connection, not concurrent writers, filesystem replacement or
unauthorized readers. SQLite WAL/shared-memory sidecars may require filesystem
access; read-only mode is not immutable-file mode and must not ignore WAL data.

Status reads handoff metadata, validates stored bindings and counts swarms/returns
inside one transaction. In read-only WAL inspection, a return committed by another
connection during the read appears in the next report, not mixed with an older
handoff state in the current report. Normal writable mode uses the existing
BEGIN IMMEDIATE serialization. Validation failure rolls the snapshot back.
The result is a point-in-time observation, not a lease, dispatch grant or proof
that imported returns are authenticated or completed work.

## Private project queue report

Use `python scripts/jarvis_network.py --root /data --database handoffs.sqlite3 --read-only queue-report --project ai-jarvis`
to summarize one existing project's recorded handoff, execution and control states
from a single transaction. Version-1 jarvis.queue_report is a separate report;
it changes no existing packet or database schema. Contextless records are counted
explicitly, not treated as ready or successful. Source, asset, platform and available
mission/memory/destination identities plus exact context/handoff digests bind the
selected metadata. Draft text, execution detail and reference URLs are omitted.
The report is always owner_private and changes no holds, reviews or attempts.

recorded_attempts sums current context attempt counters. It does not measure
actual worker runs, retries or failures; contexts are proposed records. Duplicate
attempts are marked not_recorded, and completion_verification is not_established:
an imported unverified return is not verified mission completion. Report checksums
bind this metadata observation, not full review/lineage eligibility or authentication.
The report grants no dispatch authority and is not a lease or public export.

## Opt-in retained context checkpoints

The local API checkpoint_context(handoff_id, expected_sha256=..., expected_source_revision=...,
expected_memory_revision=...) retains the exact current context before a later edit.
Its first successful call explicitly upgrades SQLite user_version from 2 to 3 and
adds context_checkpoints in the same ledger. Existing tables/records and strict
packet schemas are unchanged. No history is invented for revisions already lost.
Stop older clients before opting in. New/default ledgers remain version 2 until capture is used;
there is no automatic capture worker. Retain a checked version-2 backup before
opting in. Older code rejects version 3; rollback needs the matching old backup,
not a lowered pragma or deleted table. Never overwrite an active ledger.

Capture requires exact context/source/memory revisions, refuses read-only handles,
deduplicates by handoff and context revision, and permits at most 1,000 retained
contexts per ledger. Rejection rolls back the schema upgrade and insert together.
Capture does not alter current context, reviews, attempts or execution/control state.
Historical profiles retain their original profile schema and provenance.

load_checkpoint(handoff_id, revision, expected_sha256=..., expected_source_revision=...,
expected_memory_revision=...) retrieves an independent, always owner-private copy
with historical_context_only_not_approval authority and retry_authorized=false.
It does not restore historical approvals or rewind current holds. Ordinary saves
still reject cancellation reversal, unknown-outcome clearing and memory regression.
This is selective local history, not authenticated shared storage or automatic
recovery. Checkpoint tables remain writable by someone controlling the database;
hashes are integrity checks, not an adversarial-file boundary or authenticated authorship.
Checked backups support SQLite versions 2 and 3, validate every retained profile
and preserve history on restoration. Corrupt checkpoints prevent publication.

For an existing staged handoff/context, the operator CLI exposes these same APIs:

```sh
python scripts/jarvis_network.py --root YOUR-PRIVATE-ROOT --database ledger.sqlite3 capture-checkpoint --allow-schema-upgrade --handoff YOUR-HANDOFF-ID --digest YOUR-CONTEXT-SHA256 --source-revision YOUR-40-CHAR-SOURCE-SHA --memory-revision 1
python scripts/jarvis_network.py --root YOUR-PRIVATE-ROOT --database ledger.sqlite3 load-checkpoint --handoff YOUR-HANDOFF-ID --checkpoint-revision 1 --digest YOUR-CAPTURED-CONTEXT-SHA256 --source-revision YOUR-CAPTURED-40-CHAR-SOURCE-SHA --memory-revision 1 --out private/history-001.json
```

Replace placeholders with values from the actual saved context/capture receipt.
capture-checkpoint requires --allow-schema-upgrade on every call, including duplicate
captures; this explicit local opt-in is not identity authentication or release approval.
It requires an existing ledger and prints a metadata receipt with checkpoint_revision,
context_sha256 and duplicate. An exact replay at the unchanged current revision is
deduplicated. It cannot capture already-replaced context. --read-only rejects capture.
load-checkpoint always opens the database read-only, even without --read-only. Its
checkpoint revision, digest, source and memory revision select the retained historical
record, which may differ from current context. It writes a new owner-private JSON file
inside --root and refuses existing outputs, path escapes, missing ledgers and mismatches.
Neither command dispatches work, retries a mission, accepts facts or restores approvals.

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

There is no reconciliation resolution/release operation in this increment. A future explicit
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

## Proposed reconciliation evidence

For an outcome_unknown record with at least one saved evidence reference,
prepare-reconciliation emits a separate jarvis.reconciliation_proposal. Version-1
and version-2 contexts retain the original version-1 proposal shape. Version-3
contexts produce an explicit version-2 proposal with the exact destination_id;
no field is silently added to the version-1 proposal. A consumer supporting only
version 1 must reject version 2, not discard the destination or guess a resource.
It requires the exact current context digest, source/memory revisions and saved
inspection digest; context, local review, ancestor or return changes can invalidate
that inspection. It retains mission/project/asset/platform identities, scoped
configuration/actions/budget, execution checkpoint, control state and selected
evidence references from the existing context. Context and inspection digests
bind the remaining source records; draft text and unrelated context references
are omitted. The proposal has its own checksum, covering destination_id when
present, and is always owner_private. A destination is a scoped opaque label;
the trusted collector still needs to check its actual resource mapping. No new
authentication, destination verification or hold-release authority is implied.

```sh
python scripts/jarvis_network.py --root /data --database handoffs.sqlite3 prepare-reconciliation --handoff YOUR-HANDOFF-ID --inspection-digest YOUR-INSPECTION-SHA256 --digest YOUR-CONTEXT-SHA256 --source-revision YOUR-40-CHAR-SOURCE-SHA --memory-revision 1 --out reconciliation-proposal-001.json
```

Replace placeholders using fresh load-context/inspect-recovery results after
saving the selected evidence references. The output uses proposed_unverified,
evidence_verification=not_established and proposed_resolution=retain_hold.
References are supplied observations, not verified destination facts. This command
does not fetch URLs, record approval, increment attempts, dispatch work, resolve
an outcome or clear any hold. It sends nothing and refuses existing output files.
It is a point-in-time proposal, not a lease; future authenticated resolution must
recheck current context/inspection and owner authority atomically with its write.
Keep the proposal private and verify actual destination evidence independently.
No import/approval/release operation for proposals is implemented.

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
this envelope opt-in alone; SQLite user_version remains 2 unless checkpoints are explicitly captured.

## Version-3 destination binding

Version 3 retains all version-2 fields and adds one required opaque destination_id,
for example repository-one or channel-one. This identifies an intended resource
within the existing project/platform scope; it is not a URL, credential, verified
account identity or authenticated connection. Use a bounded identifier and retain
the owner's mapping to the actual resource in authorized evidence. All seventeen
portable platforms remain supported and distinct, including codex.

Create the version-3 context, or explicitly upgrade an older context, while the
original handoff is still pending_review. Binding after original review/export is
rejected; do not retroactively label previously exported work. Once bound, the
destination cannot change or be removed, and schema downgrade is rejected. For
a genuinely different destination use a separately scoped, reviewed mission;
never allocate another identity to evade an existing hold or deduplication.

Use the existing save-context/load-context/review-context/export-context commands.
For version 3, export-context is required: the legacy export command rejects even
a fully reviewed record because its version-1 packet cannot retain destination
metadata. Rejection leaves the handoff state unchanged. Use the private context
envelope rather than stripping its destination binding; original handoff packets
remain unchanged. Version-1/2 legacy export compatibility is preserved.
Both export paths enforce version-3 pause/cancel, unknown-outcome and fresh-review
guards. Compatible private envelopes retain the full version-3 context while the
strict version-1 handoff remains unchanged. Inspection digests bind the
destination through its context digest; retrieve the matching context to inspect
the resource ID. Version-2 reconciliation proposals also retain destination_id
explicitly so a reviewer can see its exact scope. Existing version-1/2 profiles remain valid and reject a silently
added destination_id. Destination binding alone does not migrate tables; SQLite
user_version remains 2 unless retained checkpoints are explicitly captured.
Backups retain destination identity and controls. Older application versions reject
version-3 context; do not roll them back against these records.

This is immutable local destination metadata, not a complete connection registry,
authenticated adapter, destination-specific return protocol or live dispatch.
Legacy manual exports and unverified returns still bind only the original target
and handoff digest. An authenticated worker must enforce the exact resource and
owner release gate before external delivery; version-3 labels alone grant nothing.

## Destination-scoped discovery

Use destination-status to find existing version-3 records without knowing their
handoff IDs. Project, platform and destination must all match exactly:

```sh
python scripts/jarvis_network.py --root /data --database handoffs.sqlite3 destination-status --project ai-jarvis --platform codex --destination repository-one
```

Replace repository-one with the intended opaque resource ID. The existing ledger
is required; a missing file is rejected rather than silently creating an empty
registry. The private report contains matching mission/asset IDs, source/memory
and context revisions/digests, local review and execution/control state. It omits
draft text, execution detail, evidence/context URLs and unrelated records.
Version-1/2 records are not assigned an inferred destination and remain available
through the existing status/load commands. Invalid stored context stops the query.

This read-only view changes no records or holds. Use its exact revisions for a
subsequent load-context and fresh inspection; it is not a lease or dispatch
eligibility check. Dispatch authorization is always false. A matching record,
including a locally reviewed one, proves neither an authenticated connection nor
current provider availability. This local command supplies no access-control
service; future hosted adapters must authenticate and authorize project/resource
access. Do not expose the report publicly.

## Destination-bound read observations

bind-observation wraps the existing strict connector read-observation format in
a separate version-1 jarvis.destination_observation receipt. Supply an existing
version-3 context and its exact digest/source/memory revisions. Provider and source
revision must match that context. Observation structure, checksum and timestamp
use the existing connector validator; stale observations retain unverified status
and future observations are rejected. Original observation and packet fields are
unchanged. The receipt includes destination/mission identity, context revision and
digest, original read metadata and a separate receipt checksum, always private.

```sh
python scripts/jarvis_network.py --root /data --database handoffs.sqlite3 bind-observation --handoff YOUR-HANDOFF-ID --file read-observation.json --digest YOUR-CONTEXT-SHA256 --source-revision YOUR-40-CHAR-SOURCE-SHA --memory-revision 1 --out destination-read-001.json
```

The collector must obtain and retain the real response independently, compute its
SHA-256 over those exact bytes, and verify that its resource matches the intended
opaque destination. This command does not fetch URLs or prove that a supplied
hash, URL, scope label or destination mapping is authentic. It omits context text,
reference lists and execution detail, changes no ledger state or holds, sends
nothing and refuses existing output files. The source observation remains data;
no authenticated registry or live adapter is installed. Runtime availability stays
unknown and dispatch authorization stays false, even after a real successful read.
Check current revisions again before later decisions; the receipt is not a lease,
write authorization or authenticated delivery/mission-completion receipt.

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
