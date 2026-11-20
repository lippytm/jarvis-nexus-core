"""Authored portfolio planning defaults, not a live account or product inventory."""
from dataclasses import asdict, dataclass
import json
from types import MappingProxyType

from control_tower.funnels import DESTINATIONS
from control_tower.network_contract import PROJECTS, canonical, digest

CATALOG_VERSION = "2026-10-22.1"


@dataclass(frozen=True)
class Initiative:
    id: str
    project_id: str
    title: str
    summary: str
    audience: str
    formats: tuple
    plan_steps: tuple
    outcome: str
    evidence_gaps: tuple
    boundaries: tuple
    destination_label: str
    destination_urls: tuple = ()
    destination_state: str = "unassigned"
    journey_kind: str = "none"


_ITEMS = (
    Initiative("jarvis-tools", "ai-jarvis", "Jarvis tools and assistant building",
        "Turn a recurring work problem into a small reusable tool and a reviewed assistant mission.",
        "Charles and future Jarvis collaborators", ("Tool proposal", "Tested change", "Teaching note"),
        ("Choose one repeated task and a reproducible example.", "Draft a minimal change with explicit inputs and outputs.", "Review the change and retain its actual test evidence."),
        "One useful change with reproducible checks and a clear recovery path.",
        ("A real task selected for the next cycle", "Independent release review", "Observed benefit in actual use"),
        ("Generated proposals are inactive.", "The owner retains release and account authority."),
        "Jarvis Nexus development repository", ("https://github.com/lippytm/jarvis-nexus-core",), "owner_reference_unverified"),
    Initiative("website-learning", "ai-evolutionary-evolutions", "Education website and membership inquiries",
        "Develop programming, Linux and AI learning material with a clear inquiry journey on AI Evolutionary Evolutions.",
        "Learners exploring practical technology", ("Lesson page", "Inquiry page", "Learning checklist"),
        ("Select one learner question and one lesson outcome.", "Prepare the lesson and one optional inquiry action.", "Verify the actual page, form receipt and source attribution."),
        "A reviewed lesson and a working, measured inquiry path when account access is available.",
        ("Hostinger product and site identity", "Supported form delivery", "Actual consented inquiry evidence"),
        ("Keep this education destination separate from the proposed affiliate platform.", "An inquiry is not paid access or proof of learning."),
        "AI Evolutionary Evolutions", ("https://aievolutionaryevolutions.com",), "owner_reference_unverified", "member"),
    Initiative("affiliate-builder", "funding-affiliates", "Affiliate website and membership platform",
        "Design the separate platform for affiliate products, member tools and reusable website-building services.",
        "Prospective creators and affiliate partners", ("Offer brief", "Site specification", "Member workflow"),
        ("Choose one audience and one useful member outcome.", "Describe the smallest offer and its delivery workflow.", "Assign a separate destination and test demand before expanding."),
        "One reviewable offer with a named delivery method and a clearly assigned destination.",
        ("Separate website assignment", "Validated customer interest", "Actual fulfillment and support capacity"),
        ("Do not route this platform to the education site by default.", "Prices, demand and income remain unvalidated."),
        "Separate affiliate platform — destination not assigned"),
    Initiative("funding-customers", "funding-affiliates", "Business financing customer journey",
        "Help prospective business-financing customers understand the referral route and reach the selected provider.",
        "Business owners seeking financing information", ("Educational explanation", "Referral page brief", "Attribution review"),
        ("Choose one customer question and confirm current provider information.", "Draft an accurate explanation and visible affiliate disclosure.", "Review the customer destination and measure a permitted referral event."),
        "A clearly disclosed customer referral path with no invented financing outcome.",
        ("Current provider terms and link behavior", "Authorized attribution data", "Confirmed commission records if any"),
        ("Keep customer financing distinct from recruiting referral partners.", "No approval, amount, rate or earnings guarantee."),
        "Owner-provided financing destinations", DESTINATIONS["funding_customer"], "owner_reference_unverified", "funding_customer"),
    Initiative("referral-partners", "funding-affiliates", "Referral partner recruitment",
        "Explain the partner opportunity and route interested people to the correct partner application.",
        "Prospective referral partners", ("Partner overview", "Application guide", "Follow-up checklist"),
        ("Confirm the current partner program and audience.", "Explain responsibilities and compensation only from verified terms.", "Review the partner application route and retain consented outcomes."),
        "A partner-specific application path with clear expectations and documented terms.",
        ("Current partner terms", "Verified application destination", "Actual application and commission evidence"),
        ("Do not replace a financing-customer link with a partner application.", "No invented earnings or automatic outreach."),
        "Owner-provided partner destinations", DESTINATIONS["funding_partner"], "owner_reference_unverified", "funding_partner"),
    Initiative("publishing-library", "publishing-studio", "Publishing library and creative worlds",
        "Develop sourced educational titles and clearly labelled fiction, including the Encyclopedia of Everything Applied and original creative worlds.",
        "Readers and learners", ("Book chapter", "Audio script", "Newsletter outline"),
        ("Select one title, reader need and chapter-sized deliverable.", "Separate sourced factual claims from fiction and speculation.", "Review references, rights, accessibility and edition changes."),
        "One reviewed chapter or script with a reusable source and edition record.",
        ("Current manuscript and rights inventory", "Reader feedback", "Human accessibility review before Studio restart"),
        ("The paused Studio Work Cycle remains paused.", "A planning pack is not a finished book, audiobook or sale."),
        "Publishing destination not assigned"),
    Initiative("interactive-video", "publishing-studio", "Interactive video and teaching studio",
        "Adapt one reviewed lesson or chapter into a storyboard, narration and meaningful interaction plan.",
        "Video learners and prospective creator customers", ("Storyboard", "Narration script", "Interaction map"),
        ("Choose one learning or entertainment outcome.", "Map scenes, narration, captions and interaction choices.", "Review asset rights and test the intended viewer experience."),
        "A reviewable short-video production brief with captions and an interaction purpose.",
        ("Actual source assets and permissions", "Target player capability", "Viewer and accessibility testing"),
        ("An outline is not a rendered video or working interactive player.", "Commercial platform hosting needs its own assignment."),
        "Video platform destination not assigned"),
    Initiative("linux-learning", "linux-education", "Linux and programming learning",
        "Create practical lessons for the proposed Arch, Bedrock and Omarchy learning path.",
        "Charles and future programming learners", ("Lesson", "Practice worksheet", "Environment checklist"),
        ("Choose one concept and identify the actual learner environment.", "Prepare a small exercise with expected observations.", "Review compatibility and use a disposable environment for any later execution."),
        "An instructor-reviewed exercise with explicit environment assumptions.",
        ("Verified operating system and device setup", "Current compatibility documentation", "Observed learner transfer beyond answer matching"),
        ("Do not infer an installed or compatible merged Linux system.", "This pack does not run installers or system commands."),
        "Local learning workspace", (), "local_only"),
    Initiative("robotics-simulation", "robotics-research", "Robotics simulation and education",
        "Explore a single simulated robotics task before considering hardware execution.",
        "Robotics learners and researchers", ("Simulation specification", "Evaluation plan", "Teaching explanation"),
        ("Define a simulated task and environment assumptions.", "Choose observable success and failure conditions.", "Review simulation results separately from physical robot readiness."),
        "A bounded simulation brief with measurable conditions and documented limits.",
        ("Selected simulator and compatible environment", "Actual simulation results", "Separate physical-system review if ever applicable"),
        ("No physical robot control is included.", "A source check does not establish real-world safety or readiness."),
        "Local simulation workspace", (), "local_only"),
    Initiative("wearables-research", "robotics-research", "Wearable technology concepts",
        "Develop practical CryptoClockworks, CryptoCyberSecurity and related wearable concepts around user needs.",
        "Potential wearable users", ("Concept brief", "Interface sketch", "Prototype evaluation plan"),
        ("Choose one everyday user need and a minimal concept.", "Identify device, battery, data and accessibility requirements.", "Review feasibility using sourced specifications and observed prototype results."),
        "One testable concept with its technical assumptions and evidence gaps exposed.",
        ("Actual component specifications", "User feedback", "Measured prototype behavior"),
        ("No medical, security or protection effectiveness is asserted.", "No device or sensor access is implied."),
        "Research destination not assigned"),
    Initiative("business-operations", "business-operations", "Business operating system",
        "Organize project decisions, expenses, documents and follow-ups without mixing private records into public code.",
        "Charles and authorized collaborators", ("Operating checklist", "Decision brief", "Expense review template"),
        ("Choose one recurring administrative bottleneck.", "Define a minimal record, owner and review cadence.", "Verify the record against authorized source documents."),
        "One reusable operating routine with an owner and evidence-based completion check.",
        ("Authorized source records", "Current expense and revenue data", "Actual review completion"),
        ("Keep tax IDs, credentials and private documents out of exported public examples.", "Templates do not establish legal or tax compliance."),
        "Private operating workspace", (), "local_only"),
    Initiative("personal-workflow", "business-operations", "Personal focus, access and continuity",
        "Make it easier to resume work, organize learning and capture ideas across devices and breaks.",
        "Charles", ("Session plan", "Resume bookmark", "Accessibility checklist"),
        ("Choose one achievable outcome for the available time.", "Record the next action and any access or device obstacle.", "Finish with a concise bookmark and the evidence needed to resume."),
        "A practical session plan and a clear restart point after a break.",
        ("Actual available time and device context", "User-confirmed accessibility needs", "Observed completion and usefulness"),
        ("No calendar, device, health record or background monitoring access is assumed.", "The owner controls personal priorities and pace."),
        "Private personal workspace", (), "local_only"),
)

INITIATIVES = MappingProxyType({item.id: item for item in _ITEMS})


def initiative(initiative_id):
    if not isinstance(initiative_id, str) or initiative_id not in INITIATIVES:
        raise ValueError("unknown initiative")
    item = asdict(INITIATIVES[initiative_id])
    item["project_label"] = PROJECTS[item["project_id"]]
    item["destination"] = {
        "label": item.pop("destination_label"), "urls": item.pop("destination_urls"),
        "state": item.pop("destination_state"),
    }
    # Public API uses JSON-native lists so the browser and Python share one shape.
    return json.loads(canonical(item))


def portfolio_catalog():
    record = {"schema_version": 1, "kind": "jarvis.portfolio_catalog",
              "catalog_version": CATALOG_VERSION,
              "scope": "authored planning defaults; not a live account, product or revenue inventory",
              "initiatives": [initiative(item.id) for item in _ITEMS],
              "live_metrics": None, "external_actions": 0}
    return {**record, "catalog_sha256": digest(record)}
