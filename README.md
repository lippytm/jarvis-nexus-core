# JARVIS NEXUS CORE — AI Builds AI

AI Jarvis Assistants Swarms Systems Networks — Intergalactic Corporate Services LLC

This development branch contains a Python Control Tower prototype for bounded
builder proposals, explicit connector observations, and synthetic membership and
funding-referral workflows. The current review target is [draft PR #5](https://github.com/lippytm/jarvis-nexus-core/pull/5).

The portfolio expansion adds a portable workbench with twelve initiatives across
seven work areas, a five-role mission compiler, seven-channel editorial briefs,
and a real read-only Hostinger transport. It builds on the spelling composer and
durable local handoff ledger. Assistant specifications and compiled missions are
inactive planning artifacts; they do not start external agents or publish content.

The daily diary expansion adds private-by-default capture, a versioned local
diary store, audience-filtered daily briefs, and a reusable multimedia compiler.
An explicitly selected public-candidate entry can become an EPUB, narration
script, documentary and trailer drafts, an original fictional film treatment,
a music-film draft, ad-copy candidates and an interactive teaching page. The
optional local renderer creates a text-card MP4 and a generic narration WAV.

## Keep a daily diary and develop a media edition

Open [Jarvis Daily Diary](web/jarvis-diary.html) locally. Record an observation,
its evidence classification, sources and one next action. Download the entry
before closing: browser draft memory lasts for the visit. Native browser
spellchecking can assist text entry; actual behavior depends on the browser.

The [diary workbench guide](docs/JARVIS_DIARY_WORKBENCH.md) explains capture and
import. The [media runbook](docs/DIARY_MEDIA_RUNBOOK.md) covers persistent local
history, daily briefs and media export. A public engineering example is supplied:

```bash
python scripts/jarvis_diary.py validate --entry-file examples/diary/public-project-entry.json
python scripts/jarvis_diary.py pack --entry-file examples/diary/public-project-entry.json --product first-diary-edition --source-revision e645c64975dc05f3b0a0f9e06d7cc903d70031b0 --out reports/first-diary-edition.zip
```

This example describes an earlier verified public commit. It contains no private
life record. The compiler uses local templates and synthesis, makes no external
model calls, and does not publish. [Milestone and verified scope](docs/DIARY_MULTIMEDIA_MILESTONE_2026_10_22.md).

## Choose a useful portfolio mission

Open [Jarvis Portfolio Workbench](web/jarvis-workbench.html) locally. Search or
filter the catalog, select an initiative, write one objective and choose a 15-,
30-, 60- or 90-minute planning window. Copy a planning brief or download a strict
mission request. Save a download before closing: draft memory lasts for the visit.

From the repository root, compile a supplied example:

```bash
python scripts/jarvis_portfolio.py plan --request examples/portfolio/jarvis-tools.request.json --mission first-tool-cycle --source-revision a67e743e8b32e552ccddd9e16a2108fe2f816274 --out reports/first-tool-cycle.mission.json
```

The source revision above is the example's previous-milestone context. Use the
actual source context for a new task. The compiler produces five role drafts,
acceptance checks, planned dependencies and a resume bookmark. It makes no model
calls. [Full usage, twelve initiatives and next priorities](docs/PORTFOLIO_EXPANSION_2026_10_22.md).

## Write and review a Jarvis draft

Open [Jarvis Composer](web/jarvis-composer.html) as a local HTML file in a browser.
It provides optional native browser spelling, explicitly selected corrections
for common typos, undo, copy, and text/JSON downloads. It requires no server,
build step or API key. It does not modify ChatGPT's native input box.

See the [composer guide and verification limits](docs/JARVIS_COMPOSER.md).
Browser rendering and native clipboard/spellcheck behavior still require a
target-browser check; the retained automated checks cover the authored logic
and HTML structure.

## Check the Hostinger read connection

The [Hostinger runbook](docs/HOSTINGER_CONNECTION_RUNBOOK.md) documents the fixed
read-only inventory endpoint, secure runtime configuration and explicit CLI. The
actual presence check for this milestone found no configured `HOSTINGER_API_TOKEN`;
no authenticated read was attempted. The site's product, account access and API
compatibility remain unverified. The secure output CLI currently requires POSIX;
the workbench and composer are separate browser files.

## Build portable assistant specifications

```bash
python scripts/jarvis_network.py catalog --out reports/provider-catalog.json
python scripts/jarvis_network.py demo --out reports/network-demo.json
```

These commands write new files and refuse to overwrite existing evidence. The
demo uses local synthetic packets. The [network milestone guide](docs/NETWORK_MILESTONE_2026_10_22.md)
documents factory, review, export, return-import and ledger commands, with
[seven generated project manifests](examples/network/project_index.json).

## Verify the Control Tower

From the repository root with Python 3.11 or later:

```bash
python scripts/verify_control_tower.py
```

The command checks source syntax, runs the offline unit tests and demonstration,
and saves a JSON evidence record plus a test log under `reports/`. It uses the
Python standard library and makes no model, payment, or deployment calls.

Test the authored composer, portfolio, diary and media-player helpers with Node
18 or later (CI uses Node 24):

```bash
node --test --test-reporter=tap tests/*.mjs
```

## Review the implementation

- [Daily diary and multimedia milestone](docs/DIARY_MULTIMEDIA_MILESTONE_2026_10_22.md)
- [Diary entry, revision history and privacy contract](docs/DIARY_DATA_CONTRACT.md)
- [Media production and local CLI runbook](docs/DIARY_MEDIA_RUNBOOK.md)
- [Creative product designs, viability and stage gates](docs/DIARY_PRODUCT_STUDIO.md)
- [Portfolio expansion and next three engineering priorities](docs/PORTFOLIO_EXPANSION_2026_10_22.md)
- [Workbench usage and browser verification limits](docs/JARVIS_WORKBENCH.md)
- [Portfolio verification: 163 Python tests and 43 syntax checks](docs/evidence/portfolio_expansion_2026_10_22.json)
- [Twelve synthetic planning missions](examples/portfolio/mission_index.json)
- [Hostinger read-only connection runbook](docs/HOSTINGER_CONNECTION_RUNBOOK.md)
- [Network milestone and next three engineering priorities](docs/NETWORK_MILESTONE_2026_10_22.md)
- [Provider routes, account requirements and Hostinger probe](docs/PROVIDER_CONNECTIONS_2026_10_22.md)
- [Network milestone verification](docs/evidence/network_milestone_2026_10_22.json)
- [Public repository metadata inventory](examples/network/public_repository_inventory.json)
- [Earlier October 22 engineering update](docs/ENGINEERING_UPDATE_2026_10_22.md)
- [Recovered v1.0 source reconciliation](docs/V10_RECONCILIATION.md)
- [Membership and referral website edit specification](docs/WEBSITE_CONVERSION_REVIEW.md)
- [Synthetic journey example](examples/membership_journey.json)
- [Recorded local verification](docs/evidence/control_tower_2026_10_22.json)
- [Seven management workflows](docs/SEVEN_WORKFLOWS_V05.md)

Generated tools remain draft source, and orchestration produces bounded proposals.
Synthetic payment events do not authenticate a payment provider. Connector
configuration and historical read observations do not establish current access,
write permission, deployment, revenue, or customer conversion.

## Existing service prototypes

The repository also contains the earlier JavaScript service and installer
prototypes. Their operation, hosting cost, production security and replacement
coverage for third-party products were outside this Control Tower verification.
Review those sources and their deployment assumptions before running the installer.
