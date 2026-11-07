import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { Script, createContext } from 'node:vm';

const html = readFileSync(new URL('../web/jarvis-workbench.html', import.meta.url), 'utf8');
const embedded = html.match(/<script id="portfolio-catalog" type="application\/json">([\s\S]*?)<\/script>/);
assert.ok(embedded, 'The shipped page must contain its catalog.');
const catalog = JSON.parse(embedded[1]);
const trackedCatalog = JSON.parse(readFileSync(new URL('../examples/portfolio/catalog.json', import.meta.url), 'utf8'));
const scripts = [...html.matchAll(/<script id="(jarvis-workbench-(?:core|app))">([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length, 2);
const pureSource = scripts.find(match => match[1] === 'jarvis-workbench-core')[2];
const appSource = scripts.find(match => match[1] === 'jarvis-workbench-app')[2];
// Only authored pure helpers are evaluated. No catalog text or generated code runs.
const context = createContext({ TextEncoder });
new Script(pureSource, { filename: 'jarvis-workbench-core.js' }).runInContext(context, { timeout: 1000 });
const core = context.JarvisWorkbench;
const plain = value => JSON.parse(JSON.stringify(value));
const cloneCatalog = () => structuredClone(catalog);
const ids = items => Array.from(items, item => item.id);
const request = (objective = 'Draft one reviewable improvement.', minutes = 30) => core.buildMissionRequest('jarvis-tools', 'chatgpt', objective, minutes);
const canonical = value => {
  if (Array.isArray(value)) return value.map(canonical);
  if (value !== null && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
  return value;
};

test('both shipped authored scripts compile', () => {
  assert.doesNotThrow(() => new Script(pureSource));
  assert.doesNotThrow(() => new Script(appSource));
});

test('the complete embedded catalog matches the tracked catalog without drift', () => {
  assert.deepEqual(catalog, trackedCatalog);
  assert.equal(catalog.initiatives.length, 12);
  assert.deepEqual(ids(catalog.initiatives).sort(), Array.from(core.INITIATIVE_IDS).sort());
  assert.equal(new Set(catalog.initiatives.map(item => item.project_id)).size, 7);
  assert.equal(core.validateCatalog(catalog), catalog);
});

test('the catalog content digest verifies without implying author authentication', () => {
  const { catalog_sha256, ...record } = catalog;
  assert.equal(createHash('sha256').update(JSON.stringify(canonical(record))).digest('hex'), catalog_sha256);
  assert.equal(catalog.live_metrics, null);
  assert.equal(catalog.external_actions, 0);
});

test('a catalog with live metrics, wrong schema or external actions is rejected', () => {
  for (const [key, value] of [['schema_version', true], ['kind', 'live.dashboard'], ['live_metrics', {}], ['external_actions', 1], ['external_actions', false]]) {
    const changed = cloneCatalog(); changed[key] = value;
    assert.throws(() => core.validateCatalog(changed));
  }
  assert.throws(() => core.validateCatalog(null));
});

test('missing, duplicate and unknown initiative or project IDs are rejected', () => {
  const missing = cloneCatalog(); missing.initiatives.pop();
  assert.throws(() => core.validateCatalog(missing));
  const duplicate = cloneCatalog(); duplicate.initiatives[1].id = duplicate.initiatives[0].id;
  assert.throws(() => core.validateCatalog(duplicate));
  const unknown = cloneCatalog(); unknown.initiatives[0].id = 'unknown';
  assert.throws(() => core.validateCatalog(unknown));
  const project = cloneCatalog(); project.initiatives[0].project_id = 'unlisted';
  assert.throws(() => core.validateCatalog(project));
});

test('catalog plans, gaps and destination assignments must be explicit', () => {
  for (const key of ['plan_steps', 'evidence_gaps', 'boundaries', 'formats']) {
    const changed = cloneCatalog(); changed.initiatives[0][key] = [];
    assert.throws(() => core.validateCatalog(changed));
  }
  const unknownJourney = cloneCatalog(); unknownJourney.initiatives[0].journey_kind = 'automatic_sale';
  assert.throws(() => core.validateCatalog(unknownJourney));
  const inheritedSite = cloneCatalog(); inheritedSite.initiatives.find(item => item.id === 'affiliate-builder').destination.urls = ['https://aievolutionaryevolutions.com'];
  assert.throws(() => core.validateCatalog(inheritedSite), /cannot inherit a website/);
});

test('the education site and unassigned affiliate platform remain separate', () => {
  const education = catalog.initiatives.find(item => item.id === 'website-learning');
  const affiliate = catalog.initiatives.find(item => item.id === 'affiliate-builder');
  assert.equal(education.project_id, 'ai-evolutionary-evolutions');
  assert.equal(education.destination.state, 'owner_reference_unverified');
  assert.deepEqual(education.destination.urls, ['https://aievolutionaryevolutions.com']);
  assert.equal(affiliate.project_id, 'funding-affiliates');
  assert.equal(affiliate.destination.state, 'unassigned');
  assert.deepEqual(affiliate.destination.urls, []);
});

test('financing customers and referral partners retain different journeys and references', () => {
  const customer = catalog.initiatives.find(item => item.id === 'funding-customers');
  const partner = catalog.initiatives.find(item => item.id === 'referral-partners');
  assert.equal(customer.journey_kind, 'funding_customer');
  assert.equal(partner.journey_kind, 'funding_partner');
  assert.equal(customer.destination.urls.some(url => partner.destination.urls.includes(url)), false);
});

test('search is case-insensitive and includes useful catalog details', () => {
  assert.deepEqual(ids(core.filterInitiatives(catalog.initiatives, { query: 'CRYPTOCLOCKWORKS' })), ['wearables-research']);
  assert.deepEqual(ids(core.filterInitiatives(catalog.initiatives, { query: '  caption rights  ' })), ['interactive-video']);
  assert.deepEqual(ids(core.filterInitiatives(catalog.initiatives, { query: 'resume bookmark' })), ['personal-workflow']);
});

test('project filtering returns the assigned initiatives without moving them', () => {
  const snapshot = JSON.stringify(catalog);
  assert.deepEqual(ids(core.filterInitiatives(catalog.initiatives, { projectId: 'funding-affiliates' })), ['affiliate-builder', 'funding-customers', 'referral-partners']);
  assert.equal(JSON.stringify(catalog), snapshot);
});

test('journey filters keep education, financing and partner work distinct', () => {
  assert.deepEqual(ids(core.filterInitiatives(catalog.initiatives, { journey: 'member' })), ['website-learning']);
  assert.deepEqual(ids(core.filterInitiatives(catalog.initiatives, { journey: 'funding_customer' })), ['funding-customers']);
  assert.deepEqual(ids(core.filterInitiatives(catalog.initiatives, { journey: 'funding_partner' })), ['referral-partners']);
});

test('combined filters and unmatched terms return no invented fallback initiative', () => {
  assert.deepEqual(ids(core.filterInitiatives(catalog.initiatives, { projectId: 'ai-jarvis', journey: 'member' })), []);
  assert.deepEqual(ids(core.filterInitiatives(catalog.initiatives, { projectId: 'unknown' })), []);
  assert.deepEqual(ids(core.filterInitiatives(catalog.initiatives, { query: 'not-a-real-portfolio-term' })), []);
  assert.deepEqual(ids(core.filterInitiatives(catalog.initiatives)), ids(catalog.initiatives));
});

test('invalid or oversized filter input is rejected', () => {
  assert.throws(() => core.filterInitiatives(catalog.initiatives, { query: 'x'.repeat(161) }), /160/);
  for (const options of [{ query: null }, { projectId: 1 }, { journey: [] }]) assert.throws(() => core.filterInitiatives(catalog.initiatives, options), /Invalid catalog filter/);
});

test('mission export has exactly the six request keys and preserves the objective', () => {
  const objective = '  A useful outcome.\nKeep this whitespace. 😀\n';
  assert.deepEqual(plain(request(objective)), { schema_version: 1, kind: 'jarvis.mission_request', initiative_id: 'jarvis-tools', target: 'chatgpt', objective, timebox_minutes: 30 });
  assert.deepEqual(Object.keys(request()).sort(), ['initiative_id', 'kind', 'objective', 'schema_version', 'target', 'timebox_minutes']);
});

test('all 12 initiative IDs and all 12 draft targets are accepted', () => {
  assert.equal(core.INITIATIVE_IDS.length, 12);
  assert.equal(core.TARGETS.length, 12);
  for (const id of core.INITIATIVE_IDS) assert.equal(core.buildMissionRequest(id, 'chatgpt', 'Objective', 15).initiative_id, id);
  for (const [target] of core.TARGETS) assert.equal(core.buildMissionRequest('jarvis-tools', target, 'Objective', 90).target, target);
  assert.equal(core.TARGETS.find(([id]) => id === 'openai')[1], 'OpenAI API draft');
});

test('unknown and incorrectly typed initiative and target IDs are rejected', () => {
  for (const invalid of ['', 'unknown', 'JARVIS-TOOLS', null, undefined, {}, ['jarvis-tools']]) assert.throws(() => core.buildMissionRequest(invalid, 'chatgpt', 'Objective', 30), /listed initiative/);
  for (const invalid of ['', 'unknown', 'ChatGPT', null, undefined, {}, ['chatgpt']]) assert.throws(() => core.buildMissionRequest('jarvis-tools', invalid, 'Objective', 30), /listed draft destination/);
});

test('timeboxes accept only the four integer choices', () => {
  for (const minutes of [15, 30, 60, 90]) assert.equal(request('Objective', minutes).timebox_minutes, minutes);
  for (const invalid of [true, false, '30', 0, 1, 15.5, 45, 120, NaN, Infinity, -Infinity, null]) assert.throws(() => request('Objective', invalid), /timebox/);
  assert.throws(() => core.buildMissionRequest('jarvis-tools', 'chatgpt', 'Objective', undefined), /timebox/);
});

test('the ASCII objective limit is exactly 2,000 UTF-8 bytes', () => {
  assert.equal(request('x'.repeat(2000)).objective.length, 2000);
  assert.throws(() => request('x'.repeat(2001)), /2,000/);
});

test('UTF-8 byte limits account for multibyte characters and emoji', () => {
  assert.equal(request('€'.repeat(666) + 'ab').objective.length, 668);
  assert.throws(() => request('€'.repeat(667)), /2,000/);
  assert.equal(request('😀'.repeat(500)).objective.length, 1000);
  assert.throws(() => request('😀'.repeat(501)), /2,000/);
});

test('blank objectives include Unicode whitespace and U+0085', () => {
  for (const text of ['', ' ', '\t\n\r', '\u00a0\u2003', '\u0085', ' \u0085\n', '\ufeff']) assert.throws(() => request(text), /Add an objective/);
});

test('C0 controls are rejected except tab, LF and CR', () => {
  for (let unit = 0; unit < 32; unit += 1) {
    const objective = `a${String.fromCharCode(unit)}b`;
    if ([9, 10, 13].includes(unit)) assert.equal(request(objective).objective, objective);
    else assert.throws(() => request(objective), /control characters/);
  }
});

test('invalid surrogate text cannot be silently normalized during export', () => {
  for (const objective of ['\ud800', '\udc00', 'a\ud800b', '\udc00\ud800', '😀\ud800']) assert.throws(() => request(objective), /invalid Unicode/);
  assert.equal(request('\ud83d\ude00').objective, '😀');
});

test('non-string objectives are rejected', () => {
  for (const objective of [null, 5, true, {}, ['Objective']]) assert.throws(() => request(objective), /must be text/);
  assert.throws(() => core.buildMissionRequest('jarvis-tools', 'chatgpt', undefined, 30), /must be text/);
});

test('character and byte counts remain distinct', () => {
  assert.deepEqual(plain(core.countObjective('Hi 😀')), { characters: 4, bytes: 7 });
  assert.deepEqual(plain(core.countObjective('')), { characters: 0, bytes: 0 });
});

test('request validation rejects extra authority fields, missing fields and wrong schema', () => {
  for (const addition of [{ approved: true }, { sha256: 'a'.repeat(64) }, { integration_finished: true }]) assert.throws(() => core.validateRequest({ ...request(), ...addition }), /unexpected fields/);
  const missing = plain(request()); delete missing.target;
  assert.throws(() => core.validateRequest(missing), /unexpected fields/);
  for (const wrong of [{ schema_version: true }, { schema_version: '1' }, { kind: 'jarvis.approved_mission' }]) assert.throws(() => core.validateRequest({ ...request(), ...wrong }), /schema/);
  assert.throws(() => core.validateRequest({ ...request(), timebox_minutes: '30' }), /timebox/);
});

test('the plain-text brief includes the chosen request, plan, gaps and boundaries', () => {
  const item = catalog.initiatives.find(item => item.id === 'jarvis-tools');
  const brief = core.buildBrief(item, request('Improve <tags> without executing them.'));
  for (const text of ['DRAFT PLANNING BRIEF', item.title, item.project_label, item.outcome, ...item.plan_steps, ...item.evidence_gaps, ...item.boundaries, 'Improve <tags> without executing them.', '30 minutes']) assert.ok(brief.includes(text), text);
  assert.match(brief, /does not start a mission/);
});

test('a brief cannot substitute another initiative or accept an invalid request', () => {
  assert.throws(() => core.buildBrief(catalog.initiatives.find(item => item.id === 'website-learning'), request()), /does not match/);
  assert.throws(() => core.buildBrief(catalog.initiatives[0], { ...request(), objective: 'x'.repeat(2001) }), /2,000/);
});

test('the affiliate brief does not inherit education or financing URLs', () => {
  const item = catalog.initiatives.find(item => item.id === 'affiliate-builder');
  const brief = core.buildBrief(item, core.buildMissionRequest(item.id, 'hostinger', 'Define one offer before assigning its own destination.', 60));
  assert.match(brief, /Catalog state: unassigned/);
  assert.doesNotMatch(brief, /https?:\/\//);
  assert.doesNotMatch(brief, /aievolutionaryevolutions\.com/);
});

test('per-initiative memory starts with explicit empty drafts and returns copies', () => {
  const memory = core.createDraftMemory();
  assert.deepEqual(plain(memory.read('jarvis-tools')), { objective: '', target: 'chatgpt', timebox_minutes: 30 });
  const draft = memory.read('jarvis-tools'); draft.objective = 'Accidental mutation';
  assert.equal(memory.read('jarvis-tools').objective, '');
});

test('switching initiatives retains separate in-memory objectives and choices', () => {
  const memory = core.createDraftMemory();
  memory.write('jarvis-tools', { objective: 'First objective', target: 'github', timebox_minutes: 15 });
  memory.write('website-learning', { objective: 'Second objective', target: 'hostinger', timebox_minutes: 60 });
  assert.deepEqual(plain(memory.read('jarvis-tools')), { objective: 'First objective', target: 'github', timebox_minutes: 15 });
  assert.equal(memory.read('website-learning').objective, 'Second objective');
});

test('in-progress text is preserved for editing but still must pass export validation', () => {
  const memory = core.createDraftMemory();
  const objective = 'x'.repeat(2001);
  memory.write('jarvis-tools', { objective, target: 'chatgpt', timebox_minutes: 30 });
  assert.equal(memory.read('jarvis-tools').objective, objective);
  assert.throws(() => request(memory.read('jarvis-tools').objective), /2,000/);
  assert.throws(() => memory.write('unknown', { objective: '', target: 'chatgpt', timebox_minutes: 30 }), /listed initiative/);
  assert.throws(() => memory.write('jarvis-tools', { objective: '', target: 'chatgpt', timebox_minutes: '30' }), /Invalid in-memory draft/);
});

test('the workbench has no network, persistence, external assets or HTML insertion sinks', () => {
  assert.match(html, /connect-src 'none'/);
  assert.match(html, /form-action 'none'/);
  assert.doesNotMatch(html, /<(?:script|img|iframe|link)\b[^>]*(?:src|href)\s*=/i);
  assert.doesNotMatch(pureSource + appSource, /\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|localStorage|sessionStorage|indexedDB|sendBeacon)\b/);
  assert.doesNotMatch(pureSource + appSource, /\b(?:eval|Function)\s*\(/);
  assert.doesNotMatch(appSource, /\.(?:innerHTML|outerHTML)\s*=|insertAdjacentHTML|document\.write/);
});

test('the objective has native English spelling and the separate composer link is local', () => {
  const objective = html.match(/<textarea\b[^>]*id="objective"[^>]*>/)[0];
  assert.match(objective, /spellcheck="true"/);
  assert.match(objective, /lang="en"/);
  assert.match(html, /<label[^>]*for="objective"/);
  assert.match(html, /href="jarvis-composer\.html" target="_blank" rel="noopener"/);
});

test('shared JavaScript-to-Python fixtures match actual exports and rejection rules', () => {
  const fixtures = JSON.parse(readFileSync(new URL('../docs/evidence/workbench-request-fixtures.json', import.meta.url), 'utf8'));
  for (const draft of fixtures.valid_requests) {
    assert.deepEqual(plain(core.buildMissionRequest(draft.initiative_id, draft.target, draft.objective, draft.timebox_minutes)), draft);
    assert.deepEqual(plain(core.validateRequest(draft)), draft);
  }
  for (const draft of fixtures.rejected_requests) assert.throws(() => core.validateRequest(draft));
});
