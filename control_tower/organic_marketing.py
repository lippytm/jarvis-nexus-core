"""Deterministic free-organic marketing registry and campaign compiler.

This module prepares unpublished briefs only. It performs no model calls,
account connections, publishing, outreach, analytics reads, or financial actions.
"""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


FREE_CHANNELS = {
    "linkedin": {"kind": "social", "format": "professional update", "free_mode": "organic posting"},
    "youtube": {"kind": "video", "format": "video/short", "free_mode": "organic publishing"},
    "facebook": {"kind": "social", "format": "page/group post", "free_mode": "organic posting"},
    "instagram": {"kind": "social", "format": "reel/carousel", "free_mode": "organic posting"},
    "substack": {"kind": "newsletter", "format": "newsletter/article", "free_mode": "free publishing"},
    "reddit": {"kind": "community", "format": "discussion/resource post", "free_mode": "community participation"},
    "pinterest": {"kind": "visual", "format": "pin/idea graphic", "free_mode": "organic publishing"},
    "tiktok": {"kind": "video", "format": "short video", "free_mode": "organic publishing"},
    "github": {"kind": "technical", "format": "project/docs update", "free_mode": "public repository/pages"},
    "threads": {"kind": "social", "format": "short discussion", "free_mode": "organic posting"},
    "google_business": {"kind": "listing", "format": "business profile update", "free_mode": "eligible free listing"},
    "bing_places": {"kind": "listing", "format": "business listing", "free_mode": "free listing"},
    "apple_business_connect": {"kind": "listing", "format": "business place card", "free_mode": "free business listing"},
    "nextdoor": {"kind": "local", "format": "business/local post", "free_mode": "free business presence/posting where available"},
}


@dataclass(frozen=True)
class Product:
    product_id: str
    title: str
    audience: str
    objective: str
    destination: str | None
    journey_kind: str
    disclosure: str
    prohibited_claims: tuple[str, ...]


PRODUCTS = {
    "education-hub": Product(
        "education-hub",
        "AI Evolutionary Evolutions Education Hub",
        "learners, builders, programmers and AI/robotics enthusiasts",
        "Invite people to explore practical AI, Linux, coding, blockchain, robotics and ANIMA/RPG learning.",
        "https://aievolutionaryevolutions.com",
        "education",
        "Clearly distinguish educational material from financial, legal, safety or performance guarantees.",
        ("guaranteed learning outcome", "guaranteed income"),
    ),
    "funding-getbizfunds": Product(
        "funding-getbizfunds",
        "Business Funding Information - GetBizFunds",
        "business owners seeking financing information",
        "Explain the financing-information route and direct interested business owners to the owner-provided destination.",
        "https://lippytmai.getbizfunds.com",
        "funding_customer",
        "Use a clear referral/affiliate disclosure where applicable and state that financing approval, rates and amounts are not guaranteed.",
        ("guaranteed approval", "guaranteed amount", "guaranteed rate"),
    ),
    "funding-7figures": Product(
        "funding-7figures",
        "Business Financing Information - 7 Figures Credit",
        "business owners seeking business financing information",
        "Create educational customer-facing financing content with a clear referral route.",
        "http://www.7figurescredit.com?a_aid=lippytm",
        "funding_customer",
        "Disclose the referral/affiliate relationship where applicable; never promise approval or financing results.",
        ("guaranteed approval", "guaranteed funding", "guaranteed credit result"),
    ),
    "partner-7figures": Product(
        "partner-7figures",
        "7 Figures Referral Partner Opportunity",
        "prospective referral partners",
        "Explain the partner opportunity separately from customer financing and direct interested people to the partner route.",
        "http://join.7figurespartners.com/?a_aid=lippytm",
        "funding_partner",
        "Disclose the referral relationship and only describe compensation from current verified provider terms.",
        ("guaranteed earnings", "automatic income", "guaranteed commissions"),
    ),
    "partner-lendtrack": Product(
        "partner-lendtrack",
        "LendTrack Referral Partner Route",
        "prospective referral partners",
        "Create partner-recruitment education and route qualified interest to the owner-provided partner destination.",
        "http://lendtrack.ai/join/lippytmai",
        "funding_partner",
        "Keep partner recruitment separate from financing-customer messaging; verify current program terms before claims about compensation.",
        ("guaranteed earnings", "guaranteed commissions", "guaranteed results"),
    ),
    "book-incubator": Product(
        "book-incubator",
        "19-Book / Chapter Incubator and ANIMA RPG Multiverse",
        "readers, creators, learners and technology enthusiasts",
        "Build interest in the evolving NFT/eBook/audiobook/video-book/ANIMA RPG title and chapter universe.",
        None,
        "publishing",
        "Do not claim an edition is published, sold, minted or available until that exact edition and destination are verified.",
        ("available now", "published", "minted", "guaranteed collectible value"),
    ),
    "jarvis-ai-building-ai": Product(
        "jarvis-ai-building-ai",
        "AI Building AI with AI Jarvis Assistants Swarms Systems Communications Networks",
        "AI builders, developers, entrepreneurs and technical learners",
        "Explain the Evolutionary Evolutions architecture and invite readers to follow documented builds and educational releases.",
        "https://github.com/lippytm/jarvis-nexus-core",
        "technical",
        "Distinguish tested repository artifacts from planned integrations, autonomous operation and production deployment.",
        ("fully autonomous", "production deployed", "guaranteed business result"),
    ),
}


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _digest(value):
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _tagged_url(base: str | None, channel: str, campaign_id: str) -> str | None:
    if base is None:
        return None
    parsed = urlsplit(base)
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if any(k.startswith("utm_") for k, _ in pairs):
        raise ValueError("configured destination already contains attribution fields")
    pairs.extend((("utm_source", channel), ("utm_medium", "organic"), ("utm_campaign", campaign_id)))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(pairs), parsed.fragment))


