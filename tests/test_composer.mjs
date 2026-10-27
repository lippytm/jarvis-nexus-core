import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { Script, createContext } from 'node:vm';

// Execute only the authored pure module extracted from the committed HTML.
// No page content, model output or externally generated code is executed.
const html = readFileSync(new URL('../web/jarvis-composer.html', import.meta.url), 'utf8');
const scripts = [...html.matchAll(/<script id="([^"]+)">([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length, 2, 'The self-contained app has exactly two authored scripts.');
const pureSource = scripts.find(match => match[1] === 'jarvis-spelling')[2];
const appSource = scripts.find(match => match[1] === 'jarvis-app')[2];
const context = createContext({ TextEncoder });
new Script(pureSource, { filename: 'jarvis-spelling.js' }).runInContext(context, { timeout: 1000 });
const core = context.JarvisComposer;
const plain = value => JSON.parse(JSON.stringify(value));
const replacements = text => plain(core.findSuggestions(text)).map(item => [item.original, item.replacement]);

test('both authored scripts compile independently', () => {
  assert.doesNotThrow(() => new Script(pureSource));
  assert.doesNotThrow(() => new Script(appSource));
});

test('native English spellcheck is requested without app autocorrection', () => {
  const textarea = html.match(/<textarea\b[^>]*id="draft-text"[^>]*>/)[0];
  assert.match(textarea, /spellcheck="true"/);
  assert.match(textarea, /lang="en"/);
  assert.match(textarea, /autocorrect="off"/);
  assert.match(html, /<label[^>]*for="draft-text"/);
});

test('the page blocks connections and has no external assets or storage code', () => {
  assert.match(html, /connect-src 'none'/);
  assert.match(html, /form-action 'none'/);
  assert.doesNotMatch(html, /<(?:script|img|iframe|link)\b[^>]*(?:src|href)\s*=/i);
  assert.doesNotMatch(pureSource + appSource, /\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|localStorage|sessionStorage|indexedDB|sendBeacon)\b/);
  assert.doesNotMatch(pureSource + appSource, /\b(?:eval|Function)\s*\(/);
  assert.doesNotMatch(appSource, /\.innerHTML\s*=/);
});

test('a review offers corrections without mutating its input', () => {
  const text = 'Teh update will definately arrive.';
  assert.deepEqual(replacements(text), [['Teh', 'The'], ['definately', 'definitely']]);
  assert.equal(text, 'Teh update will definately arrive.');
});

test('the limited list leaves correct words, brands and unknown words unchanged', () => {
  const text = 'Jarvis lippytm lippytmai Chatlippytm.ai.Bots OpenAI ChatGPT Gemini Claude Hostinger LinkedIn Substack GitHub Intergalactic ZephyrVision the receive separate.';
  assert.deepEqual(replacements(text), []);
});

test('URL destinations, email addresses, handles and hashtags remain unchanged', () => {
  const text = 'https://teh.example/recieve?q=adress ftp://recieve.example/teh www.adress.com/teh?q=recieve contact@recieve.example @teh #recieve teh';
  assert.deepEqual(replacements(text), [['teh', 'the']]);
});

test('backtick fenced code is excluded while surrounding prose is reviewed', () => {
  const text = 'teh introduction\n```js\nconst recieve = "adress";\n```\nrecieve updates';
  assert.deepEqual(replacements(text), [['teh', 'the'], ['recieve', 'receive']]);
});

test('tilde fences and unfinished fenced code are conservatively preserved', () => {
  assert.deepEqual(replacements('~~~python\nrecieve = "teh"\n~~~\nteh'), [['teh', 'the']]);
  assert.deepEqual(replacements('teh\n````\nrecieve\n```\nadress'), [['teh', 'the']]);
});

test('inline code supports multiple backticks and protects unfinished code', () => {
  assert.deepEqual(replacements('Use `teh` and ``recieve ` adress``; teh.'), [['teh', 'the']]);
  assert.deepEqual(replacements('teh `recieve adress'), [['teh', 'the']]);
});

test('HTML code and attributes are protected; ordinary text remains reviewable', () => {
  assert.deepEqual(replacements('<pre>teh</pre> <code>recieve</code> <p title="adress">teh</p>'), [['teh', 'the']]);
  assert.deepEqual(replacements('<script>teh recieve</script> adress'), [['adress', 'address']]);
});

test('indented code, common code signatures, calls and paths are protected', () => {
  const text = '    teh recieve\nconst teh = "recieve";\ndef recieve():\nprint("adress")\nC:\\teh\\recieve /docs/adress teh';
  assert.deepEqual(replacements(text), [['teh', 'the']]);
});

test('compound words, code identifiers, accents and mixed-case terms are not rewritten', () => {
  assert.deepEqual(replacements('tehran teh_status teh2 teh-code thieré tEh Teh'), [['Teh', 'The']]);
});

