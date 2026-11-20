# Original diary RPG episode contract

The [episode compiler](../control_tower/episode.py) turns one valid diary entry into a deterministic local anime/RPG production plan: three original fictional worlds, six or seven narrated scene drafts, and three proposed quest cards. It preserves the supplied labels on diary records. It makes no provider calls, fetches no news or sources, executes no quests, and grants no publication approval.

This contract describes the JSON plan. A rendered video, narration file, player or interactive experience is a separate artifact with its own checks. A successful compilation does not establish that those artifacts exist, that a viewer learned something, or that any real business/project task was completed.

## Python API and audience selection

```python
from control_tower.episode import build_episode, validate_episode

public_episode = build_episode(
    entry,
    source_revision="a" * 40,  # Synthetic example; supply the actual context revision.
    episode_id="example-episode",
)

owner_episode = build_episode(
    private_entry,
    source_revision="a" * 40,
    episode_id="owner-example",
    audience="owner",
)

checked = validate_episode(public_episode)
```

`build_episode(entry, *, source_revision, episode_id, audience="public")` first applies the [diary contract](DIARY_DATA_CONTRACT.md). The default public audience requires `visibility="public_candidate"`. A private or internal entry fails before an episode, source digest or output digest is constructed. An explicit owner audience permits any of the three valid diary visibilities for local viewing. Invalid audience values do not fall back to owner mode.

The output always records both `audience` and `source_visibility`; an owner/private draft remains labeled owner/private. It always has `publication_approval="not_granted"`. Public-candidate selection is an export filter, not permission to post, advertise, upload private material, or operate an account. Consumers must preserve these labels on any local rendition, and must not relabel an owner draft as public simply because rendering succeeded.

`source_revision` must be an exact lowercase 40-character hexadecimal context revision. The compiler records this supplied value without running Git or proving what that revision contains. It is named `source_context_revision` in the output so it is not confused with proof that the current compiler implementation was already present at that revision. `episode_id` follows the diary identifier boundary: 2–48 ASCII characters matching `[a-z][a-z0-9_.-]{1,47}`.

`validate_episode(episode)` checks the exact schema, bounded values, scene sequence, source references, quest states, audience/visibility relationship and episode content hash. It returns a deep defensive copy. It does not have the original diary and cannot independently authenticate a claimed source hash, visibility, author or evidence label. A person who rewrites a packet and recomputes its hash can create another structurally valid draft; the hash is not a signature or access-control mechanism. To check the source binding, separately validate the original diary and compare its `diary_entry_digest` with `source_entry_sha256`.

## Exact top-level object

The episode contains exactly these 21 keys; missing and extra fields are rejected.

| Key | Value or rule |
| --- | --- |
| `schema_version` | Exact integer `1`; booleans and floats rejected |
| `kind` | `jarvis.rpg_episode` |
| `episode_id` | Valid 2–48-character identifier |
| `date` | Supplied diary date, strict ASCII Gregorian `YYYY-MM-DD`, years 0001–9999 |
| `timezone` | `America/Los_Angeles` |
| `title` | Original diary title, nonblank and at most 180 UTF-8 bytes |
| `audience` | `public` or `owner` |
| `source_visibility` | Original diary visibility; public audience requires `public_candidate` |
| `source_entry_sha256` | Lowercase 64-character SHA-256 of the complete validated source diary |
| `source_context_revision` | Supplied lowercase 40-character context revision |
| `sources` | Original diary source objects, list of 0–5 |
| `worlds` | Three fictional world records in fixed order |
| `scenes` | Six or seven scene records in the sequence below |
| `quests` | Three planned quest records in fixed order |
| `observations_omitted` | Exact integer 0–5; number of original observations beyond the first three |
| `news_status` | `not_included_in_this_project_pilot` |
| `fictional_framing` | `Original fictional setting; project records and plans retain their labels.` |
| `publication_approval` | `not_granted` |
| `external_actions` | Exact integer `0` |
| `model_calls` | Exact integer `0` |
| `episode_sha256` | SHA-256 of canonical episode JSON excluding this hash field |

The full canonical JSON packet must not exceed 65,536 bytes. Canonical serialization uses sorted keys, compact separators, original Unicode encoded as UTF-8, and no nonfinite numbers. No current timestamp, random seed, file read, network result or model response affects the output. Identical validated entry content, audience, episode ID and context revision produce identical output.

