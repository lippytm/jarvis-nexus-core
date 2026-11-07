# Public diary example

`public-project-entry.json` is a deliberately public-candidate record about the
Jarvis portfolio expansion at commit
`e645c64975dc05f3b0a0f9e06d7cc903d70031b0`. Its references identify the public
commit and the successful push workflow run `39859645675`. The reported 163
Python tests and 68 web-helper cases belong to that exact previous milestone.
They are not the test totals for the later diary code.

The record contains two source-linked observations and one planned next step.
Its summary and creative directions are editorial context. It does not describe
private daily activities, authenticate an author, prove a live connector, or
report revenue. Source links are pointers for review, not an automatic truth
check. This October 22 record must not be presented as activity on another date.

`public-briefing.json` is the actual audience-filtered projection of this entry.
It is a reusable data example for a daily briefing, not an automatically
synchronized record from the user's private journal.

From the repository root:

```bash
python scripts/jarvis_diary.py validate --entry-file examples/diary/public-project-entry.json
python scripts/jarvis_diary.py briefing --entry-file examples/diary/public-project-entry.json --date 2026-10-22 --out reports/public-diary-briefing.json
python scripts/jarvis_diary.py pack --entry-file examples/diary/public-project-entry.json --product jarvis-diary-media-demo --source-revision e645c64975dc05f3b0a0f9e06d7cc903d70031b0 --duration 30 --render-preview --out reports/diary-demo.zip
```

The optional render needs the local FFmpeg build and font described in the
[runbook](../../docs/DIARY_MEDIA_RUNBOOK.md). Omitting `--render-preview` creates
the 18-file standard-library pack, including the actual EPUB and music WAV.
Rendered packs contain 21 files. Commands refuse existing output paths. Use a
fresh filename for another edition; the edition timestamp records when it was
compiled, while the diary date remains the supplied source date.

The binary demo deliverables are distributed separately. Their render metadata
and hashes are retained in `docs/evidence/diary-media-render.json`. No private
database, diary entry or binary media file is committed by this example.
