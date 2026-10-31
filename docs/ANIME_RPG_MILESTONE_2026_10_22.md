# Jarvis diary and morning briefing — anime/RPG milestone

The new watch-and-play pilot is a real **106.25-second video** accompanied by an
offline RPG page. It introduces Luma, an original fictional AI guide, and three
worlds: the Lantern Archive, Copper Forge and Sky Observatory. The episode adapts
selected public Jarvis project records into seven chapters and three proposed
quests. Its narration, captions, transcript and sources stay together.

This milestone extends the existing diary, portfolio and composer in draft PR
#5. Its local verification was completed before publication of the new commit;
the PR records later exact-commit CI and remote readback separately. This document
does not claim a merge, deployment or a background video-production service.

## What was built

| Component | Current behavior |
| --- | --- |
| Episode compiler | Converts one explicitly selected diary into six or seven scenes, three original worlds and three planned quests; selects up to the first three observations and reports omissions |
| Evidence and audience | Preserves source-linked, owner-reported, planned and fictional labels; public mode requires a public-candidate source; explicit owner mode retains private/internal classification |
| Video renderer | Uses one supplied PNG, local generic Flite `slt` speech, original oscillator music, gentle pan/zoom, scene transitions, headings and burned-in captions |
| Measured captions | Synthesizes short utterances individually, measures their WAV duration, constructs one continuous audio track and aligns every scene to exact video frames |
| RPG companion | Provides three selectable worlds, quest cards, reversible visit markers, objective notes with browser spellcheck, copied briefs, progress export, source drawer and transcript |
| Watch-and-play package | Embeds the selected episode, actual PNG, MP4 and VTT into one HTML file; ZIP also carries separate media, script, timeline and render receipt |
| Repeatable CLI | Compiles JSON or renders a fresh ZIP directly from a selected diary; it refuses existing destinations and paths escaping the chosen workspace |

The interface's exploration progress records what the viewer opened or marked
explored. It never changes the source quests from `planned` to completed. Notes
last for the visit; export them before closing. There is no progress import,
autosave, cross-device synchronization or external dispatch in this page.

## The actual pilot

The selected source is [public-diary-source.json](../examples/episodes/public-diary-source.json).
It describes the preceding diary/multimedia implementation at
`76e7a538d7c1a3a113d57727f025a2c6b27ccf13` and its retained **232 Python / 123
web-helper** checks. Those historical numbers are what the narration says. The
new code's **273 / 150** totals below are separate from the story's source record.
No real private diary entry was supplied or invented for this pilot.

The compiled [episode](../examples/episodes/jarvis-diary-pilot.json) has content
hash `19a7eaba577ef0914ed5a5a6f65dfaeab37ae4f7d9bf5837b3a7b3274bfea230`.
It contains two source-linked diary scenes, fictional opening/closing scenes,
and planned briefing, offer-experiment and next-quest scenes. **Current news is
not included.** It is a project pilot, not the complete five-story daily briefing.

| Measured property | Result |
| --- | --- |
| Video duration | 106,250 ms |
| Video stream | H.264, 1280 × 720, 24 fps, 2,550 frames |
| Muxed audio | AAC, mono, 16 kHz; duration matches video |
| Narration source | 240 words, generic local Flite `slt` voice; 1,700,000 PCM samples at 16 kHz |
| Chapters and captions | Seven contiguous scenes, 16 measured utterance cues |
| Final MP4 bytes | 8,457,088 |
| Final MP4 SHA-256 | `71c37eb6001bee27232edc614dd72cc65a2086b551e9c504efa7f3262f83c191` |
| Source artwork | Original generated command-library PNG, 1672 × 941 |

This is an anime-inspired **motion comic**: the camera and graphic overlays move
over one illustration. Full character animation, mouth movement and word-level
forced alignment are not implemented. The generic voice is not a cloned voice.
The musical bed is a simple original synthesized sequence, not a vocal song.

