# Jarvis Diary Product Studio

## Product idea and present capability

Build a small editorial practice around one useful daily record: what happened,
what supports it, what remains uncertain, and what comes next. The first audience
is the owner reviewing life and business activity. A second audience can be
invited to review a deliberately selected teaching or creative edition.

The current compiler creates local media drafts from an explicitly selected
`public_candidate` entry. Its outputs include an EPUB, an interactive text edition,
scripts, narration sources, a synthesized music bed, ad-copy candidates and an
inactive model-handoff JSON. Templates run locally without model calls. Optional
FFmpeg rendering creates a text-card MP4 and rough generic narration WAV when
the required local filters are available. These are the implementation's present
building blocks; adoption, demand, publication and revenue remain unestablished.
[Implementation: media compiler](../control_tower/media.py) and
[optional renderer](../control_tower/media_render.py).

## A repeatable capture routine

Use a proposed three-minute morning check to choose one initiative and one
practical next action. At the end of the day, allow seven minutes to write a
summary and one to three observations. Include personal context only when it
helps the owner understand the day. Keep the initial entry private, attach
specific source references where available, and label intentions as planned.

Once a week, allow thirty minutes to select one useful story. Ask: what could
another person learn, what evidence travels with the lesson, and what personal
detail can stay in the private record? Make a separate candidate edition with a
distinct entry ID when preparing a public adaptation. Export and validate it;
the browser form does not autosave. The local CLI provides separate validation,
storage, history and compilation commands.
[Capture guide](JARVIS_DIARY_WORKBENCH.md);
[local CLI](../scripts/jarvis_diary.py).

## Keep factual and fictional adaptations legible

Retain the four observation labels throughout editing: source-linked,
owner-reported, planned and fictional. A link identifies a reference; checking
whether it supports the claim is an editorial task. Summaries supply context and
should not quietly upgrade tentative observations into verified outcomes.

For documentary material, build each scene around a labelled observation and its
source IDs. Record missing corroboration as a production task. For fiction, use
an explicit fictional premise, invented characters and clear scene labels. The
current movie and music-film treatments contain reusable authored motifs; they
need editorial development to become a distinctive project. Keep the original
entry, selected edition and product manifest together so revisions remain
traceable. A digest checks content integrity, not the truth of a claim.

## One record, several useful editions

Choose formats according to the intended learning or viewing experience. Start
with two editions before attempting the entire set.

| Edition | Current starting artifact | Next editorial step |
| --- | --- | --- |
| Documentary | `documentary.md` labels observations and proposed narration. | Check claims, select permitted supporting material and review scene context. |
| Trailer | `trailer.md`, timed cues and optional 15/30/60-second text-card preview. | Test whether the premise is understandable; replace concept cards with reviewed production assets when appropriate. |
| Fictional movie | `movie_treatment.md` contains an explicitly invented story treatment. | Develop character motivation, dialogue and a bounded scene plan. |
| Music film | `music_film.md` and a simple synthesized instrumental WAV. | Revise the composition, lyrics and visual treatment; retain asset provenance. |
| Ebook | `ebook.md` and a packaged `book.epub`. | Edit the reading sequence, inspect an actual reader and verify source presentation. |
| Audio book | Narration text/SSML; optional rough generic narration WAV. | Review pronunciation, pacing and audio quality before preparing a finished narration. |
| Video book | Storyboard text plus the optional concept MP4. | Design readable chapters and synchronize any later narration; current VTT cues are storyboard text, not aligned speech captions. |
| Interactive lesson | `interactive_book.html` provides record filtering, label practice and reflection. | Observe learners using it; label matching alone does not demonstrate learning. |

Audience, visual style, audio style, learning goal and call-to-action notes guide
later editorial decisions. The current renderer uses fixed visual/audio
approaches; these notes do not automatically produce custom footage or styles.

## Reusable seven-channel editorial strategy

Prepare one master editorial packet containing the selected entry, one useful
idea, a supported claim or clearly labelled plan, a source note, a question and
one relevant next step. Reuse that substance in seven draft forms:

| Channel | Proposed editorial version | Useful response to record |
| --- | --- | --- |
| Facebook | A short diary story and a concrete discussion question. | Responses describing a related need. |
| LinkedIn | A build note: problem, artifact, evidence and remaining work. | Relevant follow-up conversations. |
| Substack | A reflective letter with a source appendix and exercise. | Replies and requests for another edition. |
| Instagram | A planned visual sequence showing context, evidence and next step. | Questions about the explanation or resource. |
| Threads | One compact idea with its uncertainty and source reference. | Substantive questions or corrections. |
| YouTube | A reviewed concept preview with companion narration text. | Observed comprehension and resource inquiries. |
| GitHub | A reproducible example, documentation and validation evidence. | Reproduction reports and actionable issue feedback. |

These are editorial drafts, with manual review and separate publication decisions.
Choose two channels for an initial trial so response review stays manageable.
The tools provide no social account connection, automated distribution or live
channel analytics.

## Preserve destination and audience boundaries

Education and membership inquiries belong to the separately configured
`website-learning` initiative and its owner-reference education site. The
`affiliate-builder` platform remains unassigned; do not borrow the education
site as its destination. Keep `funding-customers` copy focused on the customer
journey and `referral-partners` copy focused on the partner journey. Their
configured references are separate, and live access or results are unverified.
Every draft should name its initiative, intended audience and destination state.
[Portfolio catalog](../examples/portfolio/catalog.json).

## A small, honest ad-copy experiment

Begin with private feedback on two headlines for the same reviewed resource:
“Turn a daily note into a useful teaching draft” and “Keep sources with the story
of your work.” Hold the resource, audience, destination and call to action
constant. Change one message element, and record the exact version shown.

For any later authorized public or paid trial, agree a time window and spending
cap before starting. Record available exposure counts, actual visits, qualified
inquiries and eventual purchases separately. If tracking cannot establish a
denominator or attribution, mark it unknown. Clicks are not purchases; inquiry
counts do not establish commissions. Keep refunds and confirmed commissions as
separate observed records. A small trial gives directional feedback, not a
reliable market-wide conversion estimate.

## Proposed stage gates and viability decisions

The following are planning targets, not promises or automatic schedules:

| Stage | Target evidence before proceeding |
| --- | --- |
| Week 1: capture | Four usable entries, one exported candidate and recorded authoring time. |
| Week 2: editorial review | Five volunteer reviews; at least four can distinguish the intended evidence labels and explain the resource's purpose. Revise misunderstandings. |
| Week 3: resource trial | One edited ebook/lesson pair and one short preview; log completion, questions and production time. |
| Week 4 or later: offer decision | Repeated requests for a specific benefit, a defined deliverable, documented delivery effort and an owner-approved pilot offer. |

Assess usefulness and repeatability before expanding production. Track editing
hours, actual direct costs, support work and later net receipts if any. A proposed
price must cover the chosen delivery scope and the owner's assigned labor cost;
current templates establish neither willingness to pay nor a profitable price.
Continue a small pilot when users can identify a recurring benefit and delivery
effort is manageable. Narrow the format, revise the audience or pause when those
signals are absent. Compiling a pack does not resume the paused Studio Work Cycle
or authorize model calls, purchases or publication.
