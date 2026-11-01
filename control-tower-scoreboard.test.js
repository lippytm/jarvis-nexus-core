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
    rollback_ready: true,
    human_approval: { required: true, approved: false, approver: null, audit_reference: null }
  };
}

const greenPending = scoreControlTower(base());
assert.strictEqual(greenPending.traffic_light, 'GREEN');
assert.strictEqual(greenPending.promotion_blocked, true);
assert.strictEqual(greenPending.human_approval_pending, true);

const greenApproved = scoreControlTower({
  ...base(),
  human_approval: { required: true, approved: true, approver: 'synthetic-owner', audit_reference: 'TEST-AUDIT' }
});
assert.strictEqual(greenApproved.traffic_light, 'GREEN');
assert.strictEqual(greenApproved.promotion_blocked, false);

const yellow = scoreControlTower({ ...base(), evidence_completeness: 80 });
assert.strictEqual(yellow.traffic_light, 'YELLOW');

const yellowDisagreement = scoreControlTower({ ...base(), model_disagreements: ['model-a vs model-b'] });
assert.strictEqual(yellowDisagreement.traffic_light, 'YELLOW');

const orangeRisk = scoreControlTower({
  ...base(),
  risks: [{ severity: 'high', description: 'material unresolved risk', resolved: false }]
});
assert.strictEqual(orangeRisk.traffic_light, 'ORANGE');
assert.strictEqual(orangeRisk.promotion_blocked, true);

const orangeRegression = scoreControlTower({
  ...base(),
  regressions: [{ severity: 'high', test_id: 'REG-1', passed: false }]
});
assert.strictEqual(orangeRegression.traffic_light, 'ORANGE');

const red = scoreControlTower({
  ...base(),
  critical_gates: { ...base().critical_gates, privacy_security: false },
  best_practice: { score: 100, promotion_blocked: false }
});
assert.strictEqual(red.traffic_light, 'RED');
assert.strictEqual(red.best_practice_score, 100);
assert.strictEqual(red.promotion_blocked, true);

const redCriticalRisk = scoreControlTower({
  ...base(),
  risks: [{ severity: 'critical', description: 'critical unresolved risk', resolved: false }]
});
assert.strictEqual(redCriticalRisk.traffic_light, 'RED');

console.log('Control Tower scoreboard tests passed');
