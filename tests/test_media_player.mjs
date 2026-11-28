import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(new URL('../control_tower/media.py', import.meta.url), 'utf8');
const helper = source.match(/<script id="media-helper">([\s\S]+?)<\/script>/)[1];
const context = vm.createContext({});
new vm.Script(helper).runInContext(context);
const player = context.JarvisDiaryPlayer;
const native = value => JSON.parse(JSON.stringify(value));
const records = ['source_linked', 'owner_reported', 'planned', 'fictional'].map((state, index) => ({observation_id: 'record-'+index, evidence_state: state, text: 'Text '+index}));
const cues = [{start_ms:0,end_ms:3750,text:'First'}, {start_ms:3750,end_ms:7500,text:'Second'}];

test('the shipped player helper compiles without DOM or network dependencies', () => {
  assert.equal(typeof player.selectRecords, 'function');
  assert.equal(typeof player.cueAt, 'function');
  assert.equal(typeof player.checkLabel, 'function');
});
test('reading lenses preserve evidence labels and source ordering', () => {
  assert.deepEqual(native(player.selectRecords(records, 'all')), records);
  for(const r of records) assert.deepEqual(native(player.selectRecords(records, r.evidence_state)), [r]);
  assert.throws(() => player.selectRecords(records, 'verified'));
});
test('unknown lenses do not silently upgrade records to verified', () => {
  for(const value of [null, true, 0, 'complete', 'verified']) assert.throws(() => player.selectRecords(records, value));
});
test('the timeline uses inclusive starts and exclusive ends', () => {
  assert.equal(player.cueAt(cues, 0).text, 'First');
  assert.equal(player.cueAt(cues, 3749).text, 'First');
  assert.equal(player.cueAt(cues, 3750).text, 'Second');
  assert.equal(player.cueAt(cues, 7500), null);
});
test('invalid timeline input cannot select a scene', () => {
  for(const t of [-1, NaN, Infinity, '0', null]) assert.throws(() => player.cueAt(cues,t));
});
test('label practice reports an exact label match without certifying truth', () => {
  const answer = native(player.checkLabel(records[0], 'source_linked'));
  assert.equal(answer.matches, true);
  assert.match(answer.meaning, /not the truth/);
  assert.equal(player.checkLabel(records[0], 'planned').matches, false);
  assert.throws(() => player.checkLabel(records[0], 'verified'));
});
test('practice and filtering do not modify the source records', () => {
  const before = JSON.stringify(records);
  player.selectRecords(records, 'fictional');
  player.checkLabel(records[2], 'planned');
  assert.equal(JSON.stringify(records), before);
});
