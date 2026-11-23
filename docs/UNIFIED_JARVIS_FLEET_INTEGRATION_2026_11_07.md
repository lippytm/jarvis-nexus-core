# Unified Jarvis Fleet Integration Blueprint

## Purpose

This blueprint continues the current Jarvis Nexus work by defining one governed integration path across the 45 repositories presently visible to the connected GitHub account, Hostinger, Gemini/NotebookLM, Claude/Hermes, and future connection adapters.

It merges architecture and contracts, not source trees. Existing repositories remain independently versioned systems of record until their capabilities pass explicit intake, verification, and promotion gates.

## Current baseline

- `jarvis-nexus-core` remains the bounded orchestration and portable-workflow layer.
- `AI-Jarvis-Assistant-ChatGPT-Gemini-AI-GitHub-Claude-and-all-of-my-Repositories-DOG-Dog-dog-` remains the provider-neutral task, provenance, and workflow-gate implementation.
- `Hermes-AI-Hermes` remains the fleet findings/message-bus implementation and Claude/Hermes shared-evidence bridge.
- `lippytm-lippytm.ai-tower-control-ai` remains the portfolio registry, swarm architecture, governance, and rollout-control source.
- `Gemini-NotebookLM-s-AI-Agnostic-Clone-Engine-Fabric-` remains the independent Gemini/NotebookLM research and review line.
- `AI-Autonomous-Systems-for-all-of-my-lippytm.ai-Repositories-Research-and-Development-integration-` remains a useful historical cross-repository role map, but its 32+ repository inventory is stale relative to the current 45-repository account inventory.
- `Hostinger.com-with-my-AI-Jarvis-Assistant-ChatGPT-ChatGPT-Business-Gemini-AI-Claude` remains the Hostinger-facing platform specification and deployment handoff repository.

## Integration topology

```text
Human owner / HumanApprovalGate
            |
            v
Jarvis Nexus Core - command API, task envelopes, local evidence ledger
            |
            +--> Tower Control - fleet registry, roles, risk tiers, rollout state
            +--> Hermes - findings, health signals, message routing, audit evidence
            +--> Provider lines
            |      +--> Gemini/NotebookLM - independent source-grounded review
            |      +--> Claude/Hermes - supervised review and findings
            |      +--> OpenAI/ChatGPT - synthesis and bounded execution
            +--> GitHub fleet - durable code, docs, issues, PRs, CI evidence
            +--> Hostinger - interface/deployment target through gated adapters
```

No provider is assumed to share hidden memory with another. Every cross-system transition uses a signed or hashed handoff record with source identity, revision, evidence status, requested action, allowed action, risk tier, and approval state.

## Canonical contracts

### Repository profile

Each repository should eventually expose `.jarvis/repository.yaml` containing:

```yaml
schema_version: 1
repository: owner/name
fleet_role: product|infrastructure|knowledge|creative|governance
risk_tier: standard|sensitive|revenue_critical|governance
canonical_sources: []
subscriptions: []
publications: []
execution_environments: []
provider_routes: []
allowed_actions: [read, propose]
required_checks: []
required_approvals: []
```

Profiles must not contain tokens, passwords, customer data, tax records, or private account exports.

### Task envelope

```json
{
  "schema_version": 1,
  "task_id": "operator-generated-unique-id",
  "correlation_id": "workflow-correlation-id",
  "source_repository": "owner/name",
  "source_revision": "full-commit-sha",
  "objective": "bounded objective",
  "evidence_status": "verified|in_progress|planned|unknown",
  "requested_action": "read|analyze|draft|test|deploy",
  "allowed_action": "read|analyze|draft",
  "risk_tier": "standard",
  "provider_route": "gemini|claude|openai|mock",
  "approval_state": "not_required|pending|approved|denied",
  "artifact_hashes": []
}
```

### Provider result

Every provider return must preserve the task and correlation IDs, model/provider identity, source set, timestamps, output hash, completion status, uncertainty, and failure classification. Provider agreement is not independent evidence when the providers use the same source or copied conclusion.

## Connection roles

| Connection | Role | Initial permission | Promotion condition |
|---|---|---|---|
| GitHub | Durable source, PR review, CI evidence | Read and draft PR | Green checks, bounded diff, owner review |
| Hostinger | Website inventory and deployment target | Read-only inventory | Confirm account, product, site, DNS, backup, staging, rollback, and action approval |
| Gemini/NotebookLM | Independent research and review | Export/import handoff | Named source manifest and independent first pass |
| Claude/Hermes | Supervised cross-repo review and findings | Read findings; draft findings/reviews | Preserve tier rules and HumanApprovalGate |
| OpenAI/ChatGPT | Synthesis and bounded task execution | Draft/local execution | Explicit model, budget, secret injection, and workflow opt-in |

