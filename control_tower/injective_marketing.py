"""Deterministic parallel-theme marketing routes for Intergalactic Corporate Services LLC.

"Injective Marketing" is an internal working brand term: creative entertainment content
may carry one bounded, relevant business/education/product route. This module generates
unpublished planning packets only and performs no posting, outreach, account access,
payments, analytics reads, or financial actions.
"""
from hashlib import sha256
import json

from control_tower.creative_ad_foundry import CAMPAIGN_UNIVERSES, TONE_MODES, creative_blueprint
from control_tower.organic_marketing import BLOCKED_CHANNELS, FREE_CHANNELS, PRODUCTS


INJECTIVE_THEME = {
    "name": "Intergalactic Injective Marketing",
    "sponsor": "Intergalactic Corporate Services LLC",
    "relationship": "parallel_theme",
    "entry_rule": "Entertainment first; route second.",
    "definition": (
        "Use fiction, comedy, satire, puns, ANIMA/RPG story beats and educational hooks "
        "as a parallel creative layer that can introduce exactly one relevant next-step route "
        "without replacing the underlying product facts, disclosures or release state."
    ),
    "creative_universes": (
        "join-space-aliens",
        "entertainment-of-life",
        "life-is-code",
        "evolutionary-evolutions",
        "build-the-multiverse",
    ),
}

MEMBERSHIP_LADDER = {
    "free-explorer": {
        "state": "planned",
        "price": None,
        "purpose": "Free newsletter, public learning, comedy/ANIMA discovery and project updates.",
        "destination": "https://aievolutionaryevolutions.com",
        "price_rule": "No price is asserted by this module.",
    },
    "builder-member": {
        "state": "planned",
        "price": None,
        "purpose": "Deeper lessons, quests, build-alongs, book/chapter access and member tools.",
        "destination": None,
        "price_rule": "Pricing and fulfillment require separate owner review before promotion.",
    },
    "affiliate-builder": {
        "state": "planned",
        "price": None,
        "purpose": "Affiliate education, campaign-building tools and partner-oriented workflows.",
        "destination": None,
        "price_rule": "Pricing, platform destination and benefit claims remain unverified.",
    },
    "business-creator": {
        "state": "planned",
        "price": None,
        "purpose": "Business-building, advertising, publishing and systems-development membership concepts.",
        "destination": None,
        "price_rule": "Pricing, deliverables and support capacity require review before promotion.",
    },
}

ROUTES = {
    "newsletter": {
        "route_kind": "newsletter",
        "product_id": "education-hub",
        "membership_id": "free-explorer",
        "bridge": "Turn the joke or story into a useful weekly/daily learning and Life/Business update.",
    },
    "education-membership": {
        "route_kind": "membership",
        "product_id": "education-hub",
        "membership_id": "free-explorer",
        "bridge": "Invite the audience from entertainment into practical AI, Linux, coding, blockchain, robotics and ANIMA learning.",
    },
    "builder-membership": {
        "route_kind": "membership",
        "product_id": "education-hub",
        "membership_id": "builder-member",
        "bridge": "Move interested builders toward deeper quests, build-alongs and member tools after the offer is verified.",
    },
    "affiliate-builder-membership": {
        "route_kind": "membership_affiliate",
        "product_id": "partner-7figures",
        "membership_id": "affiliate-builder",
        "bridge": "Teach affiliate/referral fundamentals first, then show a verified partner route with clear disclosure.",
    },
    "funding-information": {
        "route_kind": "funding_customer",
        "product_id": "funding-7figures",
        "membership_id": None,
        "bridge": "Use a business-building story to introduce financing information without promising approval, terms or outcomes.",
    },
    "referral-partner": {
        "route_kind": "funding_partner",
        "product_id": "partner-lendtrack",
        "membership_id": "affiliate-builder",
        "bridge": "Use creator/business education to introduce a separate referral-partner opportunity without implying earnings.",
    },
    "book-anima-universe": {
        "route_kind": "publishing",
        "product_id": "book-incubator",
        "membership_id": None,
        "bridge": "Turn the comedy universe into books, chapters, ANIMA quests and multimedia discovery while release destinations remain gated.",
    },
    "jarvis-builders": {
        "route_kind": "technical",
        "product_id": "jarvis-ai-building-ai",
        "membership_id": "builder-member",
        "bridge": "Move technical curiosity toward documented Jarvis builds, tests, evidence and limitations.",
    },
}

INJECTION_POINTS = (
    "newsletter_feature",
    "social_post",
    "short_video",
    "long_video",
    "book_or_chapter",
    "anima_rpg_quest",
    "landing_page",
    "website_section",
    "developer_update",
    "community_discussion",
)


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _digest(value):
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def route_record(route_id):
    if route_id not in ROUTES:
        raise ValueError("unknown injective route")
    return json.loads(_canonical(ROUTES[route_id]))


