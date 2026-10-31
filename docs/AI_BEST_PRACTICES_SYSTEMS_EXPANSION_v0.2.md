# AI Jarvis Best Practices & Systems Expansion Master v0.2

**Owner:** Intergalactic Corporate Services LLC  
**Date:** 2026-10-26  
**Status:** Project in progress / architecture standard  
**Supersedes for planning purposes:** `docs/ANIMA_RPG_PRODUCT_CREATION_MASTER_v0.1.md`  
**Repository baseline inspected:** PR #5, head `f985733bf3911e7336821035527da4d1e15c0f8c`, open, draft, unmerged.

This document expands the Business of Businesses / Systems of Systems architecture across AI Building AI, AI Jarvis Assistants Swarms Systems Communications Networks, Linux/Bedrock/OMARCHY, trading-bot sandboxes, robotics, wearables, publishing, ANIMA RPG, websites, business funding, affiliate systems and analytics.

It is a design and governance document. It does not imply production deployment, live trading, physical-robot readiness, revenue, publication, autonomous background operation or verified external account connections.

## 1. Executive architecture decision

The portfolio should operate as a **policy-driven systems platform**, not as a collection of independent agents, websites, books and bots.

The common control plane is built from nine shared contracts:

1. **Identity Contract** — who/what is acting.
2. **Mission Contract** — exact objective, scope, acceptance criteria and stop conditions.
3. **Tool Contract** — what capabilities are available and at what risk level.
4. **Sandbox Contract** — what files, network, credentials and external systems are reachable.
5. **Memory Contract** — what may be remembered, for how long, with what provenance and visibility.
6. **Evidence Contract** — sources, revisions, tests, observations, uncertainty and classification.
7. **Risk Contract** — limits, approvals, escalation and kill conditions.
8. **Release Contract** — who may publish, deploy, spend, trade or cause physical action.
9. **Outcome Contract** — what actually happened, measured separately from what was generated.

Every Jarvis assistant, trading bot, robot, wearable, product pipeline and multimedia derivative should inherit these contracts.

## 2. Non-negotiable design laws

- Unlimited creative universe; bounded execution.
- Default deny; explicitly grant capabilities.
- Separate read, draft, write, publish, financial and physical permissions.
- One agent or bot does not inherit another agent's authority.
- High-risk actions require deterministic policy checks and human review.
- Untrusted external content is data, never instruction authority.
- Evidence and provenance travel with derivatives.
- Simulation is not physical readiness.
- Backtest profit is not live-market proof.
- Generated advertising is not revenue.
- Repository count, agent count and file count are not success metrics.
- Human authority remains the release owner for money, publication and physical robotics.
- Every failure should leave a reproducible evidence trail and a rollback path.

## 3. Current verified baseline

The repository currently contains an offline research questbook, diary/media work, ANIMA/RPG planning assets and the v0.1 product architecture.

The inspected PR is **open, draft and unmerged** at `f985733bf3911e7336821035527da4d1e15c0f8c`.

The prior verified source baseline recorded:
- 273 Python tests passed.
- 57 Python source files passed syntax checks.
- 179 authored web checks passed.
- Native browser accessibility/usability, physical glasses, live Hostinger connections and physical robotics remain unverified.

No trading-bot implementation is represented by that baseline.

## 4. AI Building AI — maturity model

AI Building AI should mean **bounded tool and workflow improvement with evidence**, not uncontrolled self-replication.

### Stage A — Manual assistant
One model, no tools, human copies results.

### Stage B — Tool-assisted specialist
One agent receives a small, well-defined toolset.

### Stage C — Evaluated workflow
The workflow has fixtures, expected outcomes, failure thresholds and regression checks.

### Stage D — Specialist network
Multiple agents are introduced only when distinct ownership or tool separation improves reliability.

### Stage E — Governed self-improvement
Agents may propose new prompts, skills, tests or tools, but proposals remain inactive until implementation, evaluation and authorization are complete.

### Stage F — Controlled production service
Only after telemetry, incident response, recovery, security review, human escalation and measurable value are established.

