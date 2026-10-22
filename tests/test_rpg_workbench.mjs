import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { Script, createContext } from 'node:vm';

const html = readFileSync(new URL('../web/jarvis-rpg.html', import.meta.url), 'utf8');
const payloads = [...html.matchAll(/<script type="application\/json" id="episode-data">([\s\S]*?)<\/script>/g)];
assert.equal(payloads.length, 1);
const episode = JSON.parse(payloads[0][1]);
const tracked = JSON.parse(readFileSync(new URL('../examples/episodes/jarvis-diary-pilot.json', import.meta.url), 'utf8'));
const scripts = [...html.matchAll(/<script id="(jarvis-rpg-(?:core|app))">([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length, 2);
const coreSource = scripts.find(match => match[1] === 'jarvis-rpg-core')[2];
const appSource = scripts.find(match => match[1] === 'jarvis-rpg-app')[2];
// The real authored helper runs in isolation; episode/user strings are data only.
const context = createContext({ TextEncoder, URL });
new Script(coreSource, { filename: 'jarvis-rpg-core.js' }).runInContext(context, { timeout: 1000 });
const core = context.JarvisRPG;
const plain = value => JSON.parse(JSON.stringify(value));
const clone = value => structuredClone(value);
const initial = () => plain(core.initialProgress(episode));
const canonical = value => Array.isArray(value) ? value.map(canonical) : value !== null && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])])) : value;
const rehash = value => {
  const { episode_sha256, ...content } = value;
  return { ...content, episode_sha256: createHash('sha256').update(JSON.stringify(canonical(content))).digest('hex') };
};
const ownerEpisode = visibility => rehash({ ...clone(episode), audience: 'owner', source_visibility: visibility });

test('both actual shipped scripts compile without a DOM or generated-code execution', () => {
  assert.doesNotThrow(() => new Script(coreSource));
  assert.doesNotThrow(() => new Script(appSource));
});

test('the shipped public pilot exactly matches its tracked source and dated revision', () => {
  assert.deepEqual(episode, tracked);
  assert.equal(episode.audience, 'public');
  assert.equal(episode.source_visibility, 'public_candidate');
  assert.equal(episode.date, '2026-10-22');
  assert.equal(episode.source_context_revision, '76e7a538d7c1a3a113d57727f025a2c6b27ccf13');
  assert.ok(episode.sources.some(source => source.url.includes('39862842245')));
  assert.deepEqual(plain(core.validateEpisode(episode)), episode);
});

test('the embedded episode content digest verifies independently against its authored data', () => {
  assert.equal(rehash(episode).episode_sha256, episode.episode_sha256);
  assert.equal(episode.publication_approval, 'not_granted');
  assert.equal(episode.external_actions, 0);
  assert.equal(episode.model_calls, 0);
  assert.equal(episode.news_status, 'not_included_in_this_project_pilot');
});

test('public editions reject private/internal sources and unknown or untyped audiences', () => {
  for (const visibility of ['private', 'internal', 'public', null]) assert.throws(() => core.validateEpisode({ ...episode, source_visibility: visibility }));
  for (const audience of ['team', 'OWNER', null, true, ['owner']]) assert.throws(() => core.validateEpisode({ ...episode, audience }));
});

test('explicit owner editions retain prominent source labels in progress and both briefs', () => {
  for (const visibility of ['private', 'internal', 'public_candidate']) {
    const owner = ownerEpisode(visibility);
    const state = core.initialProgress(owner);
    assert.equal(state.audience, 'owner');
    assert.equal(state.source_visibility, visibility);
    const label = `OWNER EDITION / ${visibility.replaceAll('_', ' ').toUpperCase()} SOURCE`;
    assert.equal(core.editionLabel(owner), label);
    assert.ok(core.questBrief(owner, state).includes(label));
    assert.ok(core.progressBrief(owner, state).includes(label));
    assert.equal(JSON.parse(core.serializeProgress(owner, state)).source_visibility, visibility);
  }
});

