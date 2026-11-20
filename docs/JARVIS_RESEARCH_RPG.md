# Jarvis Research Questbook

The Research Questbook is a self-contained offline R&D planning tool with an
original celestial interface. It helps Charles apply an inquiry, evidence and
review routine across the twelve Jarvis initiatives. It is an anime/RPG-inspired
planning companion, not a 3D game, autonomous researcher or live account dashboard.

Open `web/jarvis-research-rpg.html` in a browser with JavaScript enabled. The
page uses inline CSS, JavaScript and an embedded copy of the actual portfolio
catalog. It requires no installation, model key, account or external asset.
Current product facts and live documentary research belong in the accompanying
research report. The page supplies authored prompts, with no invented prices,
product capabilities, current-event findings or completed business outcomes.

## A useful session

1. Choose one **Jarvis initiative** and **research path**.
2. Open **Inquiry**. Write the question or decision you want to make.
3. Add an evidence note when you have a claim, source, question or fictional idea
   worth preserving. Label it before drawing a conclusion.
4. Open **Evidence** and **Review** to challenge assumptions and identify a
   useful next artifact. Marking a prompt explored is optional and reversible.
5. Keep the default owner/private classification unless you deliberately intend
   a different audience. Download the JSON draft or copy a plain-text brief.
6. On another visit, import that JSON to resume.

Each saved questbook has one initiative, one research path, one shared objective
and up to eight evidence notes. Changing either context selector retains the
objective, notes and audience classification, while resetting exploration to the
Inquiry prompt. The interface explains this next to the selectors. Review
retained notes before exporting under a different context.

The objective and ordinary notes may remain blank, so unfinished drafts can be
saved. Invalid or oversized text stays in the editing buffer while export is
disabled. Removing a row is immediate; download a checkpoint first if you may
want it later. There is no autosave, undo history or persistent app storage.

## Three research paths

| Path | Inquiry | Evidence | Review |
| --- | --- | --- | --- |
| General creative build | Identify a need, bounded question and observation that could change the plan. | Find a reproducible example or primary reference, plus an assumption or counterexample. | Propose a small artifact, acceptance check and human review. |
| Smart-glasses procurement | Define the wearing experience, essential requirements and owner-set budget. | Check exact models, regional support, compatibility, independent observations and current return terms. | Make a provisional shortlist, trial plan or decision to wait or buy nothing. |
| Documentary claims | Attribute one Greer-related or alleged false-flag claim and state what would support or contradict it. | Trace original material, preserve context and seek independent corroboration, contrary evidence and alternatives. | Write the strongest supported conclusion with uncertainty, or a clearly labelled fictional adaptation. |

Every path has exactly three prompt IDs: `inquiry`, `evidence` and `review`.
Exploration markers record use of those prompts. They do not measure truth,
reward agreement, verify a source, complete a project, approve a purchase or
authorize publication. Imported markers are bookmarks from the saved questbook;
they are not newly observed work.

The documentary path does not start with a conclusion. An unsubstantiated claim
remains unsubstantiated, and fictional adaptations retain their labels.
Repetition of a statement is not treated as independent confirmation. The
procurement path supplies decision questions, not buying recommendations.
Record source dates and exact models in notes, and consult the separate current
research report before a real procurement decision. The page cannot purchase,
connect to or operate a device.

## Portfolio and evidence boundaries

The embedded catalog exactly matches
`control_tower.portfolio.portfolio_catalog()` and the tracked
`examples/portfolio/catalog.json`: twelve initiatives mapped to seven projects.
Tests detect drift. The selected initiative shows its summary, intended outcome,
boundaries and destination classification.

The education site, AI Evolutionary Evolutions, remains separate from the
affiliate platform whose destination is unassigned. Business-financing customers
remain separate from referral-partner recruitment. Destinations are owner
references or planning assignments, not evidence of working accounts,
transactions, forms or integrations.

| Stored evidence label | Meaning |
| --- | --- |
| `attributed_claim` | A statement attributed to a person or source, not automatically established evidence. |
| `vetted_source` | The author's assessment, requiring a nonblank check note and HTTPS reference. |
| `open_question` | Something still unknown, with room to describe evidence needed to answer it. |
| `fictional` | Invented material or an explicitly fictional adaptation. |

The visible vetted-source label says **“Vetted source — your assessment.”** The
app checks for a note and URL; it does not establish sufficient vetting,
authenticity or support for a conclusion. Copied briefs repeat that labels are
author supplied, not app verification.

References remain editable text: the application does not fetch them or create
automatic external links. A reference is optional except for vetted-source
notes. If supplied, it must be HTTPS, at most 1,000 UTF-8 bytes, without
credentials, whitespace, C0 controls, backslashes or a custom port. The default
HTTPS port 443 is allowed. Accepted URL text is preserved.

## Audience and visibility

New drafts use `audience: "owner"` and `source_visibility: "private"`. The
edition banner, JSON export and copied brief retain both fields.

