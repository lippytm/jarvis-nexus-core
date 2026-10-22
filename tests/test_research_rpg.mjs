import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { Script, createContext } from 'node:vm';

const html = readFileSync(new URL('../web/jarvis-research-rpg.html', import.meta.url), 'utf8');
const payloads = [...html.matchAll(/<script type="application\/json" id="portfolio-data">([\s\S]*?)<\/script>/g)];
assert.equal(payloads.length, 1);
const catalog = JSON.parse(payloads[0][1]);
const tracked = JSON.parse(readFileSync(new URL('../examples/portfolio/catalog.json', import.meta.url), 'utf8'));
const scripts = [...html.matchAll(/<script id="jarvis-research-(core|app)">([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length, 2);
const coreSource = scripts.find(item => item[1] === 'core')[2];
const appSource = scripts.find(item => item[1] === 'app')[2];
const context = createContext({ TextEncoder, URL });
new Script(coreSource, { filename: 'jarvis-research-core.js' }).runInContext(context, { timeout: 1000 });
const core = context.JarvisResearchQuestbook.createEngine(catalog);
const plain = value => JSON.parse(JSON.stringify(value));
const fresh = () => plain(core.newBook());
const withNote = (changes = {}) => ({ ...fresh(), evidence_notes: [{ note_id: 'note-1', label: 'open_question', text: '', url: '', ...changes }] });
const canonical = value => Array.isArray(value) ? value.map(canonical) : value !== null && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])])) : value;

test('the actual shipped pure helper and DOM app both syntax-compile', () => {
  assert.doesNotThrow(() => new Script(coreSource));
  assert.doesNotThrow(() => new Script(appSource));
  assert.equal(typeof core.validate, 'function');
});

test('embedded catalog exactly matches the tracked twelve-initiative portfolio and digest', () => {
  assert.deepEqual(catalog, tracked);
  const { catalog_sha256, ...content } = catalog;
  assert.equal(createHash('sha256').update(JSON.stringify(canonical(content))).digest('hex'), catalog_sha256);
  assert.equal(catalog.initiatives.length, 12);
  assert.equal(new Set(catalog.initiatives.map(item => item.project_id)).size, 7);
  const education = catalog.initiatives.find(item => item.id === 'website-learning');
  const affiliates = catalog.initiatives.find(item => item.id === 'affiliate-builder');
  assert.deepEqual(education.destination.urls, ['https://aievolutionaryevolutions.com']);
  assert.deepEqual(affiliates.destination.urls, []);
  assert.equal(affiliates.destination.state, 'unassigned');
  assert.notEqual(catalog.initiatives.find(item => item.id === 'funding-customers').journey_kind, catalog.initiatives.find(item => item.id === 'referral-partners').journey_kind);
});

test('all twelve actual initiative exports roundtrip under each of the three campaigns', () => {
  for (const initiative of catalog.initiatives) for (const campaign of core.campaigns) {
    const book = core.newBook(initiative.id, campaign.id);
    book.objective = 'Research a bounded next step for ' + initiative.title + '.';
    assert.deepEqual(plain(core.parse(core.serialize(book))), plain(book));
  }
});

test('each campaign has inquiry/evidence/review goals without a predefined factual conclusion', () => {
  assert.deepEqual(plain(core.campaigns.map(item => item.id)), ['general-creative-build', 'smart-glasses-procurement', 'documentary-claims-research']);
  for (const campaign of core.campaigns) {
    assert.deepEqual(plain(campaign.quests.map(quest => quest.id)), ['inquiry', 'evidence', 'review']);
    for (const quest of campaign.quests) assert.ok(quest.prompt && quest.output);
  }
  const documentary = JSON.stringify(core.campaigns[2]);
  assert.match(documentary, /attributed claims/);
  assert.match(documentary, /contrary evidence/);
  assert.match(documentary, /unsubstantiated/);
  assert.match(documentary, /alternative explanations/);
  assert.match(JSON.stringify(core.campaigns[1]), /buy nothing/);
});

test('new books use the exact twelve-key owner/private visit-only draft contract', () => {
  const book = fresh();
  assert.deepEqual(Object.keys(book), plain(core.bookKeys));
  assert.equal(book.audience, 'owner');
  assert.equal(book.source_visibility, 'private');
  assert.equal(book.scope, 'visit_only_exploration');
  assert.deepEqual(book.visited_quests, ['inquiry']);
  assert.deepEqual(book.explored_quests, []);
  assert.deepEqual(book.evidence_notes, []);
  assert.deepEqual(plain(core.validate(book)), book);
});

