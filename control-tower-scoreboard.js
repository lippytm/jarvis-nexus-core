'use strict';

const SEVERITY_RANK = Object.freeze({ low: 1, medium: 2, high: 3, critical: 4 });
const ERROR_STATES = Object.freeze(new Set(['PASS','WARN','BLOCK','ESCALATE']));

function requireObject(value, field) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`Control Tower field must be an object: ${field}`);
  }
  return value;
}

function hasFailedCriticalGate(gates) {
  const obj = requireObject(gates, 'critical_gates');
  const names = Object.keys(obj);
  if (names.length === 0) throw new Error('Control Tower requires at least one critical gate');
  return names.some(name => obj[name] !== true);
}

function unresolvedMaxSeverity(risks) {
  if (!Array.isArray(risks)) throw new Error('Control Tower risks must be an array');
  let max = 0;
  for (const risk of risks) {
    if (!risk || typeof risk !== 'object') throw new Error('Control Tower risk record is invalid');
    if (!(risk.severity in SEVERITY_RANK)) throw new Error(`Unknown risk severity: ${risk.severity}`);
    if (risk.resolved !== true) max = Math.max(max, SEVERITY_RANK[risk.severity]);
  }
  return max;
}

function hasFailedRequiredRegression(regressions) {
  if (!Array.isArray(regressions)) throw new Error('Control Tower regressions must be an array');
  return regressions.some(r => {
    if (!r || typeof r !== 'object') throw new Error('Control Tower regression record is invalid');
    if (!(r.severity in SEVERITY_RANK)) throw new Error(`Unknown regression severity: ${r.severity}`);
    return r.passed !== true && SEVERITY_RANK[r.severity] >= SEVERITY_RANK.high;
  });
}

function scoreControlTower(packet) {
  requireObject(packet, 'packet');
  requireObject(packet.best_practice, 'best_practice');
  requireObject(packet.human_approval, 'human_approval');

  const numericScore = packet.best_practice.score;
  if (!Number.isInteger(numericScore) || numericScore < 0 || numericScore > 100) {
    throw new Error('Control Tower best-practice score must be an integer from 0 to 100');
  }

  const evidence = packet.evidence_completeness;
  if (!Number.isInteger(evidence) || evidence < 0 || evidence > 100) {
    throw new Error('Control Tower evidence completeness must be an integer from 0 to 100');
  }

  const errorBarrierState = packet.error_barrier_state || 'PASS';
  if (!ERROR_STATES.has(errorBarrierState)) {
    throw new Error('Unknown error barrier state');
  }

  const failedGate = hasFailedCriticalGate(packet.critical_gates);
  const maxRisk = unresolvedMaxSeverity(packet.risks);
  const failedRegression = hasFailedRequiredRegression(packet.regressions);
  const rollbackMissing = packet.rollback_ready !== true;
  const bestPracticeBlocked = packet.best_practice.promotion_blocked === true;
  const ownerApprovalPending = packet.human_approval.approved !== true;

  let state = 'GREEN';

  if (
    failedGate ||
    maxRisk >= SEVERITY_RANK.critical ||
    errorBarrierState === 'ESCALATE'
  ) {
    state = 'RED';
  } else if (
    maxRisk >= SEVERITY_RANK.high ||
    failedRegression ||
    rollbackMissing ||
    bestPracticeBlocked ||
    errorBarrierState === 'BLOCK'
  ) {
    state = 'ORANGE';
  } else if (
    evidence < 90 ||
    numericScore < 90 ||
    errorBarrierState === 'WARN' ||
    (Array.isArray(packet.model_disagreements) && packet.model_disagreements.length > 0)
  ) {
    state = 'YELLOW';
  }

  const promotionBlocked =
    state === 'RED' ||
    state === 'ORANGE' ||
    ownerApprovalPending;

  return Object.freeze({
    traffic_light: state,
    best_practice_score: numericScore,
    evidence_completeness: evidence,
    error_barrier_state: errorBarrierState,
    failed_critical_gate: failedGate,
    unresolved_max_risk_rank: maxRisk,
    failed_required_regression: failedRegression,
    rollback_missing: rollbackMissing,
    best_practice_blocked: bestPracticeBlocked,
    human_approval_pending: ownerApprovalPending,
    promotion_blocked: promotionBlocked,
    production_activation: false
  });
}

module.exports = { scoreControlTower };