test('episode schema, hashes and local-only framing are strict without extra authority fields', () => {
  for (const [key, value] of [['schema_version', true], ['kind', 'jarvis.approval'], ['external_actions', true], ['model_calls', 1], ['publication_approval', 'granted'], ['news_status', 'latest_news_verified'], ['fictional_framing', 'A true story'], ['source_entry_sha256', 'a'.repeat(64) + '\n'], ['source_context_revision', 'a'.repeat(40) + '\n'], ['date', '2026-02-29'], ['timezone', 'UTC'], ['observations_omitted', 6], ['observations_omitted', true]]) assert.throws(() => core.validateEpisode({ ...episode, [key]: value }));
  assert.throws(() => core.validateEpisode({ ...episode, completed: true }));
  for (const value of [null, [], 'text']) assert.throws(() => core.validateEpisode(value));
});

test('world order, quest mapping and planned status cannot become business completion', () => {
  assert.deepEqual(episode.worlds.map(world => world.world_id), ['archive', 'forge', 'observatory']);
  assert.deepEqual(plain(core.QUEST_WORLDS), { 'hostinger-connection': 'observatory', 'ai-building-cycle': 'forge', 'media-review': 'archive' });
  for (const mutate of [value => value.worlds.reverse(), value => value.quests.reverse(), value => value.quests[0].world_id = 'archive', value => value.quests[0].status = 'completed', value => value.quests[0].evidence_state = 'source_linked', value => value.quests[0].source_ids = [episode.sources[0].source_id]]) {
    const changed = clone(episode); mutate(changed); assert.throws(() => core.validateEpisode(changed));
  }
});

test('scene sequence, fiction framing and linked-source references remain explicit', () => {
  for (const mutate of [value => value.scenes.reverse(), value => value.scenes[0].evidence_state = 'owner_reported', value => value.scenes[0].source_ids = [episode.sources[0].source_id], value => value.scenes[1].source_ids = ['unknown'], value => value.scenes[1].evidence_state = ['planned'], value => value.scenes[1].scene_id = 'opening']) {
    const changed = clone(episode); mutate(changed); assert.throws(() => core.validateEpisode(changed));
  }
  const linked = clone(episode); linked.scenes[1].evidence_state = 'source_linked'; linked.scenes[1].source_ids = []; assert.throws(() => core.validateEpisode(linked));
  const repeated = clone(episode); repeated.scenes[1].source_ids = [episode.sources[0].source_id, episode.sources[0].source_id]; assert.throws(() => core.validateEpisode(repeated));
});

test('episode text uses strict Unicode, byte-bounded titles and code-point-bounded voiceover', () => {
  for (const title of ['\u0085', '\ud800', 'a\u0000b', '😀'.repeat(46)]) assert.throws(() => core.validateEpisode({ ...episode, title }));
  const changed = clone(episode); changed.scenes[0].voiceover = '😀'.repeat(500);
  assert.equal(Array.from(core.validateEpisode(changed).scenes[0].voiceover).length, 500);
  changed.scenes[0].voiceover += 'a'; assert.throws(() => core.validateEpisode(changed));
  const source = clone(episode); source.sources[0].title = 'é'.repeat(101); assert.throws(() => core.validateEpisode(source));
});

test('source URLs require bounded HTTPS references without credentials or custom ports', () => {
  for (const url of ['http://example.org', 'https://user:pass@example.org', 'https://@example.org', 'https://example.org:8443', 'https://example.org/a\n', 'https://example.org/\u0085', 'https://example.org\\other', 'https:///example.org', 'https://example.org/' + 'x'.repeat(1000)]) {
    const changed = clone(episode); changed.sources[0].url = url; assert.throws(() => core.validateEpisode(changed));
  }
  const duplicate = clone(episode); duplicate.sources.push(clone(duplicate.sources[0])); assert.throws(() => core.validateEpisode(duplicate));
});

