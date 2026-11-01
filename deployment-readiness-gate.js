'use strict';

const HIGH_RISKS = new Set(['high','critical']);

function requireBool(value, field) {
  if (typeof value !== 'boolean') throw new Error(field + ' must be boolean');
  return value;
}

function evaluateDeploymentReadiness(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    throw new Error('deployment readiness input required');
  }

  const traffic = input.traffic_light;
  const barrier = input.error_barrier_state;
  if (!['GREEN','YELLOW','ORANGE','RED'].includes(traffic)) throw new Error('invalid traffic_light');
  if (!['PASS','WARN','BLOCK','ESCALATE'].includes(barrier)) throw new Error('invalid error_barrier_state');

  const approved = requireBool(input.human_approval_approved, 'human_approval_approved');
  const rollbackReady = requireBool(input.rollback_ready, 'rollback_ready');
  const verificationPlan = requireBool(input.post_action_verification_plan_ready, 'post_action_verification_plan_ready');

  const risks = Array.isArray(input.unresolved_risks) ? input.unresolved_risks : [];
  const hasHighRisk = risks.some(r => r && HIGH_RISKS.has(r.severity));

  let state = 'NOT_READY';
  let reason = 'Readiness requirements are incomplete.';

  if (traffic === 'RED' || barrier === 'ESCALATE') {
    state = 'ESCALATE';
    reason = 'Critical Control Tower or error-barrier state requires escalation.';
  } else if (traffic === 'ORANGE' || barrier === 'BLOCK') {
    state = 'BLOCKED';
    reason = 'High-risk or blocking condition prevents canary eligibility.';
  } else if (traffic === 'YELLOW' || barrier === 'WARN') {
    state = 'NOT_READY';
    reason = 'Warnings or incomplete evidence must be resolved before canary review.';
  } else if (!approved) {
    state = 'READY_FOR_OWNER_REVIEW';
    reason = 'Technical gates pass; HumanApprovalGate remains pending.';
  } else if (!rollbackReady || !verificationPlan || hasHighRisk) {
    state = 'BLOCKED';
    reason = 'Approved candidate still lacks rollback, verification, or risk clearance.';
  } else {
    state = 'READY_FOR_CANARY';
    reason = 'All deterministic pre-canary gates pass.';
  }

  return Object.freeze({
    readiness_state: state,
    reason,
    deploys: false,
    production_activation: false
  });
}

module.exports = { evaluateDeploymentReadiness };
