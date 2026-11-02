'use strict';

const EVIDENCE_WEIGHT = Object.freeze({
  DETERMINISTIC_TEST: 5,
  PRIMARY_SOURCE: 4,
  REPOSITORY_ARTIFACT: 4,
  TOOL_OUTPUT: 4,
  SECONDARY_SOURCE: 3,
  USER_PROVIDED: 2,
  MODEL_ASSERTION: 1,
  SYNTHETIC_TEST_FIXTURE: 1
});

function arbitrateEvidence({ claim_type, supporting_evidence = [], contradicting_evidence = [] }) {
  if (typeof claim_type !== 'string' || claim_type.trim() === '') {
    throw new Error('claim_type is required');
  }

  const all = [...supporting_evidence, ...contradicting_evidence];
  for (const item of all) {
    if (!item || typeof item !== 'object') throw new Error('Evidence item is invalid');
    if (!(item.evidence_class in EVIDENCE_WEIGHT)) {
      throw new Error(`Unknown evidence class: ${item.evidence_class}`);
    }
    if (item.freshness === 'STALE') continue;
    if (typeof item.independence_group !== 'string' || item.independence_group.trim() === '') {
      throw new Error('Evidence independence_group is required');
    }
  }

  const currentSupport = supporting_evidence.filter(e => e.freshness !== 'STALE' && e.verification_state !== 'FAILED');
  const currentContradict = contradicting_evidence.filter(e => e.freshness !== 'STALE' && e.verification_state !== 'FAILED');

  if (claim_type === 'POLICY' && currentContradict.length > 0) {
    return Object.freeze({
      status: 'POLICY_CONFLICT',
      route: 'STOP_AND_ESCALATE',
      production_activation: false,
      human_approval_required: true
    });
  }

  if (claim_type === 'RISK' && currentContradict.length > 0) {
    return Object.freeze({
      status: 'RISK_CONFLICT',
      route: 'ROUTE_TO_DONT_DO_THAT',
      secondary_route: 'RUN_RED_TEAM',
      production_activation: false,
      human_approval_required: true
    });
  }

  if (claim_type === 'FACT' && currentContradict.length > 0) {
    return Object.freeze({
      status: 'FACT_CONFLICT',
      route: 'COLLECT_AUTHORITATIVE_EVIDENCE_OR_RUN_TEST',
      production_activation: false,
      human_approval_required: true
    });
  }

  if (currentSupport.length === 0) {
    const staleOnly = supporting_evidence.length > 0 && supporting_evidence.every(e => e.freshness === 'STALE');
    return Object.freeze({
      status: staleOnly ? 'STALE_EVIDENCE' : 'INSUFFICIENT_EVIDENCE',
      route: staleOnly ? 'REFRESH_EVIDENCE' : 'COLLECT_EVIDENCE',
      production_activation: false,
      human_approval_required: true
    });
  }

  const groups = new Set(currentSupport.map(e => e.independence_group));
  const allModelOnly = currentSupport.every(e => e.evidence_class === 'MODEL_ASSERTION');

  if (allModelOnly || groups.size === 1) {
    return Object.freeze({
      status: 'CIRCULAR_EVIDENCE',
      route: 'COLLECT_INDEPENDENT_EVIDENCE',
      production_activation: false,
      human_approval_required: true
    });
  }

  const strongestSupport = Math.max(...currentSupport.map(e => EVIDENCE_WEIGHT[e.evidence_class]));
  const strongestContradict = currentContradict.length
    ? Math.max(...currentContradict.map(e => EVIDENCE_WEIGHT[e.evidence_class]))
    : 0;

  if (strongestContradict >= strongestSupport) {
    return Object.freeze({
      status: 'CONTRADICTED',
      route: claim_type === 'DESIGN' ? 'RUN_COMPARATIVE_EVAL' : 'COLLECT_EVIDENCE',
      production_activation: false,
      human_approval_required: true
    });
  }

  const verifiedIndependent = currentSupport.filter(
    e => e.verification_state === 'VERIFIED' && e.evidence_class !== 'MODEL_ASSERTION'
  );

  if (verifiedIndependent.length >= 1 && groups.size >= 2) {
    return Object.freeze({
      status: 'VERIFIED_SUPPORT',
      route: 'PREPARE_OWNER_REVIEW',
      production_activation: false,
      human_approval_required: true
    });
  }

  return Object.freeze({
    status: 'PROVISIONAL_SUPPORT',
    route: 'COLLECT_EVIDENCE',
    production_activation: false,
    human_approval_required: true
  });
}

module.exports = { arbitrateEvidence };
