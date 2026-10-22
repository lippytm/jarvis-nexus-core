# JARVIS NEXUS CORE — AI Builds AI

AI Jarvis Assistants Swarms Systems Networks — Intergalactic Corporate Services LLC

This development branch contains a Python Control Tower prototype for bounded
builder proposals, explicit connector observations, and synthetic membership and
funding-referral workflows. The current review target is [draft PR #5](https://github.com/lippytm/jarvis-nexus-core/pull/5).

The network milestone adds a reusable spelling composer, five assistant roles
for each of seven work areas, twelve draft destinations, and a durable local
handoff ledger. The 35 example assistant specifications are inactive. They do not
start external agents, connect accounts, send posts, or execute generated code.

## Write and review a Jarvis draft

Open [Jarvis Composer](web/jarvis-composer.html) as a local HTML file in a browser.
It provides optional native browser spelling, explicitly selected corrections
for common typos, undo, copy, and text/JSON downloads. It requires no server,
build step or API key. It does not modify ChatGPT's native input box.

See the [composer guide and verification limits](docs/JARVIS_COMPOSER.md).
Browser rendering and native clipboard/spellcheck behavior still require a
target-browser check; the retained automated checks cover the authored logic
and HTML structure.

## Build portable assistant specifications

```bash
python scripts/jarvis_network.py catalog --out reports/provider-catalog.json
python scripts/jarvis_network.py demo --out reports/network-demo.json
```

These commands write new files and refuse to overwrite existing evidence. The
demo uses local synthetic packets. The [network milestone guide](docs/NETWORK_MILESTONE_2026_10_22.md)
documents factory, review, export, return-import and ledger commands, with
[seven generated project manifests](examples/network/project_index.json).

## Verify the Control Tower

From the repository root with Python 3.11 or later:

```bash
python scripts/verify_control_tower.py
```

The command checks source syntax, runs the offline unit tests and demonstration,
and saves a JSON evidence record plus a test log under `reports/`. It uses the
Python standard library and makes no model, payment, or deployment calls.

Test the actual spelling/export helper with Node 18 or later (CI uses Node 24):

```bash
node --test tests/test_composer.mjs
```

## Review the implementation

- [Network milestone and next three engineering priorities](docs/NETWORK_MILESTONE_2026_10_22.md)
- [Provider routes, account requirements and Hostinger probe](docs/PROVIDER_CONNECTIONS_2026_10_22.md)
- [Network milestone verification](docs/evidence/network_milestone_2026_10_22.json)
- [Public repository metadata inventory](examples/network/public_repository_inventory.json)
- [Earlier October 22 engineering update](docs/ENGINEERING_UPDATE_2026_10_22.md)
- [Recovered v1.0 source reconciliation](docs/V10_RECONCILIATION.md)
- [Membership and referral website edit specification](docs/WEBSITE_CONVERSION_REVIEW.md)
- [Synthetic journey example](examples/membership_journey.json)
- [Recorded local verification](docs/evidence/control_tower_2026_10_22.json)
- [Seven management workflows](docs/SEVEN_WORKFLOWS_V05.md)

Generated tools remain draft source, and orchestration produces bounded proposals.
Synthetic payment events do not authenticate a payment provider. Connector
configuration and historical read observations do not establish current access,
write permission, deployment, revenue, or customer conversion.

## Existing service prototypes

The repository also contains the earlier JavaScript service and installer
prototypes. Their operation, hosting cost, production security and replacement
coverage for third-party products were outside this Control Tower verification.
Review those sources and their deployment assumptions before running the installer.
