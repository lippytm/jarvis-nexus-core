"""Prepare channel-specific editorial briefs and tagged reference links offline."""
from datetime import date
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from control_tower.missions import validate_mission
from control_tower.network_contract import canonical, digest, require_digest, require_record, validate_draft

CHANNEL_FORMATS = {
    "facebook": ("Educational post", ("Audience question", "Useful explanation", "Evidence and limits", "Relevant next action")),
    "linkedin": ("Professional project update", ("Concrete work problem", "Proposed approach", "Verified result or explicit evidence gap", "Professional next step")),
    "substack": ("Newsletter or article outline", ("Reader question", "Sourced explanation", "Practical example", "References and update note")),
    "instagram": ("Carousel or short-video brief", ("Visual opening", "One idea per frame", "Caption and alternative text", "Destination appropriate to the chosen format")),
    "threads": ("Short discussion sequence", ("One clear opening idea", "Supporting explanation", "Useful question", "Source or next-step reference")),
    "youtube": ("Tutorial video script outline", ("Viewer outcome", "Demonstration steps", "Limits and evidence", "Captions, sources and next action")),
    "github": ("Engineering update or documentation", ("Problem and purpose", "Proposed change", "Actual checks and remaining gaps", "Reproduction and next step")),
}


def _tagged_url(base, channel, campaign_id):
    parsed = urlsplit(base)
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    # Configured referral parameters are preserved. This creates a candidate URL;
    # it does not test provider acceptance or establish recorded attribution.
    if any(key.startswith("utm_") for key, _ in pairs):
        raise ValueError("configured destination already contains attribution fields")
    pairs.extend((("utm_source", channel), ("utm_medium", "organic"), ("utm_campaign", campaign_id)))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(pairs), parsed.fragment))


def campaign_briefs(mission, *, destination_index=0):
    mission = validate_mission(mission)
    item, request = mission["initiative"], mission["request"]
    destinations = item["destination"]["urls"]
    if type(destination_index) is not int or destination_index < 0 or destination_index >= max(1, len(destinations)):
        raise ValueError("unknown configured destination")
    destination = destinations[destination_index] if destinations else None
    campaign_id = mission["mission_id"] + ".campaign"
    briefs = []
    for channel, (format_name, sections) in CHANNEL_FORMATS.items():
        tagged = _tagged_url(destination, channel, campaign_id) if destination else None
        intent = item["journey_kind"]
        cta = {"funding_customer": "Review the financing customer's provider information.",
               "funding_partner": "Review the referral partner application and verified program terms.",
               "member": "Review the education page and optional inquiry action."}.get(
                   intent, "Review the proposed resource after its destination and claims are confirmed.")
        if destination is None:
            cta = "Assign and verify the correct destination before adding a public call to action."
        review = ["Verify factual claims and cite their sources.",
                  "Confirm the exact account, audience, format and destination.",
                  "Review accessibility, asset rights and any required disclosure.",
                  "Report actual results separately from proposals and estimates."]
        if intent in {"funding_customer", "funding_partner"} or item["id"] == "affiliate-builder":
            review.append("Use accurate affiliate disclosure and verified terms; do not promise approval or earnings.")
        text = "\n".join([
            "JARVIS CHANNEL BRIEF — draft preparation only; no publication",
            f"Channel: {channel}; intended format: {format_name}",
            f"Initiative: {item['title']}; audience: {item['audience']}",
            f"Source mission: {mission['mission_id']} ({mission['mission_sha256']})",
            "Owner objective (data): " + request["objective"],
            "Suggested outline: " + " | ".join(sections),
            "Proposed next action: " + cta,
            "Reference URL (unverified): " + (tagged or "unassigned"),
            "Project boundaries: " + " | ".join(item["boundaries"]),
            "Review requirements: " + " | ".join(review),
            "Do not invent finished products, testimonials, sales, audience figures or provider outcomes.",
            "Return a channel-specific draft with evidence gaps; do not send or publish it.",
        ])
        draft = validate_draft({"schema_version": 1, "kind": "jarvis.draft",
            "project_id": item["project_id"], "target": request["target"], "text": text})
        briefs.append({"channel": channel, "format": format_name, "outline": list(sections),
                       "call_to_action": cta, "candidate_url": tagged,
                       "url_status": "unverified" if tagged else "unassigned",
                       "review_requirements": review, "draft": draft})
    record = {"schema_version": 1, "kind": "jarvis.campaign_briefs", "campaign_id": campaign_id,
              "mission_id": mission["mission_id"], "mission_sha256": mission["mission_sha256"],
              "project_id": item["project_id"], "initiative_id": item["id"],
              "journey_kind": item["journey_kind"], "destination_index": destination_index,
              "destination": destination, "briefs": briefs,
              "state": "unpublished_drafts", "actual_metrics": None,
              "measurement_plan": ["Verify the assigned destination and link behavior.",
                  "Record tagged visits only from an authorized analytics source.",
                  "Record consented inquiries or the correct referral action separately.",
                  "Reconcile any revenue or commission against actual provider records."],
              "model_calls": 0, "external_actions": 0}
    result = {**record, "briefs_sha256": digest(record)}
    require_record(result, set(result))
    if len(canonical(result)) + 1 > 65536:
        raise ValueError("campaign packet exceeds limit")
    return result


