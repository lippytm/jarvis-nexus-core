'use strict';

const assert = require('assert');
const { evaluateProductionHealth } = require('./production-health-monitor');

function base() {
  return {
    critical_error_count: 0,
    high_severity_regression_count: 0,
    security_or_privacy_violation: false,
    drift_class: 'NO_DRIFT',
    evidence_completeness: 95,
    rollback_available: true,
    health_signal: 'HEALTHY'
  };
}

let r = evaluateProductionHealth(base());
assert.strictEqual(r.operational_state, 'HEALTHY');
assert.strictEqual(r.recommended_action, 'OBSERVE');

r = evaluateProductionHealth({ ...base(), health_signal: 'DEGRADED' });
assert.strictEqual(r.operational_state, 'DEGRADED');
assert.strictEqual(r.recommended_action, 'INVESTIGATE');

r = evaluateProductionHealth({ ...base(), critical_error_count: 1 });
assert.strictEqual(r.operational_state, 'INCIDENT');
assert.strictEqual(r.recommended_action, 'ROLLBACK_RECOMMENDED');

r = evaluateProductionHealth({ ...base(), high_severity_regression_count: 1 });
assert.strictEqual(r.recommended_action, 'ROLLBACK_RECOMMENDED');

r = evaluateProductionHealth({ ...base(), drift_class: 'MATERIAL_DRIFT' });
assert.strictEqual(r.operational_state, 'INCIDENT');
assert.strictEqual(r.recommended_action, 'HOLD_ROLLOUT');

r = evaluateProductionHealth({ ...base(), drift_class: 'CRITICAL_DRIFT' });
assert.strictEqual(r.operational_state, 'CRITICAL_INCIDENT');
assert.strictEqual(r.recommended_action, 'ROLLBACK_RECOMMENDED');

r = evaluateProductionHealth({ ...base(), security_or_privacy_violation: true });
assert.strictEqual(r.operational_state, 'CRITICAL_INCIDENT');
assert.strictEqual(r.recommended_action, 'ESCALATE');

r = evaluateProductionHealth({ ...base(), critical_error_count: 1, rollback_available: false });
assert.strictEqual(r.operational_state, 'CRITICAL_INCIDENT');
assert.strictEqual(r.recommended_action, 'ESCALATE');

r = evaluateProductionHealth({ ...base(), evidence_completeness: 80 });
assert.strictEqual(r.operational_state, 'DEGRADED');
assert.strictEqual(r.recommended_action, 'INVESTIGATE');

assert.strictEqual(r.executes_rollback, false);
assert.strictEqual(r.production_mutation_allowed, false);
assert.ok(Object.isFrozen(r));
assert.ok(Object.isFrozen(r.reasons));

console.log('P11-PEE-017 production health monitor tests passed');
