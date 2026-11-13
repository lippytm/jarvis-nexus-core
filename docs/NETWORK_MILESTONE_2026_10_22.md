# AI Jarvis network milestone — October 22, 2026

## 1. Outcome and scope

This milestone turns the existing Control Tower into a portable draft-building
and review workflow spanning Charles's engineering, Hostinger, publishing,
education, funding and business projects. It continues the existing
[draft PR #5](https://github.com/lippytm/jarvis-nexus-core/pull/5) from source
revision `575ebc777fae0165c93247e8c6da44c440539c4d`.

The concrete additions are:

- A standalone Jarvis writing composer with reviewable common-typo corrections,
  undo, copy, and text/JSON export.
- A deterministic factory producing five role-specific assistant specifications
  for each of seven work areas: **35 inactive specifications** in the examples.
- Twelve documented destinations: ChatGPT, OpenAI API, Gemini, Claude, Hostinger,
  Facebook, LinkedIn, Substack, Instagram, Threads, YouTube and GitHub.
- A SQLite ledger that retains handoffs, exact-content review records,
  duplicate detection, return bindings and task budgets across restarts.
- A fixed-endpoint Hostinger inventory request/parser with an injected transport
  interface, plus a dated catalog of supported provider routes and requirements.
- YouTube and GitHub source support in the existing synthetic attribution and
  membership/referral journeys.

The local demonstration makes **zero model calls and zero external actions**.
Specifications are proposals, not running services, new provider accounts or
installed agents. Documentation, prepared packets, actual account access and a
successful live operation remain distinct evidence states. The separate GitHub
connector used to review and publish this PR is not a runtime adapter in this
package.

## 2. AI Building AI across the portfolio

Every project receives five bounded roles. The researcher prepares sourced
notes; the architect proposes a design and acceptance checks; the builder drafts
a small change; the evaluator reviews it; and the reporter prepares an
evidence-based update or channel draft. Each role can prepare drafts only.
Generated tool candidates come from the existing exact-template builder and
pass static evaluation; no generated source is executed or installed.

| Project | Intended work | Example manifest |
| --- | --- | --- |
| AI Jarvis | Engineering and coordination | [ai-jarvis](../examples/network/ai-jarvis.swarm.json) |
| AI Evolutionary Evolutions | Hostinger education and membership inquiries | [ai-evolutionary-evolutions](../examples/network/ai-evolutionary-evolutions.swarm.json) |
| Funding and affiliates | Distinct financing-customer and referral-partner journeys | [funding-affiliates](../examples/network/funding-affiliates.swarm.json) |
| Publishing studio | Sourced book, audio, video and social drafts | [publishing-studio](../examples/network/publishing-studio.swarm.json) |
| Linux education | Programming lessons and learning materials | [linux-education](../examples/network/linux-education.swarm.json) |
| Robotics research | Simulation-first research and education | [robotics-research](../examples/network/robotics-research.swarm.json) |
| Business operations | Project records and operating checklists | [business-operations](../examples/network/business-operations.swarm.json) |

The [project index](../examples/network/project_index.json) records each full
manifest digest. The `source_revision` field identifies the source context
supplied to the factory. The examples use the previously verified baseline
above; this is not the revision of the new factory implementation, a signature,
or proof that the factory fetched that commit. Validation reconstructs the full
known manifest and compares canonical bytes, including types and budgets.

The [public repository inventory](../examples/network/public_repository_inventory.json)
contains **41 public repository metadata records** observed through the GitHub
connector on October 22. It supports project discovery and future mapping.
It excludes private repositories and does not establish code quality,
deployment, installed services or synchronization among those repositories.
Only this Nexus draft branch is changed by this milestone.

### A focused growth workflow

One reviewed project result can supply a technical GitHub update, a LinkedIn
explanation, a Facebook discussion, an Instagram visual brief, a Threads draft,
a Substack article outline, and a YouTube script. These are proposed editorial
uses of a shared evidence record; the package does not automatically generate
finished media or publish them. The project and destination selectors preserve
context when moving a draft between tools.

For a first measurable campaign, choose one education or membership offer,
prepare one source-backed master brief, and adapt it to one selected channel.
Record channel-tagged visits, consented inquiries and confirmed outcomes only
when authorized source data exists. Extend the campaign after the first
complete measured journey. There are no new traffic, signup, revenue or
commission results from this offline milestone.

## 3. Durable handoffs and connection readiness

The ledger's state sequence is:

`pending_review` → `reviewed` → `export_prepared` → `returned_unverified`

Staging binds the project, intended provider, assistant, complete manifest,
source context and optional parent to an immutable content digest. Repeating
the same ID and exact content is idempotent; reusing an ID for different content
is rejected. Default budgets allow two handoffs per assistant and one child
level. Supported configuration is bounded to one through five handoffs and
zero through two levels; a registered manifest cannot quietly redefine its
budgets. The ledger caps storage at 100 swarms and 1,000 handoffs.

A review records the exact digest and a reviewer label different from the
drafting assistant. **A label and hash do not authenticate a person or provider.**
Export prepares a packet for manual transfer. That state does not prove a file
was saved or an external recipient received it. A subsequent file-write failure
can leave a prepared ledger record, which can be exported again to a new path.

Return import requires the original handoff ID, digest and target. It keeps the
response as unverified text. A child can reference a structurally valid returned
packet, but must obtain its own exact-content review before export. Imported
instructions are data, not executable commands or authority to expand scope.
Corrupt or missing stored returns block status inspection and child staging.

JSON packet loading bounds bytes before parsing, rejects duplicate keys and
non-finite numbers, and accepts regular files only. Draft text is limited to
20,000 UTF-8 bytes. CLI file paths must remain under the chosen workspace root.
Complete output files are published without replacing an existing filename;
interrupted serialization leaves no partial final artifact. This requires a
filesystem supporting same-directory hard links.

The local SQLite database stores draft and response text in plaintext. It is not
a credential store, authenticated multi-user service or a defense against an
attacker who can rewrite the database and its hashes. Keep secrets out of draft
packets. Status output contains metadata rather than the full draft text.

| Destination group | Implemented here | Live dependency still unresolved |
| --- | --- | --- |
| ChatGPT, OpenAI API, Gemini, Claude | Portable draft contracts and target-specific requirements | Actual model/account connection, scoped context and a runtime adapter |
| Hostinger | Fixed GET inventory descriptor/parser; documented AI Builder and manual-editor paths | Actual product/site identity, compatible endpoint and trusted live transport |
| Facebook, Instagram, Threads, LinkedIn, YouTube | Draft destinations, official route catalog, channel attribution IDs | Exact account/channel, relevant permissions, media handling and provider adapter |
| Substack | Reviewed editor handoff; documented optional read-only MCP route | Publication authority and, for MCP, actual eligibility and connection |
| GitHub | Draft target and repository metadata reference | This package has no GitHub dispatcher; the separate connected app supplies PR operations |

See [Provider connections](PROVIDER_CONNECTIONS_2026_10_22.md) for official
sources, required configuration and limitations. Hostinger's AI Builder API
documentation includes editing/publishing, but the implemented probe prepares
only a list request. It has **no default HTTP sender**. Its injected transport
must enforce the five-second timeout, 64 KiB cap and no-redirect policy. Even a
valid fixture response leaves live access unverified. Horizons support does not
prove that an existing manual-mode Website Builder site uses that API.

## 4. Spellcheck and practical use

Open [web/jarvis-composer.html](../web/jarvis-composer.html) in a browser. Choose
the project and destination, write a draft, review the common-typo suggestions,
apply selected corrections, and copy or download the result. Corrections are
reversible. URLs, emails, known brands and marked code are protected by the
local checker. It contains 34 typo rules; it is not a comprehensive dictionary
or grammar service. Native spelling is requested separately and depends on the
browser. No application network request or persistent browser storage is used.

This standalone composer does not change ChatGPT's native message box. See the
[composer guide](JARVIS_COMPOSER.md) for the exact export schema, browser limits,
keyboard controls and retained verification. Browser enhanced spelling may use
the browser's service independently of the page. Drafts are memory-only until
copied or downloaded.

### Reproduce the local workflow

Run commands from the repository root. Output paths must be fresh; existing
evidence is never overwritten by the network CLI.

```bash
python scripts/jarvis_network.py catalog --out reports/provider-catalog.json
python scripts/jarvis_network.py demo --out reports/network-demo.json
python scripts/jarvis_network.py factory --project ai-jarvis --targets chatgpt,gemini,claude --swarm jarvis-demo --source-revision 575ebc777fae0165c93247e8c6da44c440539c4d --out reports/jarvis-demo.swarm.json
python scripts/jarvis_network.py stage --manifest reports/jarvis-demo.swarm.json --draft examples/network/example_draft.json --assistant jarvis-demo.builder --handoff demo-first
```

Inspect the manifest and draft. Copy the `handoff_sha256` returned by staging.
After review, replace `DIGEST_FROM_STAGE` below with that exact value. The reviewer
label records local intent; it is not an authenticated human-review claim.

```bash
python scripts/jarvis_network.py review --handoff demo-first --reviewer local-reviewer --digest DIGEST_FROM_STAGE
python scripts/jarvis_network.py export --handoff demo-first --digest DIGEST_FROM_STAGE --out reports/reviewed-handoff.json
python scripts/jarvis_network.py status
```

The exported packet can be carried to the selected tool manually. No CLI command
sends it. A returned JSON packet must use `kind: jarvis.return`, schema version 1,
the original handoff ID and digest, its intended `source_provider`, a unique
`return_id`, response `text`, and at most five HTTPS `evidence_urls`. It is imported
with `python scripts/jarvis_network.py import-return --file reports/return.json`.
See `network_contract.py` for the complete validation contract. Do not represent
a fabricated fixture as a provider's actual response.

## 5. Verification and milestone status

The integrated verifier parses Python syntax before running behavior tests and
the synthetic demonstration. The separate Node job tests the actual pure helper
extracted from the shipped HTML. Both CI jobs use pinned Actions, read-only
repository permissions, five-minute limits and retained evidence artifacts.

```bash
python scripts/verify_control_tower.py
node --test tests/test_composer.mjs
```

Local results and exact source hashes are retained in
[network verification](evidence/network_milestone_2026_10_22.json), its adjacent
test log, and [composer validation](evidence/jarvis-composer-validation.json).
The final local result is **121 Python tests passed**, with **34 Python files**
passing syntax checks, and **34 individual Node tests passed**. All 37 recorded
source hashes still match. The exact Node CI command passed as well; this local
runtime summarizes it as a test-file wrapper, so the retained direct run exposes
all 34 cases. A guarded synthetic run attempted no socket connection, URL open or
subprocess creation. See [integrated checks](evidence/network_milestone_checks_2026_10_22.json)
and [Node output](evidence/network_milestone_node_2026_10_22.txt).
The current branch's exact commit and CI results are recorded on PR #5 after
publication. Older 72-test Control Tower and 99-test bot results belong to the
earlier milestone; they are not additional tests in this run.

Independent AI review reproduced and verified fixes for corrupt/missing stored
returns, partial output files, nonregular file input, deeply nested corrupt
database JSON, and JavaScript/Python draft-validation mismatch. Three exports
generated by the shipped JavaScript helper passed Python validation unchanged;
four invalid-text fixtures were rejected by both implementations.

This was an independent AI code review with offline adversarial checks, not a
human security or accessibility audit. A bounded Playwright browser installation
attempt failed on an empty/truncated archive. Rendered layout, native spellcheck,
clipboard/download behavior and assistive-technology operation remain unverified.
No screenshot or live browser success is claimed.

| Milestone | Current evidence | Completion boundary |
| --- | --- | --- |
| Dependable bot diagnostics | Earlier PR #31 repair and 99 passing tests | Still a separate draft; merged scheduled execution is a later check |
| Repeatable AI builder foundation | Existing reviewed templates and prior Control Tower evidence | Generated code remains inactive |
| Cross-project assistant specifications | Seven manifests, 35 roles, 12 targets | No external agents started |
| Durable draft exchange | Local ledger, review/export/import tests and synthetic demonstration | No authenticated cross-provider delivery |
| Spelling composer | Authored UI, helper tests and shared draft contract | Target-browser validation and hosting remain future work |
| Hostinger and social growth | Provider routes, project references and channel-tagged journey support | Account compatibility, real content delivery and real outcomes unverified |

The seven established workflows remain GitHub (1), AI Building AI (2), Hostinger
membership/connections (3), social integrations (4), funding/affiliates (5),
revenue intelligence (6), and daily intelligence (7). The publishing Studio Work
Cycle retains its separate paused state and outstanding human accessibility
review. This engineering milestone does not restart it.

## 6. The next three engineering priorities

| Priority | Next bounded implementation | Acceptance evidence |
| --- | --- | --- |
| **1. Establish one real Hostinger connection** | Identify the actual product/mode and site, then implement the compatible supported read path with credentials in its secure runtime. Validate one membership inquiry or referral destination using the existing website specification. | Dated sanitized read with exact site/product scope and provenance; then a reviewed form receipt and channel attribution. A list response alone does not prove publishing or membership access. |
| **2. Complete one verified cross-AI building cycle** | Use one small Jarvis engineering task with one selected AI provider; build the appropriate bounded runtime adapter or exercise a documented manual transfer, then review the returned proposal and test it in an isolated workspace. | A real handoff/return pair with provider provenance, exact input/output records, reproducible tests and the applicable human release review. Generated specifications alone do not meet this criterion. |
| **3. Validate the composer and one channel experiment** | Test keyboard, native spelling, copy/download and mobile layout in the target browser; prepare one evidence-based education post or video draft for one authorized account and one landing page. | Browser/accessibility findings resolved; reviewed channel-specific content; actual tagged visit and consented inquiry evidence when available. Publication and measured growth must be reported separately. |

These priorities advance the earlier prototype milestones toward observed
connections and useful outcomes. They do not promise a date, audience size,
income or autonomous operation. Use the smallest successful integration to
decide which next project or channel deserves expansion.

## Recovery

This update is reversible development work on the existing draft branch. Use a
normal revert commit if necessary; do not reset shared history. Keep the baseline
revision and prior evidence available. There is no production migration or live
account change to roll back from this milestone.
