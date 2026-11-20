# Diary-to-media production runbook

## What works in this milestone

The diary workbench captures a strict entry JSON. Python 3.11 or later validates
it, keeps optional local SQLite revision history, compiles a date-specific
briefing and exports a multimedia edition. The base compiler uses only the
standard library. It calls no model, fetches no source and contacts no platform.
The optional renderer uses an already installed local FFmpeg build.

Use the [workbench guide](JARVIS_DIARY_WORKBENCH.md) for the form and the
[data contract](DIARY_DATA_CONTRACT.md) for exact limits and privacy behavior.
The persistent store and exclusive output writer target POSIX environments;
the standalone browser page is separate. Local database files are unencrypted.

## 1. Capture and retain an entry

Open `web/jarvis-diary.html` and choose one of the twelve portfolio initiatives.
Record a title, summary, at least one classified observation and a next action.
Sources and creative direction are optional except that a source-linked
observation must have a valid source reference. New entries are private and new
observations are planned by default. Save the download before closing the page.

For real private entries, place downloads in the ignored `reports/diary/` area
or a separate trusted private workspace. Do not copy them into tracked examples.
The form does not autosave, share, sync across devices or write SQLite directly.

```bash
python scripts/jarvis_diary.py validate --entry-file reports/diary/entry.json
python scripts/jarvis_diary.py save --entry-file reports/diary/entry.json
python scripts/jarvis_diary.py list
python scripts/jarvis_diary.py history --entry-id your-entry-id
```

The default store is `reports/diary/diary.sqlite3`. The first save returns a
revision and SHA-256. Saving identical content again is idempotent. A changed
entry requires the exact current hash:

```bash
python scripts/jarvis_diary.py save --entry-file reports/diary/entry.json --expected-sha256 CURRENT_64_CHARACTER_HASH
python scripts/jarvis_diary.py export-entry --entry-id your-entry-id --out reports/diary/reopened-entry.json
```

The placeholder hash must be replaced with the actual current value. A stale
update fails and retains history. `list` and `history` emit metadata only, but
IDs, dates and hashes can still be private. Entry export deliberately contains
the complete entry, so handle it according to its visibility.

To use a different trusted directory, pass `--root` before the command and keep
all file paths relative to that root. `--db` is also a global option. Database
paths reject parent traversal, absolute paths, SQLite URI/memory forms, symlink
files and symlink parents. The database owner and permissions are checked.
These checks do not defend against malicious code already running as the same
OS user. Revision history is not an independent backup.

## 2. Compile the diary portion of a morning briefing

```bash
python scripts/jarvis_diary.py briefing --date 2026-10-22 --out reports/diary/public-brief-2026-10-22.json
python scripts/jarvis_diary.py briefing --date 2026-10-22 --audience owner --out reports/diary/owner-brief-2026-10-22.json
```

Use the intended calendar date in `America/Los_Angeles`. The default public
projection includes only entries explicitly marked `public_candidate`. The
owner projection includes that date's private and internal entries as well.
Both retain evidence labels and sources, identify excerpts, and include at most
seven eligible entries. An empty day reports no eligible entry; it invents no
events. Public output reveals no hidden private-entry count, ID or full digest.

For one supplied entry without using the database, add `--entry-file PATH`.
The tracked public example demonstrates this route. The output is JSON for an
assistant or another local tool to consume, rather than an automatic message.

The scheduled ChatGPT morning briefing is a separate execution context. Its
prompt can include a Life/Business Daily Diary section based on records that
are explicitly supplied or accessible there. It cannot automatically read this
local SQLite database, retain browser draft memory, or infer what happened in a
person's life. Supply an owner excerpt privately or an intentionally selected
public projection when that context is needed. Never publish an owner brief as
a substitute for the public projection.

## 3. Develop a public-candidate media edition

Select a suitable entry deliberately and review its text and source URLs for
material that should not be exported. The media compiler accepts only
`public_candidate`. That choice permits creation of a local draft; it is not
publication approval, a personal-information scan or a rights clearance.

```bash
python scripts/jarvis_diary.py pack --entry-file examples/diary/public-project-entry.json --product my-diary-edition --source-revision e645c64975dc05f3b0a0f9e06d7cc903d70031b0 --duration 30 --out reports/my-diary-edition.zip
```

The example source revision is the public engineering context used by the
example. For new work, provide its real 40-character source commit. This field
records supplied context; the compiler does not authenticate GitHub or compare
that commit to a local working tree. The record hash binds the full supplied
entry. `--target` selects an existing supported assistant handoff destination;
the default is `chatgpt`, and export does not dispatch the handoff.

The available storyboard/music durations are 15, 30 and 60 seconds. An optional
`--edition-timestamp YYYY-MM-DDTHH:MM:SSZ` enables repeatable base-pack bytes.
Without it, the actual current UTC compilation time is recorded. This is not
the source diary date. Renderer output can vary with FFmpeg, codec and font
versions even when base compilation is repeatable.

