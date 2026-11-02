'use strict';

const REQUIRED_GATES = Object.freeze([
  'authority',
  'privacy_security',
  'evidence_provenance',
  'testing',
  'risk',
  'rollback_recovery'
]);

function requireString(value, field) {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error(`Best-practice attestation field must be a nonempty string: ${field}`);
  }
  return value.trim();
}

function validateBestPracticeAttestation(attestation) {
  if (!attestation || typeof attestation !== 'object' || Array.isArray(attestation)) {
    throw new Error('Best-practice attestation is required');
  }

  requireString(attestation.attestation_id, 'attestation_id');
  requireString(attestation.work_packet_id, 'work_packet_id');

  if (!Array.isArray(attestation.applicable_domains) || attestation.applicable_domains.length === 0) {
    throw new Error('At least one applicable best-practice domain is required');
  }

  for (let i = 0; i < attestation.applicable_domains.length; i += 1) {
    requireString(attestation.applicable_domains[i], `applicable_domains[${i}]`);
  }

  if (!attestation.critical_gates || typeof attestation.critical_gates !== 'object') {
    throw new Error('critical_gates are required');
  }

  const failed = [];
  for (const gate of REQUIRED_GATES) {
    if (attestation.critical_gates[gate] !== true) {
      failed.push(gate);
    }
  }

  if (attestation.production_activation !== false) {
    throw new Error('Best-practice attestation must remain non-production');
  }

  const approval = attestation.human_approval;
  if (!approval || typeof approval !== 'object') {
    throw new Error('human_approval record is required');
  }

  if (approval.approved === true) {
    requireString(approval.approver, 'human_approval.approver');
    requireString(approval.audit_reference, 'human_approval.audit_reference');
  }

  return Object.freeze({
    attestation_id: attestation.attestation_id,
    work_packet_id: attestation.work_packet_id,
    all_critical_gates_passed: failed.length === 0,
    failed_critical_gates: Object.freeze(failed),
    promotion_blocked: failed.length > 0 || approval.approved !== true,
    production_activation: false
  });
}

module.exports = {
  REQUIRED_GATES,
  validateBestPracticeAttestation
};
