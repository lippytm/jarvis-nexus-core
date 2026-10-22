"""Bounded diary records and deterministic local briefings; no inferred facts.

Visibility is an export filter, not publication approval or a sensitive-data scan.
Source links retain the author's evidence state and are never fetched or verified.
"""
from copy import deepcopy
from datetime import date as calendar_date
import re

from control_tower.network_contract import MAX_PACKET_BYTES, canonical, digest, identifier
from control_tower.portfolio import INITIATIVES
from control_tower.validation import valid_https_url


DIARY_TIMEZONE = "America/Los_Angeles"
MAX_BRIEFING_ENTRIES = 7
MAX_INPUT_ENTRIES = 1000
VISIBILITIES = frozenset({"private", "internal", "public_candidate"})
EVIDENCE_STATES = frozenset({"source_linked", "owner_reported", "planned", "fictional"})
MEDIA_NOTE_KEYS = frozenset({"audience", "visual_style", "audio_style", "learning_goal", "call_to_action"})
ENTRY_KEYS = frozenset({"schema_version", "kind", "entry_id", "date", "timezone", "initiative_id", "title",
                        "visibility", "summary", "observations", "sources", "next_action", "media_notes"})


def _record(value, keys):
    if type(value) is not dict or set(value) != set(keys) or any(type(key) is not str for key in value):
        raise ValueError("invalid diary record fields")


def _text(value, limit, *, blank=False):
    if type(value) is not str or len(value) > limit:
        raise ValueError("invalid diary text")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError:
        raise ValueError("invalid diary text") from None
    if (len(encoded) > limit or any(ord(char) < 32 and char not in "\t\r\n" for char in value)
            or (not blank and not value.strip())):
        raise ValueError("invalid diary text")


def _identifier(value):
    if type(value) is not str or len(value) > 48 or not identifier(value):
        raise ValueError("invalid diary identifier")


def _date(value):
    if type(value) is not str or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        raise ValueError("invalid diary date")
    try:
        if calendar_date.fromisoformat(value).isoformat() != value:
            raise ValueError("invalid diary date")
    except ValueError:
        raise ValueError("invalid diary date") from None


def validate_diary_entry(entry):
    """Validate the exact v1 contract and return a fully independent JSON object."""
    _record(entry, ENTRY_KEYS)
    if type(entry["schema_version"]) is not int or entry["schema_version"] != 1:
        raise ValueError("unsupported diary schema")
    if type(entry["kind"]) is not str or entry["kind"] != "jarvis.diary_entry":
        raise ValueError("unsupported diary schema")
    _identifier(entry["entry_id"])
    _date(entry["date"])
    if type(entry["timezone"]) is not str or entry["timezone"] != DIARY_TIMEZONE:
        raise ValueError("unsupported diary timezone")
    if type(entry["initiative_id"]) is not str or entry["initiative_id"] not in INITIATIVES:
        raise ValueError("unknown diary initiative")
    if type(entry["visibility"]) is not str or entry["visibility"] not in VISIBILITIES:
        raise ValueError("invalid diary visibility")
    _text(entry["title"], 180)
    _text(entry["summary"], 3000)
    _text(entry["next_action"], 1500)
    _record(entry["media_notes"], MEDIA_NOTE_KEYS)
    for value in entry["media_notes"].values():
        _text(value, 600, blank=True)
    sources = entry["sources"]
    if type(sources) is not list or len(sources) > 5:
        raise ValueError("invalid diary sources")
    source_ids = set()
    for source in sources:
        _record(source, {"source_id", "title", "url"})
        _identifier(source["source_id"])
        if source["source_id"] in source_ids:
            raise ValueError("duplicate diary source identifier")
        source_ids.add(source["source_id"])
        _text(source["title"], 200)
        _text(source["url"], 1000)
        if not valid_https_url(source["url"]):
            raise ValueError("invalid diary source URL")
    observations = entry["observations"]
    if type(observations) is not list or not 1 <= len(observations) <= 8:
        raise ValueError("invalid diary observations")
    observation_ids = set()
    for observation in observations:
        _record(observation, {"observation_id", "text", "evidence_state", "source_ids"})
        _identifier(observation["observation_id"])
        if observation["observation_id"] in observation_ids:
            raise ValueError("duplicate diary observation identifier")
        observation_ids.add(observation["observation_id"])
        _text(observation["text"], 1000)
        if type(observation["evidence_state"]) is not str or observation["evidence_state"] not in EVIDENCE_STATES:
            raise ValueError("invalid diary evidence state")
        references = observation["source_ids"]
        if type(references) is not list or len(references) > 5:
            raise ValueError("invalid diary source references")
        seen = set()
        for reference in references:
            _identifier(reference)
            if reference in seen or reference not in source_ids:
                raise ValueError("invalid diary source references")
            seen.add(reference)
        if observation["evidence_state"] == "source_linked" and not references:
            raise ValueError("source-linked observation requires a source")
    if len(canonical(entry)) > MAX_PACKET_BYTES:
        raise ValueError("diary packet exceeds 64 KiB")
    return deepcopy(entry)


