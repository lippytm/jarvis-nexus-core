'use strict';

const ORDER = Object.freeze([
  'STOP_AND_ESCALATE',
  'QUARANTINE',
  'REPAIR_REGRESSION',
  'COMPLETE_ROLLBACK',
  'COLLECT_EVIDENCE',
  'RUN_RED_TEAM',
  'ROUTE_TO_FAILURE_FORENSICS',
  'RESOLVE_MODEL_DISAGREEMENT',
  'ROUTE_TO_DONT_DO_THAT',
  'ROUTE_TO_MAYBE',
  'ROUTE_TO_WHY_NOT',
  'ROUTE_TO_IF',
  'RUN_COMPARATIVE_EVAL',
  'REDUCE_CONTEXT',
  'PREPARE_OWNER_REVIEW',
  'PREPARE_CANARY',
  'CONTINUE_BOUNDED_BUILD'
]);

function requireObject(value, field) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`Priority engine field must be an object: ${field}`);
  }
  return value;
}

function rankNextAction(controlTower) {
  requireObject(controlTower, 'controlTower');

  const state = controlTower.traffic_light;
  const failedGate = controlTower.failed_critical_gate === true;
  const failedRegression = controlTower.failed_required_regression === true;
  const rollbackMissing = controlTower.rollback_missing === true;
  const evidence = controlTower.evidence_completeness;
  const approvalPending = controlTower.human_approval_pending === true;
  const modelDisagreement = controlTower.model_disagreement_present === true;
  const redTeamMissing = controlTower.red_team_required === true && controlTower.red_team_complete !== true;
  const failureIncident = controlTower.failure_incident_open === true;

  let action;
  let rationale;

  if (state === 'RED' || failedGate) {
    action = 'STOP_AND_ESCALATE';
    rationale = 'Critical gate failure or RED state requires stop, containment, and owner escalation.';
  } else if (failureIncident) {
    action = 'ROUTE_TO_FAILURE_FORENSICS';
    rationale = 'Open incident requires I Told You Not To Do That failure-forensics routing.';
  } else if (failedRegression) {
    action = 'REPAIR_REGRESSION';
    rationale = 'Failed required regression outranks new feature work.';
  } else if (rollbackMissing) {
    action = 'COMPLETE_ROLLBACK';
    rationale = 'Rollback/recovery must be ready before material change proceeds.';
  } else if (state === 'ORANGE') {
    action = 'QUARANTINE';
    rationale = 'ORANGE state indicates unresolved high-risk conditions that block promotion.';
  } else if (!Number.isInteger(evidence) || evidence < 90) {
    action = 'COLLECT_EVIDENCE';
    rationale = 'Evidence completeness is below the owner-review threshold.';
  } else if (redTeamMissing) {
    action = 'RUN_RED_TEAM';
    rationale = 'Required red-team review is incomplete.';
  } else if (modelDisagreement) {
    action = 'RESOLVE_MODEL_DISAGREEMENT';
    rationale = 'Model disagreement must be compared against evidence before promotion.';
  } else if (state === 'YELLOW') {
    action = 'RUN_COMPARATIVE_EVAL';
    rationale = 'YELLOW state without stronger blocker requires comparative evaluation.';
  } else if (state === 'GREEN' && approvalPending) {
    action = 'PREPARE_OWNER_REVIEW';
    rationale = 'All deterministic gates are ready for owner review; approval remains external.';
  } else if (state === 'GREEN' && approvalPending === false) {
    action = 'PREPARE_CANARY';
    rationale = 'Approved GREEN state may proceed only to a bounded controlled canary.';
  } else {
    action = 'CONTINUE_BOUNDED_BUILD';
    rationale = 'No higher-priority blocker is present; continue the smallest reversible build step.';
  }

  return Object.freeze({
    action,
    priority_rank: ORDER.indexOf(action) + 1,
    rationale,
    executes_action: false,
    production_activation: false
  });
}

module.exports = { ORDER, rankNextAction };
