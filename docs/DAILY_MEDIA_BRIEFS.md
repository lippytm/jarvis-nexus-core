# Daily media assignments

`control_tower.campaigns.daily_campaign_briefs` compiles an existing validated
mission into four distinct editorial assignments on each of Facebook, LinkedIn,
YouTube, Instagram, Threads and Substack. It retains the existing channel briefs
and their exact audience, objective, destination, disclosure and evidence limits.
Each assignment binds to its included source brief by SHA-256. Transfer the
complete packet with those source briefs; an assignment alone lacks that context.

The four angles are explanation, demonstration, limitations and a bounded next
step. Channel-specific production choices include a captioned illustration,
slide explainer, video storyboard, carousel, text discussion and Substack Note.
Durations, word counts and frame counts are proposed creative choices, not
verified platform upload requirements. These are media specifications requiring
copywriting, asset creation and review, not 24 completed posts or finished videos.

The new explicit `jarvis.daily_campaign_briefs` kind leaves existing mission,
campaign and strict version-1 draft contracts unchanged. Its editorial date is
an exact ISO calendar date, not a publication time, schedule or dispatch lease.
Review remains pending, publication_schedule and actual_metrics remain null,
and model_calls/external_actions remain zero. Account access, private storage
authentication, owner release and publication remain separate requirements.
The complete compact packet must fit the existing bounded JSON loader.

## Local command-line workflow

Use a previously saved validated mission, an explicit editorial date and fresh
output paths under the chosen root:

```bash
python scripts/jarvis_portfolio.py --root /your/workspace daily-campaign --mission-file mission.json --editorial-date 2026-10-29 --out daily.json
python scripts/jarvis_portfolio.py --root /your/workspace export-daily-assignment --mission-file mission.json --editorial-date 2026-10-29 --channel youtube --slot 2 --campaign-digest YOUR_DAILY_BRIEFS_SHA256 --out selected.json
```

Read `briefs_sha256` from `daily.json` and supply that exact value in the second
command. If using `--destination-index`, use the same explicit choice in both
commands. A changed date, source mission or destination invalidates the digest.
Existing files cannot be overwritten. The selector saves a draft only; neither
command stages a queue item, grants review, schedules work, connects an account
or publishes anything. The existing portfolio commands keep their behavior.

The saved [24-assignment example](../examples/portfolio/jarvis-daily-media-20261029.json)
uses source revision `3f1b4e5697e9ed74430214563008a6c8dea093fd`, the exact `codex`
engineering target and the existing `jarvis-tools` initiative. It does not claim
new integrations or runtime availability. Its mission can be reproduced with:

```python
from control_tower.missions import compile_mission
from control_tower.campaigns import daily_campaign_briefs

mission = compile_mission({
    "schema_version": 1, "kind": "jarvis.mission_request",
    "initiative_id": "jarvis-tools", "target": "codex",
    "objective": "Explain how a source revision, an exact-content review and an actual test receipt support a bounded Jarvis engineering task. Distinguish development evidence from deployed services.",
    "timebox_minutes": 30,
}, mission_id="jarvis-media-20261029",
   source_revision="3f1b4e5697e9ed74430214563008a6c8dea093fd")
packet = daily_campaign_briefs(mission, editorial_date="2026-10-29")
```

This API prepares one packet at a time. It does not reserve a mission ID in a
durable queue, detect already published content, create agents, start a worker,
or change any newsletter schedule. Use the existing ledger's exact-content
review flow and an authenticated adapter before any future external action.

## Select one source-complete assignment

`daily_assignment_draft` rebuilds the campaign from its validated mission and
requires its exact digest before selecting one channel/slot. It returns an
unchanged strict version-1 draft shape whose text includes the assignment, date,
campaign digest and complete source brief (audience, objective, destination,
disclosures and evidence limits). This avoids transferring an assignment without
the context it references. The returned draft still requires exact-content review.

```python
from control_tower.campaigns import daily_assignment_draft

draft = daily_assignment_draft(
    mission, editorial_date="2026-10-29", channel="youtube", slot=2,
    expected_campaign_sha256=packet["briefs_sha256"],
)
```

The selector does not authenticate the source or reviewer, persist a queue item,
or dispatch anything. A changed date, mission or destination choice must be
recompiled and selected with its new digest. To retain the draft, explicitly stage
it in the existing HandoffLedger with a scoped swarm/assistant/handoff identity;
that ledger preserves its original review, duplicate and restart controls.
Context envelopes and per-destination holds remain necessary wherever applicable.

The saved [YouTube slot-2 draft](../examples/portfolio/jarvis-daily-youtube-slot2.draft.json)
was selected from the exact 24-assignment example above. It targets `codex` for
preparation, includes its source brief and has not been staged in an operational
ledger, reviewed by the owner, sent to a provider or turned into a finished video.

The portfolio CLI writer flushes file contents before publishing a fresh name
without overwrite; on POSIX it also flushes the containing directory before
reporting success. A directory-sync error returns failure while retaining the
complete file. Inspect that artifact before retrying: an existing output still
cannot be overwritten. Temporary files are cleaned up. These checks do not test
physical power-loss recovery or guarantee durability of newly created ancestor
directories; non-POSIX behavior retains the existing file flush and no-overwrite.

The selected assignment now has an [unpublished script and shot plan](media/jarvis-youtube-slot2-20261029.md),
proposed captions and an original SVG storyboard. These are review artifacts;
narration recording, final caption timing, video rendering and release remain unfinished.