test('lowercase, title case and uppercase correction styles are preserved', () => {
  assert.deepEqual(replacements('teh Teh TEH'), [['teh', 'the'], ['Teh', 'The'], ['TEH', 'THE']]);
});

test('only the chosen occurrence changes', () => {
  const text = 'teh first and teh second recieve';
  const findings = core.findSuggestions(text);
  assert.equal(core.applySuggestions(text, [findings[1]]), 'teh first and the second recieve');
  assert.equal(core.applySuggestions(text, []), text);
});

test('multiple corrections apply safely despite changing offsets and duplicate selections', () => {
  const text = 'teh seperate adress';
  const findings = core.findSuggestions(text);
  assert.equal(core.applySuggestions(text, [findings[2], findings[0], findings[1], findings[0]]), 'the separate address');
});

test('Unicode preceding a correction does not corrupt offsets', () => {
  const text = '😀 teh café recieve';
  assert.equal(core.applySuggestions(text, core.findSuggestions(text)), '😀 the café receive');
});

test('stale suggestions and forged replacement text are rejected', () => {
  const suggestion = core.findSuggestions('teh update')[0];
  assert.throws(() => core.applySuggestions('new teh update', [suggestion]), /draft changed/);
  assert.throws(() => core.applySuggestions('teh update', [{ ...suggestion, replacement: '<script>alert(1)</script>' }]), /draft changed/);
  assert.throws(() => core.applySuggestions('teh update', [null]), /draft changed/);
  assert.throws(() => core.applySuggestions('teh update', {}), /Choose corrections/);
});

test('a correction that would exceed the export byte limit is rejected atomically', () => {
  const text = 'adress ' + 'x'.repeat(19993);
  assert.equal(new TextEncoder().encode(text).length, 20000);
  assert.throws(() => core.applySuggestions(text, core.findSuggestions(text)), /20,000/);
  assert.equal(text.slice(0, 6), 'adress');
});

test('empty and unknown prose has no locally known suggestions', () => {
  assert.deepEqual(replacements(''), []);
  assert.deepEqual(replacements('Supercalifragilisticexpialidocious'), []);
});

test('the draft contract has exactly its five authorized keys and preserves text', () => {
  const text = '  A Jarvis draft.\n\n😀\n';
  const draft = plain(core.buildDraft('ai-jarvis', 'chatgpt', text));
  assert.deepEqual(Object.keys(draft).sort(), ['kind', 'project_id', 'schema_version', 'target', 'text']);
  assert.deepEqual(draft, { schema_version: 1, kind: 'jarvis.draft', project_id: 'ai-jarvis', target: 'chatgpt', text });
});

test('all agreed project IDs are supported, with no extra project identifiers', () => {
  const ids = plain(core.PROJECTS).map(([id]) => id);
  assert.deepEqual(ids, ['ai-jarvis', 'ai-evolutionary-evolutions', 'funding-affiliates', 'publishing-studio', 'linux-education', 'robotics-research', 'business-operations']);
  for (const id of ids) assert.equal(core.buildDraft(id, 'github', 'Draft').project_id, id);
});

test('provider IDs include each handoff destination and distinguish OpenAI API from ChatGPT', () => {
  const ids = plain(core.TARGETS).map(([id]) => id);
  assert.deepEqual(ids, ['chatgpt', 'openai', 'gemini', 'claude', 'hostinger', 'facebook', 'linkedin', 'substack', 'instagram', 'threads', 'youtube', 'github', 'slack', 'zapier', 'claude-cowork', 'perplexity']);
  for (const id of ids) assert.equal(core.buildDraft('publishing-studio', id, 'Draft').target, id);
  assert.equal(core.TARGETS.find(([id]) => id === 'openai')[1], 'OpenAI API draft');
});

test('unknown, missing and incorrectly typed selectors are rejected', () => {
  for (const invalid of ['', 'unknown', 'AI-JARVIS', null, undefined, {}, ['ai-jarvis']]) {
    assert.throws(() => core.buildDraft(invalid, 'chatgpt', 'Draft'), /listed project/);
  }
  for (const invalid of ['', 'unknown', 'ChatGPT', null, undefined, {}, ['chatgpt']]) {
    assert.throws(() => core.buildDraft('ai-jarvis', invalid, 'Draft'), /listed draft destination/);
  }
});

test('export rejects whitespace-only drafts without trimming valid text', () => {
  for (const text of ['', '  ', '\t\n\r', '\u00a0\u2003', '\u0085', ' \u0085\n', '\ufeff']) assert.throws(() => core.buildDraft('ai-jarvis', 'chatgpt', text), /Write something/);
  assert.equal(core.buildDraft('ai-jarvis', 'chatgpt', '\n text \n').text, '\n text \n');
});