def injective_campaign(route_id, channel, *, universe_id="entertainment-of-life",
                       tone="cosmic_comedy", injection_point="social_post"):
    if route_id not in ROUTES:
        raise ValueError("unknown injective route")
    if channel in BLOCKED_CHANNELS:
        raise ValueError("blocked channel for owner")
    if channel not in FREE_CHANNELS:
        raise ValueError("unknown active channel")
    if universe_id not in CAMPAIGN_UNIVERSES:
        raise ValueError("unknown campaign universe")
    if tone not in TONE_MODES:
        raise ValueError("unknown tone")
    if injection_point not in INJECTION_POINTS:
        raise ValueError("unknown injection point")

    route = ROUTES[route_id]
    product = PRODUCTS[route["product_id"]]
    creative = creative_blueprint(product.product_id, universe_id, channel, tone=tone)
    membership = MEMBERSHIP_LADDER.get(route["membership_id"]) if route["membership_id"] else None

    body = {
        "schema_version": 1,
        "kind": "jarvis.injective_marketing_campaign",
        "state": "unpublished_draft",
        "theme": INJECTIVE_THEME,
        "route_id": route_id,
        "route_kind": route["route_kind"],
        "injection_point": injection_point,
        "channel": channel,
        "creative_universe": universe_id,
        "tone": tone,
        "entry_hook": creative["opening_hook"],
        "creative_label": creative["story_label"],
        "bridge": route["bridge"],
        "product_id": product.product_id,
        "product_title": product.title,
        "audience": product.audience,
        "membership_id": route["membership_id"],
        "membership": membership,
        "cta": creative["cta"],
        "destination": product.destination if membership is None or membership["destination"] is None else membership["destination"],
        "product_destination": product.destination,
        "disclosure": product.disclosure,
        "prohibited_claims": list(product.prohibited_claims),
        "parallel_theme_rules": [
            "Entertainment may introduce the offer; it may not rewrite the offer facts.",
            "Use one primary route per campaign derivative.",
            "Keep customer financing separate from referral-partner recruitment.",
            "Keep membership pricing and benefits unasserted until verified.",
            "Keep fiction/comedy/satire visibly separate from factual claims.",
            "Do not invent publication status, testimonials, traffic, sales, commissions or member counts.",
            "Human release review is required before any live publication or account action.",
        ],
        "external_actions": 0,
        "publishing_actions": 0,
        "actual_metrics": None,
    }
    return {**body, "campaign_sha256": _digest(body)}


def injective_funnel(route_id, *, universe_id="entertainment-of-life", tone="cosmic_comedy"):
    if route_id not in ROUTES:
        raise ValueError("unknown injective route")
    body = {
        "schema_version": 1,
        "kind": "jarvis.injective_marketing_funnel",
        "state": "planning_only",
        "route_id": route_id,
        "creative_universe": universe_id,
        "tone": tone,
        "stages": [
            {"stage": "attention", "rule": "Fiction/comedy/satire/pun or useful educational hook."},
            {"stage": "interest", "rule": "One useful idea, story, lesson, demonstration or quest."},
            {"stage": "bridge", "rule": ROUTES[route_id]["bridge"]},
            {"stage": "offer", "rule": "Present only the selected route with its real release/verification state."},
            {"stage": "action", "rule": "Use the route-specific CTA and disclosure."},
            {"stage": "measurement", "rule": "Record publication, clicks, subscriptions, consented leads, sales and commissions as separate evidenced events."},
            {"stage": "evolution", "rule": "Use Prompt #11 QA and actual evidence to improve the next derivative."},
        ],
        "external_actions": 0,
        "actual_metrics": None,
    }
    return {**body, "funnel_sha256": _digest(body)}


def newsletter_injective_map():
    sections = []
    for route_id in ROUTES:
        route = ROUTES[route_id]
        product = PRODUCTS[route["product_id"]]
        sections.append({
            "route_id": route_id,
            "headline_seed": f"Join the Space Aliens: {product.title}",
            "bridge": route["bridge"],
            "membership_id": route["membership_id"],
            "destination": product.destination,
            "state": "unpublished_newsletter_candidate",
        })
    body = {
        "schema_version": 1,
        "kind": "jarvis.injective_newsletter_map",
        "title": "Intergalactic Corporate Services LLC - Entertainment of Life / Life-Business Building",
        "sections": sections,
        "external_actions": 0,
    }
    return {**body, "map_sha256": _digest(body)}
