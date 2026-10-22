"""Deterministic original RPG episode drafts from one explicitly selected diary.

No provider calls, current-news claims, completed quests, earnings or publication.
Hashes identify supplied content; neither an author nor a source is authenticated.
"""
from copy import deepcopy
import re

from control_tower.diary import (DIARY_TIMEZONE, EVIDENCE_STATES, VISIBILITIES,
    _date, _identifier, _text, diary_entry_digest, validate_diary_entry)
from control_tower.network_contract import MAX_PACKET_BYTES, canonical, digest
from control_tower.portfolio import INITIATIVES
from control_tower.validation import valid_https_url


WORLD_IDS = ("archive", "forge", "observatory")
QUEST_IDS = ("hostinger-connection", "ai-building-cycle", "media-review")
FICTIONAL_FRAMING = "Original fictional setting; project records and plans retain their labels."
NEWS_STATUS = "not_included_in_this_project_pilot"
EPISODE_KEYS = frozenset({"schema_version", "kind", "episode_id", "date", "timezone", "title",
    "audience", "source_visibility", "source_entry_sha256", "source_context_revision", "sources",
    "worlds", "scenes", "quests", "observations_omitted", "news_status", "fictional_framing",
    "publication_approval", "external_actions", "model_calls", "episode_sha256"})
SCENE_KEYS = frozenset({"scene_id", "title", "voiceover", "screen_text", "evidence_state", "source_ids", "world_id"})
QUEST_KEYS = frozenset({"quest_id", "title", "objective", "status", "evidence_state", "source_ids", "world_id"})

_WORLDS = (
    {"world_id": "archive", "title": "The Lantern Archive",
     "description": "An original fictional command library for diary records, source references and creative editions."},
    {"world_id": "forge", "title": "The Copper Forge",
     "description": "An original fictional workshop for proposed tools, learning projects and small experiments."},
    {"world_id": "observatory", "title": "The Sky Observatory",
     "description": "An original fictional lookout for reviewing access, evidence gaps and the next planned step."},
)
_QUESTS = (
    {"quest_id": "hostinger-connection", "title": "Inspect the connection route",
     "objective": "Confirm the site's Hostinger product and available read-only access; review a supported route before any live connection attempt.",
     "status": "planned", "evidence_state": "planned", "source_ids": [], "world_id": "observatory"},
    {"quest_id": "ai-building-cycle", "title": "Review one building cycle",
     "objective": "Choose one bounded assistant or tool change, run its checks, and retain a human review before considering a release.",
     "status": "planned", "evidence_state": "planned", "source_ids": [], "world_id": "forge"},
    {"quest_id": "media-review", "title": "Review the media draft",
     "objective": "Review source labels, original asset rights, narration, captions and accessibility before considering any media publication.",
     "status": "planned", "evidence_state": "planned", "source_ids": [], "world_id": "archive"},
)
_RECORD_LABELS = {
    "source_linked": ("Source-linked record.", "SOURCE-LINKED RECORD"),
    "owner_reported": ("Owner-reported record.", "OWNER-REPORTED RECORD"),
    "planned": ("Planned record.", "PLANNED RECORD"),
    "fictional": ("Fictional diary scene.", "FICTIONAL RECORD"),
}


def _record(value, keys):
    if type(value) is not dict or any(type(key) is not str for key in value) or set(value) != set(keys):
        raise ValueError("invalid episode record fields")


def _chars(value, limit):
    if type(value) is not str or len(value) > limit:
        raise ValueError("episode text exceeds character bounds")
    _text(value, limit * 4)


def _hex(value, length):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value) is None:
        raise ValueError("invalid episode digest or context revision")


def _audience(audience, visibility):
    if (type(audience) is not str or audience not in {"public", "owner"}
            or type(visibility) is not str or visibility not in VISIBILITIES):
        raise ValueError("invalid episode audience or source visibility")
    if audience == "public" and visibility != "public_candidate":
        raise ValueError("public episode requires a public_candidate diary entry")


def _references(value, known):
    if type(value) is not list or len(value) > 5:
        raise ValueError("invalid episode source references")
    seen = set()
    for source_id in value:
        _identifier(source_id)
        if source_id not in known or source_id in seen:
            raise ValueError("invalid episode source references")
        seen.add(source_id)


def _source_ids(sources):
    if type(sources) is not list or len(sources) > 5:
        raise ValueError("invalid episode sources")
    known = set()
    for source in sources:
        _record(source, {"source_id", "title", "url"})
        _identifier(source["source_id"])
        if source["source_id"] in known:
            raise ValueError("duplicate episode source identifier")
        known.add(source["source_id"])
        _text(source["title"], 200)
        _text(source["url"], 1000)
        if not valid_https_url(source["url"]):
            raise ValueError("invalid episode source URL")
    return known


def _scene_ids(record_count):
    return (["opening"] + [f"record-{index:02d}" for index in range(1, record_count + 1)]
            + (["briefing", "revenue-experiment"] if record_count < 3 else ["briefing-revenue-plan"])
            + ["next-quests", "closing"])