def product_record(product_id: str) -> dict:
    if product_id not in PRODUCTS:
        raise ValueError("unknown product")
    return asdict(PRODUCTS[product_id])


def free_market_registry() -> dict:
    body = {
        "schema_version": 1,
        "kind": "jarvis.free_organic_market_registry",
        "state": "planning_registry",
        "channels": FREE_CHANNELS,
        "external_actions": 0,
        "live_connections": 0,
    }
    return {**body, "registry_sha256": _digest(body)}


def _cta(product: Product) -> str:
    if product.destination:
        if product.journey_kind == "funding_customer":
            return "Review the provider information and decide whether the financing route fits your business needs."
        if product.journey_kind == "funding_partner":
            return "Review the current partner program and application route before deciding whether to participate."
        if product.journey_kind == "technical":
            return "Review the documented project, evidence and current development status."
        return "Explore the reviewed resource and choose the next useful step."
    return "Follow the project while the exact public product destination and release state are verified."


def campaign_packet(product_id: str, *, campaign_id: str = "organic-001") -> dict:
    product = PRODUCTS.get(product_id)
    if product is None:
        raise ValueError("unknown product")
    if not campaign_id or len(campaign_id) > 80:
        raise ValueError("invalid campaign id")
    briefs = []
    for channel, meta in FREE_CHANNELS.items():
        candidate_url = _tagged_url(product.destination, channel, campaign_id)
        community_note = None
        if channel == "reddit":
            community_note = "Lead with useful discussion; follow each community's self-promotion and link rules."
        if channel in {"google_business", "bing_places", "apple_business_connect", "nextdoor"}:
            community_note = "Use only after business eligibility, exact listing identity and destination are verified."
        brief = {
            "channel": channel,
            "format": meta["format"],
            "free_mode": meta["free_mode"],
            "product_id": product.product_id,
            "product_title": product.title,
            "audience": product.audience,
            "objective": product.objective,
            "hook_direction": f"Connect {product.title} to one concrete problem or curiosity for {product.audience}.",
            "proof_direction": "Use only sourced facts, tested artifacts, owner-reported facts clearly labelled, or explicit plans/simulations.",
            "cta": _cta(product),
            "candidate_url": candidate_url,
            "url_status": "unverified_candidate" if candidate_url else "unassigned",
            "disclosure": product.disclosure,
            "prohibited_claims": list(product.prohibited_claims),
            "community_note": community_note,
            "state": "unpublished_draft_brief",
        }
        briefs.append(brief)
    body = {
        "schema_version": 1,
        "kind": "jarvis.organic_campaign_packet",
        "campaign_id": campaign_id,
        "product": asdict(product),
        "briefs": briefs,
        "newsletter": newsletter_section(product_id),
        "actual_metrics": None,
        "model_calls": 0,
        "external_actions": 0,
        "publishing_actions": 0,
    }
    return {**body, "packet_sha256": _digest(body)}


def newsletter_section(product_id: str) -> dict:
    product = PRODUCTS.get(product_id)
    if product is None:
        raise ValueError("unknown product")
    return {
        "headline": product.title,
        "audience": product.audience,
        "summary": product.objective,
        "cta": _cta(product),
        "destination": product.destination,
        "destination_status": "owner_provided_unverified" if product.destination else "unassigned",
        "disclosure": product.disclosure,
        "state": "newsletter_candidate_unpublished",
    }


def newsletter_packet(product_ids=None) -> dict:
    ids = list(PRODUCTS) if product_ids is None else list(product_ids)
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("product ids must be unique and non-empty")
    sections = [newsletter_section(pid) for pid in ids]
    body = {
        "schema_version": 1,
        "kind": "jarvis.organic_newsletter_packet",
        "title": "Evolutionary Evolutions - Free Organic Marketing & Product Connections",
        "sections": sections,
        "publication_state": "unpublished_draft",
        "actual_metrics": None,
        "external_actions": 0,
    }
    return {**body, "packet_sha256": _digest(body)}