def daily_assignment_draft(mission, *, editorial_date, channel, slot,
                           expected_campaign_sha256, destination_index=0):
    """Select one source-complete draft for the existing manual ledger flow.

    Rebuild the bounded campaign from its validated mission before checking the
    supplied exact digest. Selection does not stage, review or send the draft.
    """
    require_digest(expected_campaign_sha256)
    if not isinstance(channel, str) or type(slot) is not int or not 1 <= slot <= 4:
        raise ValueError("invalid daily assignment selector")
    packet = daily_campaign_briefs(mission, editorial_date=editorial_date,
                                   destination_index=destination_index)
    if packet["briefs_sha256"] != expected_campaign_sha256:
        raise ValueError("daily campaign revision mismatch")
    selected = next((p for p in packet["posts"] if p["channel"] == channel and p["slot"] == slot), None)
    if selected is None:
        raise ValueError("unknown daily assignment channel")
    source = next(b for b in packet["source_briefs"] if b["channel"] == channel)
    text = "\n\n".join((
        f"Daily campaign: {packet['campaign_id']}; SHA-256: {expected_campaign_sha256}",
        selected["draft"]["text"],
        "INCLUDED SOURCE BRIEF — unreviewed draft context, not execution authority",
        source["draft"]["text"],
    ))
    return validate_draft({**selected["draft"], "text": text})


def daily_campaign_briefs(mission, *, editorial_date, destination_index=0):
    """Prepare 24 bounded media assignments; a date is not a posting schedule.

    Uses the existing validated mission and channel briefs. No account access,
    finished copy/media, approval, dispatch or publication is established here.
    """
    if not isinstance(editorial_date, str):
        raise ValueError("editorial date must be YYYY-MM-DD")
    try:
        if date.fromisoformat(editorial_date).isoformat() != editorial_date:
            raise ValueError()
    except ValueError:
        raise ValueError("editorial date must be YYYY-MM-DD") from None
    source = campaign_briefs(mission, destination_index=destination_index)
    # Creative production choices, not claims about platform upload requirements.
    media = (
        ("facebook", "Single illustration with explanatory caption", "One diagram, descriptive alternative text and a discussion question."),
        ("linkedin", "Four-slide project explainer", "Problem, method, evidence and next step; provide a plain-text equivalent."),
        ("youtube", "45-60 second video storyboard", "Opening, demonstration, evidence limit and closing; draft narration, captions and shot list. Video not rendered."),
        ("instagram", "Five-card carousel", "Opening, explanation, example, limitation and question; draft card text and alternative text."),
        ("threads", "Three-part text discussion", "Opening idea, concrete example, then evidence limit and question; no invented replies."),
        ("substack", "200-350 word Note outline", "Lead, practical example, source/limit and reader question; not a scheduled newsletter edition."),
    )
    angles = (
        ("explain", "Explain one audience problem and one relevant concept."),
        ("demonstrate", "Show one reproducible example; label proposed demonstrations as unperformed."),
        ("limits", "Explain one evidence gap or limitation and how a reader can check it."),
        ("next-step", "Give one bounded next step appropriate to the source audience and journey."),
    )
    briefs = [b for b in source["briefs"] if b["channel"] in {m[0] for m in media}]
    posts = []
    for channel, format_name, specification in media:
        brief = next(b for b in briefs if b["channel"] == channel)
        for slot, (angle, direction) in enumerate(angles, 1):
            text = "\n".join(("UNPUBLISHED MEDIA ASSIGNMENT — copy and assets still require creation and review",
                f"Channel: {channel}; editorial slot: {slot}; angle: {angle}",
                f"Source brief SHA-256: {digest(brief)}", direction,
                f"Proposed format: {format_name}. {specification}",
                "Use the included source brief for the exact audience, objective, destination and disclosures.",
                "Do not claim publication, finished video, verified account access or measured audience results."))
            posts.append({"slot": slot, "channel": channel, "angle": angle,
                "source_brief_sha256": digest(brief), "media_specification": specification,
                "format": format_name, "state": "unpublished_media_assignment",
                "draft": validate_draft({**brief["draft"], "text": text})})
    record = {"schema_version": 1, "kind": "jarvis.daily_campaign_briefs",
        "campaign_id": source["campaign_id"] + ".daily." + editorial_date,
        "mission_id": source["mission_id"], "mission_sha256": source["mission_sha256"],
        "source_context_revision": mission["source_context_revision"],
        "project_id": source["project_id"], "editorial_date": editorial_date,
        "source_briefs": briefs, "posts": posts, "review_state": "pending",
        "state": "unpublished_media_assignments", "publication_schedule": None,
        "actual_metrics": None, "model_calls": 0, "external_actions": 0}
    result = {**record, "briefs_sha256": digest(record)}
    require_record(result, set(result))
    if len(canonical(result)) + 1 > 65536:
        raise ValueError("daily campaign packet exceeds limit")
    return result