All object/list/string types are exact built-in JSON types. Text must be nonblank, valid UTF-8 and free of C0 controls except tab, carriage return and line feed, following the diary rule. Individual scene/world/quest limits below count Unicode code points, as Python `len(str)` does, rather than JavaScript UTF-16 code units. The packet limit counts UTF-8 bytes after JSON serialization. This is a JSON contract; downstream XML or other media formats may impose further character restrictions.

## Sources and evidence

`sources` retains the diary's exact `{source_id, title, url}` objects. IDs are unique and use the 2–48-character identifier rule; titles are nonblank and at most 200 UTF-8 bytes; URLs are at most 1,000 UTF-8 bytes. URLs use the existing HTTPS boundary: nonempty hostname, no credentials, whitespace, C0 characters or backslashes, and absent port or port 443. URL validation does not fetch or verify a source.

The compiler takes the first one to three observations in their supplied order. Each becomes a separate scene with its original `evidence_state` and `source_ids`. Source-linked records must retain at least one valid source reference. Other states can retain references without becoming source-linked. No `mixed`, `verified` or `completed` evidence state is introduced.

| Evidence label | Narrated treatment |
| --- | --- |
| `source_linked` | A supplied reference is identified; it is not described as independently verified. |
| `owner_reported` | Identified as an owner report without independent verification. |
| `planned` | Identified as a plan, not a completed achievement. |
| `fictional` | Identified as fiction, not a factual event. |

Record scene titles retain the original observation ID, for example `Diary record: observation-01`. Narration introduces the supplied text with its plain evidence label and “From the diary.” Excerpts collapse whitespace and append an ellipsis when truncated to fit the character budget. They are an adaptation; the original diary remains unchanged. The omitted-observation count is explicit. With fewer than three record scenes, the omission count must be zero.

The original diary summary and media notes are not synthesized into additional story events. The supplied next action appears as an excerpt in the planned quest-priorities scene. The full source hash still covers the complete original diary, including text not narrated. This is selected-source metadata and must be handled according to the episode's audience.

## Fictional worlds

Each world has exactly `world_id`, `title` and `description`. Titles are at most 80 code points; descriptions at most 240. The three IDs and their order are fixed:

| World ID | Compiler title | Fictional purpose |
| --- | --- | --- |
| `archive` | The Lantern Archive | A command library for diary records, references and creative editions |
| `forge` | The Copper Forge | A workshop for tools, learning projects and proposed experiments |
| `observatory` | The Sky Observatory | A lookout for reviewing access, evidence gaps and next steps |

These are an authored original setting. Luma is an original fictional guide who welcomes the viewer and closes the episode with a lantern beside the unfinished page. The worlds and guide are not real infrastructure, connected services, external accounts, or assertions about the owner's personal life. The opening introduces all three worlds and names the selected portfolio initiative as context. Record scenes are placed in a fictional world according to that initiative: tool/Linux/robotics/wearable projects use the Forge; publishing/interactive-video projects use the Archive; the other registered initiatives use the Observatory. This placement is presentation metadata and establishes no project activity.

## Scene sequence and bounds

Each scene has exactly these seven keys:

| Key | Rule |
| --- | --- |
| `scene_id` | Unique valid identifier in the required sequence |
| `title` | Nonblank, at most 80 code points |
| `voiceover` | Nonblank, at most 500 code points |
| `screen_text` | Nonblank, at most 180 code points |
| `evidence_state` | One of the four diary evidence labels |
| `source_ids` | List of at most five unique IDs present in `sources` |
| `world_id` | One of `archive`, `forge`, `observatory` |

The compiler keeps each diary observation separate because a single scene label cannot truthfully merge differently labeled records. It combines two proposed planning sections when necessary to keep the output at seven scenes.

| Source observations available | Required scene IDs, in order | Total |
| --- | --- | --- |
| One | `opening`, `record-01`, `briefing`, `revenue-experiment`, `next-quests`, `closing` | 6 |
| Two | `opening`, `record-01`, `record-02`, `briefing`, `revenue-experiment`, `next-quests`, `closing` | 7 |
| Three to eight | `opening`, `record-01`, `record-02`, `record-03`, `briefing-revenue-plan`, `next-quests`, `closing` | 7 |

`opening` and `closing` are always fictional and have no source IDs. The opening narration begins with the exact `fictional_framing` statement. The closing leaves the fictional library ready for another visit; it does not award completion.

