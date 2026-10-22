# Jarvis provider connections: documented routes and implementation boundaries

**Reviewed:** October 22, 2026.  
**Starting source revision:** `575ebc777fae0165c93247e8c6da44c440539c4d`.  
**Result:** portable draft-handoff catalog and a bounded, transport-injected Hostinger inventory probe. No account connection, credential discovery, live model call, website mutation, payment action or social publication was performed.

Existing Control Tower code was inspected before researching the OpenAI interface. It contained connection plans and recorded observations, but no OpenAI network adapter in the inspected modules. The catalog describes this repository's implementation, not the capabilities or permissions of separate connected apps in ChatGPT.

## What is available in this package

`control_tower/provider_catalog.py` provides:

- `PROVIDERS`: an immutable mapping of provider records, including immutable nested records.
- `provider_catalog()`: an independent, JSON-serializable copy of the complete catalog.
- `provider_details(provider_id)`: an independent copy for an exact known ID; malformed and unknown IDs raise `ValueError("unknown_provider")`.
- `DISTRIBUTION_CHANNELS`: Facebook, LinkedIn, Substack, Instagram, Threads, YouTube and GitHub.

All twelve targets support **manual draft export** in the sense that a local context/content packet can be carried by the user to that target. This does not upload a draft, authenticate an account or create an integration. ChatGPT and the OpenAI API have separate IDs. All connection statuses remain **unverified**, all API write operations remain **not implemented**, and all live dispatchers remain **not implemented**. Hostinger additionally has an implemented inventory request/parser that requires an explicitly supplied, trusted transport.

## Official routes and required configuration