## Fleet merge workflow

1. **Inventory** - refresh repository metadata and classify every repository without changing it.
2. **Profile** - propose a repository profile from existing code and documentation.
3. **Validate** - check schema, references, risk tier, secrets, and contradictions.
4. **Observe** - run read-only health, CI, dependency, and documentation checks.
5. **Plan** - generate a bounded task envelope and provider-specific handoffs.
6. **Review** - require independent review for sensitive, revenue-critical, governance, publishing, credential, or deployment work.
7. **Draft** - create repository-specific PRs; do not mass-push directly to default branches.
8. **Verify** - run repository-native tests and record exact commit/check evidence.
9. **Promote** - merge only the profile or adapter that passed its own gates.
10. **Deploy** - use a separate authorized Hostinger or platform action with backup and rollback evidence.

## Reconciliation rules

- The live 45-repository inventory supersedes documents that claim 29 or 32+ repositories; those older documents remain historical evidence until regenerated.
- Canonical implementation wins over planning prose when they conflict, but the conflict must be recorded.
- Do not combine unrelated repositories into a monorepo merely to claim integration.
- Do not auto-merge or auto-fix revenue-critical or governance repositories.
- Do not treat configuration presence, a successful mock, or an exported handoff as proof of a live account connection.
- Do not store shared provider credentials in GitHub. Use the target environment's secret manager and least-privilege credentials.
- Do not copy Gemini, Claude, or ChatGPT conclusions and label the repetition independent verification.

## First implementation slice

The first slice is deliberately read-only and reviewable:

1. Generate a machine-readable fleet registry for all 45 repositories from observed GitHub metadata.
2. Map the existing repository roles from Tower Control, Hermes, provider-neutral Control Tower, Gemini/NotebookLM, Claude/Hermes, and Hostinger specifications.
3. Mark stale repository counts and conflicting command-center claims.
4. Add profile validation and a dry-run planner to `jarvis-nexus-core`.
5. Pilot profiles on five repositories: `jarvis-nexus-core`, the provider-neutral Control Tower, `Hermes-AI-Hermes`, Tower Control, and the Hostinger repository.
6. Run native CI and independent review before proposing wider rollout.

## Hostinger gate

The current code and documentation support a bounded website-inventory read, but no authenticated Hostinger read has been verified in the current Jarvis Nexus branch. Before any site write:

- identify the intended account, product, domain, workflow names, triggers, and output actions;
- confirm whether the target is Website Builder, WordPress, static/custom, Node, VPS, or Horizons;
- verify DNS and current site state separately;
- create a restorable backup and staging target;
- prepare a bounded diff from an approved GitHub revision;
- record rollback instructions and independent review evidence;
- obtain action-specific owner approval.

## Provider gates

### Gemini/NotebookLM

Use an independent source-grounded review line. Require a source manifest, claim-to-source matrix, contradictions, uncertainty, and recommendation. A handoff document is not proof that a Gemini project or NotebookLM collection exists.

### Claude/Hermes

Use the shared Hermes findings schema for supervised review. Claude may recommend, record findings, and draft reviews within the repository's risk rules. It may not approve truth, publication, financial action, credentials, destructive changes, or HumanApprovalGate.

### OpenAI/ChatGPT

Use the provider-neutral task contract and local ledger. Require explicit model selection, output limits, timeout, budget, secret injection, and external-call opt-in. ChatGPT Business handoffs remain explicit artifacts rather than an assumed automation API.

## Acceptance criteria

- All 45 observed repositories are represented exactly once in the generated registry.
- Every pilot repository has one validated profile and one accountable owner/reviewer path.
- No committed secret or private account record is introduced.
- Every cross-provider handoff preserves source revision and artifact hashes.
- Revenue-critical and governance repositories remain read-only unless an explicit reviewed action authorizes a draft PR.
- Hostinger remains read-only until account/product/site verification and deployment gates pass.
- Tests and check evidence are tied to the exact commit being promoted.
- No document claims that all external connections are live unless account-specific verification evidence exists.

## Immediate next actions

1. Finish review of the existing large draft PR before using it as the base for more implementation.
2. Split fleet-registry/profile validation into a small follow-up PR rather than adding it to the already broad feature PR.
3. Regenerate stale cross-repository maps from the current 45-repository inventory.
4. Resolve or supersede overlapping credential, installer, and Hostinger PRs after comparing their diffs against this contract.
5. Perform one authorized Hostinger inventory read and one independent Gemini or Claude round trip, then retain the receipts as the first live connection evidence.
