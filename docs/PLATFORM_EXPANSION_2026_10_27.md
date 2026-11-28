# Jarvis platform handoff expansion — October 27, 2026

This development change expands the existing portable network rather than creating a second runtime.

## Result

- Sixteen exact target IDs across catalog, Python draft/return contracts, inactive swarm factory and browser composer.
- Adds `slack`, `zapier`, `claude-cowork` and `perplexity` to the prior twelve targets.
- Adds the four targets to connection reporting with unverified status, unknown runtime availability and owner-review write gates.
- Adds official setup references and target-specific boundaries. Only these new catalog entries carry the October 27 review date; existing documentation entries retain their earlier review date.
- Corrects generic JSON record size checks to count UTF-8 bytes instead of an ASCII-escaped representation. Invalid UTF-8 surrogates remain rejected.
- Copies injective-campaign theme and membership data so editing one returned campaign cannot silently alter another campaign or leave its retained digest stale.
- Adds regression cases for all four targets through the real local SQLite review/export/import ledger, persistence, wrong-provider rejection, defensive catalogs and UTF-8 bounds.
- Adds browser-helper export checks for the four exact target IDs and Unicode text.

The new ledger tests use explicitly labeled synthetic fixture returns. They do not claim any provider received a message or returned an answer. An exact hash and reviewer label record integrity and local intent, not authenticated identity.

## Use the existing tools

Open `web/jarvis-composer.html` locally and select the relevant destination. The authored browser logic now exports the four additional exact IDs; actual browser rendering and native clipboard/download behavior still need target-device verification.

From the repository root with Python 3.11+, create a fresh output filename:

```bash
python scripts/jarvis_network.py catalog --out reports/expanded-provider-catalog.json
python scripts/jarvis_network.py factory --project ai-jarvis --targets github,youtube,facebook,linkedin,instagram,hostinger,slack,zapier,threads,substack,claude,claude-cowork,gemini,perplexity --swarm expanded-jarvis --source-revision e7c99a44933f14532fde05070bedb4b6ce049a52 --out reports/expanded-jarvis.swarm.json
```

That source revision is this change's inspected baseline, not proof that the factory fetched code and not the final publication head. The output contains five bounded role specifications targeting fourteen selected destinations; it does not start seventy agents. Full target coverage also retains ChatGPT and OpenAI API separately. Existing ledger stage/review/export/import-return commands remain the transfer path.

## Owner business scope retained

The public-media capacity target remains four posts per day on Facebook, LinkedIn, YouTube, Instagram, Threads and Substack: 24 daily editions. Adding Slack or Zapier as a handoff target does not add a public posting quota to those services. Timed publishing, rendered media, shared multi-device storage and live adapters remain separate engineering tasks.

Trading Bots stays R&D-only, with no broker permissions or live-money operations. RoboParty remains deferred as a future business decision. The complete portfolio and the four distinct funding/referral URLs remain in the owner's master business plan; this change does not narrow that scope.

## Verification and limits

Run syntax and behavior checks using the existing verifier:

```bash
python scripts/verify_control_tower.py
node --test --test-reporter=tap tests/*.mjs
```

The verifier parses source syntax before running Python behavior tests; the web job separately compiles and exercises the authored browser scripts. Its source hashes and checkout SHA identify the tested state. Actual CI results must be read from the matching commit/run, not inferred from this document. Local execution was unavailable during authoring; no local test success is claimed.

Official references:
- Slack OAuth: https://docs.slack.dev/authentication/installing-with-oauth/
- Zapier approval workflow: https://help.zapier.com/hc/en-us/articles/38731463206029-Request-approval-to-keep-your-workflow-running-with-Human-in-the-Loop
- Claude/Cowork custom connectors: https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp
- Perplexity Search: https://docs.perplexity.ai/docs/search/overview

No API, social publish, Slack send, Zap run, paid provisioning, merge or production deployment is implemented by this expansion. Hostinger's separate existing inventory transport remains read-only and does not establish site publishing access.

Outstanding: test the known GetBizFunds product-to-route mapping and shared comedy-program registry issue; complete durable authenticated scheduling and actual provider round trips. Do not release the overall development PR merely because the offline suite passes.

Rollback uses a normal revert of this development commit. No production database migration or external account change is included.
