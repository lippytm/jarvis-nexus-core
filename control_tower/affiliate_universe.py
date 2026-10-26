"""Deterministic Affiliate Marketing Universe planning records.

This module models opportunity categories and campaign routes only. It does not discover
or join affiliate programs, publish content, contact providers, move money, read analytics,
or represent earnings. "Unlimited possibilities" and "infinite opportunities" are creative
brand language, not guarantees of availability, acceptance, demand, commissions, or income.
"""
from hashlib import sha256
import json


AFFILIATE_UNIVERSE = {
    "name": "Affiliate Marketing Universes of Unlimited Possibilities and Infinite Opportunities",
    "sponsor": "Intergalactic Corporate Services LLC",
    "relationship": "parallel_theme",
    "creative_tagline": "Unlimited Possibilities. Infinite Opportunities. One Verified Route at a Time.",
    "reality_label": (
        "Aspirational creative framing. Programs, eligibility, terms, commissions, demand and results "
        "must be verified individually; no earnings or availability are guaranteed."
    ),
    "operating_rule": "Discover -> Verify -> Educate -> Disclose -> Route -> Measure -> Improve.",
}


OPPORTUNITY_WORLDS = {
    "business-funding-referrals": {
        "state": "owner_routes_present_unverified_current_terms",
        "purpose": "Business-financing education and separately disclosed referral-partner pathways.",
        "examples": ["7 Figures Credit", "LendTrack", "GetBizFunds"],
        "monetization_model": "provider-defined referral/affiliate compensation if eligible and earned",
        "guardrails": ["no guaranteed approval", "no guaranteed funding", "no guaranteed earnings"],
    },
    "ai-tools-software": {
        "state": "planned_opportunity_world",
        "purpose": "Educational reviews, comparisons, tutorials and disclosed referrals for useful AI/software tools.",
        "examples": [],
        "monetization_model": "affiliate/referral only after program and terms are verified",
        "guardrails": ["no invented partnership", "no unsupported performance claims"],
    },
    "hosting-websites-domains": {
        "state": "planned_opportunity_world",
        "purpose": "Website, hosting, domain and creator-platform education connected to build tutorials.",
        "examples": [],
        "monetization_model": "verified affiliate/referral programs",
        "guardrails": ["disclose affiliation", "separate tutorial value from sales claims"],
    },
    "education-memberships": {
        "state": "planned_internal_offer_world",
        "purpose": "Free and future paid learning memberships, quests, build-alongs and creator education.",
        "examples": ["Free Explorer", "Builder Member", "Affiliate Builder", "Business Creator"],
        "monetization_model": "membership pricing only after offer, fulfillment and destination are verified",
        "guardrails": ["no invented price", "no invented benefits", "no guaranteed learning or income"],
    },
    "books-media-publishing": {
        "state": "planned_product_world",
        "purpose": "eBooks, audiobooks, video books, ANIMA/RPG worlds, newsletters and derivative media.",
        "examples": ["19-Book / Chapter Incubator", "ANIMA RPG Multiverse"],
        "monetization_model": "direct product, membership or affiliate distribution after release verification",
        "guardrails": ["do not claim unpublished editions are available", "no guaranteed collectible value"],
    },
    "robotics-wearables": {
        "state": "research_opportunity_world",
        "purpose": "Educational and product-discovery content around robotics, humanoids and wearable technologies.",
        "examples": ["CryptoCyberSecurity", "CryptoCyberBorg", "CryptoCyberpunk", "CryptoCyberSteampunk", "CryptoClockworks"],
        "monetization_model": "future products, services or verified affiliate relationships",
        "guardrails": ["no unverified safety claims", "simulation is not physical readiness"],
    },
    "3d-printing-manufacturing": {
        "state": "research_opportunity_world",
        "purpose": "3D printable wearables, robotics components, digital fabrication and maker education.",
        "examples": ["3D Printable Wearable Universes"],
        "monetization_model": "future digital products, fabrication services or verified referrals",
        "guardrails": ["verify design rights", "verify material/device claims"],
    },
    "developer-linux-blockchain": {
        "state": "education_opportunity_world",
        "purpose": "Coding, Linux, Bedrock, OMARCHY, blockchain and developer-tool education.",
        "examples": ["Life Is Code", "The Code Coding Universes"],
        "monetization_model": "education, memberships, products or verified developer-tool referrals",
        "guardrails": ["tested code is not guaranteed production readiness", "no invented tool partnerships"],
    },
    "creator-studio-multimedia": {
        "state": "planned_opportunity_world",
        "purpose": "Creative Creations Studios, video, audio, animation, trailers, documentaries and ad-copy services.",
        "examples": ["Evolutionary Evolutions Creative Creations Studios"],
        "monetization_model": "services, products, memberships or verified creator-tool affiliations",
        "guardrails": ["generated draft is not published media", "verify rights and licenses"],
    },
    "newsletter-community": {
        "state": "planned_audience_world",
        "purpose": "Newsletter, community, comedy, Space Alien satire, education and recurring audience relationships.",
        "examples": ["Intergalactic Injective Marketing Desk", "Intergalactic Pun Desk"],
        "monetization_model": "future memberships, sponsorships or disclosed affiliate links after verification",
        "guardrails": ["no invented subscriber counts", "sponsorships must be real and disclosed"],
    },
    "local-business-services": {
        "state": "planned_opportunity_world",
        "purpose": "Business-building education, local services, websites, CRM, automation and lead-generation concepts.",
        "examples": [],
        "monetization_model": "services, memberships or verified referrals",
        "guardrails": ["consent for leads", "no fabricated local relationships"],
    },
    "space-alien-entertainment": {
        "state": "fictional_brand_world",
        "purpose": "Comedy, satire, ANIMA/RPG storytelling and wordplay that can introduce one relevant real-world route.",
        "examples": ["Join the Space Aliens", "Entertainment of Life", "Who's Funny Now?"],
        "monetization_model": "books, media, memberships, merchandise concepts or disclosed affiliate routes after verification",
        "guardrails": ["fiction remains labeled fiction", "jokes are not evidence or promises"],
    },
}