test('changing initiative or campaign preserves drafts and classification while resetting exploration', () => {
  let book = withNote({ text: 'Keep this unresolved question.', label: 'attributed_claim' });
  book.objective = 'My unfinished objective';
  book.source_visibility = 'internal';
  book = core.toggleExplored(core.selectQuest(book, 'review'));
  const before = plain(book);
  const next = core.setContext(book, 'wearables-research', 'smart-glasses-procurement');
  assert.equal(next.objective, before.objective);
  assert.deepEqual(plain(next.evidence_notes), before.evidence_notes);
  assert.equal(next.source_visibility, 'internal');
  assert.deepEqual(plain(next.visited_quests), ['inquiry']);
  assert.deepEqual(plain(next.explored_quests), []);
  assert.deepEqual(plain(book), before);
  assert.deepEqual(plain(core.setContext(book, book.initiative_id, book.campaign_id)), before);
});

test('quest selection is immutable, duplicate-free and limited to known prompt IDs', () => {
  const start = fresh();
  let next = core.selectQuest(start, 'evidence');
  next = core.selectQuest(next, 'evidence');
  assert.equal(next.selected_quest, 'evidence');
  assert.deepEqual(plain(next.visited_quests), ['inquiry', 'evidence']);
  assert.deepEqual(start.visited_quests, ['inquiry']);
  for (const id of ['complete', '', null, 1, {}, ['inquiry']]) assert.throws(() => core.selectQuest(next, id), /listed research quest/);
});

test('exploration toggles never create approval, verification or project-completion fields', () => {
  const campaignsBefore = JSON.stringify(core.campaigns);
  let book = fresh();
  for (const id of core.questIDs) book = core.toggleExplored(core.selectQuest(book, id));
  assert.equal(book.explored_quests.length, 3);
  const next = core.toggleExplored(book);
  assert.equal(next.explored_quests.length, 2);
  assert.equal(book.explored_quests.length, 3);
  assert.deepEqual(Object.keys(book), plain(core.bookKeys));
  assert.equal(JSON.stringify(core.campaigns), campaignsBefore);
  for (const key of ['approved', 'verified', 'completed', 'revenue', 'publication_approval']) assert.ok(!Object.hasOwn(book, key));
});

test('editing a note after context and quest transitions updates the current draft by stable ID', () => {
  let book = core.addNote(fresh());
  book = core.updateNote(book, 'note-1', 'text', 'Before navigation');
  const prior = plain(book);
  book = core.selectQuest(book, 'review');
  book = core.toggleExplored(book);
  book = core.setContext(book, 'publishing-library', 'documentary-claims-research');
  book = core.updateNote(book, 'note-1', 'text', 'After navigation');
  book = core.updateNote(book, 'note-1', 'label', 'attributed_claim');
  assert.equal(book.evidence_notes[0].text, 'After navigation');
  assert.equal(book.evidence_notes[0].label, 'attributed_claim');
  assert.equal(prior.evidence_notes[0].text, 'Before navigation');
  assert.match(appSource, /book=engine\.updateNote\(book,note\.note_id,key,input\.value\)/);
  assert.doesNotMatch(appSource, /note\[key\]\s*=\s*input\.value/);
});

test('note add/remove obeys the eight-row bound and preserves independent rows', () => {
  let book = fresh();
  for (let i = 0; i < 8; i += 1) book = core.addNote(book);
  assert.equal(new Set(book.evidence_notes.map(item => item.note_id)).size, 8);
  assert.throws(() => core.addNote(book), /eight notes/);
  const smaller = core.removeNote(book, 'note-3');
  assert.equal(smaller.evidence_notes.length, 7);
  assert.equal(book.evidence_notes.length, 8);
  assert.equal(core.addNote(smaller).evidence_notes.at(-1).note_id, 'note-3');
  assert.throws(() => core.removeNote(book, 'not-found'), /unavailable/);
  assert.throws(() => core.updateNote(book, 'note-1', 'note_id', 'renamed'), /supported note field/);
});

