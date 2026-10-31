# Jarvis Three-World Field Guide

Open `web/jarvis-rpg.html` in a current browser for an offline RPG-style companion
to the diary and project briefing. The page combines three original fictional
settings, three planned review quests, a labelled transcript, a source drawer,
local notes and a native video player. Its HTML, CSS, JavaScript and public pilot
data are self-contained. No server, package installation, login or API key is
needed.

This is an **anime-inspired companion interface**. The page does not produce a
fully animated film, verify a business result or run the proposed quests. It can
play an actual local MP4 selected by the user or embedded by the separate local
packager.

## Explore the worlds

| Fictional world | Planned quest | Intended reflection |
| --- | --- | --- |
| The Lantern Archive | `media-review` — Review the media draft | Review evidence labels, assets, narration, captions and accessibility before considering publication. |
| The Copper Forge | `ai-building-cycle` — Review one building cycle | Choose a bounded change, inspect its checks and retain human review. |
| The Sky Observatory | `hostinger-connection` — Inspect the connection route | Identify the actual Hostinger product and supported access route before a live connection attempt. |

Choose a world or a quest using the native buttons. Selection opens the related
quest and focuses its heading. Each quest has its own objective note, retained
in memory as you switch between worlds. The initial Archive view counts as one
opened world; no quest is marked explored initially.

**Mark this quest explored** adds a reversible marker for this visit. Pressing
it again removes that marker and preserves the note. The two progress indicators
count opened worlds and explored quests. They do not count completed project
tasks, verified account connections, agent runs, earnings or experience points.
Every source quest remains `planned` throughout exploration.

Objective notes request English native spellcheck. Each note may be blank and is
limited to 1,000 UTF-8 bytes for copying/export. Invalid Unicode, unsupported C0
controls and oversized notes block export while keeping the text available for
editing. The error identifies the relevant quest, including when its note is
currently on another world.

## Watch local video and use captions

The repository page starts with a usable transcript and no embedded media. Choose
**local MP4** to attach a file up to 150 MiB. The file is represented by a local
browser Blob URL; it is not uploaded, copied into progress JSON or stored by the
application. Playback begins only through the video's native controls. There is
no autoplay or automatic audio.

After selecting a video, optionally choose a matching `.vtt` file up to 128 KiB.
The caption path checks file size, strict UTF-8, a WebVTT header and the presence
of a timed cue. Use the player's captions menu to display it. These checks do not
establish accurate timing, complete WebVTT semantics or codec support. Review
the actual playback before relying on an edition.

Replacing a video clears the previous captions to avoid carrying an unrelated
track onto the new media. A pending caption read is ignored if the video or
caption selection changes. Invalid caption input leaves the existing track
unchanged. Replaced Blob URLs and visit-ending media URLs are revoked.

The local packager can provide video, captions and key art directly in a
standalone edition. The player accepts those assets only as the documented data
URI types. It still waits for the user to press play. Without playable media,
the transcript and quest features remain available.

## Keep evidence and source visibility visible

The transcript and source drawer preserve the episode's classifications:
`source_linked`, `owner_reported`, `planned` and `fictional`. Source-linked means
a reference was supplied; the app does not independently verify the reference or
claim. HTTPS source URLs appear as text and are not fetched. Opening the drawer
does not start a connection or browse those destinations.

The checked-in page embeds exactly
[`examples/episodes/jarvis-diary-pilot.json`](../examples/episodes/jarvis-diary-pilot.json).
It is the public candidate dated **2026-10-22**, with source context
`76e7a538d7c1a3a113d57727f025a2c6b27ccf13` and references to that build and its
recorded CI run. Its content is a dated project snapshot, not a live dashboard or
a researched current-news bulletin. The checked-in page contains no private diary
entry.

The same interface can serve a separately packaged owner edition:

| Episode classification | Required presentation |
| --- | --- |
| `audience: public`, `source_visibility: public_candidate` | A public-candidate banner stating that publication approval is not granted. |
| `audience: owner`, `source_visibility: private` | A prominent **OWNER EDITION / PRIVATE SOURCE** banner. |
| `audience: owner`, `source_visibility: internal` | A prominent **OWNER EDITION / INTERNAL SOURCE** banner. |
| `audience: owner`, `source_visibility: public_candidate` | An owner-edition banner that retains the public-candidate source label. |

Public-audience episodes with private or internal sources are rejected. An owner
edition requires deliberate selection by the separate local packager; this page
has no episode-JSON import control or automatic diary access. Its banner,
source drawer, copied briefs and progress export all retain the episode's
audience and source visibility. A label does not encrypt the local file,
authenticate its author or grant publication consent.

## Copy and export exploration

