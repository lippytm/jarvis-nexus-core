'use strict';

const fs = require('fs');
const path = require('path');

const DEFAULT_POLICY_PATH = path.join(__dirname, 'prompt11-policy.json');

function loadPolicy(policyPath = DEFAULT_POLICY_PATH) {
  const raw = fs.readFileSync(policyPath, 'utf8');
  return JSON.parse(raw);
}

function requireNonEmptyString(value, field) {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new Error(`Prompt #11 module field must be a nonempty string: ${field}`);
  }
  return value.trim();
}

function validatePrompt11Module(moduleRecord, policy = loadPolicy()) {
  if (!moduleRecord || typeof moduleRecord !== 'object' || Array.isArray(moduleRecord)) {
    throw new Error('Prompt #11 module record is required');
  }

  const required = ['module_id', 'version', 'state', 'source_repo', 'source_path', 'human_approval'];
  for (const field of required) {
    if (!(field in moduleRecord)) {
      throw new Error(`Prompt #11 module missing required field: ${field}`);
    }
  }

  const moduleId = requireNonEmptyString(moduleRecord.module_id, 'module_id');
  const version = requireNonEmptyString(moduleRecord.version, 'version');
  const state = requireNonEmptyString(moduleRecord.state, 'state');
  const sourceRepo = requireNonEmptyString(moduleRecord.source_repo, 'source_repo');
  const sourcePath = requireNonEmptyString(moduleRecord.source_path, 'source_path');

  let sourceRef = null;
  if (moduleRecord.source_ref !== undefined && moduleRecord.source_ref !== null) {
    sourceRef = requireNonEmptyString(moduleRecord.source_ref, 'source_ref');
  }

  if (sourceRepo !== policy.canonical_repository) {
    throw new Error('Prompt #11 module source repository is not canonical');
  }

  if (!Array.isArray(policy.allowed_states) || !policy.allowed_states.includes(state)) {
    throw new Error(`Prompt #11 module state is not consumable: ${state}`);
  }

  if (!moduleRecord.human_approval || typeof moduleRecord.human_approval !== 'object' || Array.isArray(moduleRecord.human_approval)) {
    throw new Error('Prompt #11 human approval record is required');
  }

  let approver = null;
  let auditReference = null;

  if (policy.require_human_approval) {
    if (moduleRecord.human_approval.approved !== true) {
      throw new Error('Prompt #11 module has not passed HumanApprovalGate');
    }
    approver = requireNonEmptyString(moduleRecord.human_approval.approver, 'human_approval.approver');
    auditReference = requireNonEmptyString(moduleRecord.human_approval.audit_reference, 'human_approval.audit_reference');
  }

  return Object.freeze({
    module_id: moduleId,
    version,
    source_repo: sourceRepo,
    source_path: sourcePath,
    source_ref: sourceRef,
    approval_audit_reference: auditReference,
    approver
  });
}

function buildPrompt11Reference(moduleRecord, policyPath) {
  const policy = loadPolicy(policyPath);
  const validated = validatePrompt11Module(moduleRecord, policy);

  return Object.freeze({
    policy_id: policy.policy_id,
    canonical_repository: policy.canonical_repository,
    module: validated,
    enforcement: 'reference-only',
    note: 'This adapter validates Prompt #11 governance metadata only. It does not fetch, inject, execute, deploy, or synchronize prompt content.'
  });
}

module.exports = {
  DEFAULT_POLICY_PATH,
  loadPolicy,
  validatePrompt11Module,
  buildPrompt11Reference
};