| Audience | Allowed source visibility |
| --- | --- |
| `owner` | `private`, `internal` or `public_candidate` |
| `public` | `public_candidate` only |

A public audience with private/internal visibility disables export and explains
the mismatch. The page does not silently change the classification. A valid
import restores its own audience and visibility rather than substituting defaults.

**Classification is not encryption, authentication or publication permission.**
The page cannot detect every secret or personal detail in notes or URLs. Review
the complete file before deliberately selecting public candidate visibility.
The download remains a local draft; there are no sending or publication controls.

## Export and resume contract

The download is `jarvis-research-questbook.json` with exactly twelve top-level keys:

```json
{
  "schema_version": 1,
  "kind": "jarvis.research_questbook",
  "scope": "visit_only_exploration",
  "initiative_id": "jarvis-tools",
  "campaign_id": "general-creative-build",
  "audience": "owner",
  "source_visibility": "private",
  "objective": "",
  "selected_quest": "inquiry",
  "visited_quests": ["inquiry"],
  "explored_quests": [],
  "evidence_notes": []
}
```

Campaign IDs are `general-creative-build`, `smart-glasses-procurement` and
`documentary-claims-research`. Initiative IDs come from the embedded portfolio.
Unknown selector values and extra fields reject. Exploration lists contain
unique known quest IDs; the selected quest must have been opened, and explored
quests must be a subset of opened quests.

Each of zero to eight evidence notes has exactly four keys:

```json
{
  "note_id": "note-1",
  "label": "open_question",
  "text": "",
  "url": ""
}
```

Note IDs are unique, 2–48 characters, matching
`[a-z][a-z0-9_.-]{1,47}` in full. The interface generates them locally. The
objective permits 2,000 UTF-8 bytes; each note's text permits 1,500 bytes. Blank
text is allowed except for vetted-source check notes. All text must use valid
Unicode scalar sequences. Lone surrogates and C0 controls other than tab, line
feed and carriage return reject. The nonblank check recognizes Unicode whitespace
including U+0085; U+FEFF remains ordinary text.

The complete raw import and formatted export are limited to 64 KiB of UTF-8.
Import checks UTF-8, JSON syntax, duplicate decoded keys, nesting depth, exact
shapes, types, lengths, classifications and cross-field consistency. Raw schema
tokens such as `1.0` and `1e0` reject; the schema token must be integer one.
Nested duplicate fields and escaped aliases of a field also reject.

A successful import deliberately replaces the current draft. An invalid import
preserves the exact current draft object. The asynchronous read uses both an
import ticket and an editing revision: a newer selection or an intervening draft
edit prevents an older read from overwriting the current draft. No export or
external action follows automatically.

This is a standalone browser draft contract. It is not an episode, diary entry,
mission request, authenticated ledger record or publication approval. Existing
Python episode contracts are unchanged, and no claim is made that they validate
this new kind.

## Optional artwork packaging

The source works immediately with original CSS artwork. It has exactly one
optional empty hook:

```html
<img id="questbook-art" data-jarvis-inline-art="" alt="" hidden>
```

A local packager may fill it with a base64 data URI using `image/png`,
`image/jpeg` or `image/webp`. The app assigns an accepted URI to the native
`src` property and hides the CSS fallback. HTTP URLs, SVG data and other
content types reject. Shape checking does not establish image decoding or
authenticity. Decorative artwork is hidden from assistive technology, and the
narrow-screen layout does not depend on it. No image-generation request or
additional asset is required.

## Verification and limits

Run from the repository root:

```bash
node tests/test_research_rpg.mjs
node --test --test-reporter=tap tests/test_research_rpg.mjs
```

The tests extract the actual shipped helper into an isolated Node VM and
syntax-compile both scripts. They do not execute imported JSON, notes or catalog
text as code. The authored suite passed **29 cases**, including 36 actual
initiative/campaign export-and-resume roundtrips, catalog/digest parity,
classification, note edits after navigation, byte bounds, duplicate keys,
invalid-import preservation, stale-read guards, literal script markup and safe
DOM source paths.

A static HTML check found 54 unique IDs, 24 resolved label/ARIA references, four
explicitly typed static buttons, three inline scripts, balanced tags and one
empty art hook. The embedded value matches the Python portfolio catalog. Existing
composer, portfolio, diary and story-RPG pages remain unchanged.

Native selectors, buttons, file input, progress and text controls have labels,
focus styling and status regions. Objective and note textareas request English
native spellcheck, whose behavior depends on browser dictionaries/settings and
may use the browser's own service. Calm mode starts enabled; CSS also honors the
reduced-motion preference.

No usable local Chromium, Chrome or Firefox executable was available. The
previous dedicated Playwright cache contained only metadata and no browser
binary. No installation retry or signed-in browser fallback was attempted.
Native rendering, keyboard/focus behavior, screen-reader interaction, spellcheck,
clipboard, downloads and file-chooser behavior remain unverified. Logic and
source checks do not establish those browser behaviors.
