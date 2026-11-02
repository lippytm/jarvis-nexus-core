'use strict';

const assert = require('assert');
const { decideRolloutStage } = require('./progressive-rollout-controller');

function base() {
  return {
    current_stage: 'CANARY',
    post_canary_recommendation: 'CONTINUE',
    drift_class: 'NO_DRIFT',
    human_approval_approved: true,
    rollback_ready: true,
    unresolved_risks: []
  };
}

let r = decideRolloutStage(base());
assert.strictEqual(r.action, 'ADVANCE_ONE_STAGE');
assert.strictEqual(r.recommended_stage, 'LIMITED');

r = decideRolloutStage({ ...base(), current_stage: 'LIMITED' });
assert.strictEqual(r.recommended_stage, 'PARTIAL');

r = decideRolloutStage({ ...base(), human_approval_approved: false });
assert.strictEqual(r.action, 'HOLD');
assert.strictEqual(r.recommended_stage, 'CANARY');

r = decideRolloutStage({ ...base(), rollback_ready: false });
assert.strictEqual(r.action, 'HOLD');

r = decideRolloutStage({ ...base(), drift_class: 'MATERIAL_DRIFT' });
assert.strictEqual(r.action, 'ROLLBACK');

r = decideRolloutStage({ ...base(), drift_class: 'CRITICAL_DRIFT' });
assert.strictEqual(r.action, 'ROLLBACK');

r = decideRolloutStage({ ...base(), post_canary_recommendation: 'ESCALATE' });
assert.strictEqual(r.action, 'ESCALATE');

r = decideRolloutStage({ ...base(), unresolved_risks: [{ severity: 'high' }] });
assert.strictEqual(r.action, 'HOLD');

r = decideRolloutStage({ ...base(), current_stage: 'FULL' });
assert.strictEqual(r.action, 'HOLD');
assert.strictEqual(r.recommended_stage, 'FULL');

assert.strictEqual(r.production_activation, false);
assert.strictEqual(r.deploys, false);
assert.strictEqual(r.executes_rollback, false);
assert.ok(Object.isFrozen(r));

console.log('P11-PEE-016 progressive rollout tests passed');
