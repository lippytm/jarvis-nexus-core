'use strict';

function requireInt(value, field, min, max) {
  if (!Number.isInteger(value) || value < min || value > max) {
    throw new Error(field + ' must be an integer from ' + min + ' to ' + max);
  }
  return value;
}

function evaluateCandidate(candidate) {
  if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) {
    throw new Error('repair candidate required');
  }

  const gates = candidate.critical_gates;
  if (!gates || typeof gates !== 'object' || Array.isArray(gates)) {
    throw new Error('critical_gates required');
  }

  const requiredGates = [
    'rollback_verified',
    'deterministic_tests_passed',
    'regression_tests_passed',
    'risk_clear',
    'scope_within_bounds',
    'security_privacy_authority_passed'
  ];

  const failedGates = requiredGates.filter(g => gates[g] !== true);

  const subscores = {
    deterministic_tests: requireInt(candidate.deterministic_tests, 'deterministic_tests', 0, 20),
    regression_coverage: requireInt(candidate.regression_coverage, 'regression_coverage', 0, 20),
    reversibility: requireInt(candidate.reversibility, 'reversibility', 0, 15),
    evidence_completeness: requireInt(candidate.evidence_completeness, 'evidence_completeness', 0, 15),
    scope_discipline: requireInt(candidate.scope_discipline, 'scope_discipline', 0, 10),
    risk_reduction: requireInt(candidate.risk_reduction, 'risk_reduction', 0, 10),
    maintainability: requireInt(candidate.maintainability, 'maintainability', 0, 5),
    cost_performance: requireInt(candidate.cost_performance, 'cost_performance', 0, 5)
  };

  const score = Object.values(subscores).reduce((a,b)=>a+b,0);

  let recommendation = 'READY_FOR_OWNER_REVIEW';
  if (failedGates.includes('rollback_verified')) recommendation = 'VERIFY_ROLLBACK';
  else if (failedGates.includes('deterministic_tests_passed') || failedGates.includes('regression_tests_passed')) recommendation = 'REPAIR_AND_RETEST';
  else if (failedGates.includes('scope_within_bounds')) recommendation = 'REDUCE_SCOPE';
  else if (failedGates.includes('risk_clear') || failedGates.includes('security_privacy_authority_passed')) recommendation = 'QUARANTINE';
  else if (score < 70) recommendation = 'COLLECT_EVIDENCE';

  return Object.freeze({
    candidate_id: candidate.candidate_id,
    score,
    critical_gates_passed: failedGates.length === 0,
    failed_critical_gates: Object.freeze(failedGates),
    recommendation,
    production_mutation_allowed: false,
    human_approval_required: true
  });
}

function rankRepairCandidates(candidates) {
  if (!Array.isArray(candidates) || candidates.length === 0) {
    throw new Error('repair candidates must be a nonempty array');
  }

  const evaluated = candidates.map(evaluateCandidate);

  const ranked = [...evaluated].sort((a,b) => {
    if (a.critical_gates_passed !== b.critical_gates_passed) {
      return a.critical_gates_passed ? -1 : 1;
    }
    if (a.score !== b.score) return b.score - a.score;
    return String(a.candidate_id).localeCompare(String(b.candidate_id));
  }).map((x,i) => Object.freeze({...x, rank:i+1}));

  return Object.freeze(ranked);
}

module.exports = { evaluateCandidate, rankRepairCandidates };
