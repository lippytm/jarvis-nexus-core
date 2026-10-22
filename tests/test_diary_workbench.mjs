import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { Script, createContext } from 'node:vm';

const html = readFileSync(new URL('../web/jarvis-diary.html', import.meta.url), 'utf8');
const scripts = [...html.matchAll(/<script id="(jarvis-diary-(?:core|app))">([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length, 2, 'Both actual shipped modules must be present.');
const source = scripts.find(match => match[1] === 'jarvis-diary-core')[2];
const appSource = scripts.find(match => match[1] === 'jarvis-diary-app')[2];
// Execute only the authored pure module in isolation; no DOM, generated code or user data runs.
const context = createContext({ TextEncoder, URL });
new Script(source, { filename: 'jarvis-diary-core.js' }).runInContext(context, { timeout: 1000 });
const core = context.JarvisDiary;
const plain = value => JSON.parse(JSON.stringify(value));
const fresh = () => plain(core.newDraft('2026-10-22', 'entry-test-1'));
const valid = () => ({ ...fresh(), title: 'Synthetic diary test', summary: 'A test fixture, not a report of real activity.', next_action: 'Review the fixture locally.', observations: [{ observation_id: 'observation-1', text: 'Prepare an illustrative example.', evidence_state: 'planned', source_ids: [] }] });
const withSource = () => ({ ...valid(), sources: [{ source_id: 'source-1', title: 'Illustrative reference', url: 'https://example.org/reference' }], observations: [{ observation_id: 'observation-1', text: 'A source-linked test statement, not a verified claim.', evidence_state: 'source_linked', source_ids: ['source-1'] }] });
const reject = entry => assert.throws(() => core.validateEntry(entry));
const copy = value => structuredClone(value);

test('both actual shipped modules compile', () => {
  assert.doesNotThrow(() => new Script(source));
  assert.doesNotThrow(() => new Script(appSource));
});

test('a new local draft is private with one planned observation and no invented content', () => {
  const entry = fresh();
  assert.equal(entry.visibility, 'private');
  assert.equal(entry.timezone, 'America/Los_Angeles');
  assert.equal(entry.date, '2026-10-22');
  assert.equal(entry.observations.length, 1);
  assert.equal(entry.observations[0].evidence_state, 'planned');
  assert.equal(entry.observations[0].text, '');
  assert.deepEqual(entry.sources, []);
  assert.equal(entry.title, '');
  assert.equal(entry.summary, '');
  assert.equal(entry.next_action, '');
  assert.ok(Object.values(entry.media_notes).every(value => value === ''));
  reject(entry);
});

test('the form lists the existing twelve initiatives without inventing or merging destinations', () => {
  const catalog = JSON.parse(readFileSync(new URL('../examples/portfolio/catalog.json', import.meta.url), 'utf8'));
  assert.deepEqual(plain(core.INITIATIVES), catalog.initiatives.map(item => [item.id, item.title]));
  assert.equal(core.INITIATIVES.length, 12);
  for (const [id] of core.INITIATIVES) assert.equal(core.validateEntry({ ...valid(), initiative_id: id }).initiative_id, id);
  for (const id of ['', 'unknown', 'JARVIS-TOOLS', null, true, ['jarvis-tools']]) reject({ ...valid(), initiative_id: id });
});

test('exports contain exactly the thirteen entry keys and preserve authored text', () => {
  const entry = valid(); entry.summary = '  Preserve this spacing.\nCafé 😀\tNext line.\r\n';
  const output = JSON.parse(core.serializeEntry(entry));
  assert.deepEqual(Object.keys(output).sort(), ['date', 'entry_id', 'initiative_id', 'kind', 'media_notes', 'next_action', 'observations', 'schema_version', 'sources', 'summary', 'timezone', 'title', 'visibility']);
  assert.deepEqual(output, entry);
  assert.equal(output.kind, 'jarvis.diary_entry');
  assert.equal(output.schema_version, 1);
});

test('schema, extra authority fields and missing top-level fields are rejected', () => {
  for (const value of [true, '1', 0, 2, null]) reject({ ...valid(), schema_version: value });
  reject({ ...valid(), kind: 'jarvis.approval' });
  for (const key of ['approved', 'published', 'sha256', '__proto__']) reject(JSON.parse(JSON.stringify(valid()).slice(0, -1) + `,"${key}":true}`));
  for (const key of core.ENTRY_KEYS) { const entry = valid(); delete entry[key]; reject(entry); }
  for (const entry of [null, [], 'text', 1, true]) reject(entry);
});

test('identifier full matches accept only two to forty-eight ASCII identifier characters', () => {
  for (const id of ['ab', 'a'.repeat(48), 'entry.test_1-2']) assert.equal(core.validateEntry({ ...valid(), entry_id: id }).entry_id, id);
  for (const id of ['a', 'a'.repeat(49), '1a', 'Entry', 'éa', 'aa\n', 'aa\r', 'aa\u2028', 'aa ', ' aa', null, true, 12]) reject({ ...valid(), entry_id: id });
  const entry = withSource(); entry.sources[0].source_id = 'bad\n'; reject(entry);
  const observation = valid(); observation.observations[0].observation_id = 'bad\n'; reject(observation);
});

test('Gregorian dates are strict across leap years, centuries and calendar bounds', () => {
  for (const date of ['0001-01-01', '9999-12-31', '2000-02-29', '2024-02-29', '2026-10-22']) assert.equal(core.validDate(date), true);
  for (const date of ['0000-01-01', '10000-01-01', '1900-02-29', '2026-02-29', '2026-04-31', '2026-13-01', '2026-00-01', '2026-01-00', '2026-1-01', '26-01-01', '２０２６-01-01', '2026-10-22\n', null, 20261022]) {
    assert.equal(core.validDate(date), false); reject({ ...valid(), date });
  }
});

test('today is derived in Pacific time across both standard and daylight time', () => {
  assert.equal(core.pacificDate(new Date('2026-10-22T06:59:59Z')), '2026-10-21');
  assert.equal(core.pacificDate(new Date('2026-10-22T07:00:00Z')), '2026-10-22');
  assert.equal(core.pacificDate(new Date('2026-01-02T07:59:59Z')), '2026-01-01');
  assert.equal(core.pacificDate(new Date('2026-01-02T08:00:00Z')), '2026-01-02');
  assert.throws(() => core.pacificDate(new Date(NaN)));
  for (const timezone of ['UTC', 'PST', 'America/Los_Angeles ', null]) reject({ ...valid(), timezone });
});

test('visibility is a closed intention label and never adds publishing authority', () => {
  for (const visibility of ['private', 'internal', 'public_candidate']) {
    const entry = core.validateEntry({ ...valid(), visibility });
    assert.equal(entry.visibility, visibility);
    assert.equal(Object.hasOwn(entry, 'approved'), false);
  }
  for (const visibility of ['public', 'PRIVATE', '__proto__', 'constructor', true, null]) reject({ ...valid(), visibility });
});

test('required title, summary and next-action limits are inclusive UTF-8 byte limits', () => {
  for (const [key, max] of [['title', 180], ['summary', 3000], ['next_action', 1500]]) {
    assert.equal(core.validateEntry({ ...valid(), [key]: 'x'.repeat(max) })[key].length, max);
    reject({ ...valid(), [key]: 'x'.repeat(max + 1) });
    assert.equal(core.bytes(core.validateEntry({ ...valid(), [key]: 'é'.repeat(max / 2) })[key]), max);
    reject({ ...valid(), [key]: 'é'.repeat(max / 2 + 1) });
  }
});

test('blank detection matches Python whitespace including U+0085 without rewriting text', () => {
  for (const text of ['', ' ', '\t\n\r', '\u0085', '\u00a0\u2003', '\u2028\u2029', '\u3000']) {
    for (const key of ['title', 'summary', 'next_action']) reject({ ...valid(), [key]: text });
    const source = withSource(); source.sources[0].title = text; reject(source);
    const observation = valid(); observation.observations[0].text = text; reject(observation);
  }
  // FEFF is not whitespace under Python str.strip and is preserved by the data contract.
  assert.equal(core.validateEntry({ ...valid(), title: '\ufeff' }).title, '\ufeff');
  assert.equal(core.validateEntry({ ...valid(), summary: ' \u0085x\n' }).summary, ' \u0085x\n');
});

test('C0 controls are rejected except tab, LF and CR in text fields', () => {
  for (let unit = 0; unit < 32; unit += 1) {
    const entry = valid(); entry.summary = `before${String.fromCharCode(unit)}after`;
    if ([9, 10, 13].includes(unit)) assert.equal(core.validateEntry(entry).summary, entry.summary);
    else reject(entry);
  }
  const media = valid(); media.media_notes.audience = '\u0000'; reject(media);
  const source = withSource(); source.sources[0].title = 'a\u000bb'; reject(source);
  const observation = valid(); observation.observations[0].text = 'a\u0001b'; reject(observation);
});

test('strict Unicode validation rejects lone surrogates and preserves valid scalar values', () => {
  for (const text of ['\ud800', '\udc00', 'a\ud800b', '\udc00\ud800', '😀\ud800']) {
    reject({ ...valid(), summary: text });
    const media = valid(); media.media_notes.audio_style = text; reject(media);
  }
  for (const text of ['😀', 'café', '\ufffe\uffff']) assert.equal(core.validateEntry({ ...valid(), summary: text }).summary, text);
  assert.equal(core.bytes('😀'), 4);
});

test('text fields do not coerce booleans, numbers, arrays or null into strings', () => {
  for (const value of [true, 12, null, [], {}, undefined]) {
    reject({ ...valid(), summary: value });
    const media = valid(); media.media_notes.audience = value; reject(media);
  }
});

test('one to eight observations are accepted and zero or nine are rejected', () => {
  const entry = valid();
  entry.observations = Array.from({ length: 8 }, (_, index) => ({ observation_id: `observation-${index + 1}`, text: 'A planned test.', evidence_state: 'planned', source_ids: [] }));
  assert.equal(core.validateEntry(entry).observations.length, 8);
  reject({ ...entry, observations: [] });
  reject({ ...entry, observations: [...entry.observations, { ...entry.observations[0], observation_id: 'observation-9' }] });
  reject({ ...entry, observations: {} });
});

test('observation IDs are unique and observation objects have exactly four fields', () => {
  const entry = valid(); entry.observations.push(copy(entry.observations[0])); reject(entry);
  const extra = valid(); extra.observations[0].verified = true; reject(extra);
  const missing = valid(); delete missing.observations[0].source_ids; reject(missing);
  const malformed = valid(); malformed.observations[0] = null; reject(malformed);
});

test('observation text is nonblank and bounded at one thousand UTF-8 bytes', () => {
  const entry = valid(); entry.observations[0].text = '😀'.repeat(250);
  assert.equal(core.bytes(core.validateEntry(entry).observations[0].text), 1000);
  entry.observations[0].text += 'a'; reject(entry);
});

test('evidence states are closed labels and source-linked notes require references', () => {
  for (const state of ['owner_reported', 'planned', 'fictional']) {
    const entry = valid(); entry.observations[0].evidence_state = state;
    assert.equal(core.validateEntry(entry).observations[0].evidence_state, state);
  }
  for (const state of ['source_linked', 'verified', 'completed', '__proto__', null, true]) {
    const entry = valid(); entry.observations[0].evidence_state = state; reject(entry);
  }
  assert.equal(core.validateEntry(withSource()).observations[0].evidence_state, 'source_linked');
});

test('zero to five sources are accepted and more than five are rejected', () => {
  const entry = valid();
  assert.equal(core.validateEntry(entry).sources.length, 0);
  entry.sources = Array.from({ length: 5 }, (_, index) => ({ source_id: `source-${index + 1}`, title: 'Synthetic reference', url: `https://example.org/${index}` }));
  assert.equal(core.validateEntry(entry).sources.length, 5);
  entry.sources.push({ source_id: 'source-6', title: 'Extra reference', url: 'https://example.org/6' }); reject(entry);
  reject({ ...valid(), sources: null });
});

test('source IDs are unique and source records have exactly three fields', () => {
  const duplicate = withSource(); duplicate.sources.push(copy(duplicate.sources[0])); reject(duplicate);
  const extra = withSource(); extra.sources[0].trusted = true; reject(extra);
  const missing = withSource(); delete missing.sources[0].title; reject(missing);
  const malformed = withSource(); malformed.sources[0] = []; reject(malformed);
});

test('source titles are nonblank and bounded at two hundred UTF-8 bytes', () => {
  const entry = withSource(); entry.sources[0].title = 'é'.repeat(100);
  assert.equal(core.bytes(core.validateEntry(entry).sources[0].title), 200);
  entry.sources[0].title += 'x'; reject(entry);
});

test('HTTPS source URLs preserve their original case and allowed default port', () => {
  for (const url of ['https://example.org', 'HTTPS://EXAMPLE.ORG:443/path?x=1#part', 'https://example.org:00443/a', 'https://[::1]/reference', 'https://éxample.org/path']) {
    const entry = withSource(); entry.sources[0].url = url;
    assert.equal(core.validateEntry(entry).sources[0].url, url);
  }
});

test('URL credential, whitespace, custom-port and malformed-authority cases are rejected', () => {
  for (const url of ['http://example.org', 'javascript:alert(1)', 'data:text/plain,hello', 'https:example.org', 'https:///example.org', 'https://', 'https://user:pass@example.org', 'https://@example.org', 'https://example.org:444/', 'https://example.org:80/', 'https://example.org:bad/', 'https://example.org/a b', 'https://example.org/\t', 'https://example.org/\u0085', 'https://example.org/\u0000', 'https://example.org\\evil', ' https://example.org', 'https://[bad]/']) {
    const entry = withSource(); entry.sources[0].url = url; reject(entry);
  }
});

test('the source URL byte limit is exactly one thousand without fetching it', () => {
  const base = 'https://example.org/'; const entry = withSource(); entry.sources[0].url = base + 'x'.repeat(1000 - core.bytes(base));
  assert.equal(core.bytes(core.validateEntry(entry).sources[0].url), 1000);
  entry.sources[0].url += 'x'; reject(entry);
});

test('observation references must be unique known IDs, with no invented source', () => {
  for (const refs of [['unknown'], ['source-1', 'source-1'], [true], ['source-1', null], 'source-1', null]) {
    const entry = withSource(); entry.observations[0].source_ids = refs; reject(entry);
  }
  const entry = withSource();
  entry.sources = Array.from({ length: 5 }, (_, index) => ({ source_id: `source-${index + 1}`, title: 'Reference', url: `https://example.org/${index}` }));
  entry.observations[0].source_ids = entry.sources.map(source => source.source_id);
  assert.equal(core.validateEntry(entry).observations[0].source_ids.length, 5);
  entry.observations[0].source_ids.push('source-6'); reject(entry);
});

test('media notes have five exact keys, allow blanks and enforce six-hundred-byte bounds', () => {
  assert.deepEqual(Object.keys(core.validateEntry(valid()).media_notes).sort(), ['audience', 'audio_style', 'call_to_action', 'learning_goal', 'visual_style']);
  for (const key of core.MEDIA_KEYS) {
    const entry = valid(); entry.media_notes[key] = 'é'.repeat(300);
    assert.equal(core.bytes(core.validateEntry(entry).media_notes[key]), 600);
    entry.media_notes[key] += 'x'; reject(entry);
    const missing = valid(); delete missing.media_notes[key]; reject(missing);
  }
  const extra = valid(); extra.media_notes.publish = true; reject(extra);
  const blank = valid(); blank.media_notes.audience = '\u0085 \t'; assert.equal(core.validateEntry(blank).media_notes.audience, '\u0085 \t');
});

test('validated values are copies that cannot mutate the original draft', () => {
  const entry = withSource(); const snapshot = JSON.stringify(entry); const output = core.validateEntry(entry);
  output.sources[0].title = 'Changed'; output.observations[0].source_ids.length = 0; output.media_notes.audience = 'Changed';
  assert.equal(JSON.stringify(entry), snapshot);
});

test('adding observations creates unique planned rows and enforces the row cap', () => {
  const original = fresh(); let entry = original;
  for (let count = 1; count < 8; count += 1) entry = core.addObservation(entry);
  assert.equal(original.observations.length, 1);
  assert.equal(entry.observations.length, 8);
  assert.equal(new Set(entry.observations.map(item => item.observation_id)).size, 8);
  assert.ok(entry.observations.every(item => item.evidence_state === 'planned'));
  assert.throws(() => core.addObservation(entry), /eight/);
});

test('removing observations preserves other content and keeps at least one row', () => {
  const original = valid(); const entry = core.addObservation(original);
  entry.observations[1].text = 'Second note';
  const removed = core.removeObservation(entry, 'observation-1');
  assert.equal(removed.observations[0].text, 'Second note');
  assert.equal(original.observations[0].text, 'Prepare an illustrative example.');
  assert.throws(() => core.removeObservation(removed, removed.observations[0].observation_id), /at least one/);
  assert.throws(() => core.removeObservation(entry, 'unknown'), /not found/);
});

test('adding sources creates unique stable labels and enforces five rows', () => {
  let entry = valid();
  for (let count = 0; count < 5; count += 1) entry = core.addSource(entry);
  assert.equal(new Set(entry.sources.map(item => item.source_id)).size, 5);
  assert.ok(entry.sources.every(item => item.title === '' && item.url === ''));
  assert.throws(() => core.addSource(entry), /five/);
  const removed = core.removeSource(entry, 'source-2');
  const added = core.addSource(removed);
  assert.equal(new Set(added.sources.map(item => item.source_id)).size, 5);
});

test('source removal detaches references without upgrading or downgrading evidence classification', () => {
  const original = withSource(); const snapshot = JSON.stringify(original);
  const result = core.removeSource(original, 'source-1');
  assert.deepEqual(plain(result.sources), []);
  assert.deepEqual(plain(result.observations[0].source_ids), []);
  assert.equal(result.observations[0].evidence_state, 'source_linked');
  assert.throws(() => core.validateEntry(result), /at least one source/);
  assert.equal(JSON.stringify(original), snapshot);
  assert.throws(() => core.removeSource(original, 'unknown'), /not found/);
});

test('source selection is explicit, duplicate-free and leaves classification unchanged', () => {
  const entry = withSource(); entry.observations[0].evidence_state = 'planned'; entry.observations[0].source_ids = [];
  let result = core.setSourceLink(entry, 'observation-1', 'source-1', true);
  result = core.setSourceLink(result, 'observation-1', 'source-1', true);
  assert.deepEqual(plain(result.observations[0].source_ids), ['source-1']);
  assert.equal(result.observations[0].evidence_state, 'planned');
  assert.deepEqual(entry.observations[0].source_ids, []);
  result = core.setSourceLink(result, 'observation-1', 'source-1', false);
  assert.deepEqual(plain(result.observations[0].source_ids), []);
  assert.throws(() => core.setSourceLink(entry, 'observation-1', 'unknown', true));
  assert.throws(() => core.setSourceLink(entry, 'unknown', 'source-1', true));
  assert.throws(() => core.setSourceLink(entry, 'observation-1', 'source-1', 'true'));
});

test('changing an initiative preserves the global entry content', () => {
  const entry = withSource(); const before = copy(entry); entry.initiative_id = 'personal-workflow';
  assert.deepEqual(plain(core.validateEntry(entry)), { ...before, initiative_id: 'personal-workflow' });
  assert.match(appSource, /draft\[key\]=node\.value; changed\(\)/);
});

test('serialized entries round-trip with labels, IDs, Unicode and sources intact', () => {
  const entry = withSource(); entry.summary = 'Café 😀 — "quoted"\nA new line.'; entry.visibility = 'internal';
  const serialized = core.serializeEntry(entry);
  assert.ok(serialized.endsWith('\n'));
  assert.deepEqual(plain(core.parseEntry(serialized)), entry);
  assert.ok(core.bytes(serialized) <= 65536);
});

test('JSON import rejects duplicate and escaped duplicate object keys', () => {
  const serialized = JSON.stringify(valid());
  for (const key of ['visibility', '\\u0076isibility']) {
    assert.throws(() => core.parseEntry(serialized.slice(0, -1) + `,"${key}":"public_candidate"}`), /duplicate field/);
  }
  assert.throws(() => core.parseUniqueJSON('{"x":{"a":1,"a":2}}'), /duplicate field/);
});

test('import preserves Python integer-type semantics for schema version tokens', () => {
  const serialized = JSON.stringify(valid());
  for (const token of ['1.0', '1e0', '1E+0', '1.0000000000000001']) assert.throws(() => core.parseEntry(serialized.replace('"schema_version":1', `"schema_version":${token}`)), /JSON integer/);
  assert.equal(core.parseEntry(serialized).schema_version, 1);
});

test('JSON import rejects malformed syntax, nonfinite numbers and trailing content', () => {
  for (const text of ['', '{', '{} trailing', '{"x":1,}', '[1,]', '{x:1}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}', '{"x":01}', '{"x":.5}', '{"x":"bad\nline"}', '\ufeff{}', 'undefined', '{"x":"\\q"}', '{"x":"unterminated}']) assert.throws(() => core.parseUniqueJSON(text));
  for (const text of ['null', '[]', 'true', '1', '"text"']) assert.throws(() => core.parseEntry(text));
});

test('the bounded JSON parser handles legal JSON scalars, arrays, escapes and null-prototype keys', () => {
  for (const text of ['null', 'true', 'false', '0', '-0', '1.5e-2', '[]', '{}', '[1,"a",null,false]', '{"text":"quote\\\" and slash\\\\ and \\u00e9","nested":{"ok":true}}', '{"__proto__":{"polluted":true}}']) {
    assert.deepEqual(plain(core.parseUniqueJSON(text)), JSON.parse(JSON.stringify(JSON.parse(text))));
  }
  assert.equal(Object.getPrototypeOf(core.parseUniqueJSON('{"__proto__":1}')), null);
  assert.equal(Object.hasOwn({}, 'polluted'), false);
});

test('raw import bytes are bounded before JSON parsing at exactly sixty-four KiB', () => {
  const serialized = JSON.stringify(valid());
  const padded = serialized + ' '.repeat(65536 - core.bytes(serialized));
  assert.equal(core.bytes(padded), 65536);
  assert.equal(core.parseEntry(padded).entry_id, 'entry-test-1');
  assert.throws(() => core.parseEntry(padded + ' '), /64 KiB/);
  assert.throws(() => core.parseEntry('é'.repeat(32769)), /64 KiB/);
  assert.throws(() => core.parseUniqueJSON('['.repeat(14) + '0' + ']'.repeat(14)), /nested too deeply/);
});

test('invalid imported Unicode is rejected whether raw or escaped', () => {
  assert.throws(() => core.parseUniqueJSON('{"text":"\ud800"}'), /UTF-8/);
  const serialized = JSON.stringify({ ...valid(), title: '\ud800' });
  assert.throws(() => core.parseEntry(serialized), /Unicode/);
});

test('an invalid import leaves the current unfinished draft and every nested value intact', () => {
  const current = fresh(); current.summary = 'Unsaved work'; current.media_notes.audience = 'Keep this'; current.observations[0].text = 'In progress';
  const snapshot = JSON.stringify(current);
  for (const text of ['broken', '{}', JSON.stringify({ ...valid(), approved: true }), JSON.stringify({ ...valid(), title: '' })]) {
    const result = core.tryImport(current, text);
    assert.equal(result.ok, false);
    assert.equal(result.entry, current);
    assert.equal(JSON.stringify(current), snapshot);
    assert.ok(result.error.length > 0);
  }
});

test('a successful import returns a validated replacement without altering the previous draft', () => {
  const current = fresh(); current.summary = 'Previous draft'; const snapshot = JSON.stringify(current);
  const replacement = { ...withSource(), entry_id: 'entry-imported', visibility: 'public_candidate' };
  const result = core.tryImport(current, core.serializeEntry(replacement));
  assert.equal(result.ok, true);
  assert.deepEqual(plain(result.entry), replacement);
  assert.equal(JSON.stringify(current), snapshot);
  assert.notEqual(result.entry, current);
});

test('the brief retains all four evidence classifications and recorded sources as plain text', () => {
  const entry = withSource();
  entry.observations = Object.keys(core.STATES).map((state, index) => ({ observation_id: `observation-${index + 1}`, text: `<script>illustrative ${state}</script>`, evidence_state: state, source_ids: state === 'source_linked' ? ['source-1'] : [] }));
  const preview = core.buildPreview(entry);
  for (const label of Object.values(core.STATES)) assert.ok(preview.includes(label.toUpperCase()));
  assert.ok(preview.includes('[source-1] Illustrative reference\nhttps://example.org/reference'));
  assert.ok(preview.includes('Sources: source-1'));
  assert.ok(preview.includes('<script>illustrative fictional</script>'));
  assert.ok(preview.includes('NEXT ACTION — planning only'));
  assert.ok(preview.includes('AUDIENCE: (not supplied)'));
});

test('private and public-candidate previews keep visibility separate from evidence and consent', () => {
  assert.match(core.buildPreview(valid()), /VISIBILITY: Private draft/);
  const preview = core.buildPreview({ ...valid(), visibility: 'public_candidate' });
  assert.match(preview, /VISIBILITY: Public candidate — review required/);
  assert.match(preview, /not publication consent/);
  assert.match(preview, /PLANNED — INTENTION, NOT A COMPLETED RESULT/);
  assert.throws(() => core.buildPreview(fresh()));
});

test('native form structure includes explicit labels, spellcheck and local companion links', () => {
  assert.match(html, /<form[^>]*id="diary-form"[^>]*tabindex="-1"/);
  assert.match(html, /<input[^>]*id="entry-date"[^>]*type="date"/);
  assert.match(html, /<textarea[^>]*id="summary"[^>]*lang="en"[^>]*spellcheck="true"/);
  assert.match(html, /<select id="visibility"><option value="private">/);
  assert.match(html, /href="jarvis-composer\.html"/);
  assert.match(html, /href="jarvis-workbench\.html"/);
  assert.match(html, /<input[^>]*id="import-file"[^>]*type="file"/);
  for (const tag of html.matchAll(/<button\b[^>]*>/g)) assert.match(tag[0], /type="button"/);
});

test('the application has no external assets, networking, persistence or HTML injection sinks', () => {
  assert.doesNotMatch(html, /<(?:script|img|iframe|link)\b[^>]*(?:src|href)\s*=/i);
  assert.doesNotMatch(source + appSource, /\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon|localStorage|sessionStorage|indexedDB|eval|Function)\s*\(|\b(?:localStorage|sessionStorage|indexedDB)\b|document\.cookie|\.innerHTML\b|\.outerHTML\b|insertAdjacentHTML/);
  assert.match(html, /connect-src 'none'/);
  assert.match(html, /form-action 'none'/);
  assert.match(appSource, /\.textContent=/);
  assert.match(appSource, /\.value=/);
});

test('the real import path decodes UTF-8 strictly and preserves edits made during file reading', () => {
  assert.match(appSource, /file\.size>core\.MAX_PACKET_BYTES/);
  assert.match(appSource, /new TextDecoder\("utf-8",\{fatal:true,ignoreBOM:true\}\)/);
  assert.match(appSource, /revision!==startRevision/);
  assert.match(appSource, /ticket!==importTicket/);
  assert.match(appSource, /const candidate=core\.tryImport\(draft,text\)/);
  assert.match(appSource, /if \(!candidate\.ok\)/);
});

test('shared fixtures are twelve actual valid exports and explicitly rejected contract cases', () => {
  const fixtures = JSON.parse(readFileSync(new URL('../docs/evidence/diary-workbench-fixtures.json', import.meta.url), 'utf8'));
  assert.equal(fixtures.valid_entries.length, 12);
  assert.equal(new Set(fixtures.valid_entries.map(entry => entry.initiative_id)).size, 12);
  for (const entry of fixtures.valid_entries) {
    assert.deepEqual(JSON.parse(core.serializeEntry(entry)), entry);
    assert.deepEqual(plain(core.parseEntry(JSON.stringify(entry))), entry);
  }
  assert.ok(fixtures.rejected_entries.length >= 20);
  for (const record of fixtures.rejected_entries) assert.throws(() => core.validateEntry(record.entry), record.case);
  for (const record of fixtures.rejected_json || []) assert.throws(() => core.parseEntry(record.text), record.case);
});