test('unknown fields, schemas, kinds and selector values are rejected', () => {
  const book = fresh();
  for (const [key, value] of [['schema_version', true], ['schema_version', '1'], ['schema_version', 2], ['kind', 'jarvis.rpg_progress'], ['scope', 'business_completed'], ['initiative_id', 'unknown'], ['initiative_id', ['jarvis-tools']], ['campaign_id', '__proto__'], ['selected_quest', 'unknown']]) assert.throws(() => core.validate({ ...book, [key]: value }));
  assert.throws(() => core.validate({ ...book, connected: true }), /fields/);
  const missing = fresh(); delete missing.objective;
  assert.throws(() => core.validate(missing), /fields/);
  for (const value of [null, [], 'book', 1]) assert.throws(() => core.validate(value));
});

test('public export needs explicit public-candidate visibility; owner classifications are retained', () => {
  for (const source_visibility of ['private', 'internal', 'public_candidate']) {
    const owner = { ...fresh(), source_visibility };
    assert.equal(core.parse(core.serialize(owner)).source_visibility, source_visibility);
    if (source_visibility !== 'public_candidate') assert.throws(() => core.serialize({ ...owner, audience: 'public' }), /Public audience requires/);
  }
  const publicBook = { ...fresh(), audience: 'public', source_visibility: 'public_candidate' };
  assert.equal(core.parse(core.serialize(publicBook)).audience, 'public');
  for (const value of ['', 'everyone', null, [], true]) assert.throws(() => core.validate({ ...fresh(), audience: value }));
});

test('valid resume imports preserve all classification and note fields without declassification', () => {
  const current = fresh();
  for (const source_visibility of ['private', 'internal', 'public_candidate']) {
    const imported = withNote({ text: 'A quoted claim is not established evidence.', label: 'attributed_claim' });
    imported.source_visibility = source_visibility;
    imported.objective = 'Resume this inquiry.';
    const result = core.tryImport(current, core.serialize(imported));
    assert.equal(result.ok, true);
    assert.deepEqual(plain(result.book), imported);
    assert.equal(result.book.audience, 'owner');
    assert.notEqual(result.book, imported);
    assert.deepEqual(current, fresh());
  }
});

test('vetted-source is a human label requiring a check note and HTTPS reference', () => {
  assert.throws(() => core.validate(withNote({ label: 'vetted_source', text: '', url: 'https://example.org/source' })), /Add note 1 text/);
  assert.throws(() => core.validate(withNote({ label: 'vetted_source', text: 'Checked the original date and wording.', url: '' })), /HTTPS reference/);
  const book = withNote({ label: 'vetted_source', text: 'Checked the original date and wording; authenticity remains uncertain.', url: 'https://example.org/source' });
  assert.equal(core.validate(book).evidence_notes[0].label, 'vetted_source');
  assert.match(core.brief(book), /your assessment/);
  assert.match(core.brief(book), /not app verification/);
});

test('note labels, IDs, exact shapes and duplicate IDs remain bounded', () => {
  for (const label of Object.keys(core.labels)) {
    const book = withNote({ label, text: 'Record authored by the user.', url: label === 'vetted_source' ? 'https://example.org/source' : '' });
    assert.equal(core.validate(book).evidence_notes[0].label, label);
  }
  for (const label of ['verified_by_ai', '', null, 1]) assert.throws(() => core.validate(withNote({ label })));
  for (const note_id of ['x', 'A-note', 'note-1\n', 'a'.repeat(49), null]) assert.throws(() => core.validate(withNote({ note_id })));
  const duplicate = withNote(); duplicate.evidence_notes.push({ ...duplicate.evidence_notes[0] });
  assert.throws(() => core.validate(duplicate), /unique IDs/);
  const extra = withNote(); extra.evidence_notes[0].verified = true;
  assert.throws(() => core.validate(extra), /unsupported fields/);
});

test('references allow bounded HTTPS without credentials, whitespace, backslashes or custom ports', () => {
  for (const url of ['', 'https://example.org/a?q=one#part', 'HTTPS://example.org:443/source']) assert.equal(core.validate(withNote({ url })).evidence_notes[0].url, url);
  for (const url of ['http://example.org', 'javascript:alert(1)', 'https://user:secret@example.org', 'https://@example.org', 'https://example.org:8443', 'https://example.org/a b', 'https://example.org/\u0085', 'https://example.org\\source', 'https://example.org/\n', 'https:///']) assert.throws(() => core.validate(withNote({ url })), undefined, url);
  const prefix = 'https://example.org/';
  const exact = prefix + 'a'.repeat(1000 - prefix.length);
  assert.equal(core.validate(withNote({ url: exact })).evidence_notes[0].url, exact);
  assert.throws(() => core.validate(withNote({ url: exact + 'a' })), /1,000/);
});