**Best practice:** maximize a single specialist before multiplying agents. Create another agent only when it owns a genuinely different policy, tool boundary, data domain or evaluation objective.

## 5. Standard Jarvis roles

Use role separation to prevent self-approval:

- **Planner** — mission, constraints, acceptance.
- **Researcher** — sources, uncertainty, contradictions.
- **Architect** — interfaces and failure modes.
- **Builder** — implementation inside approved scope.
- **Security Reviewer** — tool, identity, injection and data-flow risks.
- **Evaluator** — actual tests and counterexamples.
- **Evidence Reporter** — immutable summary of observations.
- **Release Owner** — human or explicitly authorized policy gate.

For high-risk systems, Builder and Evaluator should not be the same execution identity.

## 6. Universal AI Sandbox Ladder

Each mission declares a sandbox level.

### S0 — Reasoning only
No files, no network, no external actions.

### S1 — Read-only workspace
Approved local/project files only.

### S2 — Isolated code sandbox
Code execution, no live internet, no credentials, disposable filesystem.

### S3 — Allowlisted research
Read-only access to specifically approved external sources/services.

### S4 — Authenticated read
Connected account reads with least-privilege credentials and audited queries.

### S5 — Reversible writes
Drafts, branches, staging environments and reversible changes. No financial or physical side effects.

### S6 — Sensitive action proposal
The AI may prepare the action, but execution pauses for independent deterministic checks and human approval.

### S7 — Financial / physical / production execution
Disabled by default. Requires a separately approved runbook, credentials, risk limits, incident controls and explicit release authorization.

Trading bots, robots and financial systems should remain below S7 until separately approved and verified.

## 7. Sandbox security enhancements

For capable agents or higher-risk code execution:

- Use defense in depth rather than trusting one container boundary.
- Prefer disposable containers inside isolated VMs for strong separation.
- Restrict outbound network access independently of the agent.
- Use per-run or per-bot credentials, never shared master credentials.
- Deny communication across sandboxes except through explicit message channels.
- Monitor filesystem, process, network, identity and tool events by run ID.
- Provide a stop mechanism that revokes both credentials and network access.
- Red-team the sandbox itself, not only the model prompt.
- Treat shared caches, storage and services as potential cross-agent channels.
- Keep financial and physical control systems on stronger boundaries than ordinary content generation.

## 8. Agent Skills and reusable capabilities

Convert repeated Jarvis procedures into portable, versioned Skills.

Every Skill should contain:

- skill ID and semantic version;
- purpose and non-goals;
- accepted inputs and outputs;
- required permissions;
- supported tools/providers;
- deterministic validation;
- reference sources;
- security classification;
- changelog;
- owner/reviewer;
- rollback instructions.

Enhancements:

- maintain an allowlist of approved Skills;
- hash or sign releases where practical;
- scan scripts/dependencies before activation;
- pin external dependencies;
- keep experimental Skills inactive by default;
- prefer provider-neutral interfaces so a workflow can move across ChatGPT, Claude, Codex, GitHub or other supported harnesses without rewriting business logic.

## 9. Tool risk registry

Every tool receives a risk tier:

- **T0:** pure transform/calculation.
- **T1:** read-only local/project data.
- **T2:** read-only external/account data.
- **T3:** reversible write/draft.
- **T4:** external publication, account mutation or irreversible business action.
- **T5:** financial transfer/trade, security administration or physical actuation.

Agent policy should derive approvals from the tool risk registry instead of relying on the model to decide whether an action is sensitive.

## 10. Memory / MemPalace best practices

MemPalace should be a provenance-aware memory system, not a single shared writable brain.

### Namespaces
Use separate namespaces for:
- owner/private;
- project/internal;
- public-candidate;
- each trading bot;
- each robot/device;
- each customer/workflow where legally appropriate.

### Memory write policy
A memory record should include:
- record ID;
- source identity;
- timestamp;
- evidence/source references;
- classification;
- confidence/uncertainty;
- authoring agent;
- reviewer state;
- expiry/TTL where appropriate;
- superseded-by link.

