# Jarvis anime/RPG diary — watch and play runbook

This workflow produces a local **Watch & Play** edition: a narrated motion-comic video, captions and transcript, plus an interactive three-world companion with proposed quest cards and visit notes. Luma, an original fictional guide, introduces the Lantern Archive, Copper Forge and Sky Observatory. Diary records keep their supplied evidence labels, and the quests remain planned work.

The measured public pilot is **106.25 seconds**, at **1280 × 720 and 24 frames per second**. It uses generic local **Flite `slt`** speech and a simple original synthesized instrumental bed. One original generated illustration receives camera pan/zoom, transitions, headings and captions. Character animation and character lipsync are not implemented. The [episode contract](EPISODE_DATA_CONTRACT.md) defines the source and audience rules; the [RPG workbench guide](JARVIS_RPG_WORKBENCH.md) describes the interactive controls.

## Watch the delivered edition

1. Extract the delivered ZIP into a local folder.
2. Open `watch-and-play.html` in a browser. Press the native video's Play control when ready; the page does not autoplay audio.
3. Explore the three worlds and their quest cards. Open the transcript and source drawer to inspect the labels and supplied references.
4. Add an objective note or mark a quest **explored** for this visit. These interactions do not complete the real project task or change the source quest's `planned` status.
5. Use **Download progress .json** before closing if you want to retain the visit markers and notes. The page has no autosave or progress-import flow; a reload starts a fresh visit.

The ZIP also contains `episode.mp4` for direct playback. Captions are burned into that video, and a separate `captions.vtt` file is supplied for players that support it. `transcript.txt` provides the complete spoken text with evidence labels and references. The repository's [standalone workbench](../web/jarvis-rpg.html) has the same public pilot data but begins without embedded video; its file controls can attach a local MP4 and matching VTT without uploading them.

The packaged HTML embeds its art, video and caption assets, so it does not need a server or account connection to load them. The player and file controls still depend on the browser's local-file, codec and caption support. Use the separate MP4, VTT and transcript if a browser cannot play the embedded edition. Actual iPad/browser layout, assistive-technology behavior and native playback are separate checks from a successful local video render.

### Files in a Watch & Play ZIP

| File | Purpose |
| --- | --- |
| `watch-and-play.html` | Self-contained companion with embedded art, MP4, captions and selected episode data |
| `episode.mp4` | Narrated motion comic with an instrumental bed, evidence labels, audience/source label and burned-in captions |
| `narration.wav` | Continuous generic synthetic narration, including its measured pauses |
| `captions.vtt` | External caption track timed to measured synthetic utterances |
| `transcript.txt` | Spoken text, scene evidence labels, audience/source classification and supplied references |
| `timeline.json` | Scene and utterance timing, source IDs and episode/audience binding |
| `episode.json` | Validated six/seven-scene plan and three planned quests |
| `render_receipt.json` | Episode/source/art identities, duration, format and hashes of rendered files |
| `art.png` | Exact supplied PNG used by the renderer; the shipped pilot uses the original generated illustration |
| `READ-ME.txt` | Short opening instructions and the edition's scope |

## Prepare the local environment

Run the commands below from the repository root. Compiling the JSON plan uses Python 3.11+ and the standard library; it does not require an API key, a provider account or FFmpeg. Rendering additionally requires these local capabilities, as used by [episode_render.py](../control_tower/episode_render.py):

| Dependency | Required capability |
| --- | --- |
| `ffmpeg` on `PATH` | PNG decoding, image/video filters and MP4 output |
| FFmpeg `flite` filter | Generic built-in `slt` voice; no downloaded or cloned voice model |
| FFmpeg video support | `libx264`, plus `scale`, `crop`, `zoompan`, `drawbox`, `drawtext` and `fade` filters |
| FFmpeg audio support | PCM WAV output, AAC encoding, `volume`, `amix` and `alimiter` filters |
| Fixed font file | `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` |
| A local PNG | At most 20 MiB; each dimension 256–8192 pixels; at most 12 million pixels |
| `ffprobe` for inspection | Optional verification of the completed MP4's streams and duration |

The renderer does not install software or fetch art, fonts or voices. The current font path and FFmpeg process runner target the existing Linux environment. A different platform needs the same capabilities and a reviewed font-path adjustment in code. Useful read-only capability checks are:

```bash
python --version
ffmpeg -hide_banner -version
ffmpeg -hide_banner -h filter=flite
ffmpeg -hide_banner -filters
ffmpeg -hide_banner -encoders
python -c 'from pathlib import Path; print(Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf").is_file())'
```

Look for the capabilities listed above; the presence of the `ffmpeg` executable alone does not guarantee its build contains Flite, the voice or the required filters/codecs. A missing capability or a failed process produces a controlled render error. JSON compilation remains available independently of the optional renderer.

## Compile the public pilot plan

