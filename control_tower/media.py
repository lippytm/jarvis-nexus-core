"""Compile selected diary text into local media drafts; no model or network calls."""
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import io
import json
import math
import re
import struct
import wave
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

from control_tower.diary import diary_entry_digest, validate_diary_entry
from control_tower.network_contract import (
    _invalid_constant, _unique_object, canonical, digest, require_identifier, validate_draft,
)
from control_tower.portfolio import initiative

STATES = {
    "source_linked": "Source-linked record; source accuracy still requires review",
    "owner_reported": "Owner-reported; not independently verified",
    "planned": "Planned; not completed work",
    "fictional": "Fiction; not a factual event",
}
DURATIONS = (15, 30, 60)
SAMPLE_RATE = 16000


def _text_xml(value):
    # Valid JSON/UTF-8 can contain noncharacters excluded by XML 1.0.
    if any(ord(c) in (0xFFFE, 0xFFFF) for c in value):
        raise ValueError("diary text is not compatible with XML output")
    return escape(value, quote=True)


def _check_xml(value):
    if isinstance(value, str):
        _text_xml(value)
    elif isinstance(value, list):
        for item in value:
            _check_xml(item)
    elif isinstance(value, dict):
        for item in value.values():
            _check_xml(item)


def _md(value):
    value = escape(value, quote=False)
    return re.sub(r"([\\`*{}_\[\]()#+.!|>~-])", r"\\\1", value)


def _excerpt(value, limit=180):
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[:limit - 1].rstrip() + "…"


def _json_bytes(record):
    return (json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _zip_file(archive, name, content, compression=ZIP_DEFLATED):
    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = compression
    info.external_attr = 0o600 << 16
    archive.writestr(info, content)


def _edition_timestamp(value):
    if value is None:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value):
        raise ValueError("edition timestamp must be a UTC second")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise ValueError("invalid edition timestamp") from None
    return value


def _sources_markdown(entry):
    lines = ["## Source references", "", "Source links are supplied evidence pointers, not automatic verification.", ""]
    for source in entry["sources"]:
        # Escaped plain-text URLs cannot introduce Markdown/HTML commands.
        lines.extend([f"- {_md(source['source_id'])}: {_md(source['title'])}",
                      f"  {_md(source['url'])}"])
    return "\n".join(lines)


def _diary_markdown(entry):
    lines = [f"# {_md(entry['title'])}", "", f"Diary date: {entry['date']} — {entry['timezone']}",
             "", f"Initiative: {_md(entry['initiative_id'])}", "", "## Summary", "", _md(entry["summary"]), "",
             "The summary is supplied editorial context; individual records retain their evidence labels.", "", "## Records", ""]
    for item in entry["observations"]:
        lines.extend([f"### {_md(item['observation_id'])}", "", STATES[item["evidence_state"]], "", _md(item["text"]), "",
                      "Source IDs: " + (", ".join(_md(s) for s in item["source_ids"]) or "none"), ""])
    lines.extend(["## Next action", "", _md(entry["next_action"]), "", _sources_markdown(entry)])
    return "\n".join(lines) + "\n"


def _narration(entry):
    parts = ["Jarvis Life and Business Diary. Draft narration preview.", entry["title"],
             "Diary date: " + entry["date"] + ".", "Supplied editorial summary: " + entry["summary"],
             "The following records retain their original evidence labels."]
    for item in entry["observations"]:
        parts.extend([STATES[item["evidence_state"]] + ".", item["text"]])
    parts.extend(["Proposed next action.", entry["next_action"],
                  "Source references and evidence labels are included in the companion book. This draft does not establish publication, sales, or a completed film."])
    return parts