### Protection against poisoning
- Never let fetched web pages, email or social content directly rewrite trusted memory.
- Quarantine proposed memory updates.
- Require source-preserving transformation.
- Keep high-impact policy and credential information outside free-form model memory.
- Make deletions/supersession explicit rather than silently rewriting history.

## 11. Shared Evidence Record v2

Highest-priority cross-platform object:

`evidence_id`  
`schema_version`  
`project_id`  
`mission_id`  
`source_id`  
`source_type`  
`source_uri_or_locator`  
`source_revision`  
`captured_at`  
`classification`  
`claim_status`  
`statement`  
`uncertainty`  
`reviewer_state`  
`hashes`  
`derived_artifacts`  
`supersedes`  
`audience`

Recommended claim states:
`verified`, `source_linked`, `owner_reported`, `attributed_claim`, `open_question`, `planned`, `tested_local`, `simulated`, `fictional`, `blocked_unverified`.

Do not allow `source_linked` to mean independently verified.

## 12. ICSN communications envelope v2

Extend the existing Intergalactic Corporate Services Network message with:

- message_id
- schema_version
- run_id
- correlation_id
- sender_identity
- receiver_identity
- mission_id
- project_id
- requested_capability
- tool_risk_tier
- permissions
- data_classification
- source_trust
- evidence_refs
- issued_at
- expires_at
- nonce/idempotency_key
- approval_ref
- policy_decision
- acknowledgement
- result_ref
- error/status

No bot should communicate via undocumented shared files or writable common memory when a typed message channel can be used.

## 13. Prompt-injection and untrusted-content defenses

For agents reading web pages, email, files, CRM records or social content:

- treat retrieved text as untrusted data;
- separate system policy from retrieved content;
- never accept "ignore previous instructions" from data sources;
- filter or annotate external instructions before tool use;
- require structured tool arguments;
- block secrets from model-visible context unless essential;
- use allowlisted destinations for outbound data;
- add human review before externally visible or high-impact side effects;
- test prompt-injection fixtures as part of regression suites.

## 14. Evaluation system

Every important agent workflow should have three evaluation layers:

### Functional
Did it produce the required structured result?

### Safety/policy
Did it stay inside tool, identity, privacy and action boundaries?

### Outcome
Did the result create measurable value after human use?

Maintain datasets for:
- happy paths;
- edge cases;
- adversarial inputs;
- prompt injection;
- missing data;
- contradictory data;
- stale state;
- tool failure;
- unauthorized requests.

Run regression evals whenever model, prompt, Skill, tool schema or dependency changes.

## 15. Observability

Every run should emit structured telemetry:

- run ID;
- model/provider/version;
- Skill versions;
- tool calls;
- policy decisions;
- approvals;
- latency;
- token/cost estimate where available;
- errors/retries;
- evidence IDs;
- outcome IDs.

Do not log secrets or unnecessary personal information.

Use traces for diagnosis, aggregate metrics for management and evidence records for release decisions.

## 16. GitHub / software supply-chain best practices

Add to the Jarvis engineering standard:

- action dependency lockfiles where supported;
- otherwise pin GitHub Actions to full commit SHAs;
- least-privilege `GITHUB_TOKEN` permissions;
- OIDC rather than long-lived cloud credentials;
- artifact attestations/provenance for releases;
- protected branches and required reviews for sensitive areas;
- CODEOWNERS for security/financial/robotics modules;
- secret scanning and dependency review;
- reproducible build/test evidence;
- separate build and approval identities;
- signed or attested release artifacts where practical.

AI-generated code should never bypass the normal review and CI path.

## 17. Linux / Bedrock / OMARCHY enhancements

Use the Linux environment as both an educational world and a real engineering lab.

Best-practice deployment:

