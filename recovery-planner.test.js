'use strict';

const assert = require('assert');
const { createRecoveryProposal, assessRecoveryReadiness } = require('./recovery-planner');

const base = {
  proposal_id: 'REC-001',
  incident_id: 'INC-001',
  target: 'jarvis-nexus-core',
  target_ref: 'bad-ref',
  incident_severity: 'high',
  root_cause_hypothesis: 'A bounded routing regression caused the incident.',
  change_summary: 'Adjust routing condition only.',
  permitted_scope: 'Routing condition and related tests only.',
  rollback_target: 'approved-baseline',
  tests: ['unit-test'],
  regression_tests: ['incident-regression-test'],
  evidence: ['INC-001 evidence'],
  known_risks: ['Potential routing regression'],
  unresolved_gaps: []
};

const proposal = createRecoveryProposal(base);
assert.strictEqual(proposal.state, 'DRAFT');
assert.strictEqual(proposal.requires_red_team, true);
assert.strictEqual(proposal.auto_apply_allowed, false);
assert.strictEqual(proposal.production_mutation_allowed, false);
assert.ok(Object.isFrozen(proposal));
assert.ok(Object.isFrozen(proposal.tests));

assert.throws(
  () => createRecoveryProposal({ ...base, rollback_target: '' }),
  /rollback_target/
);

assert.throws(
  () => createRecoveryProposal({ ...base, tests: [] }),
  /tests must be a nonempty array/
);

let r = assessRecoveryReadiness({
  incident_severity: 'high',
  deterministic_tests_passed: false,
  regression_tests_passed: false,
  red_team_passed: false,
  rollback_verified: true,
  evidence_completeness: 95
});
assert.strictEqual(r.route, 'REPAIR_AND_RETEST');

r = assessRecoveryReadiness({
  incident_severity: 'high',
  deterministic_tests_passed: true,
  regression_tests_passed: true,
  red_team_passed: false,
  rollback_verified: true,
  evidence_completeness: 95
});
assert.strictEqual(r.route, 'RUN_RED_TEAM');

r = assessRecoveryReadiness({
  incident_severity: 'high',
  deterministic_tests_passed: true,
  regression_tests_passed: true,
  red_team_passed: true,
  rollback_verified: true,
  evidence_completeness: 95
});
assert.strictEqual(r.state, 'REVIEW_READY');
assert.strictEqual(r.route, 'PREPARE_OWNER_REVIEW');

r = assessRecoveryReadiness({
  incident_severity: 'critical',
  deterministic_tests_passed: true,
  regression_tests_passed: true,
  red_team_passed: true,
  rollback_verified: false,
  evidence_completeness: 100
});
assert.strictEqual(r.state, 'QUARANTINED');
assert.strictEqual(r.route, 'VERIFY_ROLLBACK');
assert.strictEqual(r.auto_apply_allowed, false);
assert.strictEqual(r.production_mutation_allowed, false);

console.log('P11-PEE-018 recovery planner tests passed');
