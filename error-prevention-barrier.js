'use strict';

const SENSITIVE_CLASSES = new Set([
  'PERMISSION_ERROR',
  'APPROVAL_ERROR',
  'RECOVERY_ERROR'
]);

function evaluateErrorBarrier(check) {
  if (!check || typeof check !== 'object' || Array.isArray(check)) {
    throw new Error('check object required');
  }

  const severities = new Set(['low','medium','high','critical']);
  if (!severities.has(check.severity)) {
    throw new Error('invalid severity');
  }

  if (typeof check.error_class !== 'string' || !check.error_class.trim()) {
    throw new Error('error_class required');
  }

  for (const field of [
    'irreversible_action',
    'explicit_confirmation_recorded',
    'rollback_ready',
    'post_action_verification_required'
  ]) {
    if (typeof check[field] !== 'boolean') {
      throw new Error(field + ' must be boolean');
    }
  }

  let state = 'PASS';
  const reasons = [];

  if (check.severity === 'critical' || SENSITIVE_CLASSES.has(check.error_class)) {
    state = 'ESCALATE';
    reasons.push('critical or authority-sensitive error');
  } else if (check.severity === 'high') {
    state = 'BLOCK';
    reasons.push('high-severity error');
  } else if (check.severity === 'medium') {
    state = 'WARN';
    reasons.push('medium-severity warning');
  }

  if (check.irreversible_action && !check.explicit_confirmation_recorded) {
    state = 'BLOCK';
    reasons.push('missing explicit confirmation');
  }

  if (check.irreversible_action && !check.rollback_ready) {
    state = 'BLOCK';
    reasons.push('rollback not ready');
  }

  if (!check.post_action_verification_required && state === 'PASS') {
    state = 'WARN';
    reasons.push('post-action verification not required');
  }

  return Object.freeze({
    barrier_state: state,
    progression_blocked: state === 'BLOCK' || state === 'ESCALATE',
    reasons: Object.freeze(reasons),
    production_activation: false
  });
}

const evaluateBarrier = evaluateErrorBarrier;

module.exports = { evaluateErrorBarrier, evaluateBarrier };