1. Keep the primary business machine stable.
2. Prototype OMARCHY/Arch in a recoverable environment.
3. Snapshot before major AI-generated configuration changes.
4. Test Bedrock in a VM or spare machine against the actual intended workflow before production use.
5. Document each Bedrock stratum and which package/service owns what.
6. Keep security assumptions explicit because cross-distro integration can invalidate distro-specific hardening expectations.
7. Run AI coding agents in plan/review modes before allowing unattended changes.
8. Use Git for configuration, reproducible setup scripts and rollback.
9. Separate learning labs from credentials and business production data.

ANIMA mapping remains:
Arch = Forge Realm; Bedrock = Multidistro Nexus; OMARCHY = Operator Citadel.

## 18. Trading Bot Systems — mandatory isolation

Every individual trading bot is a complete separate system with its own AI Sandbox.

No shared execution engine.

Each bot owns:
- Bot Passport and identity;
- dedicated sandbox boundary;
- data adapter/cache;
- feature/indicator calculation;
- strategy version;
- backtest engine;
- walk-forward/out-of-sample evaluation;
- paper execution simulator;
- deterministic risk engine;
- paper account or isolated simulated ledger;
- bot-specific credentials if ever needed;
- MemPalace namespace;
- logs and evidence;
- dashboard;
- kill switch;
- incident runbook.

The central Trading Control Tower is **read-only by default** and compares bot evidence. It does not grant one bot another bot's execution rights.

See `docs/TRADING_BOT_ISOLATION_STANDARD_v0.1.md`.

## 19. Trading-specific AI enhancements

- Model output is a **trade proposal**, never an order.
- A deterministic risk engine must approve every paper/live candidate independently of the model.
- News/social/web content is untrusted and cannot directly trigger orders.
- Include fees, spread, slippage, latency and corporate actions in backtests.
- Detect look-ahead bias and data leakage.
- Use out-of-sample and walk-forward testing.
- Test regime changes and stale/missing data.
- Enforce symbol/instrument allowlists.
- Apply rate, price, size, exposure and daily-loss limits.
- Detect duplicate orders and replay.
- Stop on clock drift, stale market data, API ambiguity or broken risk telemetry.
- Never advertise guaranteed returns or present AI as predictive certainty.
- Record actual paper/live results separately from backtest results.

## 20. Robotics and humanoid robotics enhancements

Use a layered authority model:

**Perception -> Proposal -> Plan -> Simulation -> Safety Check -> Human/Policy Approval -> Physical Action -> Verification**

Controls:
- independent emergency stop outside the AI model;
- safe-state fallback;
- command authentication and replay protection;
- device/robot identity;
- simulation and hardware-in-the-loop before broader deployment;
- physical workspace constraints and geofencing where appropriate;
- telemetry and incident logs;
- signed/validated software and configuration;
- explicit distinction between autonomy and human-supervised modes.

Humanoid self-maintenance should begin with diagnosis and supervised procedures before autonomous tool use.

## 21. Wearable technology enhancements

For CryptoCyberSecurity, CryptoCyberpunk, CryptoCyberBorg, CryptoCyberSteampunk and CryptoClockworks:

- modular hardware abstraction layer;
- device identity and secure pairing;
- least-privilege sensors;
- visible microphone/camera recording state;
- local processing for sensitive data where possible;
- explicit consent and retention settings;
- signed firmware/update path;
- offline degraded mode;
- accessibility-first controls;
- human-readable safety/status indicators;
- robot/human profiles that share protocol but not authority;
- event provenance through CryptoClockworks.

Do not make health, safety or security claims without appropriate validation.

## 22. Nineteen-book fractal architecture v2

The series is **19 books expressed through all 19 books**.

Each book has:
- one dominant objective;
- all other 18 systems interpreted through that objective;
- the Code/Coding Universe;
- AI Building AI;
- Jarvis roles;
- Linux/Bedrock/OMARCHY;
- robotics/wearables where relevant;
- business/value application;
- evidence/documentation;
- ANIMA RPG quests;
- Quantum Questions Entangled.

This yields **361 primary cross-book objective intersections** (19 x 19).

Every book also contains distinct versions of:
- IF
- Maybe
- Why Not?
- Don't Do That
- I Told You Not To Do That!
- We Exist for Entertainment Purposes Only
- We Exist for Space Alien Entertainment Purposes Only