test('initial progress records only the initially displayed world and empty quest notes', () => {
  const state = initial();
  assert.equal(state.scope, 'visit_only_exploration');
  assert.equal(state.selected_world, 'archive');
  assert.equal(state.selected_quest, 'media-review');
  assert.deepEqual(state.visited_worlds, ['archive']);
  assert.deepEqual(state.explored_quests, []);
  assert.deepEqual(Object.keys(state.objective_notes), Array.from(core.QUEST_IDS));
  assert.ok(Object.values(state.objective_notes).every(value => value === ''));
});

test('opening worlds selects their corresponding quest once without mutating prior state', () => {
  const original = initial(); let state = original;
  for (const world of core.WORLD_IDS) state = core.selectWorld(state, world);
  state = core.selectWorld(state, 'forge');
  assert.equal(state.selected_quest, 'ai-building-cycle');
  assert.deepEqual(plain(state.visited_worlds), ['archive', 'forge', 'observatory']);
  assert.deepEqual(original.visited_worlds, ['archive']);
  assert.deepEqual(plain(state.explored_quests), []);
  assert.throws(() => core.selectWorld(state, 'unknown'));
});

test('quest selection preserves the mapping and rejects unknown or wrongly typed IDs', () => {
  for (const id of core.QUEST_IDS) {
    const state = core.selectQuest(initial(), id);
    assert.equal(state.selected_quest, id);
    assert.equal(state.selected_world, core.QUEST_WORLDS[id]);
    assert.ok(state.visited_worlds.includes(core.QUEST_WORLDS[id]));
  }
  for (const id of ['unknown', null, ['media-review']]) assert.throws(() => core.selectQuest(initial(), id));
});

test('each quest preserves its own notes when switching and source states remain unchanged', () => {
  const original = initial(); let state = core.setNote(original, 'media-review', 'Review captions first.');
  state = core.selectQuest(state, 'hostinger-connection'); state = core.setNote(state, 'hostinger-connection', 'Check the documented access route.');
  state = core.selectQuest(state, 'media-review');
  assert.equal(state.objective_notes['media-review'], 'Review captions first.');
  assert.equal(state.objective_notes['hostinger-connection'], 'Check the documented access route.');
  assert.equal(original.objective_notes['media-review'], '');
  assert.ok(episode.quests.every(quest => quest.status === 'planned'));
});

test('exploration toggles are reversible, duplicate-free and never mutate the episode', () => {
  const snapshot = JSON.stringify(episode); let state = initial();
  for (const id of core.QUEST_IDS) { state = core.selectQuest(state, id); state = core.toggleExplored(state, id); }
  assert.equal(state.explored_quests.length, 3);
  state = core.toggleExplored(state, 'media-review');
  assert.equal(state.explored_quests.includes('media-review'), false);
  assert.equal(state.visited_worlds.length, 3);
  assert.equal(JSON.stringify(episode), snapshot);
  assert.throws(() => core.toggleExplored(initial(), 'hostinger-connection'), /Open/);
  assert.throws(() => core.toggleExplored(initial(), 'unknown'));
});

test('progress exports exactly eleven keys including source classification and no completion field', () => {
  const output = JSON.parse(core.serializeProgress(episode, initial()));
  assert.deepEqual(Object.keys(output).sort(), ['audience', 'episode_id', 'explored_quests', 'kind', 'objective_notes', 'schema_version', 'scope', 'selected_quest', 'selected_world', 'source_visibility', 'visited_worlds']);
  assert.equal(output.audience, 'public'); assert.equal(output.source_visibility, 'public_candidate');
  for (const key of ['completed', 'revenue', 'approved', 'connected']) assert.throws(() => core.validateProgress(episode, { ...initial(), [key]: true }));
});

