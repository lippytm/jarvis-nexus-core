"""Space Aliens Comedy Affiliate Marketing Program planning layer.

This module is a bounded, unpublished marketing overlay. It generates no live posts,
account actions, memberships, affiliate enrollments, sales, commissions or revenue.
Comedy/ANIMA language is creative framing; real offers retain their own facts,
disclosures, destinations, evidence state and Prompt #11 review requirements.
"""
from hashlib import sha256
import json

from control_tower.affiliate_universe import OPPORTUNITY_WORLDS
from control_tower.creative_ad_foundry import TONE_MODES, creative_blueprint
from control_tower.injective_marketing import MEMBERSHIP_LADDER, ROUTES
from control_tower.organic_marketing import BLOCKED_CHANNELS, FREE_CHANNELS, PRODUCTS
from control_tower.portfolio import portfolio_catalog

PROGRAM = {
    "name": "Space Aliens Comedy Affiliate Marketing Program",
    "sponsor": "Intergalactic Corporate Services LLC",
    "role": "parallel_injective_marketing_layer",
    "master_hook": "Join the Space Aliens in the Affiliate Marketing Universes of Life/Business Building.",
    "creative_promise": "Use comedy, satire, puns and ANIMA storytelling to open one relevant doorway into a real product, project, platform, membership, educational route or verified affiliate opportunity.",
    "reality_rule": "Unlimited creative possibilities do not imply unlimited real programs, guaranteed availability, commissions, income, approval, sales or results.",
    "operating_cycle": "Entertain -> Teach -> Bridge -> Disclose -> Route -> Measure -> Improve -> Evolve.",
}

COMEDY_FORMATS = {
    "space_alien_misunderstanding": "An alien misunderstands a human business, coding or technology concept, then the punchline reveals a useful idea.",
    "intergalactic_bureaucracy": "A fictional intergalactic department turns an ordinary business process into absurd paperwork before revealing the practical shortcut.",
    "pun_bridge": "A clean pun opens the piece, then one useful educational bridge leads to one relevant route.",
    "roast_and_rebuild": "Roast a bad idea, workflow or assumption; then rebuild it with a better documented alternative.",
    "comedy_quest": "Frame the audience's next useful action as an ANIMA/RPG comedy quest with an evidence checkpoint.",
}

PRODUCT_ROUTE_MAP = {
    "education-hub": "education-membership",
    "funding-getbizfunds": "funding-getbizfunds",
    "funding-7figures": "funding-information",
    "partner-7figures": "affiliate-builder-membership",
    "partner-lendtrack": "referral-partner",
    "book-incubator": "book-anima-universe",
    "jarvis-ai-building-ai": "jarvis-builders",
}


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _digest(value):
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def program_registry():
    initiatives = portfolio_catalog()["initiatives"]
    body = {
        "schema_version": 1,
        "kind": "jarvis.space_alien_comedy_affiliate_registry",
        "state": "planning_registry",
        "program": PROGRAM,
        "coverage_basis": "all items currently present in the referenced Jarvis registries",
        "registered_products": sorted(PRODUCTS),
        "registered_portfolio_initiatives": sorted(item["id"] for item in initiatives),
        "registered_opportunity_worlds": sorted(OPPORTUNITY_WORLDS),
        "registered_memberships": sorted(MEMBERSHIP_LADDER),
        "registered_injective_routes": sorted(ROUTES),
        "active_free_channels": sorted(FREE_CHANNELS),
        "blocked_channels": BLOCKED_CHANNELS,
        "unregistered_scope_rule": "Historical or future ideas not yet present in these registries are not claimed as connected until explicitly registered and reviewed.",
        "external_actions": 0,
        "actual_metrics": None,
    }
    return {**body, "registry_sha256": _digest(body)}


