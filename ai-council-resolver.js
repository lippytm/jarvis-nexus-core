'use strict';

const CRITICAL_CLASSES = Object.freeze(new Set(['POLICY']));
const DISAGREEMENT_CLASSES = Object.freeze(new Set([
  'FACTUAL','INTERPRETATION','DESIGN','RISK','EVIDENCE','POLICY','COST_PERFORMANCE','UNKNOWN'
]));

function requireArray(value, field) {
  if (!Array.isArray(value) || value.length === 0) {
    throw new Error(`AI Council field must be a nonempty array: ${field}`);
  }
  return value;
}

function resolveCouncil({ positions, disagreements = [], deterministic_tests_passed = false }) {
  const members = requireArray(positions, 'positions');

  const memberIds = new Set();
  for (const p of members) {
    if (!p || typeof p !== 'object') throw new Error('AI Council position record is invalid');
    if (typeof p.member_id !== 'string' || p.member_id.trim() === '') throw new Error('AI Council member_id required');
    if (memberIds.has(p.member_id)) throw new Error(`Duplicate AI Council member_id: ${p.member_id}`);
    memberIds.add(p.member_id);
  }

  let critical = false;
  let factual = false;
  let risk = false;
  let evidence = false;
  let materialCount = 0;

  for (const d of disagreements) {
    if (!d || typeof d !== 'object') throw new Error('AI Council disagreement record is invalid');
    if (!DISAGREEMENT_CLASSES.has(d.class)) throw new Error(`Unknown disagreement class: ${d.class}`);
    if (d.resolved !== true) {
      materialCount += 1;
      if (CRITICAL_CLASSES.has(d.class) || d.critical === true) critical = true;
      if (d.class === 'FACTUAL') factual = true;
      if (d.class === 'RISK') risk = true;
      if (d.class === 'EVIDENCE') evidence = true;
    }
  }

  const supportedPositions = members.filter(p => Array.isArray(p.evidence) && p.evidence.length > 0);
  const allSame = members.every(p => p.position === members[0].position);

  let consensus;
  let route;

  if (critical) {
    consensus = 'BLOCKED_DISAGREEMENT';
    route = 'STOP_AND_ESCALATE';
  } else if (factual) {
    consensus = 'SPLIT_DECISION';
    route = 'COLLECT_AUTHORITATIVE_EVIDENCE_OR_RUN_TEST';
  } else if (risk) {
    consensus = 'SPLIT_DECISION';
    route = 'APPLY_CONSERVATIVE_RISK_STATE_AND_RED_TEAM';
  } else if (evidence) {
    consensus = 'INSUFFICIENT_EVIDENCE';
    route = 'COLLECT_EVIDENCE';
  } else if (materialCount > 0) {
    consensus = 'SPLIT_DECISION';
    route = 'RUN_COMPARATIVE_EVAL';
  } else if (allSame && supportedPositions.length === members.length && deterministic_tests_passed === true) {
    consensus = 'VERIFIED_CONSENSUS';
    route = 'PREPARE_OWNER_REVIEW';
  } else if (allSame && supportedPositions.length === members.length) {
    consensus = 'PROVISIONAL_CONSENSUS';
    route = 'RUN_DETERMINISTIC_TESTS';
  } else if (allSame) {
    consensus = 'PROVISIONAL_CONSENSUS';
    route = 'COLLECT_EVIDENCE';
  } else {
    consensus = 'SPLIT_DECISION';
    route = 'RUN_COMPARATIVE_EVAL';
  }

  return Object.freeze({
    consensus,
    resolution_route: route,
    participating_members: members.length,
    unresolved_disagreements: materialCount,
    minority_positions_preserved: true,
    majority_vote_used_for_truth: false,
    production_activation: false,
    human_approval_required: true
  });
}

module.exports = { resolveCouncil };