ROUTE_CLASSES = {
    "owned_product": "Intergalactic Corporate Services LLC or owner-controlled product/service route.",
    "affiliate_referral": "Third-party program route with disclosure and verified current terms.",
    "membership": "Free or paid membership route with verified offer, pricing and fulfillment.",
    "education": "Value-first educational route with no implied purchase requirement.",
    "research": "Research/R&D route with no implied availability for purchase.",
    "fiction_entertainment": "Creative/ANIMA route that may bridge to one separately identified real offer.",
}


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _digest(value):
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def universe_registry():
    body = {
        "schema_version": 1,
        "kind": "jarvis.affiliate_universe_registry",
        "state": "planning_registry",
        "theme": AFFILIATE_UNIVERSE,
        "opportunity_worlds": OPPORTUNITY_WORLDS,
        "route_classes": ROUTE_CLASSES,
        "actual_program_count": None,
        "actual_revenue": None,
        "external_actions": 0,
    }
    return {**body, "registry_sha256": _digest(body)}


def opportunity_world(world_id):
    if world_id not in OPPORTUNITY_WORLDS:
        raise ValueError("unknown opportunity world")
    body = {
        "schema_version": 1,
        "kind": "jarvis.affiliate_opportunity_world",
        "world_id": world_id,
        **json.loads(_canonical(OPPORTUNITY_WORLDS[world_id])),
        "prompt_11_review": [
            "Verify the exact program, provider, eligibility, destination and current terms before promotion.",
            "Use a clear affiliate/referral disclosure where applicable.",
            "Do not guarantee earnings, acceptance, sales, commissions or demand.",
            "Keep owned products, memberships, research and third-party referrals visibly distinct.",
            "Record actual clicks, leads, sales and commissions only from authorized evidence sources.",
        ],
        "external_actions": 0,
    }
    return {**body, "world_sha256": _digest(body)}


def opportunity_matrix(world_ids=None):
    ids = list(OPPORTUNITY_WORLDS) if world_ids is None else list(world_ids)
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("world ids must be unique and non-empty")
    worlds = [opportunity_world(world_id) for world_id in ids]
    body = {
        "schema_version": 1,
        "kind": "jarvis.affiliate_opportunity_matrix",
        "state": "planning_only",
        "creative_horizon": "Unlimited possibilities / infinite opportunities",
        "reality_boundary": AFFILIATE_UNIVERSE["reality_label"],
        "worlds": worlds,
        "next_step": "Select one world, verify one real offer/program, create one disclosed campaign, and measure one evidenced outcome before scaling.",
        "external_actions": 0,
        "actual_metrics": None,
    }
    return {**body, "matrix_sha256": _digest(body)}
