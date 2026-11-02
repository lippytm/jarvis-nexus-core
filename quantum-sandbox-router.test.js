'use strict';

const assert = require('assert');
const { SANDBOXES, createSandboxPacket, handoffSandboxPacket } = require('./quantum-sandbox-router');

assert.deepStrictEqual(Object.keys(SANDBOXES), ['IF','MAYBE','WHY_NOT','DONT_DO_THAT','I_TOLD_YOU_NOT_TO_DO_THAT']);

const common = {
  prompt_module_id: 'P11-PEE-005',
  prompt_version: '0.1.0'
};

const ifPacket = createSandboxPacket({
  packet_id: 'QS-IF-001',
  sandbox: 'IF',
  objective: 'Test whether modular prompts reduce conflicts.',
  inputs: ['baseline','candidate'],
  ...common
});

assert.strictEqual(ifPacket.handoff_to, 'MAYBE');
assert.strictEqual(ifPacket.prompt_module_id, 'P11-PEE-005');
assert.strictEqual(ifPacket.prompt_version, '0.1.0');
assert.strictEqual(ifPacket.production_activation, false);
assert.ok(Object.isFrozen(ifPacket));

const maybe = handoffSandboxPacket(ifPacket, 'MAYBE');
assert.strictEqual(maybe.from_sandbox, 'IF');
assert.strictEqual(maybe.to_sandbox, 'MAYBE');
assert.strictEqual(maybe.prompt_module_id, 'P11-PEE-005');
assert.strictEqual(maybe.prompt_version, '0.1.0');
assert.strictEqual(maybe.provenance_preserved, true);

for (const sandbox of ['MAYBE','WHY_NOT','DONT_DO_THAT']) {
  const packet = createSandboxPacket({
    packet_id: `QS-${sandbox}-001`,
    sandbox,
    objective: 'Synthetic test objective',
    inputs: ['fixture'],
    ...common
  });
  assert.strictEqual(packet.production_activation, false);
  assert.strictEqual(packet.human_approval_required, true);
}

assert.throws(() => createSandboxPacket({
  packet_id: 'QS-BAD-001', sandbox: 'UNKNOWN', objective: 'bad', inputs: ['fixture'], ...common
}), /Unknown Quantum sandbox/);

assert.throws(() => createSandboxPacket({
  packet_id: 'QS-BAD-VER', sandbox: 'IF', objective: 'bad', inputs: ['fixture'],
  prompt_module_id: 'P11-PEE-005', prompt_version: 'v1'
}), /semantic versioning/);

const sparseInputs = new Array(1);
assert.throws(() => createSandboxPacket({
  packet_id: 'QS-SPARSE', sandbox: 'IF', objective: 'bad', inputs: sparseInputs, ...common
}), /index 0 is missing/);

assert.throws(() => createSandboxPacket({
  packet_id: 'QS-FAIL-001', sandbox: 'I_TOLD_YOU_NOT_TO_DO_THAT',
  objective: 'Analyze failure', inputs: ['incident-record'], ...common
}), /requires an incident/);

const failure = createSandboxPacket({
  packet_id: 'QS-FAIL-002', sandbox: 'I_TOLD_YOU_NOT_TO_DO_THAT',
  objective: 'Analyze failure', inputs: ['incident-record'], incident: true, ...common
});
assert.strictEqual(failure.regression_required_on_failure, true);

console.log('Quantum sandbox router tests passed');