The recurring structure is shared; content must remain different per volume.

## 23. Code/Coding Universe expansion

Book 19 is the technical spine embedded in Books 1-18.

Curriculum lanes:
- computational thinking;
- shell/Linux;
- Python;
- JavaScript/TypeScript;
- web/API engineering;
- SQL/data;
- Git/GitHub;
- DevOps;
- AI/agent engineering;
- blockchain;
- cybersecurity;
- robotics;
- wearable/IoT;
- ANIMA RPG/game logic;
- multimedia automation;
- business automation;
- testing/evidence.

Every book receives a **Code the World** lab that builds a small real artifact associated with that book's dominant objective.

## 24. Educational technology enhancements

Every lesson/quest should include:
- objective;
- prerequisites;
- mission context;
- expected observations;
- bounded practice;
- authored answer checks where appropriate;
- transfer assessment;
- reflection/explanation;
- evidence artifact;
- instructor/human review for open-ended mastery.

Do not infer mastery from answer matching alone.

Use failure as curriculum:
**predict -> attempt -> observe -> diagnose -> repair -> explain -> transfer.**

## 25. Product Creation Machine v2

Every reviewed source can generate a manifest for:
- NFT/collector edition;
- eBook;
- audiobook;
- video book;
- interactive ANIMA RPG;
- educational lesson;
- trailer;
- social short;
- newsletter;
- ad-copy kit;
- AR/wearable scene;
- robotics simulation where relevant.

Each derivative must preserve:
- source revision;
- evidence IDs;
- canon status;
- rights/license;
- accessibility requirements;
- audience;
- review state;
- output hash/version.

Use a compiler/manifest architecture rather than asking an AI to independently rewrite the same facts for every medium.

## 26. Multimedia / documentary controls

Keep separate lanes:

**Documentary:** sourced facts, attributed claims, unresolved questions.  
**ANIMA Fiction:** invented worlds and characters.  
**Hybrid Education:** fictional mission teaching real concepts.  
**Satire/Comedy:** clearly framed entertainment.

Never let a fictionalized scene silently become documentary evidence.

## 27. Website / Hostinger architecture

Maintain distinct destinations and audience journeys:

- education;
- affiliate/referral;
- business funding;
- membership;
- product/library;
- ANIMA entertainment.

Use a registry that records:
- domain/project;
- owner;
- purpose;
- audience;
- data classification;
- integrations;
- publication permission;
- analytics;
- rollback/contact.

A verified read connection should precede write automation.

## 28. Business funding / credit workflows

Enhancements:
- separate educational information from provider decisions;
- never promise approval;
- retain provider terms/source dates;
- minimize sensitive financial data;
- explicit consent for CRM storage;
- route customers vs partners separately;
- record referral attribution without exposing unnecessary PII;
- require human review for individualized high-impact recommendations.

## 29. Affiliate / advertising best practices

- clear affiliate/referral disclosures;
- approved-claim library;
- source-backed product statements;
- UTM/campaign IDs;
- deduplicated conversion events;
- refund/chargeback tracking;
- cost per acquisition and support cost;
- no fake scarcity or unverified performance claims;
- separate generated copy from actual published copy;
- separate clicks from qualified leads and revenue.

## 30. Revenue intelligence

Control Tower metrics should distinguish:

**Creation metrics:** artifacts produced.  
**Quality metrics:** tests/reviews passed.  
**Reach metrics:** impressions/visits.  
**Engagement metrics:** completion, return visits.  
**Pipeline metrics:** qualified leads.  
**Commercial metrics:** paid orders, memberships, verified commissions.  
**Cost metrics:** AI, hosting, ads, support, refunds.  
**Unit economics:** contribution margin and retention.  
**Risk metrics:** incidents, policy blocks, unresolved evidence gaps.

AI activity is valuable only when it improves a measurable objective.

## 31. Daily Diary / Briefing / Newsletter enhancements

One reviewed daily record can become many surfaces.

