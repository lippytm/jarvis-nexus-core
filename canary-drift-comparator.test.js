'use strict';

const assert = require('assert');
const { compareCanaryTelemetry } = require('./canary-drift-comparator');

function base() {
  return {
    sample_count: 20,
    success_rate: 90,
    failure_rate: 10,
    critical_error_count: 0,
    high_severity_regression_count: 0,
    evidence_completeness: 95,
    output_schema_pass_rate: 95,
    latency_ms: 1000
  };
}

let r = compareCanaryTelemetry({ baseline: base(), candidate: base() });
assert.strictEqual(r.drift_class, 'NO_DRIFT');

r = compareCanaryTelemetry({
  baseline: base(),
  candidate: { ...base(), success_rate: 95, failure_rate: 5 }
});
assert.strictEqual(r.drift_class, 'IMPROVEMENT');

r = compareCanaryTelemetry({
  baseline: base(),
  candidate: { ...base(), success_rate: 85 }
});
assert.strictEqual(r.drift_class, 'ACCEPTABLE_DRIFT');

r = compareCanaryTelemetry({
  baseline: base(),
  candidate: { ...base(), success_rate: 80 }
});
assert.strictEqual(r.drift_class, 'MATERIAL_DRIFT');

r = compareCanaryTelemetry({
  baseline: base(),
  candidate: { ...base(), output_schema_pass_rate: 84 }
});
assert.strictEqual(r.drift_class, 'MATERIAL_DRIFT');

r = compareCanaryTelemetry({
  baseline: base(),
  candidate: { ...base(), critical_error_count: 1 }
});
assert.strictEqual(r.drift_class, 'CRITICAL_DRIFT');

r = compareCanaryTelemetry({
  baseline: base(),
  candidate: { ...base(), high_severity_regression_count: 1, success_rate: 99 }
});
assert.strictEqual(r.drift_class, 'CRITICAL_DRIFT');

assert.strictEqual(r.production_activation, false);
assert.strictEqual(r.owner_review_required, true);
assert.ok(Object.isFrozen(r));
assert.ok(Object.isFrozen(r.deltas));

console.log('P11-PEE-015 canary drift comparator tests passed');