test('objective and notes enforce UTF-8 byte limits while preserving unfinished buffers', () => {
  const book = fresh(); book.objective = '🌙'.repeat(500);
  assert.equal(core.bytes(book.objective), 2000);
  assert.equal(core.validate(book).objective, book.objective);
  book.objective += 'a';
  assert.throws(() => core.serialize(book), /2,000/);
  assert.equal(book.objective.length, 1001);
  const note = withNote({ text: 'é'.repeat(750) });
  assert.equal(core.validate(note).evidence_notes[0].text, note.evidence_notes[0].text);
  const unfinished = core.updateNote(note, 'note-1', 'text', 'é'.repeat(751));
  assert.throws(() => core.validate(unfinished), /1,500/);
  assert.equal(unfinished.evidence_notes[0].text, 'é'.repeat(751));
});

test('Unicode and control checks preserve literal markup, allowed whitespace and FEFF', () => {
  for (const value of ['</script><img src=x onerror=alert(1)>', '\t\n\r', '\u0085', '\ufeff', 'Jarvis 🌙 lippytm']) {
    const book = withNote({ text: value }); book.objective = value;
    assert.deepEqual(plain(core.parse(core.serialize(book))), book);
  }
  for (const value of ['\ud800', '\udfff', 'a\u0000b', 'a\u000bb', 'a\u001fb']) {
    assert.throws(() => core.validate({ ...fresh(), objective: value }));
    assert.throws(() => core.validate(withNote({ text: value })));
  }
  for (const value of ['\u0085', '\u2028']) assert.throws(() => core.validate(withNote({ label: 'vetted_source', text: value, url: 'https://example.org' })), /Add note/);
});

test('exploration lists reject duplicate, unknown and never-opened prompt claims', () => {
  for (const updates of [{ visited_quests: [] }, { visited_quests: ['inquiry', 'inquiry'] }, { visited_quests: ['inquiry', 'done'] }, { visited_quests: 'inquiry' }, { explored_quests: ['review'] }, { explored_quests: ['inquiry', 'inquiry'] }, { explored_quests: [1] }]) assert.throws(() => core.validate({ ...fresh(), ...updates }));
});

test('the raw JSON import is byte-bounded and rejects excessive nesting or trailing content', () => {
  const json = core.serialize(fresh());
  assert.doesNotThrow(() => core.parse(json + ' '.repeat(65536 - core.bytes(json))));
  assert.throws(() => core.parse(json + ' '.repeat(65537 - core.bytes(json))), /64 KiB/);
  assert.throws(() => core.parse('['.repeat(10) + '0' + ']'.repeat(10)), /deeply/);
  assert.throws(() => core.parse(json + '{}'), /unambiguous JSON/);
  for (const raw of ['', '{', '{"schema_version":1,}', '[1,]', '{"a":NaN}', '{"a":Infinity}', '{"a":1e999}']) assert.throws(() => core.parse(raw));
});

