'use strict';

function requireBool(value, field) {
  if (typeof value !== 'boolean') throw new Error(field + ' must be boolean');
  return value;
}

function requireCount(value, field) {
  if (!Number.isInteger(value) || value < 0) throw new Error(field + ' must be a nonnegative integer');
  return value;
}

function recommendPostCanaryAction(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    throw new Error('post-canary input required');
  }

  const criticalErrors = requireCount(input.critical_error_count, 'critical_error_count');
  const highRegressions = requireCount(input.high_severity_regression_count, 'high_severity_regression_count');
  const securityViolation = requireBool(input.security_or_privacy_violation, 'security_or_privacy_violation');
  const rollbackVerified = requireBool(input.rollback_verified, 'rollback_verified');
  const verificationComplete = requireBool(input.post_canary_verification_complete, 'post_canary_verification_complete');

  if (!Number.isInteger(input.evidence_completeness) || input.evidence_completeness < 0 || input.evidence_completeness > 100) {
    throw new Error('evidence_completeness must be an integer from 0 to 100');
  }

  const drift = input.drift_class || 'NO_DRIFT';
  if (!['NO_DRIFT','IMPROVEMENT','ACCEPTABLE_DRIFT','MATERIAL_DRIFT','CRITICAL_DRIFT','INSUFFICIENT_DATA'].includes(drift)) {
    throw new Error('invalid drift_class');
  }

  let recommendation = 'HOLD';
  let rationale = 'Further evidence or verification is required.';

  if (securityViolation) {
    recommendation = 'ESCALATE';
    rationale = 'Security or privacy violation requires escalation.';
  } else if (!rollbackVerified) {
    recommendation = 'ESCALATE';
    rationale = 'Rollback verification failed or is unavailable.';
  } else if (criticalErrors > 0 || drift === 'CRITICAL_DRIFT') {
    recommendation = 'ROLLBACK';
    rationale = 'Critical error or critical drift requires rollback recommendation.';
  } else if (highRegressions > 0 || drift === 'MATERIAL_DRIFT') {
    recommendation = 'ROLLBACK';
    rationale = 'High-severity regression or material drift requires rollback recommendation.';
  } else if (
    !verificationComplete ||
    input.evidence_completeness < 90 ||
    drift === 'INSUFFICIENT_DATA'
  ) {
    recommendation = 'HOLD';
    rationale = 'Post-canary verification, evidence, or telemetry data is incomplete.';
  } else {
    recommendation = 'CONTINUE';
    rationale = drift === 'IMPROVEMENT'
      ? 'Verified candidate improvement with required checks passing.'
      : 'Required post-canary checks pass without blocking drift.';
  }

  return Object.freeze({
    recommendation,
    rationale,
    drift_class: drift,
    owner_review_required: true,
    executes_rollback: false,
    production_activation: false
  });
}

module.exports = { recommendPostCanaryAction };
