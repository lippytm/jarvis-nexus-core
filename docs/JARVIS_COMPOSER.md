# Jarvis Composer

`web/jarvis-composer.html` is a portable writing workspace for Jarvis drafts. Open
the HTML file in a current browser; it requires no build step, account, API key,
server, external assets or installed JavaScript packages. It can also be served
as a static file after a separate hosting review.

This composer **does not modify the native ChatGPT input box**. Write here, review
your text, then copy it into ChatGPT, Gemini, Claude, Hostinger or another editor
yourself. Destination choices organize the draft; they do not establish a
connection or authorize sending or publishing.

## Use the composer

1. Choose a project and draft destination. ChatGPT and **OpenAI API draft** are
   separate destinations.
2. Write or paste your draft. The English text area requests native browser
   spelling and shows characters, words and UTF-8 bytes.
3. Choose **Check common typos**. Tick only the suggestions you want, then use
   **Apply selected corrections**. Nothing is automatically selected or replaced.
4. **Undo** restores previous editor changes, including corrections and **Clear**.
   The app keeps up to 50 previous text states in memory. Ordinary browser text
   editing shortcuts remain available; the app does not intercept them.
5. **Copy text** copies the exact draft. If clipboard permission or support is
   unavailable, the text is selected for manual copying with Ctrl+C or ⌘C.
6. **Download .txt** exports the exact text. **Export review draft .json** creates
   `jarvis-draft.json` for a separate Jarvis review process.

The draft and theme selection are held in memory only. There is no autosave,
local/session storage, analytics, service worker or application network request.
Closing or reloading the page loses the draft; copy or download it first. Copying
and downloading occur only after the corresponding button is activated.

## What spelling support means

The textarea has `spellcheck="true"` and `lang="en"`. `spellcheck` is a hint, not a
guarantee: availability, dictionary selection and spelling marks depend on the
browser and its settings. Browser spelling can flag brand names separately from
the local checker. The page includes a control to stop requesting native spelling.
Enhanced browser spelling may send text to the browser's own service; the app
cannot control that implementation. See the primary
[MDN spellcheck reference](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Global_attributes/spellcheck).

The local suggestion engine is a deliberately small list of 34 common English
typos. It is not a dictionary, grammar service, fact checker or AI model. A result
with no matches means only that none of those rules matched eligible text.

- Recognized lowercase, title-case and uppercase forms retain their case.
- Jarvis, lippytm and the listed platform/brand terms are preserved. Unknown words
  are left alone unless they exactly match a word in the small typo list.
- URLs, email addresses, handles, hashtags, common path forms, mixed-case terms
  and compound/code identifiers are excluded.
- Backtick code spans; backtick/tilde code fences; indented code; HTML code,
  preformatted, script and style blocks; and several common code signatures are
  excluded. Unfinished marked code is treated conservatively.
- Unmarked code cannot always be identified. Wrap code in backticks or fenced
  code blocks. The engine deliberately prefers leaving a questionable span alone.
- At most 40 suggestions are displayed at once, with the total disclosed. Apply
  selected changes and check again for any remaining matches. Editing clears
  stale suggestions. Applying stale or forged corrections is rejected.

Corrections operate on text; user content is never rendered as HTML or executed.
Application clipboard access uses `navigator.clipboard.writeText` only on a copy
action. It can fail because of browser support, permissions or secure-context
requirements; see [MDN's writeText reference](https://developer.mozilla.org/en-US/docs/Web/API/Clipboard/writeText).

## Draft export contract

The JSON has **exactly five keys**:

```json
{
  "schema_version": 1,
  "kind": "jarvis.draft",
  "project_id": "ai-jarvis",
  "target": "chatgpt",
  "text": "The exact draft text, including its whitespace."
}
```

| Project ID | Label |
| --- | --- |
| `ai-jarvis` | AI Jarvis |
| `ai-evolutionary-evolutions` | AI Evolutionary Evolutions |
| `funding-affiliates` | Funding and affiliates |
| `publishing-studio` | Publishing studio |
| `linux-education` | Linux education |
| `robotics-research` | Robotics research |
| `business-operations` | Business operations |

Provider IDs are `chatgpt`, `openai`, `gemini`, `claude`, `hostinger`, `facebook`,
`linkedin`, `substack`, `instagram`, `threads`, `youtube` and `github`.

Export requires a listed project and target, valid Unicode text that is not
whitespace-only, and no more than **20,000 UTF-8 bytes** using `TextEncoder`.
Unpaired surrogate code units are rejected instead of silently replaced. C0
control characters are rejected except tab, line feed and carriage return.
Blank detection includes Unicode whitespace such as U+0085. The
character counter counts Unicode code points, which differs from bytes, combined
visible glyphs and platform-specific posting limits. No platform character limit
or acceptance is claimed. Oversized drafts stay visible for editing; exports and
local spelling checks reject them instead of silently truncating them. A proposed
correction that would cross the byte limit is rejected without changing the draft.

The export has no hash, approval, account, connection or publication authority.
The separate Python ledger may wrap it with an immutable content hash and a local
review record. This page provides no send, publish, account-login or payment action.

## Accessibility and appearance

The page provides a visible keyboard focus indicator, a skip link, explicit form
labels, native buttons/selects/checkboxes, status announcements for deliberate
actions, and text alongside color cues. Counters are not announced on every
keystroke. Applied corrections and undo return focus to the editor. The layout
adapts to narrow screens, and appearance can follow the system or use light/dark
mode for the current visit. No external fonts or images are loaded.

## Offline verification

From the repository root with Node 18 or later:

```bash
node --test tests/test_composer.mjs
```

The built-in Node test runner extracts the authored pure module from the HTML;
it does not run generated code or a live browser session. Tests cover protected
spans, explicit selections, stale/forged corrections, undo, byte boundaries,
Unicode handling, exact export keys and allowed selectors. Both inline scripts
are compiled for syntax. Static checks enforce the network/storage/asset limits.

Those tests do not establish that browser-native spelling, clipboard permissions,
downloads, responsive rendering or assistive technologies work in every browser.
Review those interactions in the target browser before hosting. No Hostinger or
social account was connected or changed by this implementation.

The [recorded validation](evidence/jarvis-composer-validation.json) and
[actual Node output](evidence/jarvis-composer-node-tests.txt) report the local
result and its limits. The local runtime aggregates `node --test` output by file;
running `node tests/test_composer.mjs` displays the individual built-in test cases.
Three [shared export fixtures](evidence/composer-draft-fixtures.json), generated
by the shipped JavaScript helper, also passed Python's `validate_draft`; four
invalid-text cases were rejected by both implementations.

A single bounded attempt to install headless Chromium through the existing
Playwright runtime failed because the downloaded archive was empty/truncated
(the extractor reported a missing ZIP directory signature). No browser UI,
native underlines, clipboard integration, download interaction or screenshot was
verified. HTML structure checks and independent DOM-path inspection are separate
from rendered browser validation.
