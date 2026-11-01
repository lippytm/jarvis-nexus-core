'use strict';

const assert = require('assert');
const { createCommunicationEnvelope } = require('./sandbox-communications');

const base = {
  message_id: 'MSG-001',
  work_packet_id: 'WP-001',
  sender_id: 'chatgpt-business',
  sender_type: 'CHATGPT_BUSINESS',
  recipients: ['evidence-officer'],
  phase: 'FIRST_PASS',
  prompt_module_id: 'P11-PEE-009',
  prompt_version: '0.1.0',
  payload_type: 'POSITION',
  payload_summary: 'Independent first-pass position.',
  claim_refs: ['CLM-000001'],
  evidence_refs: [],
  independence_preserved: true,
  production_activation: false
};

const env = createCommunicationEnvelope(base);
assert.strictEqual(env.production_activation, false);
assert.strictEqual(env.independence_preserved, true);
assert.ok(Object.isFrozen(env));
assert.ok(Object.isFrozen(env.recipients));

assert.throws(
  () => createCommunicationEnvelope({ ...base, independence_preserved: false }),
  /preserve independence/
);

assert.throws(
  () => createCommunicationEnvelope({ ...base, production_activation: true }),
  /non-production/
);

assert.throws(
  () => createCommunicationEnvelope({ ...base, recipients: ['x','x'] }),
  /Duplicate recipient/
);

assert.throws(
  () => createCommunicationEnvelope({ ...base, prompt_version: 'v1' }),
  /semantic versioning/
);

console.log('P11-PEE-009 sandbox communications tests passed');
