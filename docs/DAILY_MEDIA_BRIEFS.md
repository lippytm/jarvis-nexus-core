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
