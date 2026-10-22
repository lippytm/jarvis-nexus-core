"""Prepare channel-specific editorial briefs and tagged reference links offline."""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from control_tower.missions import validate_mission
from control_tower.network_contract import canonical, digest, require_record, validate_draft

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
