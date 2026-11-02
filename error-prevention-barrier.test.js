'use strict';

const assert = require('assert');
const { evaluateErrorBarrier } = require('./error-prevention-barrier');

function base() {
  return {
    error_class: 'INPUT_ERROR',
    severity: 'low',
    irreversible_action: false,
    explicit_confirmation_recorded: false,
    rollback_ready: true,
    post_action_verification_required: true
  };
}

assert.strictEqual(evaluateErrorBarrier(base()).barrier_state, 'PASS');
assert.strictEqual(
  evaluateErrorBarrier({ ...base(), severity: 'medium' }).barrier_state,
  'WARN'
);
assert.strictEqual(
  evaluateErrorBarrier({ ...base(), severity: 'high' }).barrier_state,
  'BLOCK'
);
assert.strictEqual(
  evaluateErrorBarrier({ ...base(), error_class: 'PERMISSION_ERROR' }).barrier_state,
  'ESCALATE'
);
assert.strictEqual(
  evaluateErrorBarrier({
    ...base(),
    irreversible_action: true,
    explicit_confirmation_recorded: false
  }).barrier_state,
  'BLOCK'
);
assert.strictEqual(
  evaluateErrorBarrier({
    ...base(),
    irreversible_action: true,
    explicit_confirmation_recorded: true,
    rollback_ready: false
  }).barrier_state,
  'BLOCK'
);
assert.strictEqual(
  evaluateErrorBarrier({ ...base(), post_action_verification_required: false }).barrier_state,
  'WARN'
);

const result = evaluateErrorBarrier(base());
assert.strictEqual(result.production_activation, false);
assert.ok(Object.isFrozen(result));
assert.ok(Object.isFrozen(result.reasons));

console.log('P11-PEE-011 error prevention barrier tests passed');
