'use strict';

const assert = require('assert');
const { scoreControlTower } = require('./control-tower-scoreboard');

function base() {
  return {
    critical_gates: {
      authority: true,
      privacy_security: true,
      evidence_provenance: true,
      testing: true,
      risk: true,
      rollback_recovery: true
    },
    best_practice: { score: 95, promotion_blocked: false },
    risks: [],
    regressions: [],
    evidence_completeness: 95,
    model_disagreements: [],
    error_barrier_state: 'PASS',
    rollback_ready: true,
    human_approval: { required: true, approved: false, approver: null, audit_reference: null }
  };
}

assert.strictEqual(scoreControlTower(base()).traffic_light, 'GREEN');
assert.strictEqual(scoreControlTower({ ...base(), error_barrier_state: 'WARN' }).traffic_light, 'YELLOW');
assert.strictEqual(scoreControlTower({ ...base(), error_barrier_state: 'BLOCK' }).traffic_light, 'ORANGE');
assert.strictEqual(scoreControlTower({ ...base(), error_barrier_state: 'ESCALATE' }).traffic_light, 'RED');

const greenApproved = scoreControlTower({
  ...base(),
  human_approval: { required: true, approved: true, approver: 'synthetic-owner', audit_reference: 'TEST-AUDIT' }
});
assert.strictEqual(greenApproved.traffic_light, 'GREEN');
assert.strictEqual(greenApproved.promotion_blocked, false);

assert.strictEqual(scoreControlTower({ ...base(), evidence_completeness: 80 }).traffic_light, 'YELLOW');
assert.strictEqual(scoreControlTower({ ...base(), model_disagreements: ['model-a vs model-b'] }).traffic_light, 'YELLOW');
assert.strictEqual(scoreControlTower({
  ...base(),
  risks: [{ severity: 'high', description: 'material unresolved risk', resolved: false }]
}).traffic_light, 'ORANGE');
assert.strictEqual(scoreControlTower({
  ...base(),
  regressions: [{ severity: 'high', test_id: 'REG-1', passed: false }]
}).traffic_light, 'ORANGE');

const red = scoreControlTower({
  ...base(),
  critical_gates: { ...base().critical_gates, privacy_security: false },
  best_practice: { score: 100, promotion_blocked: false }
});
assert.strictEqual(red.traffic_light, 'RED');
assert.strictEqual(red.best_practice_score, 100);
assert.strictEqual(red.promotion_blocked, true);

assert.throws(() => scoreControlTower({ ...base(), error_barrier_state: 'UNKNOWN' }), /Unknown error barrier state/);

console.log('Control Tower scoreboard tests passed');
