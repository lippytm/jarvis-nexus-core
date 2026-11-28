# Control Tower 1–7 Workflow Upgrade v0.4
Status: engineering candidate; **no vendor credentials or deployments**.

| # | Workflow | Next engineering gate |
|---|---|---|
| 1 | GitHub CI and quality | Latest SHA passes CI; independent review of static gate and code |
| 2 | AI Building AI | Template-only sandbox builder + independent static evaluator; no code execution |
| 3 | Hostinger membership funnel | Mock signup with affirmative consent; verified Hostinger-supported embed/backend choices |
| 4 | Social distribution | Facebook/Instagram/Threads/LinkedIn/Substack source attribution with verified app scopes; publishing approval |
| 5 | Funding & partners | Funding consumer vs affiliate partner funnel separation, referral disclosures, no sensitive credit fields |
| 6 | Analytics and monetization | Channel conversion counts from mock events; commission amounts only from verified provider statements |
| 7 | 09:30 briefing and knowledge fabric | Evidence-backed project status, 3 ROI-ranked next actions, unresolved connection blockers |

## Communications protocol
- All source adapters translate to typed events with timestamp, stable ID, source, consent, project, and evidence reference.
- All Jarvis agent messages carry an agent passport, task budget, risk class and correlation ID.
- Unknown provider accessibility is *blocked*, not silently successful.
- Gemini, Claude and ChatGPT messaging is limited to supported authorized interfaces; do not assume cross-account chats can be scraped.
- MemPalace is a proposed versioned evidence store; do not represent it as deployed.
- Failed events are quarantined; repeated events are deduplicated; agent requests to increase their own permissions are denied.
- Secrets and customer credit/financial data never pass through briefing payloads.
- No autonomous publication, enrollment, payment, production modifications or unrestricted agent replication.

## Further test plan
1. Run all unit tests in GitHub Actions on the branch head.
2. Security review generated source AST gate and test intentionally hostile candidates.
3. Introduce event-contract versioning and signed audit chain.
4. Prototype accessible Hostinger-compatible consent forms and membership entitlement webhook simulations.
5. Verify actual provider API support, contract and billing rights before enabling connections.
6. Build synthetic funnel metrics dashboard with no inflated real-world results.
7. Promote code only through reviewed PR after owner's approval.
