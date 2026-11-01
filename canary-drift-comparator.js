'use strict';

function requireMetrics(m, field) {
  if (!m || typeof m !== 'object' || Array.isArray(m)) {
    throw new Error(field + ' metrics are required');
  }
  const numeric = [
    'sample_count','success_rate','failure_rate','critical_error_count',
    'high_severity_regression_count','evidence_completeness',
    'output_schema_pass_rate','latency_ms'
  ];
  for (const k of numeric) {
    if (typeof m[k] !== 'number' || !Number.isFinite(m[k])) {
      throw new Error(field + '.' + k + ' must be numeric');
    }
  }
  if (!Number.isInteger(m.sample_count) || m.sample_count < 1) {
    throw new Error(field + '.sample_count must be a positive integer');
  }
  return m;
}

function compareCanaryTelemetry({ baseline, candidate }) {
  const b = requireMetrics(baseline, 'baseline');
  const c = requireMetrics(candidate, 'candidate');

  const deltas = Object.freeze({
    success_rate: c.success_rate - b.success_rate,
    failure_rate: c.failure_rate - b.failure_rate,
    critical_error_count: c.critical_error_count - b.critical_error_count,
    high_severity_regression_count: c.high_severity_regression_count - b.high_severity_regression_count,
    evidence_completeness: c.evidence_completeness - b.evidence_completeness,
    output_schema_pass_rate: c.output_schema_pass_rate - b.output_schema_pass_rate,
    latency_ms: c.latency_ms - b.latency_ms
  });

  let drift = 'NO_DRIFT';
  const reasons = [];

  if (deltas.critical_error_count > 0 || deltas.high_severity_regression_count > 0) {
    drift = 'CRITICAL_DRIFT';
    reasons.push('Critical errors or high-severity regressions increased.');
  } else if (
    deltas.success_rate <= -10 ||
    deltas.output_schema_pass_rate <= -10 ||
    deltas.evidence_completeness <= -10
  ) {
    drift = 'MATERIAL_DRIFT';
    reasons.push('Material quality or evidence degradation detected.');
  } else {
    const anyChange = Object.values(deltas).some(v => v !== 0);
    const improvement =
      deltas.success_rate > 0 &&
      deltas.failure_rate <= 0 &&
      deltas.critical_error_count <= 0 &&
      deltas.high_severity_regression_count <= 0 &&
      deltas.output_schema_pass_rate >= 0 &&
      deltas.evidence_completeness >= 0;

    if (improvement) {
      drift = 'IMPROVEMENT';
      reasons.push('Candidate improves success without quality/regression degradation.');
    } else if (anyChange) {
      drift = 'ACCEPTABLE_DRIFT';
      reasons.push('Changes detected within default noncritical thresholds.');
    }
  }

  return Object.freeze({
    drift_class: drift,
    deltas,
    reasons: Object.freeze(reasons),
    production_activation: false,
    owner_review_required: true
  });
}

module.exports = { compareCanaryTelemetry };