The tracked source is [public-diary-source.json](../examples/episodes/public-diary-source.json). Its two source-linked records describe the preceding public diary/multimedia milestone and its retained checks. The compiled reference is [jarvis-diary-pilot.json](../examples/episodes/jarvis-diary-pilot.json). The next building, connection and media-review cycle remains proposed work.

Use a fresh output name:

```bash
python scripts/jarvis_episode.py compile \
  --entry-file examples/episodes/public-diary-source.json \
  --source-revision 76e7a538d7c1a3a113d57727f025a2c6b27ccf13 \
  --episode rpg-20261022-jarvis-pilot \
  --audience public \
  --out reports/anime-rpg/pilot-plan-review.json
```

The command validates the diary and writes the local plan. It prints output/content hashes, audience and source visibility. `public` is the default, but showing it explicitly makes the intended output clear. A private or internal diary fails in public mode before an episode is produced. The command does not publish the JSON or invoke a model.

Inspect the plan before rendering. It selects up to the first three diary observations, preserves each observation's label and source IDs, and reports how many further observations were omitted. It uses six or seven scenes. Its three quest IDs are `hostinger-connection`, `ai-building-cycle` and `media-review`; all remain planned. This project pilot omits a current-news segment and makes no claim to contain a verified five-item news briefing.

The compiler retains the supplied context revision; it does not use that value to fetch Git history or verify sources. The pilot's context revision refers to the preceding diary milestone, not to proof that the new anime/RPG compiler already existed there. For a new diary, supply the context revision you actually intend to retain.

## Render a local Watch & Play edition

The pilot artwork is at `reports/anime-rpg/assets/command-library.png` in the working environment. A fresh repository checkout does not contain this asset. Extract `art.png` from the delivered edition and place a copy at that local path, or supply another suitable PNG that you intend to use.

```bash
python scripts/jarvis_episode.py render \
  --entry-file examples/episodes/public-diary-source.json \
  --source-revision 76e7a538d7c1a3a113d57727f025a2c6b27ccf13 \
  --episode rpg-20261022-jarvis-pilot \
  --audience public \
  --art-file reports/anime-rpg/assets/command-library.png \
  --out reports/anime-rpg/pilot-watch-play-review.zip
```

`render` compiles directly from the selected diary entry again; it does not consume the JSON output from `compile`. Keep the source and compilation parameters the same if the rendered episode is meant to match the reviewed plan. The renderer synthesizes and measures narration chunks, aligns scene durations to video frames, produces the media and receipt, then packages the local edition.

The CLI uses the fixed code-owned `web/jarvis-rpg.html` beside the script's repository. There is no custom-HTML/template argument. A caller's `--root` changes the input/output root, not the trusted template location. Diary text is data: FFmpeg reads it through fixed local text files, and no diary text becomes shell code or a filter expression.

The global `--root` option, when needed, appears before `compile` or `render`. Input and output paths must remain within that root. Output extensions are `.json` for compilation and `.zip` for rendering. Existing output files are preserved and rejected as destinations: select another fresh name when repeating a command. The CLI prepares the complete output before committing the destination; a failed renderer does not leave a finished-looking partial ZIP at the requested path.

### Render bounds and timing

The output narration/video budget is **four minutes (240 seconds)**. An over-budget episode fails rather than silently dropping its remaining scenes. Each individual local FFmpeg invocation has a 45-second process timeout. The four-minute budget is a media-duration limit, not a guaranteed wall-clock completion time for all rendering work. Multiple speech, scene and muxing steps can take longer to compute.

Each render file, the embedded companion HTML and the final ZIP are bounded at 50 MiB. Larger assets or outputs can fail even when the text plan is valid. The original PNG has its separate 20 MiB/dimension bound.

Captions follow **measured synthetic utterances**: the renderer breaks narration into short spoken chunks, measures each generated WAV and places the corresponding caption on that audio interval. The continuous narration and frame-aligned scene timeline avoid per-scene AAC padding in the caption clock. These are utterance captions; they are not word-level forced alignment, mouth animation or lipsync. Review the actual narration, pronunciation and captions before using a rendition beyond this local draft.

## Explicit owner/private viewing

A personal diary does not need to be relabeled public to become a local owner edition. Save or explicitly export one valid diary entry to a local path such as `reports/diary/owner-entry.json`, retaining its `private` or `internal` visibility. The diary workbench and [diary CLI](../scripts/jarvis_diary.py) provide the separate entry/export workflow.

The following example records the currently checked-out commit as the chosen code context. It does not claim that private diary content is stored in that commit:

```bash
episode_context_revision=$(git rev-parse HEAD)
python scripts/jarvis_episode.py compile \
  --entry-file reports/diary/owner-entry.json \
  --source-revision "$episode_context_revision" \
  --episode owner-diary-review \
  --audience owner \
  --out reports/anime-rpg/owner-plan-review.json
```