def validate_episode(episode):
    """Validate a complete local draft, its internal references and content hash.

    The source hash is a claimed binding. Without the original diary this method
    cannot establish its visibility, provenance or factual accuracy independently.
    """
    _record(episode, EPISODE_KEYS)
    if (type(episode["schema_version"]) is not int or episode["schema_version"] != 1
            or type(episode["kind"]) is not str or episode["kind"] != "jarvis.rpg_episode"):
        raise ValueError("unsupported episode schema")
    _identifier(episode["episode_id"])
    _date(episode["date"])
    if type(episode["timezone"]) is not str or episode["timezone"] != DIARY_TIMEZONE:
        raise ValueError("unsupported episode timezone")
    _text(episode["title"], 180)
    _audience(episode["audience"], episode["source_visibility"])
    _hex(episode["source_entry_sha256"], 64)
    _hex(episode["source_context_revision"], 40)
    _hex(episode["episode_sha256"], 64)
    for key, expected in (("news_status", NEWS_STATUS), ("fictional_framing", FICTIONAL_FRAMING),
                          ("publication_approval", "not_granted")):
        if type(episode[key]) is not str or episode[key] != expected:
            raise ValueError("invalid episode framing or publication status")
    for key in ("external_actions", "model_calls"):
        if type(episode[key]) is not int or episode[key] != 0:
            raise ValueError("episode must remain a local draft")
    if type(episode["observations_omitted"]) is not int or not 0 <= episode["observations_omitted"] <= 5:
        raise ValueError("invalid episode omission count")
    known_sources = _source_ids(episode["sources"])
    worlds = episode["worlds"]
    if type(worlds) is not list or len(worlds) != 3:
        raise ValueError("invalid episode worlds")
    for index, world in enumerate(worlds):
        _record(world, {"world_id", "title", "description"})
        if type(world["world_id"]) is not str or world["world_id"] != WORLD_IDS[index]:
            raise ValueError("invalid episode world order or identifier")
        _chars(world["title"], 80)
        _chars(world["description"], 240)
    scenes = episode["scenes"]
    if type(scenes) is not list or not 6 <= len(scenes) <= 7:
        raise ValueError("episode requires six or seven scenes")
    identifiers = []
    for scene in scenes:
        _record(scene, SCENE_KEYS)
        _identifier(scene["scene_id"])
        if scene["scene_id"] in identifiers:
            raise ValueError("duplicate episode scene identifier")
        identifiers.append(scene["scene_id"])
        _chars(scene["title"], 80)
        _chars(scene["voiceover"], 500)
        _chars(scene["screen_text"], 180)
        if type(scene["world_id"]) is not str or scene["world_id"] not in WORLD_IDS:
            raise ValueError("unknown episode scene world")
        if type(scene["evidence_state"]) is not str or scene["evidence_state"] not in EVIDENCE_STATES:
            raise ValueError("invalid episode evidence state")
        _references(scene["source_ids"], known_sources)
        if scene["evidence_state"] == "source_linked" and not scene["source_ids"]:
            raise ValueError("source-linked episode scene requires a reference")
        if scene["scene_id"] in {"opening", "closing"}:
            if scene["evidence_state"] != "fictional" or scene["source_ids"]:
                raise ValueError("episode framing must remain fictional")
        elif not scene["scene_id"].startswith("record-"):
            if scene["evidence_state"] != "planned" or scene["source_ids"]:
                raise ValueError("episode proposals must remain planned")
    record_count = sum(value.startswith("record-") for value in identifiers)
    if not 1 <= record_count <= 3 or identifiers != _scene_ids(record_count):
        raise ValueError("invalid episode scene sequence")
    if record_count < 3 and episode["observations_omitted"]:
        raise ValueError("invalid episode omission count")
    quests = episode["quests"]
    if type(quests) is not list or len(quests) != 3:
        raise ValueError("episode requires exactly three planned quests")
    for index, quest in enumerate(quests):
        _record(quest, QUEST_KEYS)
        if (type(quest["quest_id"]) is not str or quest["quest_id"] != QUEST_IDS[index]
                or type(quest["world_id"]) is not str or quest["world_id"] != _QUESTS[index]["world_id"]):
            raise ValueError("invalid episode quest order or world")
        _chars(quest["title"], 80)
        _chars(quest["objective"], 400)
        for key in ("status", "evidence_state"):
            if type(quest[key]) is not str or quest[key] != "planned":
                raise ValueError("episode quests must remain planned")
        _references(quest["source_ids"], known_sources)
        if quest["source_ids"]:
            raise ValueError("authored episode quests do not establish source-backed results")
    if len(canonical(episode)) > MAX_PACKET_BYTES:
        raise ValueError("episode packet exceeds 64 KiB")
    if digest({key: value for key, value in episode.items() if key != "episode_sha256"}) != episode["episode_sha256"]:
        raise ValueError("episode content hash mismatch")
    return deepcopy(episode)


