# Jarvis portfolio expansion: useful AI building across work and life

**Prepared:** October 22, 2026, Pacific time.  
**Development baseline:** `a67e743e8b32e552ccddd9e16a2108fe2f816274`.  
**Review destination:** [existing draft Nexus PR #5](https://github.com/lippytm/jarvis-nexus-core/pull/5).  
**Scope:** implemented local planning tools, authored portfolio defaults, offline checks and a real read-only Hostinger transport. Publication of this development branch is separate from a merge, deployment or social publication.

The goal is to make the Jarvis portfolio easier to use, expand and evaluate. A selected idea can now become a concrete mission with five assistant roles, acceptance checks, evidence gaps, a restart point and seven channel-specific editorial briefs. This gives the same working method to education, business operations, creative work, learning, product experiments and personal continuity.

The catalog covers twelve initiatives in the seven existing project areas. These are authored starting points, not an exhaustive inventory of the owner's life, accounts, companies or completed products. New priorities can be added through a reviewed catalog change. Live audience, sales, commissions, available time and learning outcomes remain unknown unless supported by actual records.

## 1. What is implemented

### A portable portfolio workbench

Open [Jarvis Portfolio Workbench](../web/jarvis-workbench.html) in a browser. It contains the complete catalog and works without a server, package installation or API key. It supports search, project and journey filters, visible outcomes and evidence gaps, per-initiative objectives, twelve draft destinations and four planning windows: 15, 30, 60 or 90 minutes.

The workbench can copy a complete planning brief or download a six-field mission request. An objective is limited to 2,000 UTF-8 bytes; malformed text, unsupported selectors and invalid timeboxes are rejected. Text is preserved rather than silently rewritten. Objectives remain in memory for the current visit. Download the request before closing or reloading; autosave and device synchronization are not implemented.

The existing [spelling composer](../web/jarvis-composer.html) remains available beside the workbench. It provides selected common-typo corrections, undo and export. Both pages request native browser spelling where supported. They do not alter ChatGPT's own input field. Their authored logic has automated checks; actual browser layout, spelling, clipboard, downloads and assistive-technology behavior still need a target-browser review. See the [workbench guide](JARVIS_WORKBENCH.md) and [composer guide](JARVIS_COMPOSER.md).

### A mission compiler and shared assistant contract

`control_tower/missions.py` resolves a validated request against the catalog and creates an inactive mission. Each mission includes a researcher, architect, builder, evaluator and reporter; the selected project and target; an unchanged known swarm manifest; ordered planning dependencies; role acceptance checks; and a resume bookmark.

The timebox is a planning allocation, not a timer or runtime limit. A 30-minute plan allocates 4, 4, 12, 6 and 4 minutes to the five roles. These estimates are not measured productivity or completion promises. The compiler makes zero model calls and starts zero external assistants.

Every exported role draft uses the existing `jarvis.draft` contract. It can enter the durable handoff ledger for explicit review and export. Compiling a mission does not stage all its roles, mark a review complete, dispatch providers or change ledger dependency state. An imported result still requires validation and evidence review under the existing [network workflow](NETWORK_MILESTONE_2026_10_22.md).

### Seven-channel editorial preparation

`control_tower/campaigns.py` creates distinct briefs for Facebook, LinkedIn, Substack, Instagram, Threads, YouTube and GitHub. A briefing contains a suggested format and outline, the initiative's audience and boundaries, a proposed next action, and factual, accessibility and asset-review requirements.

The AI target and publication channel are separate fields in the workflow. For example, a Gemini-targeted draft can ask for a YouTube script outline; that does not create a YouTube connection. A brief is preparation for writing or production, not a finished video, published post or measured campaign.

Candidate links add campaign tags while preserving configured referral parameters. Both financing-customer and partner examples preserve `a_aid=lippytm` where it was already present. No link has been live-tested by this generator, and a correctly constructed URL is not proof of attribution or commission.

### A real Hostinger read-only transport

`control_tower/hostinger_live.py` and `scripts/jarvis_hostinger.py` add a standard-library HTTPS sender for the fixed Horizons website-list GET endpoint. The implementation verifies TLS certificates and hostnames, uses a bounded response parser, rejects redirects, performs no retry and sanitizes reports. It has no write operation.

The actual configuration check in this session returned **`credential_present: false`** for `HOSTINGER_API_TOKEN`, with **zero transport calls** and **zero writes requested**. Consequently, no authenticated Hostinger request was attempted. The implementation status is now "read transport implemented"; account status remains "unverified." The sanitized [configuration receipt](evidence/hostinger_config_2026_10_22.json) is retained.

The credential must be configured securely in the intended runtime; it should not be pasted into a chat, command argument or public file. Once available, an authorized read can establish a point-in-time Horizons inventory result. The sanitized report omits site identifiers and domains, so separate authenticated site/product evidence is required to determine whether the actual website is covered by that endpoint. The current education site's API editability has not been established. See the [Hostinger runbook](HOSTINGER_CONNECTION_RUNBOOK.md) for precise prerequisites and limits, including the DNS timing limitation and POSIX-only secure output command.

## 2. Twelve initiatives with useful next deliverables

| Initiative | First concrete deliverable | Creative expansion to test | Evidence required before expansion |
| --- | --- | --- | --- |
| Jarvis tools and assistant building | One reusable tool for a repeated task, with a reproducible check | Turn a successful tool into a teaching note and a reusable assistant mission | Actual task benefit, reviewed source and a recovery path |
| Education website and membership inquiries | One practical lesson with one optional inquiry action | Connect a lesson, worked example, checklist and follow-up question around one learner outcome | Correct Hostinger product/site, form delivery and a consented inquiry receipt; learning requires a separate assessment |
| Affiliate website and membership platform | One offer and member-workflow specification with its own destination | Combine a useful template, small tool and service workflow into a coherent offer | Separate site assignment, customer interest, fulfillment capacity and current terms |
| Business financing customers | One clear financing-information/referral page | Explain the customer's questions through a comparison checklist and source-backed FAQ | Current provider terms, correct customer link behavior and actual authorized attribution |
| Referral partners | One partner-specific application brief | Develop an onboarding checklist and reusable explanation of the partner journey | Current partner terms, application destination and actual application evidence |
| Publishing library and creative worlds | One reviewed chapter or script with a source and edition record | Reuse a rights-cleared excerpt as a discussion prompt, teaching note or audio script | Current manuscript, rights inventory, reader feedback and the outstanding human accessibility review |
| Interactive video and teaching studio | One short production brief with captions and an interaction purpose | Test a viewer decision point or worked-example pause before building a larger interactive player | Available assets, permissions, actual player capability and viewer/accessibility feedback |
| Linux and programming learning | One instructor-reviewed exercise for a named environment | Offer beginner, guided and extension paths around the same concept | Verified environment and compatibility; a transfer exercise rather than answer matching alone |
| Robotics simulation and education | One simulator experiment with measurable conditions | Compare two bounded design choices in simulation and explain the result | Selected simulator, reproducible actual results and explicit simulation limits |
| Wearable technology concepts | One concept specification with assumptions and feedback questions | Explore several interaction or form-factor options before selecting a prototype | Actual component specifications, user feedback and measured prototype behavior |
| Business operating system | One repeatable weekly routine with an owner and completion check | Connect project status, decisions, reusable assets and an evidence-based review | Authorized source records, actual costs/revenue where relevant and completed review evidence |
| Personal focus, access and continuity | One manageable session plan and restart bookmark | Adapt the same goal to a short or longer session and preserve the next action | Actual available time, device context, user-confirmed access needs and observed usefulness |

The catalog stores the outcome, suggested formats, proposed steps, missing evidence and scope for every initiative. The workbench presents these details before a request is exported. It does not infer health data, finances, family priorities or other private life information from the general expansion request.

### Keep the destination map precise

The education initiative refers to `https://aievolutionaryevolutions.com`. The separate affiliate platform has **no assigned URL** and does not inherit the education destination. Financing customers retain their configured customer routes; referral-partner recruitment retains its own application routes. These links are owner references whose current behavior needs verification.

An unassigned initiative yields an unassigned campaign destination and an instruction to choose and verify it. It does not receive an invented website or a misleading public call to action. The distinction is checked in Python, JavaScript and independent review.

## 3. How to use AI building AI as a repeatable working process

Choose one objective that will produce an inspectable result. A useful request names a deliverable and an observable check, such as "prepare a lesson on reading a small Python function, with a worked example and one transfer exercise." A request to improve everything at once cannot supply a meaningful acceptance check.

The five roles give the work structure:

1. **Researcher:** identify supplied artifacts and relevant primary sources; distinguish facts, goals and evidence gaps.
2. **Architect:** define a small deliverable, its inputs, outputs and dependencies while preserving the selected audience and destination.
3. **Builder:** prepare the artifact or minimal code change with meaningful checks and a recovery approach.
4. **Evaluator:** independently assess the actual artifact against the acceptance criteria and record failures or missing evidence.
5. **Reporter:** retain what actually happened, cite the version and checks, and set the next bounded action.

These role descriptions are implemented drafts. In this release they require manual handoff through the existing review flow; they are not autonomous processes. Increasing the number of role specifications does not demonstrate better results. Reuse should be justified by a successful task and useful evidence.

### Run the compiler

From the repository root with Python 3.11 or later, this example uses the supplied request and explicitly records the previous milestone as its source context:

```bash
python scripts/jarvis_portfolio.py plan --request examples/portfolio/jarvis-tools.request.json --mission first-tool-cycle --source-revision a67e743e8b32e552ccddd9e16a2108fe2f816274 --out reports/first-tool-cycle.mission.json
python scripts/jarvis_portfolio.py export-role --mission-file reports/first-tool-cycle.mission.json --role builder --out reports/first-tool-cycle.builder.json
python scripts/jarvis_portfolio.py export-swarm --mission-file reports/first-tool-cycle.mission.json --out reports/first-tool-cycle.swarm.json
python scripts/jarvis_portfolio.py campaign --mission-file reports/first-tool-cycle.mission.json --out reports/first-tool-cycle.campaign.json
```

For a workbench request, place its downloaded JSON inside this checkout and substitute that relative path for `--request`. Use the actual source-context commit for the task under review. The compiler validates the revision's format; it does not authenticate that revision or fetch its contents. A source-context revision is distinct from the commit containing this compiler.

Commands refuse to overwrite existing files. Choose a fresh mission ID and fresh output names for another attempt. Role draft export is a local transformation; it does not authorize sending, execute generated code or bypass ledger review. Whole mission and campaign packets must fit the existing 64 KiB loader.

The [example index](../examples/portfolio/mission_index.json) contains twelve synthetic requests and twelve compiled missions, totaling **60 inactive role drafts**, plus separate financing-customer and referral-partner campaign samples. The earlier **35 assistant specifications** describe five roles across seven work areas. These counts describe different artifacts; they are not 95 running agents.

### Keep continuity portable

The mission carries its selected initiative, source context, original objective, evidence gaps, acceptance criteria and next action. That packet can support a review in another selected AI environment without relying on undocumented shared memory. A different provider receives only the content actually transferred to it.

The workbench can prepare a brief locally. Cross-device synchronization, mobile installation, background execution and automatic discovery of other AI conversations are future capabilities. Preserve a downloaded request or reviewed packet before changing devices. Sensitive material should remain in its authorized private workspace and should not be added to public portfolio examples.

## 4. Growth, viability and flexible design

The next growth work should test one complete journey. A practical sequence is a useful resource, an appropriate channel-specific explanation, the correct destination, a clear next action and a verified response. Every step needs evidence of its own. A view is different from an inquiry; an inquiry is different from paid access; a provider application is different from a confirmed commission.

| Channel | Brief already generated | First observation to retain after an authorized experiment |
| --- | --- | --- |
| Facebook | Educational post around a reader question | Actual post reference and visits or relevant responses |
| LinkedIn | Professional project update | Actual publication, qualified discussion and destination visits |
| Substack | Newsletter/article outline with sources | Actual editor publication and permitted readership or referral data |
| Instagram | Carousel or short-video brief, caption and alternative text | Actual asset/publication and format-appropriate destination behavior |
| Threads | Short discussion sequence | Actual post, useful responses and source/destination behavior |
| YouTube | Tutorial script outline with captions and sources | Actual video, viewer response and the stated next action |
| GitHub | Engineering update or reproducible documentation | Actual version, verification and observed use or actionable feedback |

The current generator supplies the middle preparation step. It does not post, render media, acquire customers, connect analytics or calculate revenue. Do not multiply a speculative outcome by the number of channels or agents. Start with one audience and one channel that fits the resource, then reuse the verified source material in other formats.

For viability, a proposed product should answer four questions: What recurring need does it address? What is the smallest useful deliverable? How will it be delivered and supported? What evidence would justify another iteration? Pricing, expenses and potential earnings require current actual inputs; none are fabricated in the catalog.

Flexibility comes from the common request and draft contracts, selectable timeboxes and independent content formats. Diversity comes from testing different audiences, learning paths, presentation formats and interaction designs against the same stated outcome. Provider choice is useful only if the return can be reviewed through the same evidence requirements. A provider name is not a quality guarantee.

Maintain one active deliverable at a time until the actual workload supports parallel execution. Record elapsed time and reuse benefit during real work, then adjust the planning allocation. The current timeboxes and twelve initiatives are starting defaults, not a measured capacity plan.

## 5. Verification, milestones and recovery

### Local checks retained for this revision's source

- **163 Python tests passed**, with zero failures, errors or skips; **43 Python files** passed syntax checks. [Integrated JSON evidence](evidence/portfolio_expansion_2026_10_22.json) and [test log](evidence/portfolio_expansion_2026_10_22.txt).
- The combined Node command passed both the composer and workbench test files. Direct individual-case runs passed **34 composer cases and 34 workbench cases**, 68 total. The workbench's [retained evidence](evidence/workbench-validation.json) also records twelve JavaScript exports accepted unchanged by Python and eleven invalid fixtures rejected. [Combined Node log](evidence/portfolio-web-tests.txt) and [composer case log](evidence/portfolio-composer-tests.txt).
- The workbench's embedded catalog equals both the tracked catalog and the Python catalog. Static checks cover IDs, labels, ARIA references and source structure. These are not a rendered accessibility audit.
- An independent AI reviewer exercised compiler/campaign boundaries, all five role handoffs and the Hostinger transport's eighteen offline tests. Guards observed zero accidental DNS/socket attempts during those transport tests. The review found a cyclic-symlink exception in the portfolio CLI; it was fixed and independently retested for root, input and output paths. [Review record](evidence/portfolio_review_2026_10_22.json).
- The actual Hostinger presence-only check found a missing credential. It made no network request and retained an unverified account state. No paid model request, deployment, social publication or physical-device action was part of these local checks.

The workflow now runs Python checks and both web test files, retaining evidence artifacts. Its four action versions were resolved against official release tags and `action.yml` files declaring Node 24, then pinned to exact commits. [Pin provenance](evidence/action_pins_2026_10_22.json). Local checks do not substitute for the workflow result on the published head; that result is attached to [PR #5](https://github.com/lippytm/jarvis-nexus-core/pull/5).

### Milestone state and exit evidence

| Milestone | State at preparation | Required evidence to advance |
| --- | --- | --- |
| Portfolio catalog, workbench, mission compiler and channel briefs | Implemented and locally verified | Published exact-head CI plus target-browser review for native UI behavior |
| Hostinger read path | Implemented; configuration check reports missing token | Secure runtime configuration, real read receipt and actual product/site identity |
| First useful cross-AI building cycle | Draft and ledger contracts implemented | One real task handed to the selected provider, returned, independently checked and applied to a reviewed change |
| One measured audience journey | Briefs and candidate links implemented | Authorized publication, verified destination/form behavior and actual analytics or response records |
| Broader portfolio reuse | Twelve planning examples prepared | Observed benefit from a successful first cycle and a deliberate next initiative |

These milestones are dependency-based. They carry no promised completion date or growth percentage. Account configuration, provider permission, real source material and review availability can change their timing.

To recover from a local planning error, keep the original request, correct the objective or catalog under review and compile to fresh filenames. Existing evidence is preserved. If a provider return fails validation, retain the failure and ask for a corrected draft; do not label it an accepted result. Any later release follows the repository review process. The paused Studio Work Cycle stays paused until its independent human accessibility review is complete.

## 6. The next three engineering priorities

### 1. Establish one verified Hostinger connection and one useful site journey

Configure the authorized credential securely, run the bounded read, identify the actual site's product and project, and choose the supported integration path. Then prepare one reversible education lesson/inquiry improvement for the correct destination. Keep the affiliate platform separate.

**Exit evidence:** a genuine read receipt with provenance, confirmed site identity, reviewed change, actual form receipt and a verified destination. A successful Horizons response alone does not meet every requirement.

### 2. Complete one real AI-to-AI building cycle

Select one small Jarvis tool mission. Export a reviewed role draft through the ledger to the chosen AI environment, collect an actual return, validate its structure, review its contents independently and retain meaningful test results for any applied change. Build a reusable example from that completed cycle.

**Exit evidence:** exact source revision, exported content hash, actual returned artifact, independent findings, relevant checks, recovery instructions and an observed benefit. The current sixty inactive example drafts are preparation for this step.

### 3. Validate the workbench in a real browser and run one measured channel experiment

Check keyboard use, focus, narrow-screen layout, text preservation, spelling, clipboard, downloads and assistive-technology behavior in the intended browser. Use the validated workbench to prepare one useful resource and one channel brief. After the destination and publication scope are confirmed, measure the actual audience response and correct the next iteration.

**Exit evidence:** browser/version and review findings; a verified published resource when authorized; actual tagged visits or appropriate responses; and a next improvement justified by those observations. The independent human accessibility requirement for restarting the Studio remains separate.