test('progress cannot change its episode, audience, source visibility or exploration scope', () => {
  for (const [key, value] of [['schema_version', true], ['kind', 'jarvis.approval'], ['scope', 'business_completion'], ['episode_id', 'another-episode'], ['audience', 'owner'], ['source_visibility', 'private'], ['selected_world', 'forge'], ['selected_quest', 'unknown']]) assert.throws(() => core.validateProgress(episode, { ...initial(), [key]: value }));
  const owner = ownerEpisode('private'); const state = core.initialProgress(owner);
  assert.throws(() => core.validateProgress(owner, { ...state, audience: 'public', source_visibility: 'public_candidate' }));
});

test('visited and explored lists reject duplicates, unknown IDs and unvisited-world claims', () => {
  for (const list of [[], ['archive', 'archive'], ['unknown'], 'archive', null]) assert.throws(() => core.validateProgress(episode, { ...initial(), visited_worlds: list }));
  for (const list of [['hostinger-connection'], ['media-review', 'media-review'], ['completed'], null]) assert.throws(() => core.validateProgress(episode, { ...initial(), explored_quests: list }));
  const state = initial(); state.objective_notes.extra = ''; assert.throws(() => core.validateProgress(episode, state));
});

test('quest notes accept blank text, preserve Unicode and enforce exactly one thousand UTF-8 bytes', () => {
  for (const value of ['', ' \t\n', 'é'.repeat(500), '😀'.repeat(250), 'A <script>literal note</script>.']) {
    const state = core.setNote(initial(), 'media-review', value);
    assert.equal(core.validateProgress(episode, state).objective_notes['media-review'], value);
  }
  for (const value of ['x'.repeat(1001), '😀'.repeat(251), '\ud800', 'a\u0000b']) {
    const state = core.setNote(initial(), 'media-review', value);
    assert.equal(state.objective_notes['media-review'], value, 'Unfinished text must stay available for editing.');
    assert.throws(() => core.serializeProgress(episode, state), /media-review/);
  }
  for (const value of [null, true, 12]) assert.throws(() => core.setNote(initial(), 'media-review', value));
});

test('quest briefs carry planned status, episode references and the note without creating claims', () => {
  const state = core.setNote(initial(), 'media-review', 'Review the <example> caption.');
  const brief = core.questBrief(episode, state);
  assert.match(brief, /Project status and evidence state: PLANNED/);
  assert.match(brief, /Explored during this visit: no/);
  assert.match(brief, /do not establish quest completion/);
  for (const source of episode.sources) assert.ok(brief.includes(source.url));
  assert.ok(brief.includes('Review the <example> caption.'));
  assert.match(core.progressBrief(episode, state), /no business-completion or publication approval/);
});

test('MP4 selection checks local metadata bounds and rejects format, size and newline tricks', () => {
  for (const file of [{ name: 'pilot.mp4', type: 'video/mp4', size: 1 }, { name: 'PILOT.MP4', type: '', size: core.MAX_VIDEO_BYTES }]) assert.equal(core.videoFile(file), true);
  for (const file of [{ name: 'pilot.mp4\n', type: 'video/mp4', size: 10 }, { name: 'pilot.webm', type: 'video/webm', size: 10 }, { name: 'pilot.mp4', type: 'text/html', size: 10 }, ...[0, -1, true, NaN, 1.5, core.MAX_VIDEO_BYTES + 1].map(size => ({ name: 'pilot.mp4', type: 'video/mp4', size }))]) assert.throws(() => core.videoFile(file));
});

test('local captions are bounded UTF-8 VTT with a header and at least one timed cue', () => {
  const vtt = 'WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nA labelled scene.\n';
  assert.equal(core.captionText(vtt), vtt);
  assert.equal(core.captionText('\ufeff' + vtt), vtt);
  const bounded = vtt + ' '.repeat(core.MAX_VTT_BYTES - core.bytes(vtt));
  assert.equal(core.bytes(core.captionText(bounded)), core.MAX_VTT_BYTES);
  for (const text of ['WEBVTT', 'not captions', 'WEBVTT\n\n00:99:01.000 --> 00:00:02.000\nbad', vtt + '\u0000', vtt + '\ud800', bounded + ' ']) assert.throws(() => core.captionText(text));
});