def diary_entry_digest(entry):
    """Content integrity only; does not authenticate authors, sources or claims."""
    return digest(validate_diary_entry(entry))


def _excerpt(value, limit):
    encoded = value.encode("utf-8")
    return encoded[:limit].decode("utf-8", errors="ignore"), len(encoded) > limit


def _brief_entry(entry):
    summary, summary_truncated = _excerpt(entry["summary"], 400)
    action, action_truncated = _excerpt(entry["next_action"], 240)
    observations = []
    for observation in entry["observations"][:3]:
        text, truncated = _excerpt(observation["text"], 160)
        observations.append({"observation_id": observation["observation_id"], "text_excerpt": text,
                             "text_truncated": truncated, "evidence_state": observation["evidence_state"],
                             "source_ids": list(observation["source_ids"])})
    sources = []
    for source in entry["sources"]:
        title, truncated = _excerpt(source["title"], 80)
        sources.append({"source_id": source["source_id"], "title_excerpt": title,
                        "title_truncated": truncated, "url": source["url"]})
    return {"entry_id": entry["entry_id"], "initiative_id": entry["initiative_id"], "title": entry["title"],
            "visibility": entry["visibility"], "summary_excerpt": summary, "summary_truncated": summary_truncated,
            "next_action_excerpt": action, "next_action_truncated": action_truncated,
            "evidence_states": sorted({row["evidence_state"] for row in entry["observations"]}),
            "observations": observations, "observations_omitted": len(entry["observations"]) - len(observations),
            "sources": sources}


def build_diary_briefing(entries, *, diary_date, audience="public"):
    """Select a date and audience before constructing any content or digest.

    Public output includes public_candidate entries only. Owner output is an
    explicit request for all visibilities. No hidden-entry count/ID/hash is emitted.
    All supplied entries are validated; errors never echo private values.
    """
    _date(diary_date)
    if type(audience) is not str or audience not in {"public", "owner"}:
        raise ValueError("invalid diary briefing audience")
    if type(entries) not in (list, tuple) or len(entries) > MAX_INPUT_ENTRIES:
        raise ValueError("invalid diary briefing entries")
    selected, seen = [], set()
    for value in entries:
        entry = validate_diary_entry(value)
        if entry["entry_id"] in seen:
            raise ValueError("duplicate diary entry identifier")
        seen.add(entry["entry_id"])
        if entry["date"] == diary_date and (audience == "owner" or entry["visibility"] == "public_candidate"):
            selected.append(entry)
    if len(selected) > MAX_BRIEFING_ENTRIES:
        raise ValueError("at most seven eligible daily diary entries")
    result = {"schema_version": 1, "kind": "jarvis.diary_briefing", "date": diary_date,
              "timezone": DIARY_TIMEZONE, "audience": audience,
              "status": "ready" if selected else "no_eligible_entry",
              "entries": [_brief_entry(entry) for entry in sorted(selected, key=lambda entry: entry["entry_id"])],
              "entry_count": len(selected), "publication_approval": "not_granted",
              "source_verification": "not_performed", "external_actions": 0}
    result["briefing_sha256"] = digest(result)
    if len(canonical(result)) > MAX_PACKET_BYTES:
        raise ValueError("diary briefing exceeds 64 KiB")
    return result
