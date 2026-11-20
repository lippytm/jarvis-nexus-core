# Engineering Priorities — Expansion Plan v0.2
Status: **reviewable source only**, not production integrated. Parent PR #5; issues #1–#4.

| Priority | Output | Acceptance gate |
|---|---|---|
| P1 validator and QA | Deterministic synthetic tests for event contract, provenance and consent | Tests pass in clean environment, independent reviewer signs off |
| P2 membership + affiliate | Synthetic Hostinger landing page -> opt-in -> CRM contract -> revenue metrics | UTM source persisted, explicit consent, cancellation/refund events idempotent |
| P3 Hostinger adapter | Capability matrix for site builder, forms, webhooks and allowed custom code | Owner-authenticated account check; supported method proven in sandbox |
| P4 social adapters | Facebook, Instagram, Threads, LinkedIn, Substack | Approved API products, permissions, rate limits, no prohibited scraping or unsolicited messaging |
| P5 AI-building-AI | Finite budgets, agent passports, tool scaffolds, QA reviewer, evidence | No self-approval, no privilege expansion, no unsupervised deployments |
| P6 verified finance | Funding and partner funnels separated | Provider-owned applications; verified commission vs projected amounts separated |
| P7 dashboard | 09:30 daily briefing -> project/health/ROI summaries | Unavailable is never represented as 0; source links and timestamps |
| P8 security and operations | CI tests, audit, privacy, data deletion, recovery, cost caps | Documented rollback, least privilege and failure-injection tests |

## Products and monetization
- Free educational newsletter -> optional membership without forced affiliate purchase.
- Ebook/audio/video editions and AI toolkits -> rights reviews, accessibility and support processes.
- Business funding site and 7FiguresCredit -> prospective borrower referral only; no approval claims.
- LendTrack and 7FiguresPartners -> prospective partner recruitment, subject to independent program conditions.
- AI Jarvis automated development toolkit -> private trial, then licensed service only after functionality, rights and security review.

## Network connections
ChatGPT Business, Gemini, Claude, GitHub, Hostinger, HubSpot/Airtable, Meta/Facebook/Instagram/Threads, LinkedIn and Substack each receive an adapter contract; each must record verified current access, scope, data boundaries, rate limits, audit status and fallback. Agent-generated code stays on review branches and must pass independent evaluation.

## Build-loop rule
Research -> requirements -> agent-generated candidate -> tests -> independent evaluator -> human approval -> limited rollout -> performance comparison -> evidence-backed briefing. Each agent run has fixed task count, recursion depth, time and dollar budgets. No agent may authorize its own increase.

## Pending work
Implement real schemas and validated per-platform adapters, synthetic end-to-end fixtures, secure runtime storage, CI and dashboards. Current Python prototypes are offline demonstrations, not authorization or proof of integrations.
