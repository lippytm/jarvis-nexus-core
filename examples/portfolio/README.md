# Portfolio planning examples

These are synthetic, inactive examples for the [portfolio expansion](../../docs/PORTFOLIO_EXPANSION_2026_10_22.md). They do not describe completed work or live account state.

- `catalog.json` is the exact authored catalog embedded in the workbench.
- Each of the twelve initiatives has a `.request.json` and a compiled `.mission.json`.
- `mission_index.json` records their filenames, project mappings and mission hashes.
- `funding-customers.campaign.json` and `referral-partners.campaign.json` each contain seven unpublished channel briefs. They use their respective second configured destination and preserve its referral parameter.

Every request selects Gemini as a draft destination solely to exercise provider/channel separation. No Gemini or other model call is made. All examples identify `a67e743e8b32e552ccddd9e16a2108fe2f816274` as source context, the previous development baseline. That field does not identify the later commit that introduces the compiler.

There are sixty role drafts across these twelve missions. They reuse the five-role contract; this count is not a count of running assistants. To adapt an example, copy its request to a fresh path, edit the objective and selected target, and compile a new mission with an appropriate source-context revision. Preserve the original examples and evidence.