def _excerpt(value, limit):
    text = " ".join(value.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _scene(scene_id, title, voiceover, screen_text, evidence_state, world_id, source_ids=()):
    return {"scene_id": scene_id, "title": title, "voiceover": voiceover, "screen_text": screen_text,
            "evidence_state": evidence_state, "source_ids": list(source_ids), "world_id": world_id}


def _project_world(initiative_id):
    if initiative_id in {"jarvis-tools", "linux-learning", "robotics-simulation", "wearables-research"}:
        return "forge"
    if initiative_id in {"publishing-library", "interactive-video"}:
        return "archive"
    return "observatory"


def build_episode(entry, *, source_revision, episode_id, audience="public"):
    """Compile one selected diary into a bounded six/seven-scene original draft.

    Public is the default. An explicit owner audience permits private/internal
    source entries for local viewing; it does not make those sources publishable.
    """
    entry = validate_diary_entry(entry)
    _audience(audience, entry["visibility"])
    _hex(source_revision, 40)
    _identifier(episode_id)
    project_title = INITIATIVES[entry["initiative_id"]].title
    scenes = [_scene("opening", "The command library opens",
        FICTIONAL_FRAMING + " Welcome. I'm Luma, your guide through the Lantern Archive, Copper Forge and Sky Observatory. "
        + "Our selected project is " + project_title + ". Come with me; we'll read the records, then choose the next page.",
        "FICTIONAL SETTING · Archive / Forge / Observatory\nSelected project: " + project_title,
        "fictional", "archive")]
    selected = entry["observations"][:3]
    for index, observation in enumerate(selected, 1):
        spoken_label, screen_label = _RECORD_LABELS[observation["evidence_state"]]
        prefix = spoken_label + " From the diary: "
        scenes.append(_scene(f"record-{index:02d}", "Diary record: " + observation["observation_id"],
            prefix + _excerpt(observation["text"], 500 - len(prefix)),
            screen_label + "\n" + _excerpt(observation["text"], 179 - len(screen_label)),
            observation["evidence_state"], _project_world(entry["initiative_id"]), observation["source_ids"]))
    if len(selected) < 3:
        scenes.extend([
            _scene("briefing", "Plan the dated briefing",
                "Proposed briefing step. At the Observatory, place this dated record beside its sources and keep the labels in view. "
                "The project diary is our focus here; current news is not included in this pilot.",
                "PLANNED · Attach the record to a dated review.\nCurrent news is not included.", "planned", "observatory"),
            _scene("revenue-experiment", "Plan one offer experiment",
                "Proposed offer experiment. In the Forge, sketch one small learning or media offer. "
                "Who is it for, how would it be delivered, and what would help you judge interest? Keep the result open until you have evidence.",
                "PLANNED · Define one offer and a way to test interest.\nNo revenue result is claimed.", "planned", "forge"),
        ])
    else:
        scenes.append(_scene("briefing-revenue-plan", "Plan a briefing and offer experiment",
            "Proposed briefing and offer experiment. At the Observatory, keep the dated record and its sources together. "
            "Then sketch one small learning or media offer in the Forge, with an audience, delivery route and a way to judge interest. Current news is outside this pilot.",
            "PLANNED · Dated briefing + one offer experiment.\nNews and revenue outcomes are not supplied.", "planned", "observatory"))
    prefix = ("Three proposed quests await: inspect the Hostinger connection route, review one AI-building cycle, and review the media draft. "
              "The diary's next action is: ")
    scenes.append(_scene("next-quests", "Three proposed quests",
        prefix + _excerpt(entry["next_action"], 500 - len(prefix)),
        "PLANNED · Hostinger connection / AI-building cycle / media review\nNext: " + _excerpt(entry["next_action"], 107),
        "planned", "forge"))
    scenes.append(_scene("closing", "Leave a lantern for the next visit",
        "In our fictional library, Luma places a lantern beside the unfinished page. "
        "The quests are still proposals; you choose what to try next. Bring back a reviewed record, and we'll open the next chapter together.",
        "FICTIONAL CLOSING · Keep the record. Review the plan.\nNo quest completion or publication is granted.",
        "fictional", "archive"))
    result = {"schema_version": 1, "kind": "jarvis.rpg_episode", "episode_id": episode_id,
        "date": entry["date"], "timezone": entry["timezone"], "title": entry["title"],
        "audience": audience, "source_visibility": entry["visibility"],
        "source_entry_sha256": diary_entry_digest(entry), "source_context_revision": source_revision,
        "sources": deepcopy(entry["sources"]), "worlds": deepcopy(list(_WORLDS)), "scenes": scenes,
        "quests": deepcopy(list(_QUESTS)), "observations_omitted": len(entry["observations"]) - len(selected),
        "news_status": NEWS_STATUS, "fictional_framing": FICTIONAL_FRAMING,
        "publication_approval": "not_granted", "external_actions": 0, "model_calls": 0}
    result["episode_sha256"] = digest(result)
    return validate_episode(result)
