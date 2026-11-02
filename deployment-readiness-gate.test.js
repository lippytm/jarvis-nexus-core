'use strict';

const assert = require('assert');
const { evaluateDeploymentReadiness } = require('./deployment-readiness-gate');

function base() {
  return {
    traffic_light: 'GREEN',
    error_barrier_state: 'PASS',
    human_approval_approved: false,
    rollback_ready: true,
    post_action_verification_plan_ready: true,
    unresolved_risks: []
  };
}

assert.strictEqual(evaluateDeploymentReadiness({ ...base(), traffic_light: 'RED' }).readiness_state, 'ESCALATE');
assert.strictEqual(evaluateDeploymentReadiness({ ...base(), error_barrier_state: 'ESCALATE' }).readiness_state, 'ESCALATE');
assert.strictEqual(evaluateDeploymentReadiness({ ...base(), traffic_light: 'ORANGE' }).readiness_state, 'BLOCKED');
assert.strictEqual(evaluateDeploymentReadiness({ ...base(), error_barrier_state: 'BLOCK' }).readiness_state, 'BLOCKED');
assert.strictEqual(evaluateDeploymentReadiness({ ...base(), traffic_light: 'YELLOW' }).readiness_state, 'NOT_READY');
assert.strictEqual(evaluateDeploymentReadiness(base()).readiness_state, 'READY_FOR_OWNER_REVIEW');

assert.strictEqual(
  evaluateDeploymentReadiness({ ...base(), human_approval_approved: true }).readiness_state,
  'READY_FOR_CANARY'
);

assert.strictEqual(
  evaluateDeploymentReadiness({ ...base(), human_approval_approved: true, rollback_ready: false }).readiness_state,
  'BLOCKED'
);

assert.strictEqual(
  evaluateDeploymentReadiness({ ...base(), human_approval_approved: true, post_action_verification_plan_ready: false }).readiness_state,
  'BLOCKED'
);

assert.strictEqual(
  evaluateDeploymentReadiness({
    ...base(),
    human_approval_approved: true,
    unresolved_risks: [{ severity: 'high' }]
  }).readiness_state,
  'BLOCKED'
);

const result = evaluateDeploymentReadiness(base());
assert.strictEqual(result.deploys, false);
assert.strictEqual(result.production_activation, false);
assert.ok(Object.isFrozen(result));

console.log('P11-PEE-012 deployment readiness tests passed');