| Target | Supported official boundary | Configuration still required |
|---|---|---|
| **ChatGPT / Business** (`chatgpt`) | A portable packet can be reviewed in a user-selected chat. This repository has no ability to modify ChatGPT's account, private conversations or runtime. API usage is distinct from subscription usage. [Official pricing distinction](https://learn.chatgpt.com/docs/pricing) and [API authentication](https://developers.openai.com/api/reference/overview). | User-controlled destination and appropriate project-data sharing. No API credential is inferred from a ChatGPT subscription. |
| **OpenAI API** (`openai`) | The Responses API supports model requests and tool-enabled application workflows. API authentication requires appropriate bearer credentials. [Responses reference](https://developers.openai.com/api/reference/responses/overview), [authentication reference](https://developers.openai.com/api/reference/overview). | Authorized project credential or workload identity, model permission, application context and a usage budget. Secrets remain in a secure server runtime. |
| **Gemini** (`gemini`) | Google documents content generation, streaming and an Interactions API. [API reference](https://ai.google.dev/api), [credential guide](https://ai.google.dev/gemini-api/docs/generate-content/api-key). | Authorized project/API credential, allowed model, usage configuration and explicitly supplied context. This does not import existing Gemini app conversations. |
| **Claude** (`claude`) | The Messages API provides direct programmatic model access; application code manages its context and tool loop. [API overview](https://platform.claude.com/docs/en/api/overview), [Messages guide](https://platform.claude.com/docs/en/build-with-claude/working-with-messages). | Claude Console/API access or supported workload identity, allowed model, API version and budget. A Claude/Cowork consumer session is not proof of an API connection. |
| **Hostinger** (`hostinger`) | Current official documentation describes API operations to list, create, edit, publish and clone AI Builder/Horizons projects. Manual-mode Website Builder separately documents custom-code embeds and editor publishing. [AI Builder integrations](https://docs.hostinger.com/ai-builder/integrations), [embed guide](https://www.hostinger.com/support/6463152-hostinger-ai-builder-manual-mode-how-to-embed-custom-code/), [manual publish guide](https://www.hostinger.com/support/6475340-hostinger-ai-builder-manual-mode-how-to-publish-a-website/). | Confirm the existing site's product/mode and project identity; configure authorized API access only for compatible endpoints or use the supported editor/embed route. Horizons API support does not establish that `aievolutionaryevolutions.com` is API-editable. |
| **Facebook** (`facebook`) | The Pages API documents Page management and publication permissions, including `pages_manage_posts`. This is Page functionality. [Pages API](https://developers.facebook.com/documentation/pages-api.md/), [posts](https://developers.facebook.com/documentation/pages-api/posts.md/). | Meta app, actual Page authority, appropriate access token, endpoint permissions and required access/review. Personal-profile access is a separate question. |
| **Instagram** (`instagram`) | Official publishing documentation distinguishes Instagram Login from Facebook Login and their tokens/permission sets for professional accounts. [Content publishing](https://developers.facebook.com/documentation/instagram-platform/content-publishing.md/). | Select the login path, verify the professional account, obtain that path's authorized token/permissions and validate media support. Facebook access alone is insufficient evidence. |
| **Threads** (`threads`) | The Threads API documents its own authorization and post-creation flow. [Getting started](https://developers.facebook.com/documentation/threads/get-started.md/), [create posts](https://developers.facebook.com/documentation/threads/create-posts.md/). | App with Threads use case, user authorization, required permissions and applicable app review/access. No posting or reply adapter is included. |
| **LinkedIn** (`linkedin`) | The Posts API distinguishes member publication (`w_member_social`) from organization publication (`w_organization_social` plus an appropriate organization role). [Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2026-10), [API access](https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access). | Approved app/product access, OAuth consent, exact member/organization target, required role, supported API version and media flow. |
| **Substack** (`substack`) | The official editor supports drafts and publication; official embeds/RSS support distribution. Substack also documents a **read-only MCP** connector for eligible publications, not a publishing connector. [Editor](https://support.substack.com/hc/en-us/articles/360037831771-How-do-I-publish-a-new-post-on-Substack), [MCP](https://support.substack.com/hc/en-us/articles/50834026608916-How-to-connect-Substack-to-your-AI-Assistant), [embeds](https://support.substack.com/hc/en-us/articles/25665267911572-How-do-I-embed-Substack-posts-or-notes-on-a-website), [RSS](https://support.substack.com/hc/en-us/articles/360038239391-Is-there-an-RSS-feed-for-my-publication). | Publication/editor authority for manual handoff. The documented MCP connection requires a publication Admin, a Bestseller publication and an MCP-compatible client. User eligibility is unverified. |
| **YouTube** (`youtube`) | The Data API documents video upload and metadata with OAuth authorization. [Video insertion](https://developers.google.com/youtube/data/reference/rest/v3/videos/insert), [OAuth](https://developers.google.com/youtube/v3/guides/authentication). | Enabled API project, channel-authorized OAuth/upload scope, actual video asset, quota, explicit privacy, audience and applicable synthetic-media declarations. |
| **GitHub** (`github`) | REST API operations use appropriately scoped tokens or GitHub App access; Actions can use their scoped workflow token. [Authentication](https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api), [fine-grained permissions](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens). | Exact owner/repository/branch, operation-specific permissions, observed revision and review policy. A metadata read does not establish write or merge authority. |

### Two boundaries that changed the implementation choice

**Hostinger:** the retrieved integrations page was last updated October 20, 2026 and explicitly includes AI Builder API edit/publish capabilities. Therefore this design does not assume that Hostinger's API is limited to hosting infrastructure. It first requires identification of the actual product and site, because the documented Horizons inventory is not an inventory proof for every manual-mode builder project. The manual editor/embed route remains separately documented.

**Substack:** the official MCP help article says its connector reads publication metrics/settings and cannot publish posts, send Notes or modify accounts. No official general-purpose publishing API was established in the official materials reviewed for this task. This is a bounded research finding, not a claim that every possible private or future integration is impossible. The chosen publishing handoff is a reviewed local draft for the official editor. Private endpoint and session-cookie automation are not part of the implementation.

The retrieved YouTube video-insertion reference states that privacy can default to public and that unverified API projects are not automatically restricted to private uploads. Any future upload adapter must specify privacy explicitly; project verification is not a publication-control mechanism. No upload was attempted.

## Hostinger inventory probe

Implementation: `control_tower/hostinger_probe.py`. Only the following request is prepared:

```text
GET https://developers.hostinger.com/api/horizons/v1/websites
```

The fixed base URL and bearer authentication are documented in the [API overview](https://docs.hostinger.com/api-reference/overview). The [website-list operation](https://docs.hostinger.com/api-reference/endpoints/horizons/websites/get-website-list) and [official OpenAPI specification](https://developers.hostinger.com/openapi/openapi.json) establish an unpaginated response array. The inspected schema requires `website_id`, `status`, `created_at` and `website_url`; optional `description` and `domain` are nullable strings. Known status values are active, suspended, deleting and deleted. The probe counts entries and returns no site identifiers, domains, descriptions or interface URLs.

### Interface and limits

- `prepare_request(token)` validates the caller-supplied token's header-safe form and returns an immutable GET descriptor. Its representation excludes the credential. Only trusted transport code should call `headers_for_transport()`; never log/serialize the request internals or use `dataclasses.asdict()` on it.
- `probe(transport, token)` invokes `transport(request)` exactly once. The injected transport returns `ProbeResponse`; this package has no default HTTP sender and reads no environment variables or credential stores.
- The descriptor requests a **5-second timeout**, a **64 KiB response cap**, identity encoding and **no redirects**. A trusted transport must enforce these before returning. The adapter rejects any reported redirect, changed final URL, oversized body, unsupported content encoding or unexpected status. It cannot sandbox arbitrary caller-supplied Python transport code.
- Parsing rejects duplicate JSON keys, non-finite values, invalid UTF-8, malformed JSON, unexpected collection/schema shape and duplicate website IDs. It does not follow any URL in the response.
- Authentication, rate-limit, server and transport errors become fixed sanitized statuses. Provider bodies and raw exception messages are never returned. No automatic retry occurs.
- A valid response returns aggregate counts, a SHA-256 digest and an observation candidate marked `caller_supplied_transport_unverified`. Even successful offline fixtures leave `connection_status: unverified` and `live_access_verified: false`.

This separation is deliberate: a mocked response, or a response supplied by an untrusted callback, cannot authenticate a real account. A later live read requires an approved runtime transport, securely configured credentials and retained provenance before a separate observation can describe live access. The read does not establish editing/publishing permission, checkout behavior, affiliate attribution or existing-site compatibility. Hostinger documents tokens as inheriting their owner's permissions; the GET-only adapter does not change those credential permissions.

## Verification performed

The added standard-library tests cover catalog coverage, immutable/defensive copies, unknown provider rejection, official-documentation URL boundaries, separation of export from live authority, exact GET request constraints, token redaction, redirects, response limits, schema changes, duplicate JSON/website identities, sanitized errors, no retry and no false claim of live access.

```text
python3 -m py_compile control_tower/provider_catalog.py control_tower/hostinger_probe.py tests/test_provider_catalog.py tests/test_hostinger_probe.py
python3 -m unittest discover -s tests -p test_provider_catalog.py -v
python3 -m unittest discover -s tests -p test_hostinger_probe.py -v
```

Result at authoring: syntax passed; **6 catalog tests and 11 offline probe tests passed**. The broader integrated repository suite is a separate root-level check.

### Research limitations

Only primary official documentation was used. Some Meta direct page fetches returned access/rate-limit errors; their official indexed documentation excerpts supplied the boundaries recorded here. This does not establish an outage or account-access failure. Hostinger's public OpenAPI was retrieved through the web research tool after the shell's network sandbox prevented downloading that public specification. No authenticated Hostinger endpoint was called.

Documentation capability, implemented code, authorized account access and a successful live operation are separate evidence states. The next bounded task is to verify the actual Hostinger product/site identity through a supported authorized read and then select one reversible integration. Production publication, model dispatch and social posting remain outside this change.
