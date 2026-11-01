'use strict';

function nonEmptyString(value, field) {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error(field + ' must be a nonempty string');
  }
  return value.trim();
}

function validateCanaryManifest(manifest) {
  if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest)) {
    throw new Error('canary manifest is required');
  }

  const stringFields = [
    'canary_id','target','candidate_ref','baseline_ref','task_class','scope',
    'rollback_target','rollback_procedure_reference',
    'post_canary_verification_plan','evidence_collection_plan'
  ];
  for (const field of stringFields) nonEmptyString(manifest[field], field);

  if (!Number.isInteger(manifest.max_runs) || manifest.max_runs < 1 || manifest.max_runs > 1000) {
    throw new Error('max_runs must be an integer from 1 to 1000');
  }

  for (const field of ['success_criteria','failure_criteria','stop_conditions']) {
    if (!Array.isArray(manifest[field]) || manifest[field].length === 0) {
      throw new Error(field + ' must be a nonempty array');
    }
    for (let i = 0; i < manifest[field].length; i += 1) {
      if (!Object.prototype.hasOwnProperty.call(manifest[field], i)) {
        throw new Error(field + ' contains a sparse entry');
      }
      nonEmptyString(manifest[field][i], field + '[' + i + ']');
    }
  }

  if (!manifest.human_approval || typeof manifest.human_approval !== 'object') {
    throw new Error('human_approval record is required');
  }
  if (manifest.human_approval.approved !== true) {
    throw new Error('HumanApprovalGate is required for canary eligibility');
  }
  nonEmptyString(manifest.human_approval.approver, 'human_approval.approver');
  nonEmptyString(manifest.human_approval.audit_reference, 'human_approval.audit_reference');

  if (manifest.production_activation !== false) {
    throw new Error('canary manifest must remain non-production');
  }

  return Object.freeze({
    canary_id: manifest.canary_id,
    target: manifest.target,
    candidate_ref: manifest.candidate_ref,
    baseline_ref: manifest.baseline_ref,
    max_runs: manifest.max_runs,
    ready_for_canary_execution_review: true,
    deploys: false,
    production_activation: false
  });
}

module.exports = { validateCanaryManifest };