The briefing, offer experiment and next-quest scenes are always planned and have no source IDs. The proposed briefing keeps the dated record and its labels together. The proposed revenue experiment is to define a small offer, audience and delivery route and review how interest could be assessed. It does not invent customers, funding outcomes, commissions, sales, earnings or a working business integration. Current news is expressly not supplied by this pilot. The schema does not contain a five-news-item digest.

Validation enforces structural labels and bounded text, not the factual truth of arbitrary prose edited into a packet. Generated plans retain their prescribed labels; renderers must show those labels rather than presenting every scene as an achieved real-world event.

## Three planned quest cards

Each quest has exactly `quest_id`, `title`, `objective`, `status`, `evidence_state`, `source_ids` and `world_id`. Titles are nonblank and at most 80 code points; objectives are nonblank and at most 400. IDs, order and world bindings are fixed:

| Quest ID | World | Compiler objective |
| --- | --- | --- |
| `hostinger-connection` | `observatory` | Confirm the site's Hostinger product and available read-only access; review a supported route before any live connection attempt. |
| `ai-building-cycle` | `forge` | Choose one bounded assistant/tool change, run its checks and retain a human review before considering release. |
| `media-review` | `archive` | Review source labels, asset rights, narration, captions and accessibility before considering publication. |

All three cards have `status="planned"`, `evidence_state="planned"` and an empty `source_ids` list. They are authored next-step proposals, not source-backed result records. The schema rejects a completed status, evidence upgrades, reward fields, XP fields, money fields, extra quest IDs or a changed order/world binding. An interactive viewer may separately record which cards or worlds it visited, but a visit or answer must not mutate these project quests into completed work. Any interaction export needs a separate schema and an explicit meaning limited to that interaction.

## Loading and validating a saved packet

Use the existing bounded loader before validating a file:

```python
from control_tower.network_contract import load_packet
from control_tower.episode import validate_episode

episode = validate_episode(load_packet("path/to/local-episode.json"))
```

The loader checks raw size, UTF-8, duplicate JSON keys and nonfinite numbers before the episode validator sees the object. `validate_episode` cannot recover duplicate keys that a prior permissive JSON parser has already discarded. The compiler and validator do not themselves read files, create directories, import accounts, dispatch prompts or perform network I/O. File selection, output privacy, persistent audience labels and safe rendering remain the caller's responsibilities.

The included SHA-256 detects a changed packet when its stored hash is left unchanged. Structural violations are rejected even if a caller recomputes a matching hash: examples include public/private inconsistency, completed quest status, unknown source/world references, unsupported evidence states and excessive text. Recomputing a hash does not make unsupported claims true or grant permission to publish.

## Tracked public pilot

The [public source diary](../examples/episodes/public-diary-source.json) and [compiled episode](../examples/episodes/jarvis-diary-pilot.json) are a reproducible public-only example. They refer to context revision `76e7a538d7c1a3a113d57727f025a2c6b27ccf13` and the linked milestone CI run. The two supplied records describe the completed diary workbench, revision history and multimedia compiler, plus the retained 232 Python and 123 JavaScript-helper checks documented in the [preceding milestone](DIARY_MULTIMEDIA_MILESTONE_2026_10_22.md). These are that milestone's counts, not the expanded episode milestone's test totals.

The pilot has seven scenes, three proposed quests and 240 narration words. Its fictional guide, Luma, leads into the next planned building and connection cycle. The source and compiled episode remain `public_candidate`/`public`; neither contains a private owner diary. A regression test rebuilds the tracked pilot from its source and compares the complete result, so compiler-template changes cannot silently leave the tracked example stale. Actual rendered duration and media quality require the separate renderer's evidence.

## Local verification

```bash
python -m py_compile control_tower/episode.py tests/test_episode.py
python -m unittest discover -s tests -p test_episode.py -v
```

At implementation review, 25 focused standard-library tests passed. They cover deterministic source and output hashes, defensive copies, rejection of private/internal input before public-output digest construction, explicit owner handling, every registered initiative, one through eight observations, six/seven-scene bounds, omission counts, evidence/source preservation, fixed planned quests, tampering, Unicode/code-point limits, exact types/fields, duplicate raw JSON keys, oversized input and the tracked pilot's reproducibility. Tests use synthetic records, temporary files and the supplied public milestone example; no private owner records, live provider calls, source fetches or publication actions are involved.
