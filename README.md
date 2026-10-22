# JARVIS NEXUS CORE — AI Builds AI

AI Jarvis Assistants Swarms Systems — Intergalactic Corporate Services LLC

This development branch contains a Python Control Tower prototype for bounded
builder proposals, explicit connector observations, and synthetic membership and
funding-referral workflows. The current review target is [draft PR #5](https://github.com/lippytm/jarvis-nexus-core/pull/5).

## Verify the Control Tower

From the repository root with Python 3.11 or later:

```bash
python scripts/verify_control_tower.py
```

The command checks source syntax, runs the offline unit tests and demonstration,
and saves a JSON evidence record plus a test log under `reports/`. It uses the
Python standard library and makes no model, payment, or deployment calls.

## Review the implementation

- [October 22 engineering update and next three priorities](docs/ENGINEERING_UPDATE_2026_10_22.md)
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
