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

  let recommendation = 'HOLD';
  let rationale = 'Further evidence or verification is required.';

  if (securityViolation) {
    recommendation = 'ESCALATE';
    rationale = 'Security or privacy violation requires escalation.';
  } else if (!rollbackVerified) {
    recommendation = 'ESCALATE';
    rationale = 'Rollback verification failed or is unavailable.';
  } else if (criticalErrors > 0) {
    recommendation = 'ROLLBACK';
    rationale = 'Critical errors require rollback recommendation.';
  } else if (highRegressions > 0) {
    recommendation = 'ROLLBACK';
    rationale = 'High-severity regression requires rollback recommendation.';
  } else if (!verificationComplete || input.evidence_completeness < 90) {
    recommendation = 'HOLD';
    rationale = 'Post-canary verification or evidence is incomplete.';
  } else {
    recommendation = 'CONTINUE';
    rationale = 'Required post-canary checks pass.';
  }

  return Object.freeze({
    recommendation,
    rationale,
    owner_review_required: true,
    executes_rollback: false,
    production_activation: false
  });
}

module.exports = { recommendPostCanaryAction };