test('packaging hooks accept only explicit bitmap, MP4 and VTT base64 data-URI shapes', () => {
  assert.equal(core.inlineAsset('data:image/png;base64,AAAA', 'art'), true);
  assert.equal(core.inlineAsset('data:video/mp4;base64,AAAA', 'video'), true);
  assert.equal(core.inlineAsset('data:text/vtt;base64,AAAA', 'captions'), true);
  for (const value of ['', 'https://example.org/a.mp4', 'javascript:alert(1)', 'blob:unknown', 'data:image/svg+xml;base64,AAAA', 'data:video/mp4;base64,AAAA\n']) assert.equal(core.inlineAsset(value, 'video'), false);
  assert.equal(core.inlineAsset('data:image/png;base64,AAAA', 'unknown'), false);
});

test('the actual DOM source has native video controls, no autoplay and keyboard-labelled notes', () => {
  const video = html.match(/<video\b[^>]*>/)[0];
  assert.match(video, /\bcontrols\b/); assert.match(video, /\bplaysinline\b/); assert.match(video, /preload="metadata"/); assert.doesNotMatch(video, /autoplay/);
  assert.match(html, /<textarea[^>]*id="objective-note"[^>]*lang="en"[^>]*spellcheck="true"/);
  assert.match(html, /id="quest-detail" tabindex="-1"/);
  assert.match(html, /<dialog id="evidence-dialog" aria-labelledby="evidence-heading"/);
  for (const tag of html.matchAll(/<button\b[^>]*>/g)) assert.match(tag[0], /type="button"/);
  assert.match(html, /prefers-reduced-motion:reduce/);
});

test('source hooks are unique and the shipped interface imports only MP4/VTT media', () => {
  for (const name of ['art', 'video', 'captions']) assert.equal([...html.matchAll(new RegExp(`data-jarvis-inline-${name}=""`, 'g'))].length, 1);
  const files = [...html.matchAll(/<input\b[^>]*type="file"[^>]*>/g)];
  assert.equal(files.length, 2);
  assert.ok(files.some(match => match[0].includes('video/mp4')));
  assert.ok(files.some(match => match[0].includes('text/vtt')));
  assert.doesNotMatch(files.map(match => match[0]).join(''), /application\/json/);
  assert.match(appSource, /edition-label"\)\.textContent=core\.editionLabel\(episode\)/);
  assert.match(appSource, /episode\.audience==="owner"/);
});

test('untrusted episode and note values use text sinks, with no network or persistence API', () => {
  assert.doesNotMatch(coreSource + appSource, /\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon|eval|Function)\s*\(|\b(?:localStorage|sessionStorage|indexedDB)\b|document\.cookie|\.innerHTML\b|\.outerHTML\b|insertAdjacentHTML/);
  assert.doesNotMatch(html, /<(?:script|img|iframe|link)\b[^>]*(?:src|href)\s*=/i);
  assert.match(html, /connect-src 'none'/);
  assert.match(html, /media-src data: blob:/);
  assert.match(appSource, /node\.textContent=text/);
  assert.match(appSource, /core\.validateEpisode\(JSON\.parse\(\$\("episode-data"\)\.textContent\)\)/);
});

test('the actual media path is user initiated, clears stale captions and revokes local URLs', () => {
  assert.doesNotMatch(appSource, /video\.play\(/);
  assert.match(appSource, /core\.videoFile\(file\)/);
  assert.match(appSource, /video\.pause\(\);clearCaptions\(\)/);
  assert.match(appSource, /if\(ticket!==captionTicket\)return/);
  assert.match(appSource, /new TextDecoder\("utf-8",\{fatal:true,ignoreBOM:true\}\)/);
  assert.match(appSource, /URL\.revokeObjectURL\(videoURL\)/);
  assert.match(appSource, /window\.addEventListener\("pagehide"/);
});