def _epub(entry, product_id, entry_hash, timestamp):
    text = lambda value: _text_xml(value)
    paragraphs = [f"<h1>{text(entry['title'])}</h1>",
                  f"<p>Diary date: {entry['date']}. Selected diary edition.</p>",
                  "<p>Draft adaptation. Evidence labels describe the supplied record; they do not authenticate a source or prove a claim.</p>",
                  f"<h2>Editorial summary</h2><p>{text(entry['summary'])}</p>", "<h2>Diary records</h2>"]
    for item in entry["observations"]:
        paragraphs.extend([f"<h3>{text(item['observation_id'])}</h3>",
                           f"<p><strong>{text(STATES[item['evidence_state']])}</strong></p>",
                           f"<p>{text(item['text'])}</p>",
                           "<p>Source IDs: " + text(", ".join(item["source_ids"]) or "none") + "</p>"])
    paragraphs.extend(["<h2>Learning and reflection</h2>",
        f"<p>Proposed learning goal: {text(entry['media_notes']['learning_goal'] or 'Distinguish a source-linked record from a plan and a fictional adaptation.')}</p>",
        "<p>Choose one record. Explain what its evidence label establishes, what it leaves uncertain, and which source or observation would help you check it.</p>",
        "<h2>Next action</h2>", f"<p>{text(entry['next_action'])}</p>", "<h2>Sources</h2>"])
    for source in entry["sources"]:
        paragraphs.append(f"<p>{text(source['source_id'])}: {text(source['title'])}<br/><a href=\"{text(source['url'])}\">{text(source['url'])}</a></p>")
    xhtml = '<?xml version="1.0" encoding="UTF-8"?>\n<html xmlns="http://www.w3.org/1999/xhtml" lang="en" xml:lang="en"><head><title>' + text(entry["title"]) + '</title></head><body>' + "\n".join(paragraphs) + '</body></html>'
    identifier = "urn:sha256:" + digest({"product_id": product_id, "entry_sha256": entry_hash})
    package = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="publication-id" version="3.0" xml:lang="en">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="publication-id">{identifier}</dc:identifier><dc:title>{text(entry['title'])}</dc:title><dc:language>en</dc:language><dc:creator>Jarvis diary drafting tools</dc:creator><meta property="dcterms:modified">{timestamp}</meta></metadata>
<manifest><item id="book" href="book.xhtml" media-type="application/xhtml+xml"/><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/></manifest><spine><itemref idref="book"/></spine></package>'''
    nav = '''<?xml version="1.0" encoding="UTF-8"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en"><head><title>Contents</title></head><body><nav epub:type="toc" id="toc"><h1>Contents</h1><ol><li><a href="book.xhtml">Diary, records, reflection and sources</a></li></ol></nav></body></html>'''
    container = '''<?xml version="1.0" encoding="UTF-8"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="EPUB/package.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'''
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        _zip_file(archive, "mimetype", b"application/epub+zip", ZIP_STORED)
        for name, content in (("META-INF/container.xml", container), ("EPUB/package.opf", package), ("EPUB/nav.xhtml", nav), ("EPUB/book.xhtml", xhtml)):
            _zip_file(archive, name, content.encode())
    return buffer.getvalue()


def music_bed(duration_seconds):
    if type(duration_seconds) is not int or duration_seconds not in DURATIONS:
        raise ValueError("duration must be 15, 30 or 60 seconds")
    # A newly authored simple oscillator sequence; no sampled recording or voice.
    notes = (261.6256, 329.6276, 391.9954, 293.6648, 349.2282, 440.0, 391.9954, 329.6276)
    samples = bytearray()
    for index in range(duration_seconds * SAMPLE_RATE):
        t = index / SAMPLE_RATE
        beat = int(t / 0.5)
        local = t % 0.5
        envelope = min(1.0, local / 0.025, (0.5 - local) / 0.10)
        overall = min(1.0, t / 0.5, (duration_seconds - t) / 1.0)
        frequency = notes[beat % len(notes)]
        signal = (math.sin(2 * math.pi * frequency * t) + 0.3 * math.sin(4 * math.pi * frequency * t))
        value = int(32767 * 0.11 * envelope * overall * signal)
        samples.extend(struct.pack("<h", value))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(samples)
    return buffer.getvalue()


def _timed_cues(entry, duration):
    source_items = [o for o in entry["observations"] if o["evidence_state"] != "fictional"]
    items = [source_items[i] if len(source_items) > i else None for i in range(2)]
    texts = ["JARVIS DAILY DIARY\n" + _excerpt(entry["title"], 120)]
    for item in items:
        texts.append((STATES[item["evidence_state"]] + "\n" + _excerpt(item["text"], 180)) if item else "CREATIVE DEVELOPMENT\nA recorded idea still needs evidence and review.")
    texts.append("NEXT ACTION — PLANNED\n" + _excerpt(entry["next_action"], 180))
    return [{"cue_id": f"scene-{i + 1:02d}", "start_ms": i * duration * 250,
             "end_ms": (i + 1) * duration * 250, "text": value,
             "source_observation_ids": ([items[i - 1]["observation_id"]] if i in (1, 2) and items[i - 1] else []),
             "role": "title" if i == 0 else "next_action" if i == 3 else "record"}
            for i, value in enumerate(texts)]


