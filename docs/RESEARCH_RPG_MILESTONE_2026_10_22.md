# Jarvis Research RPG — offline questbook milestone

The [Research Questbook](../web/jarvis-research-rpg.html) adds a reusable inquiry,
evidence and review routine across **12 Jarvis initiatives and three campaigns**:
general creative building, smart-glasses procurement research and documentary
claims research. It is an offline R&D tool with an original celestial interface,
not a 3D game, live research service or completed documentary.

These are local working-tree results based on tested parent
`de12358af2a5687ad220881f8117a26b4d34cbc6`, with the changed source identified by
SHA-256 below. This record does not claim CI for a new commit, a merge, deployment,
hardware trial or account connection.

## What works locally

The page embeds the exact authored portfolio catalog: twelve initiatives mapped
to seven projects. Its context panel preserves the separate education site and
unassigned affiliate platform, and the distinction between financing customers
and referral partners. No destination is presented as a verified integration.

Each campaign supplies three prompts: **Inquiry, Evidence and Review**. The
procurement path asks for requirements, primary specifications, limitations and
a justified shortlist or no-purchase decision. The documentary path treats
Greer-related statements and alleged false-flag narratives as attributed claims,
asks for corroboration and contrary evidence, and retains uncertainty and
fictional labels. It does not reward agreement with a predetermined conclusion.
Current facts and live research belong in the separate research report.

Users can edit one objective and up to eight evidence notes, attach optional
HTTPS references, switch prompts, mark exploration, copy a brief, download JSON
and import that JSON to resume. Context changes preserve text and classification
while resetting exploration. Notes remain editable after these transitions.
There is no autosave, background synchronization, external fetch or account action.
One optional bitmap data-URI hook supports locally packaged artwork; the original
CSS design works without it.

## Classification and contract

The exact twelve-key `jarvis.research_questbook` contract contains:

```text
schema_version, kind, scope, initiative_id, campaign_id,
audience, source_visibility, objective, selected_quest,
visited_quests, explored_quests, evidence_notes
```

The version is integer `1` and the scope is `visit_only_exploration`. Each note
contains exactly `note_id`, `label`, `text` and `url`. Labels distinguish
`attributed_claim`, `vetted_source`, `open_question` and `fictional`. A vetted-source
note needs a nonblank account of the author's check and an HTTPS reference; it
remains the author's assessment, not app verification.

New books default to **owner/private**. Owner editions may retain private,
internal or public-candidate source visibility. Public editions require explicit
public-candidate visibility; mismatched selections block export. JSON and copied
briefs preserve both fields. Classification neither encrypts a file nor grants
publication permission.

Imports and formatted exports are limited to 64 KiB. Validation rejects malformed
Unicode, disallowed controls, duplicate decoded keys, unexpected fields,
unknown selectors and inconsistent exploration/classification. Objective text
allows 2,000 UTF-8 bytes; each note allows 1,500 text bytes and a reference of up
to 1,000 bytes. Invalid imports preserve the exact prior draft. Import tickets
and edit revisions also reject stale reads after intervening edits.

The [usage and contract guide](JARVIS_RESEARCH_RPG.md) records the complete rules.
This new browser format does not modify existing Python diary or episode
contracts and does not claim to be an authenticated ledger entry.

## Actual verification

| Check | Result and scope |
| --- | --- |
| Python syntax | **57 files**, zero syntax errors |
| Python suite | **273 passed**, zero failures, errors or skips |
| All authored Node cases | **179**: 34 composer + 34 portfolio + 48 diary + 7 media-player + 27 RPG + 29 research |
| Whole Node invocation | **Six test-file wrappers passed** in the runtime's TAP output; this is distinct from the authored case total |
| Research helper suite | **29 passed**, including **36 initiative × campaign export/resume roundtrips** |
| HTML structure | 54 unique IDs, 24 resolved static label/ARIA references, four typed static buttons, three inline scripts, one empty art hook, balanced tags |
| Catalog identity | Embedded JSON equals the tracked catalog and actual Python `portfolio_catalog()` |
| Existing pages | Composer, portfolio, diary and story-RPG source remain unchanged |

Commands used for the local verification entry points:

```bash
python3 scripts/verify_control_tower.py
node --test --test-reporter=tap tests/*.mjs
node tests/test_research_rpg.mjs
```

The [verification record](evidence/research-rpg-verification.json) retains the
counts, hashes and provenance of the existing local logs. The six-wrapper output
does not itself print 179 individual cases: that total is the exact sum of the
authored cases in the six passing files. The new research file was also executed
directly, exposing all 29 passing cases.

An independent AI reviewer reran those 29 cases and exercised the actual app
handlers in a minimal DOM stub. Retained note edits after state cloning,
public/private export gating, valid owner/private resume, invalid-classification
preservation, delayed imports after edits, rejection before reading an oversized
file and fatal UTF-8 rejection all passed. No concrete blocker remained in that
bounded review. The stub is not a native browser or an accessibility audit.

| Frozen source | SHA-256 |
| --- | --- |
| `web/jarvis-research-rpg.html` | `dd0528a35d2744e4838e4df39b6cc9ca0e73a5bd33cc1faccdc865eaa292c228` |
| `tests/test_research_rpg.mjs` | `ed55ff24f48f6eec27de99171d859c7f7d077b95f0457c74b52c8d01104f8ec6` |
| `docs/JARVIS_RESEARCH_RPG.md` | `fbbb62f35ea6663a04ca45879ddeebc59619b63d16419785390a5b88ffc10339` |

## Limits and next three priorities

No usable local browser binary was available; no installation retry or signed-in
session fallback occurred. Native rendering, keyboard/focus, screen-reader
interaction, spellcheck, clipboard, downloads and file selection remain
unverified. No AR hardware was tested or purchased. No live Hostinger/provider
connection was established, and no Greer documentary/movie was produced.
Exploration markers do not establish business completion, revenue or truth.

These next steps align with the R&D report and extend the
[earlier engineering priorities](ANIME_RPG_MILESTONE_2026_10_22.md) of a bounded
building cycle, complete watch experience and evidenced connection:

1. **One shared evidence record across diary, research and scenes.** Define a
   reviewed mapping that keeps source identity, attribution, uncertainty,
   classification and edition changes attached as material moves between the
   existing formats. Build a small explicit adapter with tests; do not silently
   treat the questbook's author-assigned label as verified evidence.
2. **One tested Lens Studio AI-building cycle and observed device trial.**
   Select one original, bounded AR interaction, retain the actual tool/model
   return and independent checks, then exercise it on a compatible device when
   one is available. Record observed usability and failures separately from
   simulator results or source checks. Validate the questbook's target browser
   too. No purchase, installed Lens Studio environment or successful trial is
   implied by this priority.
3. **One repeatable reviewed-record-to-draft route.** Carry a deliberately
   reviewed record through a script, captions, an actual playable episode and
   platform-specific drafts while retaining evidence and audience labels.
   Use the existing Hostinger runbook to identify one permitted read route and
   useful draft destination when access allows, keeping education and affiliate
   destinations separate. Success requires retained output and review evidence;
   a planned handoff does not establish a connection or publication.

The existing Studio Work Cycle remains paused. These priorities do not activate
provider missions, authorize publication or replace the owner's review.
