'use strict';

const assert = require('assert');
const {
  loadPolicy,
  validatePrompt11Module,
  buildPrompt11Reference
} = require('./prompt11-policy-adapter');

const policy = loadPolicy();

assert.strictEqual(policy.production_injection_enabled, false);
assert.strictEqual(policy.reference_only, true);

const pending = {
  module_id: 'P-011-PEE-001',
  version: '0.1.0',
  state: 'review_ready',
  source_repo: 'lippytm/Prompt-11-',
  source_path: 'docs/P011-PEE-001-prompt-engineering-evolution-engine.md',
  human_approval: {
    approved: false,
    approver: null,
    audit_reference: null
  }
};

assert.throws(
  () => validatePrompt11Module(pending, policy),
  /state is not consumable|HumanApprovalGate/
);

const wrongRepo = {
  ...pending,
  state: 'approved',
  source_repo: 'example/not-canonical',
  human_approval: {
    approved: true,
    approver: 'owner',
    audit_reference: 'TEST-ONLY'
  }
};

assert.throws(
  () => validatePrompt11Module(wrongRepo, policy),
  /not canonical/
);

const approved = {
  module_id: 'P-011-XPIO-001',
  version: '1.0.0',
  state: 'approved',
  source_repo: 'lippytm/Prompt-11-',
  source_path: 'prompts/P011-XPIO-001-master-operating-prompt.md',
  source_ref: 'example-approved-ref',
  human_approval: {
    approved: true,
    approver: 'authorized-owner',
    audit_reference: 'TEST-FIXTURE-ONLY'
  }
};

const ref = buildPrompt11Reference(approved);
assert.strictEqual(ref.enforcement, 'reference-only');
assert.strictEqual(ref.module.module_id, 'P-011-XPIO-001');
assert.strictEqual(ref.module.source_repo, 'lippytm/Prompt-11-');
assert.strictEqual(ref.module.approval_audit_reference, 'TEST-FIXTURE-ONLY');

console.log('Prompt #11 adapter tests passed');
