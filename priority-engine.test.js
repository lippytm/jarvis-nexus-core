'use strict';

const assert = require('assert');
const { rankNextAction } = require('./priority-engine');

function base() {
  return {
    traffic_light: 'GREEN',
    failed_critical_gate: false,
    failed_required_regression: false,
    rollback_missing: false,
    evidence_completeness: 95,
    human_approval_pending: true,
    model_disagreement_present: false,
    red_team_required: false,
    red_team_complete: true,
    failure_incident_open: false
  };
}

assert.strictEqual(
  rankNextAction({ ...base(), traffic_light: 'RED' }).action,
  'STOP_AND_ESCALATE'
);

assert.strictEqual(
  rankNextAction({ ...base(), failure_incident_open: true }).action,
  'ROUTE_TO_FAILURE_FORENSICS'
);

assert.strictEqual(
  rankNextAction({ ...base(), failed_required_regression: true }).action,
  'REPAIR_REGRESSION'
);

assert.strictEqual(
  rankNextAction({ ...base(), rollback_missing: true }).action,
  'COMPLETE_ROLLBACK'
);

assert.strictEqual(
  rankNextAction({ ...base(), traffic_light: 'ORANGE' }).action,
  'QUARANTINE'
);

assert.strictEqual(
  rankNextAction({ ...base(), evidence_completeness: 75 }).action,
  'COLLECT_EVIDENCE'
);

assert.strictEqual(
  rankNextAction({ ...base(), red_team_required: true, red_team_complete: false }).action,
  'RUN_RED_TEAM'
);

assert.strictEqual(
  rankNextAction({ ...base(), model_disagreement_present: true }).action,
  'RESOLVE_MODEL_DISAGREEMENT'
);

assert.strictEqual(
  rankNextAction({ ...base(), traffic_light: 'YELLOW' }).action,
  'RUN_COMPARATIVE_EVAL'
);

assert.strictEqual(
  rankNextAction(base()).action,
  'PREPARE_OWNER_REVIEW'
);

assert.strictEqual(
  rankNextAction({ ...base(), human_approval_pending: false }).action,
  'PREPARE_CANARY'
);

const result = rankNextAction(base());
assert.strictEqual(result.executes_action, false);
assert.strictEqual(result.production_activation, false);
assert.ok(Object.isFrozen(result));

console.log('P11-PEE-007 priority engine tests passed');