def product_campaign(product_id, channel, *, tone="cosmic_comedy", comedy_format="pun_bridge"):
    if product_id not in PRODUCTS:
        raise ValueError("unknown product")
    if product_id not in PRODUCT_ROUTE_MAP:
        raise ValueError("product has no reviewed route mapping")
    if comedy_format not in COMEDY_FORMATS:
        raise ValueError("unknown comedy format")
    if tone not in TONE_MODES:
        raise ValueError("unknown tone")
    creative = creative_blueprint(product_id, "entertainment-of-life", channel, tone=tone)
    product = PRODUCTS[product_id]
    route_id = PRODUCT_ROUTE_MAP[product_id]
    body = {
        "schema_version": 1,
        "kind": "jarvis.space_alien_comedy_affiliate_campaign",
        "state": "unpublished_draft",
        "program_name": PROGRAM["name"],
        "product_id": product_id,
        "route_id": route_id,
        "channel": channel,
        "tone": tone,
        "comedy_format": comedy_format,
        "comedy_direction": COMEDY_FORMATS[comedy_format],
        "opening_hook": creative["opening_hook"],
        "story_label": creative["story_label"],
        "audience": product.audience,
        "product_objective": product.objective,
        "business_bridge": "After the entertainment beat, teach one useful point and present only the mapped route as the next optional step.",
        "cta": creative["cta"],
        "destination": creative["destination"],
        "disclosure": creative["disclosure"],
        "prohibited_claims": creative["prohibited_claims"],
        "prompt_11_gate": [
            "Keep fiction/comedy/satire visibly separate from factual claims.",
            "Use exactly one primary route per derivative.",
            "Verify the exact offer, destination, terms and release state before publication.",
            "Preserve affiliate/referral disclosure where applicable.",
            "Never guarantee approval, income, commissions, sales, demand or business results.",
            "Do not invent product availability, testimonials, member counts, traffic, revenue or conversions.",
            "Human release review and authorized account access are required before live publication.",
        ],
        "external_actions": 0,
        "publishing_actions": 0,
        "actual_metrics": None,
    }
    return {**body, "campaign_sha256": _digest(body)}


def product_campaign_family(product_id, *, tone="cosmic_comedy", comedy_format="pun_bridge"):
    campaigns = [product_campaign(product_id, channel, tone=tone, comedy_format=comedy_format) for channel in FREE_CHANNELS]
    body = {
        "schema_version": 1,
        "kind": "jarvis.space_alien_comedy_affiliate_family",
        "state": "unpublished_drafts",
        "product_id": product_id,
        "campaign_count": len(campaigns),
        "campaigns": campaigns,
        "blocked_channels": BLOCKED_CHANNELS,
        "external_actions": 0,
        "publishing_actions": 0,
        "actual_metrics": None,
    }
    return {**body, "family_sha256": _digest(body)}


def portfolio_injection_map():
    initiatives = portfolio_catalog()["initiatives"]
    rows = []
    for item in initiatives:
        rows.append({
            "initiative_id": item["id"],
            "project_id": item["project_id"],
            "injection_state": "creative_overlay_candidate",
            "required_next_step": "Select one relevant product, route or opportunity world; verify its facts and destination; then generate one bounded comedy derivative.",
        })
    body = {
        "schema_version": 1,
        "kind": "jarvis.space_alien_portfolio_injection_map",
        "state": "planning_only",
        "initiatives": rows,
        "external_actions": 0,
    }
    return {**body, "map_sha256": _digest(body)}


def newsletter_program_map():
    sections = []
    for product_id in sorted(PRODUCTS):
        product = PRODUCTS[product_id]
        sections.append({
            "product_id": product_id,
            "headline_seed": f"Space Aliens Comedy Affiliate Desk: {product.title}",
            "route_id": PRODUCT_ROUTE_MAP[product_id],
            "format": "joke -> useful idea -> one business bridge -> Prompt #11 reality check -> CTA",
            "state": "unpublished_newsletter_candidate",
        })
    body = {
        "schema_version": 1,
        "kind": "jarvis.space_alien_comedy_affiliate_newsletter_map",
        "title": "Space Aliens Comedy Affiliate Marketing Desk",
        "sections": sections,
        "external_actions": 0,
    }
    return {**body, "map_sha256": _digest(body)}
