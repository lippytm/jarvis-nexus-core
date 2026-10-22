# Jarvis Integrated Seven-Workflow Milestone v0.6
**Stage:** draft software and GitHub QA; not live website/social/financial system.

- Workflow 1 (GitHub): CI for deterministic unit tests; compare head SHA, failures and security checks. Do not merge on green CI alone.
- Workflow 2 (AI builds AI): bounded orchestrator + allowlisted template generator + independent static evaluator. Static AST checks are NOT a security sandbox or independent human security audit.
- Workflow 3 (Hostinger): distinct consented membership vs funding/partner routing models; Hostinger account API support remains unverified.
- Workflow 4 (social): LinkedIn, Facebook, Instagram, Threads, Substack require approved platform credentials/scopes; no scraping, unconsented outreach or posting.
- Workflow 5 (funding): `lippytmai.getbizfunds.com`, LendTrack, 7FiguresCredit and 7FiguresPartners pathways are user-supplied; no credit/commission data ingested.
- Workflow 6 (analytics): synthetic UTM attribution; live revenue, refunds, membership entitlements and CAC data are unavailable.
- Workflow 7 (daily briefing): external scheduler at 09:30 Pacific remains separate; no automatic invocation of this demo. Evidence is required before marking deployment as verified.

## New integrated prototype
`control_tower/demo.py` exercises membership/funding/partner routing, three synthetic channel events, round-trip reporting, code-template generation, static evaluation, connection registry and dashboard. It has **zero external actions** and does not run generated code.

## Acceptance gates for next version
1. GitHub Actions success on the SHA containing this file and new tests.
2. Independent security review and stricter sensitive-data validation.
3. Controlled isolated build worker with full sandbox lifecycle and separate evaluator.
4. Local Hostinger-compatible form design; simulated payment webhook events, unsubscribe/refund and partner disclosures.
5. Provider API capability matrix with verifiable sources, permitted scopes and account owner approvals.
6. Analytics data contracts preserving privacy, cost/revenue provenance and cancellation handling.
7. Briefing integration through an authenticated, supported ingestion interface with reversible deploy and audit trail.
