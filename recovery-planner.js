'use strict';

function requireString(value, field) {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error(field + ' must be a nonempty string');
  }
  return value.trim();
}

function createRecoveryProposal(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    throw new Error('recovery input required');
  }

  const severity = requireString(input.incident_severity, 'incident_severity');
  if (!['low','medium','high','critical'].includes(severity)) {
    throw new Error('invalid incident_severity');
  }

  if (!Array.isArray(input.tests) || input.tests.length === 0) {
    throw new Error('tests must be a nonempty array');
  }
  if (!Array.isArray(input.regression_tests) || input.regression_tests.length === 0) {
    throw new Error('regression_tests must be a nonempty array');
  }

  const proposal = {
    proposal_id: requireString(input.proposal_id, 'proposal_id'),
    incident_id: requireString(input.incident_id, 'incident_id'),
    target: requireString(input.target, 'target'),
    target_ref: requireString(input.target_ref, 'target_ref'),
    state: 'DRAFT',
    incident_severity: severity,
    root_cause_hypothesis: requireString(input.root_cause_hypothesis, 'root_cause_hypothesis'),
    change_summary: requireString(input.change_summary, 'change_summary'),
    permitted_scope: requireString(input.permitted_scope, 'permitted_scope'),
    rollback_target: requireString(input.rollback_target, 'rollback_target'),
    tests: Object.freeze(input.tests.map((v,i)=>requireString(v,'tests['+i+']'))),
    regression_tests: Object.freeze(input.regression_tests.map((v,i)=>requireString(v,'regression_tests['+i+']'))),
    evidence: Object.freeze(Array.isArray(input.evidence) ? input.evidence.map((v,i)=>requireString(v,'evidence['+i+']')) : []),
    known_risks: Object.freeze(Array.isArray(input.known_risks) ? [...input.known_risks] : []),
    unresolved_gaps: Object.freeze(Array.isArray(input.unresolved_gaps) ? [...input.unresolved_gaps] : []),
    requires_red_team: severity === 'high' || severity === 'critical',
    requires_human_approval: true,
    auto_apply_allowed: false,
    production_mutation_allowed: false
  };

  return Object.freeze(proposal);
}

function assessRecoveryReadiness(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    throw new Error('recovery assessment required');
  }

  const deterministicPass = input.deterministic_tests_passed === true;
  const regressionPass = input.regression_tests_passed === true;
  const redTeamPass = input.red_team_passed === true;
  const rollbackVerified = input.rollback_verified === true;
  const evidenceComplete = Number.isInteger(input.evidence_completeness) && input.evidence_completeness >= 90;
  const highSeverity = input.incident_severity === 'high' || input.incident_severity === 'critical';

  let state = 'TESTABLE';
  let route = 'RUN_TESTS';

  if (!rollbackVerified) {
    state = 'QUARANTINED';
    route = 'VERIFY_ROLLBACK';
  } else if (!deterministicPass || !regressionPass) {
    state = 'TESTABLE';
    route = 'REPAIR_AND_RETEST';
  } else if (highSeverity && !redTeamPass) {
    state = 'TESTED';
    route = 'RUN_RED_TEAM';
  } else if (!evidenceComplete) {
    state = 'TESTED';
    route = 'COLLECT_EVIDENCE';
  } else {
    state = 'REVIEW_READY';
    route = 'PREPARE_OWNER_REVIEW';
  }

  return Object.freeze({
    state,
    route,
    auto_apply_allowed: false,
    production_mutation_allowed: false,
    human_approval_required: true
  });
}

module.exports = { createRecoveryProposal, assessRecoveryReadiness };