**Copy quest brief** includes the selected planned objective, the current note,
episode references and explicit exploration limits. **Copy exploration brief**
includes all three notes and the visit markers. Both include the audience and
source visibility. A read-only preview shows the latest text selected for
copying. If clipboard access fails, the preview opens and selects the text for
Ctrl+C or ⌘C.

**Download progress .json** creates `jarvis-rpg-progress.json` with exactly eleven
keys:

```json
{
  "schema_version": 1,
  "kind": "jarvis.rpg_progress",
  "scope": "visit_only_exploration",
  "episode_id": "rpg-20261022-jarvis-pilot",
  "audience": "public",
  "source_visibility": "public_candidate",
  "selected_world": "archive",
  "selected_quest": "media-review",
  "visited_worlds": ["archive"],
  "explored_quests": [],
  "objective_notes": {
    "hostinger-connection": "",
    "ai-building-cycle": "",
    "media-review": ""
  }
}
```

World and quest IDs are closed lists. Markers must be unique; an explored quest
must belong to an opened world. Selected world and quest must match their fixed
mapping. Audience, source visibility and episode ID must match the embedded
episode, so an export cannot silently reclassify an owner edition as public.
No additional completion, approval, connection or revenue fields are accepted.

This is a portable exploration record, with no Python progress consumer or import
flow implemented. Reloading starts a fresh visit. There is no autosave, browser
storage, analytics or background sync. The separate local diary and portfolio
links work when their HTML files remain beside this page.

## Packaging interface

The packager replaces exactly one JSON payload block:

```html
<script type="application/json" id="episode-data">…</script>
```

Validate the selected episode through `control_tower.episode.validate_episode`
and enforce source/audience selection before embedding it. Encode `<` as
`\u003c` inside the JSON so text containing a closing-script sequence remains
data. The page performs structural, reference and classification checks before
rendering. Python packaging and the tracked-fixture tests verify the episode
content digest; the browser helper does not independently recompute that digest
or authenticate provenance.

The source contains exactly one empty attribute for each media hook:

| Hook | Data URI accepted by the app |
| --- | --- |
| `data-jarvis-inline-art=""` on `img#episode-art` | Base64 `image/png`, `image/jpeg` or `image/webp`. |
| `data-jarvis-inline-video=""` on `video#episode-video` | Base64 `video/mp4`. |
| `data-jarvis-inline-captions=""` on `track#episode-captions` | Base64 `text/vtt`, used with an embedded video. |

The app assigns an accepted URI to the corresponding native `src` property.
Empty hooks are valid and require no substitution for the source page to work.
Arbitrary HTTP URLs and SVG data URLs are rejected by these hooks. Asset shape
checks do not establish correct media decoding or caption alignment. The
packager owns receipt/hash binding and verification of the actual rendered media.

## Accessibility and validation limits

The interface uses native buttons, textarea, progress elements, file inputs,
video controls and a modal dialog. Controls have labels, visible keyboard focus,
status announcements and a focusable skip-link target. The source drawer has a
Close button and the native dialog's keyboard behavior. **Calm mode** starts on
and removes interface transitions; the CSS also honors reduced-motion settings.
There are no flashing effects. Desktop, tablet and narrow-screen layouts are
defined in the inline CSS.

All episode and note strings are inserted with text/value DOM properties.
There are no HTML insertion sinks or generated-code execution paths. The content
security policy blocks connections, external assets, objects and form submission;
it permits only local Blob/data images and media. Native spellcheck depends on
the browser dictionary and settings and may use its own service.

Run the authored tests from the repository root:

```bash
node --test --test-reporter=tap tests/test_rpg_workbench.mjs
node tests/test_rpg_workbench.mjs
```

The tests extract the shipped pure helper, run it in an isolated VM and
syntax-compile both shipped scripts. They cover public and explicit owner
classification, exact pilot parity and content digest, source/scene contracts,
world/quest transitions, immutable planned states, note bounds, safe export,
media metadata bounds, caption checks and actual DOM-path structure. They do not
execute diary text or episode data as code.

The frozen UI passed **27 authored Node cases** on 2026-10-22. The CI-style
`node --test` command also passed; this runtime reports the file as one wrapper
test, while direct invocation reports all 27 cases. A bounded static HTML check
found 60 unique IDs, 20 resolved label/ARIA references, six explicitly typed
static buttons, three inline scripts and exactly one of each packaging hook.
The embedded pilot matches the tracked JSON and passes Python's episode
validator. The existing composer, portfolio and diary pages remain unchanged.
Independent read-only review found no concrete UI blocker, including explicit
owner classification, text-only DOM insertion and immutable planned quest states.

No browser installation or native rendering was attempted. Actual desktop/iPad
layout, dialog/focus behavior, native spellcheck, playback/caption decoding,
clipboard/download integration and assistive-technology interaction remain
unverified. Pure-helper and source checks do not establish those browser
behaviors.
