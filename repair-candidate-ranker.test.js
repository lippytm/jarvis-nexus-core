'use strict';

const assert = require('assert');
const { evaluateCandidate, rankRepairCandidates } = require('./repair-candidate-ranker');

function candidate(id) {
  return {
    candidate_id: id,
    deterministic_tests: 20,
    regression_coverage: 20,
    reversibility: 15,
    evidence_completeness: 15,
    scope_discipline: 10,
    risk_reduction: 10,
    maintainability: 5,
    cost_performance: 5,
    critical_gates: {
      rollback_verified: true,
      deterministic_tests_passed: true,
      regression_tests_passed: true,
      risk_clear: true,
      scope_within_bounds: true,
      security_privacy_authority_passed: true
    }
  };
}

let r = evaluateCandidate(candidate('A'));
assert.strictEqual(r.score, 100);
assert.strictEqual(r.critical_gates_passed, true);
assert.strictEqual(r.recommendation, 'READY_FOR_OWNER_REVIEW');

r = evaluateCandidate({
  ...candidate('B'),
  critical_gates: { ...candidate('B').critical_gates, rollback_verified: false }
});
assert.strictEqual(r.score, 100);
assert.strictEqual(r.critical_gates_passed, false);
assert.strictEqual(r.recommendation, 'VERIFY_ROLLBACK');

r = evaluateCandidate({
  ...candidate('C'),
  critical_gates: { ...candidate('C').critical_gates, deterministic_tests_passed: false }
});
assert.strictEqual(r.recommendation, 'REPAIR_AND_RETEST');

r = evaluateCandidate({
  ...candidate('D'),
  critical_gates: { ...candidate('D').critical_gates, scope_within_bounds: false }
});
assert.strictEqual(r.recommendation, 'REDUCE_SCOPE');

r = evaluateCandidate({
  ...candidate('E'),
  critical_gates: { ...candidate('E').critical_gates, risk_clear: false }
});
assert.strictEqual(r.recommendation, 'QUARANTINE');

const weak = {
  ...candidate('F'),
  deterministic_tests: 10,
  regression_coverage: 10,
  reversibility: 8,
  evidence_completeness: 8,
  scope_discipline: 5,
  risk_reduction: 5,
  maintainability: 3,
  cost_performance: 3
};
r = evaluateCandidate(weak);
assert.strictEqual(r.score, 52);
assert.strictEqual(r.recommendation, 'COLLECT_EVIDENCE');

const ranked = rankRepairCandidates([
  { ...candidate('high-bad'), critical_gates: { ...candidate('high-bad').critical_gates, rollback_verified: false } },
  { ...candidate('safe-90'), cost_performance: 0, maintainability: 0 },
  candidate('safe-100')
]);
assert.strictEqual(ranked[0].candidate_id, 'safe-100');
assert.strictEqual(ranked[1].candidate_id, 'safe-90');
assert.strictEqual(ranked[2].candidate_id, 'high-bad');
assert.strictEqual(ranked[2].score, 100);
assert.strictEqual(ranked[2].critical_gates_passed, false);
assert.ok(Object.isFrozen(ranked));

console.log('P11-PEE-019 repair candidate ranker tests passed');
