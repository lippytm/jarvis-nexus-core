# Jarvis Life & Business Daily Diary

Open `web/jarvis-diary.html` in a current browser to write a local diary entry,
classify observations, record references and choose a next action. The page is a
self-contained HTML file with its own CSS and JavaScript. It needs no server,
build step, account, key, external asset or package installation.

The workbench produces a **local draft**, a plain-text diary brief and an entry
JSON file. It does not perform the next action, start an assistant, contact a
website, verify a source or publish anything. No content is saved automatically.

## Write and keep an entry

1. Check the date. It starts at today's date in `America/Los_Angeles`, using the
   browser's clock and Pacific timezone conversion. The timezone stays fixed.
   You can select a different calendar date.
2. Choose one of the twelve existing portfolio initiatives. Changing the
   initiative preserves the rest of this single draft; it does not create a
   separate draft for each initiative.
3. Keep the generated local entry ID, enter your own valid ID or choose
   **Generate ID**. Generating an ID does not clear the other fields. An ID is a
   local record label, with no signature or authentication meaning.
4. Add a title and daily summary. Choose a visibility intention; **Private** is
   the default.
5. Write at least one observation, and choose its evidence classification.
   New observations start as **Planned**. Add or remove rows up to the limit of
   eight observations.
6. Add sources when useful, up to five. Each source needs a title and an HTTPS
   URL. Select its checkbox under an observation to attach it. A source-linked
   observation needs at least one attached source.
7. Write a next action. Optional creative-direction fields can remain blank.
8. Review the plain-text preview. Once the entry passes the form's contract
   checks, use **Copy diary brief** or **Download entry .json**.

The download filename is `jarvis-diary-entry.json`. The page requests a browser
download; the browser decides where and how to save it. Exporting leaves the
draft in the form. Keep or download your work before reloading or closing the
page, because those actions discard the in-memory draft.

If clipboard access is unavailable, the page selects the full plain-text brief
and asks you to use Ctrl+C or ⌘C. This fallback does not send the text anywhere.

## Evidence and visibility are separate

Every observation carries its classification in the JSON and the copied brief.

| Evidence state | Meaning |
| --- | --- |
| `source_linked` | The author attached one or more references. The workbench has not independently checked them. |
| `owner_reported` | The person writing the entry supplied this statement. |
| `planned` | An intention or proposed step; it does not establish a completed result. |
| `fictional` | Illustrative or creative material, not a real-world observation. |

Observation and source IDs are stable row labels. The page generates IDs for
new rows and preserves IDs imported from an existing file. The form edits the
observation text, classification, source titles, URLs and source links without
renaming these row IDs. The main entry ID remains editable.

Removing a source explicitly detaches its references from all observations. It
does **not** change their evidence classifications. If a source-linked
observation then has no source, export stays blocked until you attach another
source or deliberately choose the appropriate classification. Removing an
observation preserves the other rows; the form keeps at least one observation.

| Visibility intention | Local meaning |
| --- | --- |
| `private` | Personal working notes; the default. |
| `internal` | Intended for a separate local team review. It does not grant team access or transmit the entry. |
| `public_candidate` | Suitable for a separate local media-draft review. It is not publication consent. |

Visibility labels do not encrypt downloaded files or control access to them.
The copied preview includes the visibility label and all observation
classifications, source IDs and source URLs. Source URLs are plain text: the
page does not fetch them or turn them into account connections.

## Import safely

Use **Import a diary entry** to select an existing JSON file. A successful import
replaces the form with that entry, including its visibility intention. It does
not combine entries or infer missing fields.

The file must pass the entire contract before replacement. Invalid JSON,
duplicate keys, malformed Unicode, unknown fields, unknown initiatives, broken
source references and oversized content leave the current draft intact. The
import path checks the byte size before reading, decodes UTF-8 strictly and
checks the size again before parsing. It rejects a leading UTF-8 BOM and
excessive JSON nesting.

If you edit the form while the selected file is being read, the page preserves
those edits and asks you to choose the file again before replacing them. If you
choose another file during a read, only the most recent selection can replace
the draft.

The initial form is blank. It does not silently import test fixtures or seed
fictional events as actual diary history. The retained fixture file contains
explicitly synthetic test data and is not itself a single importable entry.

## Exact entry contract

An entry has exactly these thirteen top-level keys:

```json
{
  "schema_version": 1,
  "kind": "jarvis.diary_entry",
  "entry_id": "entry-example-1",
  "date": "2026-10-22",
  "timezone": "America/Los_Angeles",
  "initiative_id": "personal-workflow",
  "title": "Illustrative planning example",
  "visibility": "private",
  "summary": "This is a fictional example of the data format, not a report of real activity.",
  "observations": [
    {
      "observation_id": "observation-1",
      "text": "An illustrative note for a local review.",
      "evidence_state": "fictional",
      "source_ids": []
    }
  ],
  "sources": [],
  "next_action": "Review this example before using the format.",
  "media_notes": {
    "audience": "",
    "visual_style": "",
    "audio_style": "",
    "learning_goal": "",
    "call_to_action": ""
  }
}
```

