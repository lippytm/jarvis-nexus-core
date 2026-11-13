# Unified AI Jarvis Control Tower — Foundation v0.1
Date: 2026-10-21. Status: **proposal on a review branch, not deployed**. Links and programs below are user-supplied; existence does not establish API authorization, commission terms or tracking access.

## Portfolio lanes
1. **AI building AI**: versioned agent/tool proposals -> sandbox build -> independent tests and safety review -> human-approved deployment -> evidence returned to 09:30 America/Los_Angeles briefing.
2. **Funding consumer path**: education -> consented outbound referral at `lippytmai.getbizfunds.com` or `https://www.7figurescredit.com?a_aid=lippytm`. No promises of approval; providers manage credit applications.
3. **Funding partner path**: referral partner education -> `https://lendtrack.ai/join/lippytmai` or `https://join.7figurespartners.com/?a_aid=lippytm`; distinct from borrower acquisition.
4. **Membership / affiliate education**: free opt-in -> explicit offer -> hosted payment processing only if separately authorized -> entitlement changes from verified payment webhooks -> cancellation.
5. **Creative products**: ebooks, audiobooks, video books, learning materials, AI toolkits; rights, accessibility and QA gates before publishing.
6. **Distribution**: Hostinger website landing pages plus Facebook, Instagram, Threads, LinkedIn and Substack. Platform adapters depend on supported APIs, approved scopes and owned business accounts.
7. **Engineering**: GitHub CI health, blockers, PRs, cost and risk. Gemini/Claude integrations require independent account/API access; do not assume access to private chats.

## Canonical event fields
`event_id, event_type, source, occurred_at, observed_at, project_id, campaign_id, utm_source, utm_medium, utm_campaign, actor, consent_status, evidence_url, confidence, approval_state, payload`.
System stores no government IDs, SSNs, full credit applications, payment card numbers, access tokens or raw financial account details. Use opaque references instead.

## Proposed agent passports
Every agent has `agent_id`, owner, scope, allowed tools, disallowed actions, max tasks, max model calls, max cost, timeout, audit destination, version and rollback instructions.
Independent evaluator cannot be same identity as builder. Human owner approves external posts, payments, checkout activation, production releases, partner outreach and membership term changes. Agent can never increase its own permissions.

## 09:30 Daily Briefing contract
- Five dated, reliably sourced stories with confidence and practical actions.
- Portfolio status: *verified / planned / blocked / unknown*; only label verified using direct evidence.
- Funnel table by channel: visits, clicks, consented signups, qualified leads, partner applications, verified funded deals, verified commission receipts, refunds, net results; unavailable where no access.
- Proposals: three ROI-ranked, bounded tasks with estimated cost and test conditions.
- Changes since prior run; incidents, privacy issues, owner approval queue and evidence reference IDs.

## Test-first release gates
- Schema rejects invalid event types, invalid timestamps, unknown consent states, invalid approval states, duplicate IDs, and suspicious sensitive payload keys.
- Distinct borrower and partner event types and funnels; marketing unsubscribe honored.
- Client source/UTM attribution preserved across accepted events; duplicate delivery idempotent.
- No commission reported as earned without external verification.
- Source adapter failures reported as unknown/unavailable, not zero.
- Secrets never logged; data minimization, account isolation and retention policy.
- Replay test: mock social campaign -> Hostinger mock signup -> lead event -> Jarvis proposed task -> QA result -> next briefing; zero outbound calls during sandbox tests.

## Phased release
P0: local fixtures + event validator + reproducible tests.
P1: read-only dashboard and synthetic attribution.
P2: scoped connectors and legal/compliance review.
P3: owner-approved limited pilot for membership/affiliate funnels.
P4: measure conversion and revenue, retain rollback and QA evidence.

Related GitHub tasks: #1, #2, #3, #4.
