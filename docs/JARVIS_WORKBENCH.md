# Jarvis Portfolio Workbench

Open `web/jarvis-workbench.html` in a current browser to explore the authored
portfolio catalog and prepare one bounded mission request. The page is
self-contained: its HTML, CSS, JavaScript and complete catalog are in one file.
It needs no build step, account, API key, server, external assets or JavaScript
packages.

This is a **catalog and planning workspace**. It does not display live account
status, completed integrations, revenue or measured progress. The twelve
initiatives are planning defaults mapped to the existing seven project areas.
The page does not start a mission or contact an assistant, account, website,
calendar or device.

## Use the workbench

1. Search by idea, outcome, audience, format or evidence gap. Use the project-area
   and journey-focus filters to narrow the list.
2. Select an initiative to see its intended outcome, proposed steps, missing
   evidence, possible formats, destination assignment and scope notes.
3. Write one objective and choose a draft destination and a 15, 30, 60 or 90 minute
   planning timebox. A timebox is planning input; it does not start a timer or
   promise completion.
4. Choose **Copy planning brief** to copy the objective plus the catalog's plan,
   outcome, gaps and boundaries. The preview displays exactly what will be copied.
   If browser clipboard access fails, the complete preview is selected for manual
   copying with Ctrl+C or ⌘C.
5. Choose **Download request .json** to create `jarvis-mission-request.json` for
   the separate local portfolio mission compiler.

Changing a filter does not replace the selected initiative or erase its objective.
If the selection falls outside the filters, a visible note explains why it remains
open. Switching initiatives keeps each initiative's objective, destination and
timebox in memory for the current visit. Closing or reloading the page loses that
work. There is no autosave, local/session storage, analytics or background task.

The **Spelling composer** link opens the existing `jarvis-composer.html` in a
separate tab. Keep both files in the same `web` directory for that link to work.
The composer remains a separate writing workspace; this workbench does not change
it or the native ChatGPT input box. The objective textarea requests English native
spellcheck. Browser spelling depends on its dictionary/settings and may use the
browser's own spellcheck service. The application itself makes no network request.

## Separate destinations and journeys

The page displays the catalog's destination state without inventing a fallback.

| Initiative | Project area | Destination treatment |
| --- | --- | --- |
| Education website and membership inquiries | `ai-evolutionary-evolutions` | The catalog assigns the owner-reference education site, `aievolutionaryevolutions.com`; live access and results remain unverified. |
| Affiliate website and membership platform | `funding-affiliates` | A separate platform with no assigned destination; it does not inherit the education site. |
| Business financing customer journey | `funding-affiliates` | Customer-specific owner-reference financing destinations. |
| Referral partner recruitment | `funding-affiliates` | Separate partner-application references and a different journey focus. |

Local workspaces and other unassigned destinations remain explicitly labelled.
Owner reference URLs appear as text; the workbench does not fetch them, check their
status or turn them into account connections. Catalog scope notes remain visible,
including the paused Studio Work Cycle and simulation-only robotics boundary.

## Mission request contract

An exported request has **exactly six keys**:

```json
{
  "schema_version": 1,
  "kind": "jarvis.mission_request",
  "initiative_id": "jarvis-tools",
  "target": "chatgpt",
  "objective": "Prepare one reviewable improvement with a reproducible check.",
  "timebox_minutes": 30
}
```

The accepted initiative IDs are:

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

Target IDs are `chatgpt`, `openai`, `gemini`, `claude`, `hostinger`, `facebook`,
`linkedin`, `substack`, `instagram`, `threads`, `youtube` and `github`. ChatGPT and
**OpenAI API draft** are separate choices. Choosing either does not create access.

`objective` must be a nonblank string of no more than **2,000 UTF-8 bytes**.
Validation rejects unpaired surrogate code units and C0 controls except tab, LF
and CR. Blank detection includes Unicode whitespace such as U+0085. Valid text
is preserved without trimming or rewriting. The character counter uses Unicode
code points; byte length is displayed separately. Oversized text remains visible
for editing and cannot be exported.

