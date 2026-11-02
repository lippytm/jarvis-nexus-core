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

const base = {
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

const pendingState = {
  ...base,
  state: 'review_ready',
  human_approval: { approved: false, approver: null, audit_reference: null }
};
assert.throws(
  () => validatePrompt11Module(pendingState, policy),
  /state is not consumable/
);

const approvalFalse = {
  ...base,
  human_approval: { approved: false, approver: 'authorized-owner', audit_reference: 'TEST' }
};
assert.throws(
  () => validatePrompt11Module(approvalFalse, policy),
  /HumanApprovalGate/
);

const missingApprover = {
  ...base,
  human_approval: { approved: true, approver: '', audit_reference: 'TEST' }
};
assert.throws(
  () => validatePrompt11Module(missingApprover, policy),
  /human_approval\.approver/
);

const missingAudit = {
  ...base,
  human_approval: { approved: true, approver: 'authorized-owner', audit_reference: null }
};
assert.throws(
  () => validatePrompt11Module(missingAudit, policy),
  /human_approval\.audit_reference/
);

const wrongRepo = {
  ...base,
  source_repo: 'example/not-canonical'
};
assert.throws(
  () => validatePrompt11Module(wrongRepo, policy),
  /not canonical/
);

for (const [field, value] of [
  ['module_id', null],
  ['version', ''],
  ['source_path', null],
  ['source_ref', {}]
]) {
  const invalid = { ...base, [field]: value };
  assert.throws(() => validatePrompt11Module(invalid, policy), /nonempty string/);
}

const ref = buildPrompt11Reference(base);
assert.strictEqual(ref.enforcement, 'reference-only');
assert.strictEqual(ref.module.module_id, 'P-011-XPIO-001');
assert.strictEqual(ref.module.source_repo, 'lippytm/Prompt-11-');
assert.strictEqual(ref.module.approval_audit_reference, 'TEST-FIXTURE-ONLY');
assert.ok(Object.isFrozen(ref), 'reference wrapper must be frozen');
assert.ok(Object.isFrozen(ref.module), 'module descriptor must be frozen');

console.log('Prompt #11 adapter tests passed');