The canonical daily record should contain:
- date/time;
- owner-reported work;
- externally verified news;
- engineering status;
- decisions;
- risks;
- next missions;
- documentary notes;
- ANIMA/RPG translation;
- publication candidates.

Never mix current news, owner-reported progress and fictional RPG scenes without labels.

## 32. Resilience and recovery

Every production service should have:
- backup policy;
- restore test;
- rollback;
- dependency inventory;
- incident owner;
- stop mechanism;
- recovery-time target;
- data-retention policy.

Trading, robotics and publication systems require explicit incident playbooks before higher permissions are granted.

## 33. Privacy and data minimization

- collect only what the workflow needs;
- separate owner/private from public-candidate material;
- do not put secrets into prompts, logs or artifacts;
- redact before cross-platform transfer;
- use synthetic data for educational demos;
- apply retention/expiry policies;
- review third-party telemetry and model/provider data handling.

## 34. Model/provider strategy

Do not force one model to do everything.

For each workflow:
1. establish an eval baseline with a capable model;
2. measure correctness/safety;
3. test smaller/faster models for lower-risk stages;
4. select by quality, latency and cost;
5. preserve provider/model version in evidence.

A provider abstraction is useful, but critical behavior must be tested per provider/model rather than assumed equivalent.

## 35. Priority roadmap

### P0 — Do now
1. Shared Evidence Record v2.
2. Identity/Agent Passport v2.
3. Universal Sandbox + Tool Risk registry.
4. Trading Bot Isolation Standard.
5. GitHub supply-chain hardening inventory.
6. Update 19-book canonical matrix to the fractal 19 x 19 structure.

### P1 — Next
1. Source-to-Product Compiler manifest.
2. One portable/versioned Jarvis Skill with tests.
3. One paper-only trading bot prototype in a dedicated sandbox.
4. One robot simulation using the shared mission/evidence contracts.
5. One website destination registry with verified read-only connection.

### P2 — After evidence
1. Cross-platform orchestration adapters.
2. Wearable/AR prototype.
3. Expanded paper-trading bot population.
4. First complete Book -> audio -> video -> RPG -> ad derivative stack.
5. Production-grade observability and incident dashboards.

### P3 — Gated future
Financial execution, physical autonomous robotics, production self-modification and broad autonomous publication remain separately gated.

## 36. Acceptance standard for any new AI capability

A capability is not "integrated" until all are true:

- exact owner/project is identified;
- identity is unique;
- permissions are explicit;
- sandbox boundary is documented;
- tool risks are classified;
- tests/evals pass;
- failure/stop conditions are tested;
- evidence is retained;
- output location is known;
- human/release authority is defined;
- rollback/recovery exists;
- observed outcome is distinguished from predicted benefit.

## 37. Reference standards consulted

- OpenAI, "Securing our frontier model training environment" (2026): https://openai.com/index/securing-our-frontier-model-training-environment/
- OpenAI, "A practical guide to building AI agents" (2026): https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/
- OpenAI Agents SDK, guardrails/human review: https://developers.openai.com/api/docs/guides/agents/guardrails-approvals
- Anthropic, Agent Skills donation to AAIF (2026): https://www.anthropic.com/news/donating-agent-skills-to-the-agentic-ai-foundation
- NIST AI RMF and Generative AI Profile: https://www.nist.gov/itl/ai-risk-management-framework
- OWASP GenAI Security Project / Agentic Security Initiative: https://genai.owasp.org/initiatives/agentic-security-initiative/
- GitHub Actions security guidance: https://docs.github.com/en/actions/how-tos/secure-your-work
- CFTC AI Trading Bots advisory: https://www.cftc.gov/LearnAndProtect/AdvisoriesAndArticles/AITradingBots.html
- Bedrock Linux FAQ: https://bedrocklinux.org/faq.html
- Omarchy Manual: https://omarchy.org/manual/

## Closing rule

**Build intelligence by increasing verified capability, not by increasing uncontrolled authority.**

Every world teaches something. Every quest builds something. Every build produces evidence. Every failure becomes a safer, better next version.
