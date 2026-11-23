# Fleet synergy: AI Systems, Hostinger AI Agents Plus, and AI-improving-AI

Owner framing: *flexible and diverse across all AI systems; Hostinger.com AI Agents Plus; AI creating, building and improving better AI systems; through the Jarvis assistants, swarms, systems and communications networks.*

This document turns that framing into boundaries a reviewer can check. It adds no capability claim.

## 1. What "flexible and diverse" means operationally

Flexibility is not unbounded action. It is the ability to route the same bounded task to a different provider, model, environment or repository without rewriting the task or losing the evidence.

- A task envelope names `requested_action`, `allowed_action` and `provider_route`. Swapping the route must not change the objective, the evidence labels or the approval state.
- Diversity is measured by independent source lines, not by the number of provider names in a list. Gemini, Claude and ChatGPT reading the same summary are one source line, not three.
- A provider that is unavailable degrades to a declared alternative or to a queued draft. It never silently substitutes an unapproved route or escalates its own permission.

## 2. Hostinger AI Agents Plus

**Status: unverified.** No code search across the connected account returned the string `AI Agents Plus`. No repository in the fleet currently implements, wraps or references that Hostinger product by name.

What the fleet *does* have is adjacent and must not be confused with it:

- A bounded, read-only Hostinger website-inventory adapter (`src/jarvis/hostinger.py`, the value recorded by the connected account's GitHub code search), including pagination and duplicate-record validation.
- `config/hostinger-builder-capabilities.json`, which describes documented builder surfaces with an explicit scope note: no account, product entitlement or site connection was verified.
- Hostinger documentation reviewed 2026-10-20 covering website-list, pagination, Horizons website operations and a static-archive deployment endpoint.

Those are builder and hosting capabilities. Whether `AI Agents Plus` is a separate product, a plan tier, an entitlement inside a plan, or a renamed surface is **not established by anything observed in this fleet**. Before any integration claim:

1. Confirm the exact product name and the account entitlement that includes it.
2. Capture the official API or interface contract for that product.
3. Determine the authentication model and whether tokens inherit broader account permissions than the intended integration scope.
4. Build the adapter against a named, reviewable capability - not against a product name.
5. Keep the first version read-only and receipt-producing, as the website-inventory adapter already is.

Until those five steps produce evidence, Hostinger remains a **read-only** target and no agent runtime is described as hosted there.

## 3. AI creating, building and improving better AI systems

The recursive claim is the one most likely to be overstated, so the fleet should hold it to the following rules.

**What the fleet already supports as local, code-backed capability:**

- A bounded offline scaffold generator that produces tool templates without executing generated code.
- An admission rule in the swarm registry: generated output carries a template header and a content hash.
- Skill and workflow libraries covering swarm manufacturing, self-healing agent operations, agent interoperability, agentic swarm governance and an autonomous self-improvement engine - all currently documents and specs, not running agents.
- Hermes findings plus the Claude-to-Hermes bridge, which let a supervised model record findings into the same store the automated engine writes to.

**What is prohibited until separately evidenced:**

- Describing a document as a running agent. A skill file is a specification.
- Self-modifying code, self-deployment, or a system granting itself broader permission.
- Provider agreement presented as verification.
- An improvement claimed on the strength of a generated proposal rather than executed tests at a named revision.

**The improvement loop that is actually defensible:**

```text
observe -> propose -> review -> draft -> test at a named revision -> record evidence -> human decision
```

Each arrow is a separate, logged step. No step is skipped because a model proposed it.

## 4. Assistants, swarms, systems, communications networks

| Layer | In this fleet | State |
|---|---|---|
| Assistants | Provider-neutral task contract with per-provider adapters | Local, mock-verified; live provider calls require keys and opt-in |
| Swarms | Role catalog, swarm unit model, cross-repo role map, swarm factory roadmap | Architecture and documents; the historical role map has a stale repository count |
| Systems | Tower Control registry, Hermes fleet engine, Jarvis Nexus control tower | Implemented to differing degrees; registry still incomplete |
| Communications networks | Findings store, correlation and handoff records, per-device session labels | Findings path is real; no live cross-device or cross-provider synchronization |

No layer above may be described as fully connected. The communications layer in particular has no live synchronization today.

## 5. Acceptance criteria

- No document in this fleet claims a Hostinger `AI Agents Plus` integration without a captured product contract and an account-entitlement record.
- No improvement cycle is recorded as complete without tests executed at a named commit.
- No skill, workflow or blueprint file is counted as a deployed agent.
- Provider diversity is reported as independent source lines, with shared sources declared.
- Read-only remains the default for every Hostinger and revenue tier.
