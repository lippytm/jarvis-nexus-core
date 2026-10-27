# Jarvis Docker development path

This image packages the existing Python handoff ledger and offline CLI.
It is a one-shot tool, not a deployed API, always-on Codex server or automatic
recovery worker. No social/provider credentials, Docker socket, host directory,
network interface or published port is configured by Compose.

## Run on an authorized Docker host

From this branch with Docker Engine and Compose available:

```sh
docker compose build
docker compose run --rm jarvis
docker compose run --rm jarvis python -m unittest discover -s tests -p test_handoff_context.py -v
```

The first run displays ledger metadata and initializes a version-2 database in
the named jarvis-ledger volume. It does not start a worker. Repeating the command
uses the same ledger. Image builds need registry access; runtime Compose calls
use network_mode: none. The non-root UID/GID is 10001, the root filesystem is
read-only, /tmp is temporary and /data holds persistent local state.

To run another existing CLI operation, replace the command explicitly:

```sh
docker compose run --rm jarvis python scripts/jarvis_network.py --root /data --database handoffs.sqlite3 status
```

The context API from HANDOFF_CONTEXT_PROFILE.md is also available through
save-context and load-context. Given an existing staged handoff and a bounded,
matching context JSON already placed in /data by the authorized local operator:

```sh
docker compose run --rm jarvis python scripts/jarvis_network.py --root /data --database handoffs.sqlite3 save-context --file context.json --expected-revision 0
docker compose run --rm jarvis python scripts/jarvis_network.py --root /data --database handoffs.sqlite3 load-context --handoff YOUR-HANDOFF-ID --source-revision YOUR-40-CHAR-SOURCE-SHA --memory-revision 1 --out recovered-context-001.json
```

Replace the placeholders with the original handoff's exact values. The first
write expects context revision 0; subsequent writes require the current revision
returned by save/load. Identical saves at that current revision are duplicates.
A load writes a new owner-private JSON file and refuses existing outputs, stale
source or memory revisions. Exported context remains proposed or locally reviewed;
these commands do not authenticate users, approve releases, dispatch work or
expose a public endpoint. Protect /data and the exported files. Running status
does not perform a mission or save context.

## Verification

The Docker CI job builds this Dockerfile, validates Compose, runs all 18 local
context tests inside a restricted container, stages a synthetic Codex handoff
on a named volume, then reads it in a second container after the first is removed.
It checks the exact handoff digest and SQLite schema version. Existing Python
and Node jobs remain separate. CI is runner evidence, not proof Docker is
installed on the owner's device or that this ChatGPT runtime recovered.

The image intentionally contains no Node runtime: the full web suite runs in
its existing CI job. The base image tag is mutable; the build logs record the
resolved image. Pin an approved digest and complete image/dependency review
before a reproducible release. No image is pushed to a registry by this setup.

## Data, rollback and boundaries

Keep the named volume when replacing or removing a container. Do not run
docker compose down -v on valuable state. A volume is persistence, not a backup.
Use SQLite Connection.backup while access is controlled, and verify restoration
before relying on it. Follow the v1-to-v2 rollback procedure in
HANDOFF_CONTEXT_PROFILE.md; reverting only the image does not revert a database.

Start with one operator. This setup does not supply authentication, encrypted
backups, shared multi-user hosting, Sites deployment, leases, timed retries or
automatic failover. Container restart cannot establish whether an uncertain
external action succeeded. Blocked/unknown outcomes stay recorded until reviewed.
Do not mount credentials or private diary exports into a build context. A hosting
destination and owner release approval are required before deployment.
Trading remains research/backtesting/paper only; RoboParty remains deferred.
