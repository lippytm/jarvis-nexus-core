'use strict';

const assert = require('assert');
const { arbitrateEvidence } = require('./evidence-arbitrator');

const det = {
  evidence_id: 'E1',
  evidence_class: 'DETERMINISTIC_TEST',
  independence_group: 'test-run-1',
  freshness: 'CURRENT',
  verification_state: 'VERIFIED'
};
const primary = {
  evidence_id: 'E2',
  evidence_class: 'PRIMARY_SOURCE',
  independence_group: 'primary-source-1',
  freshness: 'CURRENT',
  verification_state: 'VERIFIED'
};
const model1 = {
  evidence_id: 'M1',
  evidence_class: 'MODEL_ASSERTION',
  independence_group: 'model-family-a',
  freshness: 'CURRENT',
  verification_state: 'UNVERIFIED'
};
const model2 = {
  ...model1,
  evidence_id: 'M2',
  independence_group: 'model-family-b'
};

let r = arbitrateEvidence({ claim_type: 'FACT', supporting_evidence: [det, primary] });
assert.strictEqual(r.status, 'VERIFIED_SUPPORT');
assert.strictEqual(r.route, 'PREPARE_OWNER_REVIEW');

r = arbitrateEvidence({ claim_type: 'FACT', supporting_evidence: [model1, model2] });
assert.strictEqual(r.status, 'CIRCULAR_EVIDENCE');
assert.strictEqual(r.route, 'COLLECT_INDEPENDENT_EVIDENCE');

r = arbitrateEvidence({
  claim_type: 'FACT',
  supporting_evidence: [primary],
  contradicting_evidence: [det]
});
assert.strictEqual(r.status, 'FACT_CONFLICT');

r = arbitrateEvidence({
  claim_type: 'RISK',
  supporting_evidence: [primary],
  contradicting_evidence: [det]
});
assert.strictEqual(r.status, 'RISK_CONFLICT');
assert.strictEqual(r.route, 'ROUTE_TO_DONT_DO_THAT');

r = arbitrateEvidence({
  claim_type: 'POLICY',
  supporting_evidence: [primary],
  contradicting_evidence: [det]
});
assert.strictEqual(r.status, 'POLICY_CONFLICT');
assert.strictEqual(r.route, 'STOP_AND_ESCALATE');

r = arbitrateEvidence({
  claim_type: 'FACT',
  supporting_evidence: [{ ...primary, freshness: 'STALE' }]
});
assert.strictEqual(r.status, 'STALE_EVIDENCE');
assert.strictEqual(r.route, 'REFRESH_EVIDENCE');

assert.strictEqual(r.production_activation, false);
assert.strictEqual(r.human_approval_required, true);

console.log('P11-PEE-009 evidence arbitrator tests passed');