| Field or group | Accepted values and bounds |
| --- | --- |
| `schema_version`, `kind` | Integer `1` and exact string `jarvis.diary_entry`. Imported fractional or exponent schema tokens such as `1.0` or `1e0` are rejected to match Python's strict integer contract. |
| `entry_id`, `observation_id`, `source_id` | Full ASCII match `[a-z][a-z0-9_.-]{1,47}`: 2–48 characters. Observation IDs are unique within the observation list; source IDs are unique within the source list. |
| `date`, `timezone` | Strict ASCII `YYYY-MM-DD`, valid Gregorian date from year 0001 through 9999; timezone exactly `America/Los_Angeles`. |
| `initiative_id` | One of the twelve existing portfolio initiative IDs listed below. |
| `title` | Nonblank, at most 180 UTF-8 bytes. |
| `visibility` | `private`, `internal` or `public_candidate`. |
| `summary` | Nonblank, at most 3,000 UTF-8 bytes. |
| `observations` | 1–8 objects, each with exactly `observation_id`, `text`, `evidence_state`, `source_ids`. Text is nonblank and at most 1,000 UTF-8 bytes. |
| `source_ids` | Up to five unique IDs from the entry's source list. At least one is required for `source_linked`. |
| `sources` | 0–5 objects, each with exactly `source_id`, `title`, `url`. Title is nonblank and at most 200 UTF-8 bytes. |
| `url` | At most 1,000 UTF-8 bytes, HTTPS, a nonempty hostname, no credentials, whitespace, C0 controls or backslash; port absent or 443. Original URL text is preserved. |
| `next_action` | Nonblank, at most 1,500 UTF-8 bytes. |
| `media_notes` | Exactly `audience`, `visual_style`, `audio_style`, `learning_goal`, `call_to_action`. Every value is a string, may be blank and is at most 600 UTF-8 bytes. |
| Complete JSON | At most 65,536 UTF-8 bytes. Both imported file text and formatted export text are bounded. |

All text values are strict strings with valid Unicode. Unpaired UTF-16 surrogate
units are rejected before encoding. C0 controls are rejected except tab, LF and
CR. Nonblank checks follow Python's whitespace treatment, including U+0085.
Valid strings retain their original whitespace and content. Byte limits use
`TextEncoder`; an emoji can consume four bytes, so the displayed counts are not
character counts. Over-limit text stays in the form for correction.

The browser uses its native URL parser in addition to the stated URL bounds.
It can reject malformed hosts that Python's URL splitter merely parses. The
accepted shared fixture exports have been checked against the Python consumer;
this does not claim that every unusual URL has identical parser behavior.

The initiative IDs are:

```text
jarvis-tools
website-learning
affiliate-builder
funding-customers
referral-partners
publishing-library
interactive-video
linux-learning
robotics-simulation
wearables-research
business-operations
personal-workflow
```

Their labels match `examples/portfolio/catalog.json`. The diary does not inherit
website destinations or conflate the education site, unassigned affiliate
platform, financing-customer journey and referral-partner journey. Sources are
separate references supplied for the entry.

## Local accessibility and companion tools

The form uses native inputs, selects, fieldsets, legends and buttons, with
explicit labels, visible focus and a skip link. Add-row actions focus the new
row's first editable field; remove-row actions focus the relevant add button.
Status messages explain validation and import/export results. The page includes
responsive layouts and system, light or dark appearance choices. Appearance
changes apply only to the current visit.

The prose fields request English native spellcheck. Its behavior depends on
browser dictionaries and settings and may use the browser's own service. The
application's code makes no network request. The **Spelling composer** link opens
the existing `jarvis-composer.html` in a separate tab; the **Portfolio** link opens
`jarvis-workbench.html`. Keep these files together in the `web` directory.

The diary does not change native ChatGPT input, connect to social accounts,
generate images or audio, or make a hosted site. User text reaches the page only
through text and value DOM properties, with no HTML insertion sink. The content
security policy blocks connections, external assets, objects and form submission.

## Offline verification and retained evidence

From the repository root:

```bash
node --test --test-reporter=tap tests/test_diary_workbench.mjs
node tests/test_diary_workbench.mjs
```

The tests extract the actual authored pure module from the shipped HTML and run
it in an isolated VM with `TextEncoder` and `URL`. They syntax-compile both
shipped modules. Imported diary text, source data and generated content are not
executed. The direct invocation exposes individual test-case counts when the
CI-style runner reports a single file wrapper.

The suite covers the exact contract, Pacific dates, source-link integrity, row
operations, UTF-8 limits, strict Unicode and whitespace, safe import replacement,
duplicate JSON keys, integer schema tokens, bounded parsing, classification
labels and source-preserving previews. Static checks inspect native controls,
the real import path and DOM/network/storage patterns. Those source checks are
not browser interaction tests.

- [Validation record](evidence/diary-workbench-validation.json)
- [Actual Node test output](evidence/diary-workbench-node-tests.txt)
- [Shared JavaScript/Python fixtures](evidence/diary-workbench-fixtures.json)

The shared fixture pack contains twelve synthetic exports covering all twelve
initiatives, 39 invalid entry records and seven invalid serialized import cases.
The Python checks use `control_tower.diary.validate_diary_entry` and, for raw JSON
cases, `control_tower.network_contract.load_packet` before validation.

The retained October 22, 2026 run passed **48 individual Node cases**, with zero
failures or skipped cases. Python accepted all twelve valid exports unchanged and
rejected all 39 invalid records and all seven serialized import cases. The static
HTML check found 57 unique IDs, 36 resolved label/ARIA references and balanced
markup. The existing composer and portfolio workbench, including their tests and
documentation, remained unchanged.

Independent offline review found no concrete DOM insertion, import-contract or
draft-preservation blocker. Its targeted actual-core probes covered literal HTML
text, Unicode whitespace and surrogate handling, integer schema tokens and
duplicate keys. The asynchronous import ticket/revision handling was inspected
in source; it was not exercised in a browser.

No browser installation was attempted for this milestone. The earlier headless
Chromium download failed in the environment. Rendered desktop/mobile layout,
native date and spelling behavior, actual clipboard/download interactions and
assistive-technology behavior remain unverified. No deployment, account activity
or external request is part of this implementation or its validation.
