'use strict';

const assert = require('assert');
const { recommendPostCanaryAction } = require('./post-canary-verifier');

function base() {
  return {
    critical_error_count: 0,
    high_severity_regression_count: 0,
    security_or_privacy_violation: false,
    rollback_verified: true,
    post_canary_verification_complete: true,
    evidence_completeness: 95,
    drift_class: 'NO_DRIFT'
  };
}

assert.strictEqual(recommendPostCanaryAction(base()).recommendation, 'CONTINUE');
assert.strictEqual(
  recommendPostCanaryAction({ ...base(), drift_class: 'IMPROVEMENT' }).recommendation,
  'CONTINUE'
);
assert.strictEqual(
  recommendPostCanaryAction({ ...base(), drift_class: 'ACCEPTABLE_DRIFT' }).recommendation,
  'CONTINUE'
);
assert.strictEqual(
  recommendPostCanaryAction({ ...base(), drift_class: 'MATERIAL_DRIFT' }).recommendation,
  'ROLLBACK'
);
assert.strictEqual(
  recommendPostCanaryAction({ ...base(), drift_class: 'CRITICAL_DRIFT' }).recommendation,
  'ROLLBACK'
);
assert.strictEqual(
  recommendPostCanaryAction({ ...base(), drift_class: 'INSUFFICIENT_DATA' }).recommendation,
  'HOLD'
);
assert.strictEqual(
  recommendPostCanaryAction({ ...base(), security_or_privacy_violation: true }).recommendation,
  'ESCALATE'
);
assert.strictEqual(
  recommendPostCanaryAction({ ...base(), rollback_verified: false }).recommendation,
  'ESCALATE'
);
assert.strictEqual(
  recommendPostCanaryAction({ ...base(), critical_error_count: 1 }).recommendation,
  'ROLLBACK'
);
assert.strictEqual(
  recommendPostCanaryAction({ ...base(), high_severity_regression_count: 1 }).recommendation,
  'ROLLBACK'
);
assert.strictEqual(
  recommendPostCanaryAction({ ...base(), evidence_completeness: 80 }).recommendation,
  'HOLD'
);
assert.strictEqual(
  recommendPostCanaryAction({ ...base(), post_canary_verification_complete: false }).recommendation,
  'HOLD'
);

const r = recommendPostCanaryAction(base());
assert.strictEqual(r.executes_rollback, false);
assert.strictEqual(r.production_activation, false);
assert.strictEqual(r.owner_review_required, true);
assert.ok(Object.isFrozen(r));

console.log('P11-PEE-014 post-canary verification tests passed');
