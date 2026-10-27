"""Official-documentation catalog for portable Jarvis handoffs, not live access.

This module does not inspect credentials, contact providers, publish, or install tools.
Available manual draft export means a human can carry a local packet to the target;
it does not mean this module writes into an account. Separate app connectors, if any,
are outside this catalog's implementation status.
"""
from copy import deepcopy
from types import MappingProxyType


REVIEWED_ON = "2026-10-22"
DISTRIBUTION_CHANNELS = ("facebook", "linkedin", "substack", "instagram", "threads", "youtube", "github")


def _record(label, category, interfaces, requirements, boundaries, urls, documentation_status="documented"):
    return {
        "label": label, "category": category, "reviewed_on": REVIEWED_ON,
        "connection_status": "unverified", "api_documentation_status": documentation_status,
        "handoff_modes": {"manual_draft_export": "available", "live_api": "not_implemented"},
        "handoff_delivery": "human_transfer_required",
        "live_api_adapter": "not_implemented", "write_operations": "not_implemented",
        "official_interfaces": list(interfaces), "required_configuration": list(requirements),
        "boundaries": list(boundaries), "documentation_urls": list(urls),
    }


_DATA = {
    "chatgpt": _record(
        "ChatGPT / ChatGPT Business", "assistant_ui",
        ("Manual handoff of a local draft or context packet",),
        ("User-controlled destination chat or workspace", "Review which project information may be transferred"),
        ("This package cannot read, modify or synchronize a ChatGPT account or runtime.",
         "A ChatGPT subscription is not evidence that an OpenAI API project credential is configured."),
        ("https://learn.chatgpt.com/docs/pricing", "https://developers.openai.com/api/reference/overview"),
        "manual_handoff"),
    "openai": _record(
        "OpenAI API", "model_api",
        ("Responses API for model requests and tool-enabled workflows",),
        ("Authorized API project and server-held credential or workload identity", "Model access and usage budget",
         "Application-owned conversation state and reviewed tool permissions"),
        ("API calls do not imply access to existing ChatGPT conversations.",
         "API usage and subscription usage must be accounted for separately."),
        ("https://developers.openai.com/api/reference/responses/overview",
         "https://developers.openai.com/api/reference/overview", "https://learn.chatgpt.com/docs/pricing")),
    "gemini": _record(
        "Google Gemini API", "model_api",
        ("Gemini content generation and streaming APIs", "Interactions API documented for agent workflows"),
        ("Authorized Google project and Gemini API credential", "Allowed model, usage limits and billing configuration",
         "Explicit context supplied by the application"),
        ("Consumer Gemini conversations are not imported by this catalog.",
         "No API request, training, shared memory service or model upgrade is performed here."),
        ("https://ai.google.dev/api", "https://ai.google.dev/gemini-api/docs/generate-content/api-key")),
    "claude": _record(
        "Anthropic Claude API", "model_api",
        ("Messages API for model requests",),
        ("Claude Console access and API credential or configured workload identity",
         "Model access, API version and usage budget", "Application-managed context and tool loop"),
        ("Claude consumer chats and Cowork state are not synchronized by the Messages API adapter plan.",
         "No live model call or generated-code execution is included."),
        ("https://platform.claude.com/docs/en/api/overview",
         "https://platform.claude.com/docs/en/build-with-claude/working-with-messages")),
    "hostinger": _record(
        "Hostinger", "website",
        ("Public API including documented Horizons / AI Builder website operations",
         "Manual-mode Website Builder custom-code embeds and editor publishing"),
        ("Identify the existing site's product/mode and exact project identifier",
         "Authorized hPanel API token for applicable API operations",
         "Confirm supported embed or server integration and publication destination"),
        ("Horizons inventory does not prove that a manual-mode Website Builder site is API-editable.",
         "The included inventory probe has a fixed stdlib HTTPS transport and explicit live CLI; evidence remains offline-only until an authorized real read.",
         "No builder editing, publication, affiliate-account connection or production checkout is implemented."),
        ("https://docs.hostinger.com/ai-builder/integrations", "https://docs.hostinger.com/api-reference/overview",
         "https://docs.hostinger.com/api-reference/endpoints/horizons/websites/get-website-list",
         "https://www.hostinger.com/support/6463152-hostinger-ai-builder-manual-mode-how-to-embed-custom-code/",
         "https://www.hostinger.com/support/6475340-hostinger-ai-builder-manual-mode-how-to-publish-a-website/")),
    "facebook": _record(
        "Facebook Pages", "distribution",
        ("Facebook Pages API for authorized Page operations",),
        ("Meta app, authorized Page and Page access token", "Endpoint-specific permissions including pages_manage_posts for publication",
         "Required app access/review and a confirmed Page role"),
        ("Page access is distinct from personal-profile access.", "Draft preparation does not publish or send messages."),
        ("https://developers.facebook.com/documentation/pages-api.md/",
         "https://developers.facebook.com/documentation/pages-api/posts.md/")),
    "instagram": _record(
        "Instagram", "distribution",
        ("Instagram professional-account content publishing APIs",),
        ("Choose Instagram Login or Facebook Login integration path", "Authorized professional account and app access",
         "Matching token and content-publishing permissions for the chosen login path", "Supported media and account capabilities"),
        ("Instagram Login and Facebook Login use different token and permission requirements.",
         "A Facebook connection does not automatically verify Instagram publishing permission."),
        ("https://developers.facebook.com/documentation/instagram-platform/content-publishing.md/",)),
    "threads": _record(
        "Threads", "distribution",
        ("Threads API for supported post creation and publishing",),
        ("Meta app with Threads use case", "Authorized Threads account and user access token",
         "Required Threads permissions and app access review"),
        ("Threads authorization is a separate provider capability.", "No account discovery, posting or reply automation is implemented."),
        ("https://developers.facebook.com/documentation/threads/get-started.md/",
         "https://developers.facebook.com/documentation/threads/create-posts.md/")),
    "linkedin": _record(
        "LinkedIn", "distribution",
        ("LinkedIn Posts API",),
        ("LinkedIn app product access and member OAuth", "w_member_social for member publication or w_organization_social for organization publication",
         "Required organization role for organization posts", "Supported API version and media-upload flow"),
        ("Member publication permission is distinct from organization access.",
         "Read permission is not inferred from write permission or a public profile."),
        ("https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2026-10",
         "https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access")),
    "substack": _record(
        "Substack", "distribution",
        ("Publication editor for reviewed manual draft handoff", "Documented post/note embeds and publication RSS",
         "Official read-only MCP publication-data connector for eligible publications"),
        ("Authorized publication/editor access for manual publishing",
         "For the documented MCP connector: publication Admin, Bestseller publication and compatible client",
         "Explicitly choose publication audience and email/app delivery when publishing manually"),
        ("The official MCP connector cannot publish posts, send Notes or modify the account.",
         "No official general-purpose publishing API was established in the official documentation reviewed on 2026-10-22.",
         "Eligibility for the user's publication remains unverified; no private endpoint or cookie automation is used."),
        ("https://support.substack.com/hc/en-us/articles/50834026608916-How-to-connect-Substack-to-your-AI-Assistant",
         "https://support.substack.com/hc/en-us/articles/360037831771-How-do-I-publish-a-new-post-on-Substack",
         "https://support.substack.com/hc/en-us/articles/25665267911572-How-do-I-embed-Substack-posts-or-notes-on-a-website",
         "https://support.substack.com/hc/en-us/articles/360038239391-Is-there-an-RSS-feed-for-my-publication"),
        "read_only_mcp_documented"),
    "youtube": _record(
        "YouTube", "distribution",
        ("YouTube Data API including authorized video upload and metadata",),
        ("Google API project with YouTube Data API enabled", "Channel-authorized OAuth and applicable upload scope",
         "Upload media, quota budget and explicit privacy setting", "Required audience and synthetic-media declarations"),
        ("API key alone does not authorize uploading to a channel.",
         "Choose upload privacy explicitly; do not assume an unverified API project forces private uploads.",
         "The catalog does not render video or upload an asset."),
        ("https://developers.google.com/youtube/data/reference/rest/v3/videos/insert",
         "https://developers.google.com/youtube/v3/guides/authentication")),
    "github": _record(
        "GitHub", "engineering_and_distribution",
        ("GitHub REST APIs and scoped GitHub App or token access", "Repository-backed review and Actions workflows"),
        ("Exact owner/repository and target branch", "GitHub App installation or appropriate token permissions",
         "Separate read, contents, pull-request and Actions permissions as applicable", "Observed revision and review/merge policy"),
        ("A successful metadata read does not prove write or merge permission.",
         "Existing connected GitHub app access is separate from this package's unimplemented API dispatcher."),
        ("https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api",
         "https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens")),
}
_EXPANSION_REVIEWED_ON = "2026-10-27"
for _provider_id, _provider in {
    "slack": _record(
        "Slack", "communications",
        ("Reviewed manual handoff; Slack app OAuth for a future runtime adapter",),
        ("Exact workspace and channel IDs", "Authorized app installation and operation-specific scopes",
         "Explicit approval for any message send"),
        ("No message delivery, workspace read or Slack app installation is performed here.",
         "A review label does not authenticate a Slack user."),
        ("https://docs.slack.dev/authentication/installing-with-oauth/",)),
    "zapier": _record(
        "Zapier", "workflow_automation",
        ("Reviewed manual workflow specification", "Documented Human in the Loop approval step"),
        ("Exact account, workflow and permitted actions", "Connected destination apps",
         "Confirm paid-plan eligibility and task budget before selecting Human in the Loop"),
        ("No Zap is created, enabled, triggered or modified here.",
         "An approval step must enforce the decision; merely adding a notification is insufficient."),
        ("https://help.zapier.com/hc/en-us/articles/38731463206029-Request-approval-to-keep-your-workflow-running-with-Human-in-the-Loop",)),
    "claude-cowork": _record(
        "Claude Cowork", "assistant_workspace",
        ("Reviewed manual context/artifact handoff", "Documented custom remote MCP connectors"),
        ("Owner-selected Claude workspace", "Permitted files and connector scopes",
         "Confirm account entitlement and authorization in the target workspace"),
        ("The Claude Messages API does not establish synchronization with Cowork.",
         "This package does not install plugins, run Cowork or transfer private files."),
        ("https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp",)),
    "perplexity": _record(
        "Perplexity", "research",
        ("Reviewed manual research handoff", "Search API for ranked web results"),
        ("Authorized account or API project for the selected route", "Server-held API credential for API use",
         "Research scope and usage budget"),
        ("Search results are evidence candidates, not verified conclusions.",
         "No API call or access to existing Perplexity conversations is implemented."),
        ("https://docs.perplexity.ai/docs/search/overview",)),
}.items():
    _provider["reviewed_on"] = _EXPANSION_REVIEWED_ON
    _DATA[_provider_id] = _provider
del _provider_id, _provider


_DATA["hostinger"]["read_only_probe"] = "implemented_with_stdlib_https_transport"
_DATA["hostinger"]["live_api_adapter"] = "implemented_read_only_horizons_inventory"
_DATA["hostinger"]["live_validation"] = "not_performed"
_DATA["hostinger"]["credential_environment_variable"] = "HOSTINGER_API_TOKEN"


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


PROVIDERS = _freeze(_DATA)


def provider_catalog():
    """Return independent JSON-serializable copies; no access checks or side effects."""
    return deepcopy(_DATA)


def provider_details(provider_id):
    """Strict lookup without aliases, arbitrary URLs, fallback routes or dispatch."""
    if type(provider_id) is not str or not 1 <= len(provider_id) <= 64 or provider_id not in _DATA:
        raise ValueError("unknown_provider")
    return deepcopy(_DATA[provider_id])
