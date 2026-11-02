'use strict';

function requireBool(v, field) {
  if (typeof v !== 'boolean') throw new Error(field + ' must be boolean');
  return v;
}

function requireCount(v, field) {
  if (!Number.isInteger(v) || v < 0) throw new Error(field + ' must be a nonnegative integer');
  return v;
}

function evaluateProductionHealth(event) {
  if (!event || typeof event !== 'object' || Array.isArray(event)) {
    throw new Error('production monitoring event required');
  }

  const criticalErrors = requireCount(event.critical_error_count, 'critical_error_count');
  const highRegs = requireCount(event.high_severity_regression_count, 'high_severity_regression_count');
  const security = requireBool(event.security_or_privacy_violation, 'security_or_privacy_violation');
  const rollbackAvailable = requireBool(event.rollback_available, 'rollback_available');

  if (!Number.isInteger(event.evidence_completeness) || event.evidence_completeness < 0 || event.evidence_completeness > 100) {
    throw new Error('evidence_completeness must be an integer from 0 to 100');
  }

  const drift = event.drift_class;
  if (!['NO_DRIFT','IMPROVEMENT','ACCEPTABLE_DRIFT','MATERIAL_DRIFT','CRITICAL_DRIFT','INSUFFICIENT_DATA'].includes(drift)) {
    throw new Error('invalid drift_class');
  }

  let state = 'HEALTHY';
  let action = 'OBSERVE';
  const reasons = [];

  if (security) {
    state = 'CRITICAL_INCIDENT';
    action = 'ESCALATE';
    reasons.push('Security or privacy violation detected.');
  } else if (!rollbackAvailable && (criticalErrors > 0 || highRegs > 0 || drift === 'MATERIAL_DRIFT' || drift === 'CRITICAL_DRIFT')) {
    state = 'CRITICAL_INCIDENT';
    action = 'ESCALATE';
    reasons.push('Material incident with rollback unavailable.');
  } else if (drift === 'CRITICAL_DRIFT') {
    state = 'CRITICAL_INCIDENT';
    action = 'ROLLBACK_RECOMMENDED';
    reasons.push('Critical drift detected.');
  } else if (criticalErrors > 0 || highRegs > 0) {
    state = 'INCIDENT';
    action = 'ROLLBACK_RECOMMENDED';
    reasons.push('Critical errors or high-severity regressions detected.');
  } else if (drift === 'MATERIAL_DRIFT') {
    state = 'INCIDENT';
    action = 'HOLD_ROLLOUT';
    reasons.push('Material drift detected.');
  } else if (event.evidence_completeness < 90 || drift === 'INSUFFICIENT_DATA' || event.health_signal === 'UNKNOWN') {
    state = 'DEGRADED';
    action = 'INVESTIGATE';
    reasons.push('Evidence or health signal is incomplete.');
  } else if (event.health_signal === 'DEGRADED') {
    state = 'DEGRADED';
    action = 'INVESTIGATE';
    reasons.push('Health signal reports degradation.');
  }

  return Object.freeze({
    operational_state: state,
    recommended_action: action,
    reasons: Object.freeze(reasons),
    owner_review_required: state !== 'HEALTHY',
    executes_rollback: false,
    production_mutation_allowed: false
  });
}

module.exports = { evaluateProductionHealth };