test('JSON imports reject duplicate decoded keys, including escaped aliases and prototype names', () => {
  const json = core.serialize(fresh());
  assert.throws(() => core.parse(json.replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1')), /duplicate/);
  assert.throws(() => core.parse(json.replace('"objective": ""', '"objective": "", "objec\\u0074ive": "changed"')), /duplicate/);
  assert.throws(() => core.parse(json.replace('"objective": ""', '"objective": "", "__proto__": {}')), /unsupported fields/);
  assert.equal({}.polluted, undefined);
});

test('raw schema tokens must be integer one, not decimal, exponent, boolean or string lookalikes', () => {
  const json = core.serialize(fresh());
  for (const token of ['1.0', '1e0', 'true', '"1"', 'null', '01', '-0']) assert.throws(() => core.parse(json.replace('"schema_version": 1', '"schema_version": ' + token)), undefined, token);
});

test('every invalid import preserves the exact previous draft object, including unfinished text', () => {
  const current = withNote({ text: 'Unsaved edit \ud800' });
  for (const raw of ['{}', 'not json', core.serialize(fresh()).replace('"private"', '"unknown"'), '{"schema_version":1,"schema_version":1}', ' '.repeat(65537)]) {
    const result = core.tryImport(current, raw);
    assert.equal(result.ok, false);
    assert.equal(result.book, current);
    assert.equal(result.book.evidence_notes[0].text, 'Unsaved edit \ud800');
  }
});

test('resume import tickets reject stale reads and intervening edits', () => {
  assert.equal(core.sameImportRevision({ ticket: 2, revision: 3 }, { ticket: 2, revision: 3 }), true);
  assert.equal(core.sameImportRevision({ ticket: 2, revision: 3 }, { ticket: 3, revision: 3 }), false);
  assert.equal(core.sameImportRevision({ ticket: 2, revision: 3 }, { ticket: 2, revision: 4 }), false);
  assert.match(appSource, /await file\.arrayBuffer\(\)/);
  assert.match(appSource, /sameImportRevision\(start,\{ticket:importTicket,revision\}\)/);
  assert.ok(appSource.indexOf('sameImportRevision(start') < appSource.indexOf('const result=engine.tryImport(book,text)'));
  assert.ok(appSource.indexOf('if(!result.ok)') < appSource.indexOf('book=result.book'));
});

test('copied briefs carry audience, source visibility, evidence labels and planned research goals', () => {
  const book = withNote({ label: 'attributed_claim', text: 'A speaker asserted this; corroboration is still missing.', url: 'https://example.org/original' });
  book.campaign_id = 'documentary-claims-research'; book.source_visibility = 'internal';
  const text = core.brief(book);
  assert.match(text, /OWNER \/ INTERNAL/);
  assert.match(text, /no evidence verification or project completion/);
  assert.equal((text.match(/PLANNED RESEARCH PROMPT/g) || []).length, 3);
  assert.match(text, /Attributed claim/);
  assert.match(text, /https:\/\/example.org\/original/);
  assert.match(text, /not encryption or publication permission/);
});

test('the single optional artwork hook accepts bitmap data URIs and rejects external assets', () => {
  assert.equal((html.match(/data-jarvis-inline-art=""/g) || []).length, 1);
  for (const mime of ['png', 'jpeg', 'webp']) assert.equal(core.inlineArt('data:image/' + mime + ';base64,YQ=='), 'data:image/' + mime + ';base64,YQ==');
  for (const value of ['', null, 'https://example.org/art.png', 'data:image/svg+xml;base64,YQ==', 'data:text/html;base64,YQ==', 'data:image/png;base64,Y Q==']) assert.equal(core.inlineArt(value), null);
});

test('native controls have spellcheck, keyboard focus, reduced-motion and explicit classification language', () => {
  assert.match(html, /<textarea id="objective" spellcheck="true" lang="en"/);
  assert.match(appSource, /input\.spellcheck=true;input\.lang="en"/);
  assert.match(html, /prefers-reduced-motion:reduce/);
  assert.match(html, /body data-calm="true"/);
  assert.match(html, /:focus-visible/);
  assert.match(html, /id="quest-detail" tabindex="-1"/);
  assert.match(html, /Private is a classification, not encryption/);
  assert.match(html, /not a 3D game/);
  for (const match of html.matchAll(/<button\b([^>]*)>/g)) assert.match(match[1], /type="button"/);
});

test('untrusted data uses text/value DOM sinks without app network or persistent storage APIs', () => {
  assert.doesNotMatch(appSource, /innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(|new Function/);
  assert.match(appSource, /\.textContent=/);
  assert.match(appSource, /\.value=/);
  assert.doesNotMatch(coreSource + appSource, /\bfetch\s*\(|XMLHttpRequest|WebSocket|EventSource|sendBeacon|localStorage|sessionStorage|indexedDB|document\.cookie/);
  assert.match(html, /connect-src 'none'/);
  assert.match(html, /img-src data:/);
  assert.doesNotMatch(html, /<script[^>]+src=|<link[^>]+href=/);
});

test('save, copy and import actions are explicit user handlers with no background export or sending', () => {
  assert.match(appSource, /\$\("export-book"\)\.addEventListener\("click"/);
  assert.match(appSource, /\$\("copy-brief"\)\.addEventListener\("click"/);
  assert.match(appSource, /\$\("import-book"\)\.addEventListener\("change"/);
  assert.match(appSource, /anchor\.download="jarvis-research-questbook\.json"/);
  assert.match(appSource, /URL\.revokeObjectURL\(url\)/);
  assert.match(appSource, /new TextDecoder\("utf-8",\{fatal:true\}\)/);
  assert.match(appSource, /file\.size>engine\.maxFileBytes/);
  assert.doesNotMatch(appSource, /setInterval|requestAnimationFrame/);
});