test('C0 controls other than tab, line feed and carriage return are rejected', () => {
  for (let unit = 0; unit < 32; unit += 1) {
    const text = `a${String.fromCharCode(unit)}b`;
    if ([9, 10, 13].includes(unit)) assert.equal(core.buildDraft('ai-jarvis', 'chatgpt', text).text, text);
    else assert.throws(() => core.buildDraft('ai-jarvis', 'chatgpt', text), /control characters/);
  }
});

test('the 20,000-byte boundary is inclusive for ASCII', () => {
  assert.equal(core.buildDraft('ai-jarvis', 'chatgpt', 'x'.repeat(20000)).text.length, 20000);
  assert.throws(() => core.buildDraft('ai-jarvis', 'chatgpt', 'x'.repeat(20001)), /20,000/);
  assert.throws(() => core.findSuggestions('teh '.repeat(5001)), /20,000/);
});

test('UTF-8 byte limits count multibyte characters and emoji correctly', () => {
  assert.equal(core.buildDraft('ai-jarvis', 'chatgpt', '€'.repeat(6666) + 'ab').text.length, 6668);
  assert.throws(() => core.buildDraft('ai-jarvis', 'chatgpt', '€'.repeat(6667)), /20,000/);
  assert.equal(core.buildDraft('ai-jarvis', 'chatgpt', '😀'.repeat(5000)).text.length, 10000);
  assert.throws(() => core.buildDraft('ai-jarvis', 'chatgpt', '😀'.repeat(5001)), /20,000/);
});

test('invalid surrogate text is rejected instead of silently replaced on export', () => {
  for (const text of ['\ud800', '\udc00', 'A\ud800B', '\udc00\ud800']) {
    assert.throws(() => core.buildDraft('ai-jarvis', 'chatgpt', text), /invalid Unicode/);
    assert.throws(() => core.findSuggestions(text), /invalid Unicode/);
  }
  assert.equal(core.buildDraft('ai-jarvis', 'chatgpt', '\ud83d\ude00').text, '😀');
});

test('non-string draft values are rejected', () => {
  for (const text of [undefined, null, 1, true, {}, ['teh']]) {
    assert.throws(() => core.buildDraft('ai-jarvis', 'chatgpt', text), /must be a string/);
    assert.throws(() => core.findSuggestions(text), /must be a string/);
  }
});

test('character count uses Unicode code points and bytes remain a separate measure', () => {
  assert.deepEqual(plain(core.countText('Hi 😀 there')), { characters: 10, words: 2, bytes: 13 });
  assert.deepEqual(plain(core.countText('')), { characters: 0, words: 0, bytes: 0 });
});

test('review JSON survives serialization without creating authority or connection fields', () => {
  const draft = core.buildDraft('ai-evolutionary-evolutions', 'hostinger', 'Text with "quotes", <tags> and\nnewlines');
  assert.deepEqual(JSON.parse(JSON.stringify(draft)), plain(draft));
  assert.equal('approved' in draft, false);
  assert.equal('sha256' in draft, false);
  assert.equal('connected' in draft, false);
});

test('the shared JavaScript-to-Python fixtures match actual exports and rejection rules', () => {
  const fixtures = JSON.parse(readFileSync(new URL('../docs/evidence/composer-draft-fixtures.json', import.meta.url), 'utf8'));
  for (const draft of fixtures.valid_drafts) {
    assert.deepEqual(plain(core.buildDraft(draft.project_id, draft.target, draft.text)), draft);
  }
  for (const text of fixtures.rejected_texts) {
    assert.throws(() => core.buildDraft('ai-jarvis', 'chatgpt', text));
  }
});

test('undo restores chosen corrections and cleared text', () => {
  const history = core.createHistory('teh original');
  history.record('the original');
  history.record('');
  assert.equal(history.undo(), 'the original');
  assert.equal(history.undo(), 'teh original');
  assert.equal(history.current, 'teh original');
  assert.equal(history.canUndo, false);
  assert.equal(history.undo(), null);
});

test('editor history ignores duplicate records and respects its bounded capacity', () => {
  const history = core.createHistory('', 2);
  assert.equal(history.record('a'), true);
  assert.equal(history.record('a'), false);
  history.record('b');
  history.record('c');
  assert.equal(history.undo(), 'b');
  assert.equal(history.undo(), 'a');
  assert.equal(history.undo(), null);
  for (const limit of [0, 101, 1.5, true]) assert.throws(() => core.createHistory('', limit), /Invalid editor history/);
});

test('expanded workspace targets export exact IDs and preserve Unicode text', () => {
  const ids = plain(core.TARGETS).map(([id]) => id);
  assert.equal(ids.length, 16);
  for (const target of ['slack', 'zapier', 'claude-cowork', 'perplexity']) {
    assert.ok(ids.includes(target));
    const text = 'Mission: café 😀 — reviewed draft only.';
    assert.deepEqual(plain(core.buildDraft('ai-jarvis', target, text)),
      { schema_version: 1, kind: 'jarvis.draft', project_id: 'ai-jarvis', target, text });
  }
});