`timebox_minutes` must be an integer equal to `15`, `30`, `60` or `90`. The pure
validator rejects numeric strings, booleans, fractions and unknown values. The
native select is explicitly converted to a number before constructing the JSON.

The export carries no project override, hash, authenticated review, completion
claim, live connection or external-action authority. The local compiler resolves
the initiative through its catalog and produces planning output under its own
validation and review rules. Copying a brief or downloading a request does not
execute that compiler.

## Embedded catalog and updates

The complete data from `examples/portfolio/catalog.json` is embedded in the
`portfolio-catalog` JSON script block. The page does not fetch the tracked file at
runtime. Node tests compare the embedded JSON value with the tracked catalog,
including its metadata, and independently check the catalog's content digest.
That digest is an integrity check, not author authentication.

When the tracked catalog changes, update the embedded JSON in the same review.
Do not edit only the visible cards or replace a missing destination with another
project's URL. Preserve JSON data exactly; if a future text value contains a `<`
character, encode it as `\u003c` in the JSON script block to prevent a closing
script tag from ending the data block. JSON decoding preserves that character's
original value. The drift test must still pass.

## Accessibility and local limits

The page uses labelled native inputs, selects and buttons; a skip link; visible
keyboard focus; text alongside color; and status announcements for deliberate
actions and filter results. Selecting an initiative focuses its heading. The
catalog, details and request retain a meaningful source order on narrow screens.
Appearance can follow system preferences or use light/dark mode for the current
visit. User text is assigned through text/value DOM properties, never HTML sinks.

There are no external fonts, images, API calls, account controls, sending buttons
or publication actions. The content security policy blocks connections and form
submission. The only non-anchor navigation link opens the separate local spelling
composer; reference URLs in the catalog remain text.

## Offline verification

From the repository root with Node 18 or later:

```bash
node --test --test-reporter=tap tests/test_workbench.mjs
```

The retained tests extract the actual authored pure helper module from the shipped
HTML and execute it in an isolated VM with `TextEncoder`. The embedded catalog is
data; no catalog text, user text or generated code is executed. Tests cover catalog
drift and integrity, filters, destination separation, exact request keys, unknown
selectors, timeboxes, UTF-8/control-character boundaries, plain-text briefs and
per-initiative draft memory. Both inline application scripts are syntax-compiled.

In this local runtime the `--test` command may report the file as one test wrapper.
`node tests/test_workbench.mjs` exposes the individual built-in test cases.

No further browser installation was attempted after the previous environment's
failed headless Chromium download. Rendered desktop/mobile layout, native
spellcheck, real clipboard/download interaction and assistive-technology behavior
remain unverified. Static structure and pure-helper tests do not establish those
browser behaviors. No hosting, deployment or account changes are included here.

## Retained validation evidence

The October 22, 2026 validation records **34 individual Node test cases passed**,
with no failures or skipped cases. Both the CI-style command and direct built-in
test invocation completed successfully. The twelve request examples generated by
the shipped JavaScript helper were accepted unchanged by the Python
`validate_mission_request` consumer; all eleven invalid examples were rejected.

A bounded HTML structure check verified unique IDs, valid label/ARIA references,
balanced markup, explicit button types and the focusable skip-link target. The
embedded catalog matches its tracked source. The existing spelling composer and
its tests/documentation are unchanged. Independent offline review found no
concrete DOM insertion, export-contract or initiative-boundary blocker.

- [Validation record](evidence/workbench-validation.json)
- [Actual Node test output](evidence/workbench-node-tests.txt)
- [Shared JavaScript/Python request fixtures](evidence/workbench-request-fixtures.json)

These results cover authored source structure and pure logic. They do not verify
rendered layout, browser-native input, clipboard/download integration or
assistive-technology behavior.