The original key art was generated separately through the built-in image tool.
The local compiler/render processes themselves make zero model calls. The PNG
is bundled with the delivered edition and remains outside Git under ignored
`reports/`. The [runbook](ANIME_RPG_RUNBOOK.md) records its exact provenance hash
and instructions for supplying the artwork in a new checkout.

## Verification and independent review

| Check | Local result |
| --- | --- |
| Python source syntax | **57 files** checked, no syntax errors |
| Python suite | **273 tests passed**, no failures, errors or skips |
| Authored JavaScript helper cases | **150 passed**: 34 composer, 34 portfolio, 48 diary, seven media-player, 27 RPG |
| CI-style Node invocation | Five test-file groups passed in the local runtime; direct runs retain individual case totals |
| Actual video | Full audio/video decode succeeded; final ffprobe matches the measured timeline |
| Visual samples | Final scene midpoint frames 1, 3 and 7 inspected by root; independent reviewer also inspected the revised opening |
| Package consistency | Episode/art identity, media byte counts/hashes, required receipt semantics, scene/source bindings, continuous WAV duration and regenerated VTT checked |
| HTML structure | Unique IDs and media hooks; label/ARIA references resolve; selected episode matches the Python contract and tracked fixture |

An independent AI reviewer inspected the compiler, renderer, CLI, UI and selected
actual media. Findings led to exact receipt/timeline validation, rejection of
duplicate JSON fields, internal construction of the companion from the selected
episode, and smaller header plates that keep Luma's eyes visible. These fixes
were retested against the actual media and adversarial fixtures. No concrete
blocker remained in that bounded review.

The retained records are [Python verification](evidence/anime_rpg_2026_10_22.json),
[web verification](evidence/anime-rpg-web-tests.json),
[render evidence](evidence/anime-rpg-render.json), and
[independent review](evidence/anime-rpg-review.json).

No native browser, iPad, clipboard/download, speech-pronunciation listening or
assistive-technology acceptance is claimed. UI helper checks and successful
FFmpeg decoding are separate from that target-device work. Independent AI review
is also separate from the outstanding human accessibility review.

## Owner editions and daily continuation

The default public mode rejects private/internal diary sources before rendering.
Explicit `--audience owner` permits local private viewing while keeping the
source classification on the video, transcript, receipt, timeline, companion
banner and exported notes. It does not relabel the diary public. The selected
private text can be present throughout such an owner's media package; labels
and hashes do not encrypt it or authenticate the author.

The command reads one deliberately selected local diary file. It does not scrape
personal activity, read the browser's visit memory, automatically open the local
diary database, or invent missing personal events. The [runbook](ANIME_RPG_RUNBOOK.md)
contains public and owner examples and the actual four-minute render budget.

A recurring morning briefing can use the same original fictional frame and
quest structure while preserving dated, sourced facts. A new MP4 exists only
when the source, art and rendering tools are available and an actual render
completes. A changed recurring prompt alone does not install a video service.
The scheduled briefing's five timely stories and seven workflows remain separate
requirements from this selected-project pilot.

## 6. The next three engineering priorities

1. **One verified Hostinger connection and useful journey.** Confirm the actual
   site/product and read access, retain a real read receipt, and select one
   educational or inquiry journey with an observable outcome. A fictional quest
   or a prior configuration check does not establish an account connection.
2. **One real, bounded AI-building cycle.** Choose a useful assistant/tool change,
   obtain a real provider return, review it independently, and retain acceptance
   evidence, cost and benefit. Compiled handoffs and templates are still inactive
   planning artifacts until execution is evidenced.
3. **The complete daily watch experience.** Validate this player and captions on
   the target browser/device, include an explicitly supplied personal diary and
   a freshly verified five-story briefing in a reviewed episode, then extend
   scene artwork/animation only where it improves understanding. Completion
   means an actual playable dated episode with working captions and a reviewed
   source record, followed by one small educational-product feedback experiment.

The existing Studio Work Cycle stays paused. No Hostinger/social publishing,
account write, real-world quest completion, sales or commissions are established
by the video or the RPG interface.
