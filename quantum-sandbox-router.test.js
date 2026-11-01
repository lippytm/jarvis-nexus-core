'use strict';

const assert = require('assert');
const {
  SANDBOXES,
  createSandboxPacket,
  handoffSandboxPacket
} = require('./quantum-sandbox-router');

assert.deepStrictEqual(
  Object.keys(SANDBOXES),
  ['IF','MAYBE','WHY_NOT','DONT_DO_THAT','I_TOLD_YOU_NOT_TO_DO_THAT']
);

const ifPacket = createSandboxPacket({
  packet_id: 'QS-IF-001',
  sandbox: 'IF',
  objective: 'Test whether modular prompts reduce conflicts.',
  inputs: ['baseline','candidate']
});

assert.strictEqual(ifPacket.handoff_to, 'MAYBE');
assert.strictEqual(ifPacket.production_activation, false);
assert.strictEqual(ifPacket.model_call_performed, false);
assert.ok(Object.isFrozen(ifPacket));
assert.ok(Object.isFrozen(ifPacket.input_references));

const maybe = handoffSandboxPacket(ifPacket, 'MAYBE');
assert.strictEqual(maybe.from_sandbox, 'IF');
assert.strictEqual(maybe.to_sandbox, 'MAYBE');
assert.strictEqual(maybe.production_activation, false);
assert.ok(Object.isFrozen(maybe));

for (const sandbox of ['MAYBE','WHY_NOT','DONT_DO_THAT']) {
  const packet = createSandboxPacket({
    packet_id: `QS-${sandbox}-001`,
    sandbox,
    objective: 'Synthetic test objective',
    inputs: ['fixture']
  });
  assert.strictEqual(packet.production_activation, false);
  assert.strictEqual(packet.human_approval_required, true);
}

assert.throws(
  () => createSandboxPacket({
    packet_id: 'QS-BAD-001',
    sandbox: 'UNKNOWN',
    objective: 'bad',
    inputs: ['fixture']
  }),
  /Unknown Quantum sandbox/
);

assert.throws(
  () => createSandboxPacket({
    packet_id: 'QS-FAIL-001',
    sandbox: 'I_TOLD_YOU_NOT_TO_DO_THAT',
    objective: 'Analyze failure',
    inputs: ['incident-record']
  }),
  /requires an incident/
);

const failure = createSandboxPacket({
  packet_id: 'QS-FAIL-002',
  sandbox: 'I_TOLD_YOU_NOT_TO_DO_THAT',
  objective: 'Analyze failure',
  inputs: ['incident-record'],
  incident: true
});
assert.strictEqual(failure.regression_required_on_failure, true);

console.log('Quantum sandbox router tests passed');
