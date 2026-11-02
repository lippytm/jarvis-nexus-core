'use strict';

const assert = require('assert');
const { validateBestPracticeAttestation } = require('./best-practice-attestation');

const base = {
  attestation_id: 'BPA-TEST-001',
  work_packet_id: 'WP-TEST-001',
  applicable_domains: ['governance','testing','evidence'],
  critical_gates: {
    authority: true,
    privacy_security: true,
    evidence_provenance: true,
    testing: true,
    risk: true,
    rollback_recovery: true
  },
  production_activation: false,
  human_approval: {
    required: true,
    approved: false,
    approver: null,
    audit_reference: null
  }
};

const pending = validateBestPracticeAttestation(base);
assert.strictEqual(pending.all_critical_gates_passed, true);
assert.strictEqual(pending.promotion_blocked, true);

const failed = validateBestPracticeAttestation({
  ...base,
  critical_gates: { ...base.critical_gates, testing: false }
});
assert.strictEqual(failed.all_critical_gates_passed, false);
assert.deepStrictEqual(failed.failed_critical_gates, ['testing']);
assert.strictEqual(failed.promotion_blocked, true);

assert.throws(
  () => validateBestPracticeAttestation({ ...base, production_activation: true }),
  /non-production/
);

assert.throws(
  () => validateBestPracticeAttestation({
    ...base,
    human_approval: { required: true, approved: true, approver: '', audit_reference: 'AUDIT' }
  }),
  /human_approval\.approver/
);

const approved = validateBestPracticeAttestation({
  ...base,
  human_approval: { required: true, approved: true, approver: 'synthetic-owner', audit_reference: 'TEST-AUDIT' }
});
assert.strictEqual(approved.promotion_blocked, false);
assert.ok(Object.isFrozen(approved));
assert.ok(Object.isFrozen(approved.failed_critical_gates));

console.log('Best-practice attestation tests passed');
