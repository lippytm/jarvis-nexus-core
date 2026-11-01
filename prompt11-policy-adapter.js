'use strict';

const fs = require('fs');
const path = require('path');

const DEFAULT_POLICY_PATH = path.join(__dirname, 'prompt11-policy.json');

function loadPolicy(policyPath = DEFAULT_POLICY_PATH) {
  const raw = fs.readFileSync(policyPath, 'utf8');
  return JSON.parse(raw);
}

function validatePrompt11Module(moduleRecord, policy = loadPolicy()) {
  if (!moduleRecord || typeof moduleRecord !== 'object') {
    throw new Error('Prompt #11 module record is required');
  }

  const required = ['module_id', 'version', 'state', 'source_repo', 'source_path', 'human_approval'];
  for (const field of required) {
    if (!(field in moduleRecord)) {
      throw new Error(`Prompt #11 module missing required field: ${field}`);
    }
  }

  if (moduleRecord.source_repo !== policy.canonical_repository) {
    throw new Error('Prompt #11 module source repository is not canonical');
  }

  if (!policy.allowed_states.includes(moduleRecord.state)) {
    throw new Error(`Prompt #11 module state is not consumable: ${moduleRecord.state}`);
  }

  if (policy.require_human_approval) {
    if (!moduleRecord.human_approval || moduleRecord.human_approval.approved !== true) {
      throw new Error('Prompt #11 module has not passed HumanApprovalGate');
    }
    if (!moduleRecord.human_approval.approver || !moduleRecord.human_approval.audit_reference) {
      throw new Error('Prompt #11 human approval evidence is incomplete');
    }
  }

  return Object.freeze({
    module_id: moduleRecord.module_id,
    version: moduleRecord.version,
    source_repo: moduleRecord.source_repo,
    source_path: moduleRecord.source_path,
    source_ref: moduleRecord.source_ref || null,
    approval_audit_reference: moduleRecord.human_approval.audit_reference
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