| Files in the base pack | Actual output and intended use |
| --- | --- |
| `README.md`, `manifest.json`, `source_entry.json` | Usage, file hashes and byte counts, source identity and the complete selected entry |
| `diary.md`, `ebook.md`, `book.epub` | Readable source edition and packaged EPUB with navigation, reading order, reflection and references |
| `narration.txt`, `narration.ssml` | Plain narration and XML speech-markup source; these are text until rendered |
| `documentary.md` | Evidence-labeled documentary scene and visual-source draft |
| `trailer.md`, `trailer_cues.json`, `trailer_text.vtt` | Four-scene timed text storyboard; cue timings are not speech alignment |
| `movie_treatment.md` | An explicitly fictional original treatment, separate from factual diary claims |
| `music_film.md`, `music_bed.wav` | Original lyric/visual draft and actual synthesized instrumental sketch, with no sung vocals |
| `ad_copy.md` | Three editable headline variants, source-linked claim candidates and the initiative's assigned destination status |
| `media_handoff.json` | Bounded assistant draft referring to the source entry and digest; requires manual source attachment and review |
| `interactive_book.html` | Self-contained reading lenses, timed text preview, evidence-label practice and a visit-only reflection field |

This is 18 files including the manifest. Full source text stays in the source
entry even when a short visual card or brief uses an explicit excerpt. EPUB and
SSML exports reject U+FFFE/U+FFFF rather than silently altering the stored entry.
Source links remain unverified pointers. A planned step never becomes a
completed claim merely because it appears in an ebook or a video.

## 4. Render a rough video and narration preview

Add `--render-preview` to the pack command. This adds `preview.mp4`,
`narration.wav`, and `render_receipt.json`, for 21 files in the ZIP. A failed
optional render leaves no partially committed pack. Omit the flag if local
dependencies are unavailable.

The current renderer requires `ffmpeg` on PATH, the `drawtext` and `flite`
filters, the `libx264` encoder, and
`/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`. It does not install dependencies
or download fonts. Each FFmpeg call has a 45-second timeout. It uses fixed local
filenames, text files, a fixed filtergraph, disabled text expansion, and no
shell. Output is capped before bundling; the CLI caps a final artifact at 50 MiB.

The video is a 960-by-540, 24-fps text-card concept with the synthetic music bed.
It is visibly labeled as a concept animatic. There is no live-action footage,
character animation, voice clone or full music-film performance. The separate
narration uses FFmpeg's built-in generic `kal` voice, from the plain TXT script.
It does not consume the SSML file. The narration may run longer than the video;
neither the video nor its VTT claims to be synchronized to that narration.

The October 22 demo was actually rendered with FFmpeg 6.1.1. Its MP4 is 30.000
seconds, with H.264 video and mono AAC audio. The music WAV is 30.000 seconds,
16-bit mono PCM at 16 kHz. The narration WAV is 101.38725 seconds, 16-bit mono
PCM at 8 kHz. All three decode completely; four sampled video frames were
visually checked. Listening quality, browser behavior, ebook-reader rendering
and publication accessibility have not been independently established.

## 5. Review, adapt and measure

The compiler provides a repeatable starting edition. Develop selected drafts
with an assistant by attaching the exact source entry and handoff, then review
the returned work against evidence labels and the actual product objective.
An exported handoff is not a completed AI-to-AI cycle. Retain real execution
and review evidence before marking a returned artifact accepted.

Before a public release, review claims and sources, rights to selected external
assets, reading/listening quality, captions and keyboard/screen-reader use in
the target devices. When an experiment is ready, record actual distribution,
visits, consented outcomes and costs. Ad copy alone is not revenue evidence.
The [product studio plan](DIARY_PRODUCT_STUDIO.md) proposes small testable
editions and stage gates without assuming demand or setting unapproved prices.

Output commands refuse to overwrite files. Choose a fresh edition name for a
revision. Browser drafts, private local history, export bundles, the scheduled
briefing and public publication are distinct steps with explicit handoffs.

## Primary format references

- [W3C EPUB 3.3](https://www.w3.org/TR/epub-33/) defines the ebook container,
  package metadata, reading order and navigation. Structural checks here are
  not an EPUBCheck certification or a test of all reading systems.
- [W3C SSML 1.1](https://www.w3.org/TR/speech-synthesis11/) defines speech markup.
  The emitted source is separate from this milestone's plain-text Flite render.
- [W3C WebVTT](https://www.w3.org/TR/webvtt1/) defines timed text. Its current
  published document is a Candidate Recommendation Draft; these cues represent
  storyboard text, not automatically aligned speech captions.
- [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html) documents `drawtext`
  and `flite`. Local build capabilities, not website documentation alone,
  determine whether a render can run.
