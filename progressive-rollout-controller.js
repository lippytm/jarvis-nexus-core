'use strict';

const STAGES = Object.freeze(['CANARY','LIMITED','PARTIAL','BROAD','FULL']);

function nextStage(stage) {
  const i = STAGES.indexOf(stage);
  if (i < 0) throw new Error('invalid rollout stage');
  return i === STAGES.length - 1 ? stage : STAGES[i + 1];
}

function decideRolloutStage(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    throw new Error('rollout input required');
  }

  const current = input.current_stage;
  if (!STAGES.includes(current)) throw new Error('invalid rollout stage');

  const rec = input.post_canary_recommendation;
  if (!['CONTINUE','HOLD','ROLLBACK','ESCALATE'].includes(rec)) {
    throw new Error('invalid post_canary_recommendation');
  }

  const drift = input.drift_class;
  if (!['NO_DRIFT','IMPROVEMENT','ACCEPTABLE_DRIFT','MATERIAL_DRIFT','CRITICAL_DRIFT','INSUFFICIENT_DATA'].includes(drift)) {
    throw new Error('invalid drift_class');
  }

  if (typeof input.human_approval_approved !== 'boolean') throw new Error('human_approval_approved must be boolean');
  if (typeof input.rollback_ready !== 'boolean') throw new Error('rollback_ready must be boolean');

  const highRisk = Array.isArray(input.unresolved_risks) &&
    input.unresolved_risks.some(r => r && ['high','critical'].includes(r.severity));

  let action = 'HOLD';
  let recommendedStage = current;
  let rationale = 'Remain at current rollout stage.';

  if (rec === 'ESCALATE') {
    action = 'ESCALATE';
    rationale = 'Post-canary verification requires escalation.';
  } else if (rec === 'ROLLBACK' || drift === 'MATERIAL_DRIFT' || drift === 'CRITICAL_DRIFT') {
    action = 'ROLLBACK';
    recommendedStage = 'CANARY';
    rationale = 'Rollback to the approved baseline/canary-safe state is recommended.';
  } else if (rec === 'HOLD' || drift === 'INSUFFICIENT_DATA') {
    action = 'HOLD';
    rationale = 'Evidence is insufficient or verification is incomplete.';
  } else if (!input.human_approval_approved) {
    action = 'HOLD';
    rationale = 'HumanApprovalGate is required before rollout expansion.';
  } else if (!input.rollback_ready || highRisk) {
    action = 'HOLD';
    rationale = 'Rollback readiness and high-risk clearance are required before expansion.';
  } else if (rec === 'CONTINUE') {
    if (drift === 'NO_DRIFT' || drift === 'IMPROVEMENT' || drift === 'ACCEPTABLE_DRIFT') {
      action = current === 'FULL' ? 'HOLD' : 'ADVANCE_ONE_STAGE';
      recommendedStage = nextStage(current);
      rationale = current === 'FULL'
        ? 'Already at FULL; no further rollout stage exists.'
        : 'Advance by exactly one stage under owner-approved controls.';
    }
  }

  return Object.freeze({
    action,
    current_stage: current,
    recommended_stage: recommendedStage,
    deploys: false,
    executes_rollback: false,
    production_activation: false
  });
}

module.exports = { STAGES, decideRolloutStage };
