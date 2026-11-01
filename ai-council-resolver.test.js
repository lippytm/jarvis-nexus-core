'use strict';

const assert = require('assert');
const { resolveCouncil } = require('./ai-council-resolver');

const positions = [
  { member_id: 'chatgpt', position: 'A', evidence: ['E1'] },
  { member_id: 'claude', position: 'A', evidence: ['E2'] },
  { member_id: 'gemini', position: 'A', evidence: ['E3'] },
  { member_id: 'jarvis-evaluator', position: 'A', evidence: ['E4'] }
];

let r = resolveCouncil({ positions, disagreements: [], deterministic_tests_passed: true });
assert.strictEqual(r.consensus, 'VERIFIED_CONSENSUS');
assert.strictEqual(r.resolution_route, 'PREPARE_OWNER_REVIEW');

r = resolveCouncil({ positions, disagreements: [], deterministic_tests_passed: false });
assert.strictEqual(r.consensus, 'PROVISIONAL_CONSENSUS');
assert.strictEqual(r.resolution_route, 'RUN_DETERMINISTIC_TESTS');

const noEvidence = positions.map(p => ({ ...p, evidence: [] }));
r = resolveCouncil({ positions: noEvidence, disagreements: [], deterministic_tests_passed: true });
assert.strictEqual(r.consensus, 'PROVISIONAL_CONSENSUS');
assert.strictEqual(r.resolution_route, 'COLLECT_EVIDENCE');

r = resolveCouncil({
  positions,
  disagreements: [{ class: 'FACTUAL', resolved: false }]
});
assert.strictEqual(r.consensus, 'SPLIT_DECISION');
assert.strictEqual(r.resolution_route, 'COLLECT_AUTHORITATIVE_EVIDENCE_OR_RUN_TEST');

r = resolveCouncil({
  positions,
  disagreements: [{ class: 'RISK', resolved: false }]
});
assert.strictEqual(r.resolution_route, 'APPLY_CONSERVATIVE_RISK_STATE_AND_RED_TEAM');

r = resolveCouncil({
  positions,
  disagreements: [{ class: 'POLICY', resolved: false, critical: true }]
});
assert.strictEqual(r.consensus, 'BLOCKED_DISAGREEMENT');
assert.strictEqual(r.resolution_route, 'STOP_AND_ESCALATE');
assert.strictEqual(r.majority_vote_used_for_truth, false);

const split = [
  positions[0],
  { ...positions[1], position: 'B' },
  positions[2],
  positions[3]
];
r = resolveCouncil({ positions: split, disagreements: [] });
assert.strictEqual(r.consensus, 'SPLIT_DECISION');
assert.strictEqual(r.resolution_route, 'RUN_COMPARATIVE_EVAL');

assert.throws(
  () => resolveCouncil({ positions: [positions[0], { ...positions[0] }] }),
  /Duplicate AI Council member_id/
);

assert.strictEqual(r.production_activation, false);
assert.strictEqual(r.human_approval_required, true);
assert.ok(Object.isFrozen(r));

console.log('P11-PEE-008 AI Council resolver tests passed');