Render the same selected owner entry explicitly:

```bash
python scripts/jarvis_episode.py render \
  --entry-file reports/diary/owner-entry.json \
  --source-revision "$episode_context_revision" \
  --episode owner-diary-review \
  --audience owner \
  --art-file reports/anime-rpg/assets/command-library.png \
  --out reports/anime-rpg/owner-watch-play-review.zip
```

The local edition retains `audience="owner"` and the original source visibility. Video, transcript, timeline, receipt, companion banner and exploration export retain that classification. An owner edition can contain private selected text in its JSON, narration, captions and video; keep the ZIP and extracted files in a private local location. Labels and content hashes do not encrypt those files. The repository's tracked source, pilot and checked-in page are public examples only.

Both public-candidate and owner editions retain `publication_approval="not_granted"`. These commands create local artifacts. They do not post to social platforms, upload to Hostinger, modify an account, send messages or publish a page. No provider credential is read by this compiler/render workflow.

## Measured pilot and asset provenance

The retained final render evidence is under `reports/anime-rpg/render-v2/`: `render_receipt.json` records the input and output identities, and `ffprobe.json` independently describes the produced media streams. This edition uses split header plates to preserve the guide's face. These working render files and artwork are under ignored `reports/`; they are not Git-tracked source assets. The delivered ZIP includes `art.png`, the media and the render receipt.

| Pilot property | Observed value |
| --- | --- |
| Episode | `rpg-20261022-jarvis-pilot` |
| Classification | Public audience / public-candidate source / publication approval not granted |
| Narration | 240 words; generic local Flite `slt` voice |
| Measured duration | 106,250 ms / **106.25 seconds** |
| Video | H.264, **1280 × 720**, **24 fps** |
| MP4 file size | **8,457,088 bytes** |
| Muxed audio | AAC, mono, 16 kHz |
| Motion | Camera pan/zoom over one illustration, scene transitions and text overlays |
| Captions | Measured synthetic utterance timing; burned-in and separate WebVTT |
| Source context | `76e7a538d7c1a3a113d57727f025a2c6b27ccf13` |
| Referenced milestone CI | [Run 39862842245](https://github.com/lippytm/jarvis-nexus-core/actions/runs/39862842245) |

The art was generated as an original command-library illustration for this pilot. Its local provenance path is `reports/anime-rpg/assets/command-library.png`, with dimensions **1672 × 941** and SHA-256:

```text
8228c00377bc60af5fd391efbfa930606b9aaf644938dfedf238d018773da33d
```

That same image is bundled as `art.png`. The renderer does not generate a new illustration, retrieve stock art, or download an asset during a repeat render.

Retained content and file identities:

```text
Source diary canonical content SHA-256:
ff580d4fd8b08b477848315f342bbfeebbc05820f00909288663552045b822bd

Episode canonical content SHA-256, excluding episode_sha256 itself:
19a7eaba577ef0914ed5a5a6f65dfaeab37ae4f7d9bf5837b3a7b3274bfea230

Tracked examples/episodes/public-diary-source.json file SHA-256:
0c88815eb93e3a6783b27fb658dfad468f9261b78003b980e388f1b95f58b600

Tracked examples/episodes/jarvis-diary-pilot.json file SHA-256:
3b704f2c78467dfeccc783aa34a0274409cf6ec0a737add804286ed754a1c19a

Measured reports/anime-rpg/render-v2/episode.mp4 file SHA-256:
71c37eb6001bee27232edc614dd72cc65a2086b551e9c504efa7f3262f83c191
```

A canonical content hash and a file hash answer different questions. The CLI's compact JSON formatting can differ from the tracked pretty-printed file while representing the same episode content. For a repeat render, compare the episode/art identities and inspect the new media/receipt; byte-identical video or ZIP output across FFmpeg/runtime versions is not promised.

After extracting a new rendition, optional local inspection is:

```bash
ffprobe -v error -show_format -show_streams -of json path/to/extracted/episode.mp4
```

Use the rendition's actual probe result and receipt for its duration and format. The 106.25-second measurement applies to the retained pilot described here, not every possible diary entry.

## Daily use and recurring prompts

For another day, select one dated diary entry, choose its audience explicitly, compile a fresh plan, review it, and invoke a fresh render when wanted. The source date is supplied by the diary; the compiler does not infer personal events or scrape accounts to fill a day.

A recurring daily-update prompt is a request to begin work. It is not a background video renderer. This CLI installs no scheduler, daemon or automatic publication job; it runs only when invoked with a selected diary, context, artwork and output path. A reminder or recurring prompt alone does not establish that a new episode has been compiled, rendered or delivered.

Current-news research, live account connections, execution of proposed project quests and publication remain separate work. The local watch/play experience keeps its scope visible: a source-labeled diary adaptation, an original fictional presentation, and proposed next steps for the owner to review.