def _vtt(cues):
    def clock(ms):
        seconds, milliseconds = divmod(ms, 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
    return "WEBVTT\n\nNOTE Storyboard text cues; not forced-aligned speech captions.\n\n" + "\n\n".join(
        f"{cue['cue_id']}\n{clock(cue['start_ms'])} --> {clock(cue['end_ms'])}\n{escape(cue['text'])}" for cue in cues) + "\n"


def _interactive_html(entry, cues):
    data = {"title": entry["title"], "date": entry["date"], "summary": entry["summary"],
            "observations": entry["observations"], "sources": entry["sources"], "cues": cues,
            "states": STATES, "learning_goal": entry["media_notes"]["learning_goal"]}
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True).replace("<", "\\u003c")
    template = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; img-src 'none'; media-src 'none'; base-uri 'none'; form-action 'none'"><title>Jarvis Diary — Interactive edition</title>
<style>body{font:18px/1.6 system-ui,sans-serif;background:#101728;color:#edf2fc;margin:0}main{max-width:900px;margin:auto;padding:28px}h1{line-height:1.15;font-size:clamp(2rem,6vw,3.6rem)}h2{color:#a7dfef}a{color:#9be2f0}button,select,textarea{font:inherit;border:1px solid #8393b5;border-radius:8px;padding:10px;background:#18253d;color:inherit}button{cursor:pointer;margin:5px 6px 5px 0}button:focus-visible,select:focus-visible,textarea:focus-visible,a:focus-visible{outline:3px solid #ffcd7d;outline-offset:3px}section,article{border:1px solid #41516c;border-radius:14px;padding:22px;margin:20px 0}textarea{width:100%;box-sizing:border-box;min-height:130px}.note{color:#bdcbe1}.badge{color:#ffcd7d;font-weight:700}#stage{white-space:pre-wrap;min-height:150px;font-size:1.3rem}#feedback{min-height:2em}.skip{position:absolute;left:-9999px}.skip:focus{left:12px;top:12px;background:#101728;padding:10px}.sources a{overflow-wrap:anywhere}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}</style></head>
<body><a class="skip" href="#main">Skip to content</a><main id="main" tabindex="-1"><p class="badge">JARVIS / INTERACTIVE DIARY EDITION</p><h1 id="title"></h1><p id="summary"></p><p class="note">Draft teaching resource. Classifying a diary label is not independent fact-checking or proof of learning. This page keeps no persistent answers.</p>
<section><h2>Choose a reading lens</h2><label for="lens">Record type</label> <select id="lens"><option value="all">All records</option><option value="source_linked">Source-linked</option><option value="owner_reported">Owner-reported</option><option value="planned">Planned</option><option value="fictional">Fictional</option></select><div id="records"></div></section>
<section><h2>Timed storyboard</h2><p class="note">Text-only concept preview; no video footage, speech or music is played by this page.</p><div id="stage" role="region" aria-label="Storyboard scene"></div><button id="play" type="button">Play text preview</button><button id="pause" type="button">Pause</button><button id="reset" type="button">Restart</button><p id="play-status" role="status"></p></section>
<section><h2>Practice reading evidence labels</h2><p id="question"></p><label for="answer">How is this record labeled?</label> <select id="answer"><option value="source_linked">Source-linked</option><option value="owner_reported">Owner-reported</option><option value="planned">Planned</option><option value="fictional">Fictional</option></select><div><button id="check" type="button">Check label</button><button id="next" type="button">Next record</button></div><p id="feedback" role="status"></p><label for="reflection">What would you check before presenting this as fact?</label><textarea id="reflection" spellcheck="true"></textarea><p class="note">Reflection is private to this visit and disappears on reload. No automatic grading or data submission.</p></section>
<section class="sources"><h2>Source references</h2><p class="note">Opening a source is a separate navigation. References have not been reverified by this page.</p><div id="sources"></div></section></main>
<script type="application/json" id="diary-data">__DIARY_DATA__</script>
<script id="media-helper">"use strict";globalThis.JarvisDiaryPlayer=Object.freeze({selectRecords(records,lens){if(!["all","source_linked","owner_reported","planned","fictional"].includes(lens))throw new Error("Unknown lens");return records.filter(r=>lens==="all"||r.evidence_state===lens);},cueAt(cues,milliseconds){if(!Number.isFinite(milliseconds)||milliseconds<0)throw new Error("Invalid time");return cues.find(c=>milliseconds>=c.start_ms&&milliseconds<c.end_ms)||null;},checkLabel(record,answer){if(!["source_linked","owner_reported","planned","fictional"].includes(answer))throw new Error("Invalid answer");return {matches:record.evidence_state===answer,evidenceState:record.evidence_state,meaning:"This checks the recorded label, not the truth of the claim."};}});</script>
<script>"use strict";(()=>{const d=JSON.parse(document.getElementById("diary-data").textContent),h=globalThis.JarvisDiaryPlayer,$=id=>document.getElementById(id);$("title").textContent=d.title;$("summary").textContent=d.summary;function records(){const box=$("records");box.replaceChildren();for(const r of h.selectRecords(d.observations,$("lens").value)){const a=document.createElement("article"),label=document.createElement("p"),p=document.createElement("p"),refs=document.createElement("p");label.className="badge";label.textContent=d.states[r.evidence_state];p.textContent=r.text;refs.textContent="Source IDs: "+(r.source_ids.join(", ")||"none");a.append(label,p,refs);box.append(a);}if(!box.childElementCount)box.textContent="No records with this label.";}$("lens").addEventListener("change",records);records();for(const s of d.sources){const p=document.createElement("p"),a=document.createElement("a");a.textContent=s.source_id+": "+s.title;a.href=s.url;a.target="_blank";a.rel="noopener noreferrer";p.append(a);$("sources").append(p);}let qi=0;function question(){ $("question").textContent=d.observations[qi].text;$("feedback").textContent="";}question();$("check").addEventListener("click",()=>{const r=h.checkLabel(d.observations[qi],$("answer").value);$("feedback").textContent=(r.matches?"The label matches. ":"Review the label: "+d.states[r.evidenceState]+". ")+r.meaning;});$("next").addEventListener("click",()=>{qi=(qi+1)%d.observations.length;question();});let elapsed=0,last=0,raf=null;const end=d.cues[d.cues.length-1].end_ms;function stage(){const c=h.cueAt(d.cues,Math.min(elapsed,end-1));$("stage").textContent=c?c.text:"";}function stop(){if(raf!==null)cancelAnimationFrame(raf);raf=null;}function tick(now){elapsed=Math.min(end,elapsed+now-last);last=now;stage();if(elapsed<end)raf=requestAnimationFrame(tick);else{raf=null;$("play-status").textContent="Preview complete.";}}$("play").addEventListener("click",()=>{if(raf!==null)return;if(elapsed>=end)elapsed=0;last=performance.now();$("play-status").textContent="Playing text preview.";raf=requestAnimationFrame(tick);});$("pause").addEventListener("click",()=>{stop();$("play-status").textContent="Paused.";});$("reset").addEventListener("click",()=>{stop();elapsed=0;stage();$("play-status").textContent="Ready.";});stage();})();</script></body></html>'''
    return template.replace("__DIARY_DATA__", encoded).encode()


def build_media_files(entry, *, product_id, source_revision, target="chatgpt", duration_seconds=30, edition_timestamp=None):
    entry = validate_diary_entry(entry)
    if entry["visibility"] != "public_candidate":
        raise ValueError("media export requires an explicitly selected public_candidate entry")
    _check_xml(entry)
    require_identifier(product_id, "product ID")
    if len(product_id) > 48:
        raise ValueError("product ID exceeds 48 characters")
    if not isinstance(source_revision, str) or not re.fullmatch(r"[a-f0-9]{40}", source_revision):
        raise ValueError("source revision must be a lowercase commit hash")
    if type(duration_seconds) is not int or duration_seconds not in DURATIONS:
        raise ValueError("duration must be 15, 30 or 60 seconds")
    timestamp = _edition_timestamp(edition_timestamp)
    entry_hash = diary_entry_digest(entry)
    item = initiative(entry["initiative_id"])
    diary = _diary_markdown(entry)
    parts = _narration(entry)
    narration = "\n\n".join(parts) + "\n"
    ssml = '<?xml version="1.0" encoding="UTF-8"?>\n<speak xmlns="http://www.w3.org/2001/10/synthesis" version="1.1" xml:lang="en-US">' + "".join("<p>" + _text_xml(p) + "</p>" for p in parts) + "</speak>\n"
    cues = _timed_cues(entry, duration_seconds)
    scene_lines = ["# Documentary script draft", "", "Records keep their original labels. Supplied summaries are editorial context. Planned or fictional material must be visibly identified in any production.", ""]
    for index, observation in enumerate(entry["observations"], 1):
        scene_lines.extend([f"## Scene {index}: {_md(observation['observation_id'])}", "",
            "Evidence treatment: " + STATES[observation["evidence_state"]], "",
            "Narration draft: " + _md(observation["text"]), "",
            "Visual: use a reviewed, permitted source artifact or a clearly labeled text card; no footage is supplied.", "",
            "Source IDs: " + (", ".join(observation["source_ids"]) or "none"), ""])
    scene_lines.append(_sources_markdown(entry))
    trailer = ["# Trailer concept and text cues", "", f"Planned duration: {duration_seconds} seconds. The accompanying VTT is storyboard text, not aligned speech captions.", ""]
    for cue in cues:
        trailer.extend([f"## {cue['cue_id']}: {cue['start_ms'] / 1000:g}–{cue['end_ms'] / 1000:g} seconds", "", _md(cue["text"]), ""])
    fiction = "\n".join(["# The Workshop of Possible Tomorrows", "", "## Fictional movie treatment", "",
        "This is an original fictional metaphor inspired by a project diary. Its people, scenes and dialogue are invented. It is not a documentary account of the owner's life.", "",
        "Logline: An apprentice archivist enters a workshop of possible worlds and discovers that the door worth opening is the one whose promise can be checked.", "",
        "### Scene 1 — The corridor", "A corridor branches into luminous rooms, each holding an unfinished invention. Mira carries a notebook whose pages rearrange whenever a new idea arrives.", "",
        "### Scene 2 — The workshop", "A patient mechanical guide asks Mira to choose one page. They mark what is known, what is hoped for, and what belongs only to a story. One doorway becomes steady enough to enter.", "",
        "### Scene 3 — The return", "Mira returns with a small working artifact and an honest account of its limits. The corridor is still vast. She leaves a bookmark at the next door.", "",
        "Source inspiration: " + _md(entry["title"]), "", "Production needs: original or permitted visuals, performances, sound design, editorial review and accessibility work. No filmed performances are included.", ""])
    music = "\n".join(["# A Page Becomes a Path", "", "## Original music-film concept", "",
        "Fictional creative lyric draft and abstract visual treatment, not an account of the owner's life. These lines are newly authored for the template and do not imitate a named artist. The WAV is a simple synthesized instrumental preview, with no recorded samples or vocals.", "",
        "### Verse", "A page becomes a path tonight,", "A question finds a little light.", "We keep the things we know in view,", "And mark the dreams we still pursue.", "",
        "### Chorus", "One clear step, one open door,", "Build a little, learn some more.", "Leave a note for where we start,", "Make tomorrow with a careful heart.", "",
        "Visual plan: an abstract corridor, a turning page, a workbench and a returning bookmark. The optional rendered preview uses text cards; it does not include these filmed scenes.", "",
        f"Instrumental preview: {duration_seconds} seconds, mono PCM, {SAMPLE_RATE} Hz. Review sound quality, composition, asset provenance and accessibility before distribution.", ""])
    claims = [o for o in entry["observations"] if o["evidence_state"] == "source_linked"]
    ad = ["# Ad-copy development draft", "", "Local editorial draft; no publication, offer validation or revenue is established. Source-linked statements still need factual review.", "",
          "## Headline options", "", "- Turn today's work into tomorrow's useful resource.", "- Give your ideas a source, a next step and a clear record.", "- Explore a project diary that can become a teaching resource.", "",
          "## Source-linked claim candidates", ""]
    for claim in claims:
        ad.extend(["Project record: " + _md(claim["text"]), "Sources: " + ", ".join(claim["source_ids"]), ""])
    if not claims:
        ad.append("No source-linked claims are available. Keep this as a campaign concept until evidence is supplied.")
    ad.extend(["", "## Proposed call to action", "", _md(entry["media_notes"]["call_to_action"] or "Review the resource and its source notes."), "",
        "## Destination and measurement", "", "Initiative: " + _md(item["title"]), "Destination state: " + item["destination"]["state"],
        "Configured references: " + (_md(" | ".join(item["destination"]["urls"])) or "unassigned"), "",
        "Review the real offer, permitted assets, factual claims, disclosures and destination before publication. Record actual visits, consented inquiries, purchases, refunds and confirmed commissions separately when authorized records exist. Current revenue and conversion metrics: unavailable.", ""])
    handoff = validate_draft({"schema_version": 1, "kind": "jarvis.draft", "project_id": item["project_id"], "target": target,
        "text": "\n".join(["JARVIS DIARY MEDIA HANDOFF — editorial draft only", f"Product: {product_id}; diary digest: {entry_hash}",
            f"Source context: {source_revision}", "Goal: adapt the explicitly selected diary into a reviewed multimedia resource.",
            "Source material: source_entry.json in this pack. Attach the exact selected entry with the stated digest; this handoff does not contain the full diary or retrieve it automatically.",
            "Title: " + entry["title"], "Audience: " + entry["media_notes"]["audience"],
            "Learning goal: " + entry["media_notes"]["learning_goal"],
            "Preserve source-linked, owner-reported, planned and fictional labels. A source URL is not verification.",
            "Prepare documentary narration, trailer beats, a clearly fictional movie treatment, an original music-film concept, an ebook outline, narration, an interactive lesson and factual ad-copy candidates.",
            "Keep private records out of public material; check asset rights and factual claims. Do not claim completed filming, voice rights, publication, demand, sales or commissions. No account action, purchase, provider call or publication is authorized by this packet."])})
    readme = f"""# Jarvis Diary Media Pack

Product: {product_id}
Source diary: {entry['entry_id']}
Source diary SHA-256: {entry_hash}
Edition timestamp: {timestamp}

This locally compiled draft pack adapts an explicitly selected public-candidate entry. The entry's source labels are preserved; neither links nor hashes authenticate claims. No external model or provider was called.

Open interactive_book.html for the interactive text edition. book.epub is a real packaged EPUB with diary records, reflection and sources. narration.txt and narration.ssml are narration source files, not audio. music_bed.wav is a newly synthesized instrumental preview. Documentary, trailer, fictional movie, music-film and ad-copy files are editable production drafts. trailer_text.vtt contains storyboard text cues, not speech alignment. An optional separate render command can create a text-card MP4 and generic synthetic narration WAV when local FFmpeg filters are available.

No movie footage, actors, cloned voices, paid memberships, sales or commissions are supplied. The paused Studio Work Cycle is not resumed by compiling this pack. Review factual claims, source and asset permissions, typography, captions and actual reader/player behavior before release. Reflections in the HTML are visit-only and are not saved.
"""
    files = {"README.md": readme.encode(), "source_entry.json": _json_bytes(entry), "diary.md": diary.encode(),
        "ebook.md": (diary + "\n## Reflection exercise\n\n" + _md(entry["media_notes"]["learning_goal"] or "Distinguish evidence labels and identify what needs checking.") + "\n\nChoose one record and explain what would substantiate it.\n").encode(),
        "book.epub": _epub(entry, product_id, entry_hash, timestamp), "narration.txt": narration.encode(), "narration.ssml": ssml.encode(),
        "documentary.md": "\n".join(scene_lines).encode(), "trailer.md": "\n".join(trailer).encode(),
        "trailer_cues.json": _json_bytes({"schema_version": 1, "kind": "jarvis.storyboard_cues", "duration_seconds": duration_seconds, "cues": cues, "source_entry_sha256": entry_hash}),
        "trailer_text.vtt": _vtt(cues).encode(), "movie_treatment.md": fiction.encode(), "music_film.md": music.encode(),
        "music_bed.wav": music_bed(duration_seconds), "ad_copy.md": "\n".join(ad).encode(), "media_handoff.json": _json_bytes(handoff),
        "interactive_book.html": _interactive_html(entry, cues)}
    manifest = {"schema_version": 1, "kind": "jarvis.media_manifest", "product_id": product_id,
        "source_entry_id": entry["entry_id"], "source_entry_sha256": entry_hash, "source_context_revision": source_revision,
        "initiative_id": entry["initiative_id"], "project_id": item["project_id"], "edition_timestamp": timestamp,
        "state": "local_draft_pack", "source_verification": "not_performed_by_compiler", "publication_approval": "not_granted",
        "actual_revenue": None, "model_calls": 0, "external_actions": 0,
        "files": [{"path": name, "bytes": len(content), "sha256": sha256(content).hexdigest()} for name, content in sorted(files.items())]}
    manifest["manifest_sha256"] = digest(manifest)
    files["manifest.json"] = _json_bytes(manifest)
    return files


def bundle_media(files, *, previews=None):
    """Package only fixed local output names; reject foreign/path-like additions."""
    expected = {"README.md", "source_entry.json", "diary.md", "ebook.md", "book.epub", "narration.txt", "narration.ssml",
        "documentary.md", "trailer.md", "trailer_cues.json", "trailer_text.vtt", "movie_treatment.md", "music_film.md",
        "music_bed.wav", "ad_copy.md", "media_handoff.json", "interactive_book.html", "manifest.json"}
    if not isinstance(files, dict) or set(files) != expected or any(not isinstance(v, bytes) for v in files.values()):
        raise ValueError("unexpected media output set")
    files = dict(files)
    def record(content):
        if len(content) > 65536:
            raise ValueError("invalid media evidence record")
        try:
            value = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object,
                               parse_constant=_invalid_constant)
            if type(value) is not dict:
                raise ValueError("not an object")
            canonical(value)
            return value
        except (ValueError, UnicodeError, RecursionError):
            raise ValueError("invalid media evidence record") from None

    def file_records(values):
        return [{"path": name, "bytes": len(value), "sha256": sha256(value).hexdigest()}
                for name, value in sorted(values.items())]

    manifest = record(files["manifest.json"])
    manifest_content = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    expected_records = file_records({key: value for key, value in files.items() if key != "manifest.json"})
    if (manifest.get("manifest_sha256") != digest(manifest_content)
            or canonical(manifest.get("files")) != canonical(expected_records)):
        raise ValueError("media manifest does not match pack files")
    if previews is not None:
        if not isinstance(previews, dict) or set(previews) != {"preview.mp4", "narration.wav", "render_receipt.json"} or any(not isinstance(v, bytes) for v in previews.values()):
            raise ValueError("unexpected preview output set")
        receipt = record(previews["render_receipt.json"])
        receipt_keys = {"schema_version", "kind", "source_entry_sha256", "source_context_revision", "preview_kind",
                        "expected_video_duration_seconds", "narration_kind", "speech_alignment", "external_actions", "model_calls", "files"}
        if (set(receipt) != receipt_keys or type(receipt["schema_version"]) is not int or receipt["schema_version"] != 1
                or receipt["kind"] != "jarvis.media_render_receipt"
                or receipt["preview_kind"] != "text_card_concept_animatic"
                or receipt["narration_kind"] != "rough_generic_flite_kal_voice"
                or receipt["speech_alignment"] != "not_implemented; storyboard text cues are separate"
                or any(type(receipt[key]) is not int or receipt[key] != 0 for key in ("external_actions", "model_calls"))):
            raise ValueError("invalid preview render receipt")
        if receipt["source_entry_sha256"] != manifest.get("source_entry_sha256") or receipt["source_context_revision"] != manifest.get("source_context_revision"):
            raise ValueError("preview source does not match media pack")
        cues = record(files["trailer_cues.json"])
        duration = receipt["expected_video_duration_seconds"]
        if type(duration) is not int or duration not in DURATIONS or duration != cues.get("duration_seconds"):
            raise ValueError("preview duration does not match media pack")
        expected_preview_records = file_records({name: previews[name] for name in ("preview.mp4", "narration.wav")})
        if canonical(receipt["files"]) != canonical(expected_preview_records):
            raise ValueError("preview receipt does not match rendered files")
        files.update(previews)
        manifest["optional_preview"] = "rendered_text_card_animatic_and_generic_narration"
        manifest["files"] = file_records({name: content for name, content in files.items() if name != "manifest.json"})
        manifest.pop("manifest_sha256")
        manifest["manifest_sha256"] = digest(manifest)
        files["manifest.json"] = _json_bytes(manifest)
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in sorted(files.items()):
            _zip_file(archive, name, content)
    return buffer.getvalue()
