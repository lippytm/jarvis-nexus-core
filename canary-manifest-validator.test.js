'use strict';

const assert = require('assert');
const { validateCanaryManifest } = require('./canary-manifest-validator');

function base() {
  return {
    canary_id: 'CANARY-001',
    target: 'jarvis-nexus-core',
    candidate_ref: 'candidate-sha',
    baseline_ref: 'baseline-sha',
    task_class: 'prompt-routing',
    scope: 'one bounded synthetic task class',
    max_runs: 10,
    success_criteria: ['No critical regressions', 'Expected schema output'],
    failure_criteria: ['Critical regression', 'Permission violation'],
    stop_conditions: ['Any critical error', 'Rollback unavailable'],
    rollback_target: 'baseline-sha',
    rollback_procedure_reference: 'docs/rollback.md',
    post_canary_verification_plan: 'Compare outputs and verify logs after each run.',
    evidence_collection_plan: 'Collect test output, hashes, and Control Tower packet.',
    human_approval: {
      approved: true,
      approver: 'synthetic-owner',
      audit_reference: 'TEST-AUDIT'
    },
    production_activation: false
  };
}

const ok = validateCanaryManifest(base());
assert.strictEqual(ok.ready_for_canary_execution_review, true);
assert.strictEqual(ok.deploys, false);
assert.strictEqual(ok.production_activation, false);
assert.ok(Object.isFrozen(ok));

assert.throws(
  () => validateCanaryManifest({ ...base(), human_approval: { approved: false, approver: '', audit_reference: '' } }),
  /HumanApprovalGate/
);
assert.throws(
  () => validateCanaryManifest({ ...base(), rollback_target: '' }),
  /rollback_target/
);
assert.throws(
  () => validateCanaryManifest({ ...base(), success_criteria: [] }),
  /success_criteria/
);
assert.throws(
  () => validateCanaryManifest({ ...base(), production_activation: true }),
  /non-production/
);

console.log('P11-PEE-013 canary manifest validator tests passed');
