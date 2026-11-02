'use strict';

const SANDBOXES = Object.freeze({
  IF: Object.freeze({ role: 'hypothesis-engineer', next: 'MAYBE', purpose: 'Test a measurable hypothesis and define the cheapest safe experiment.' }),
  MAYBE: Object.freeze({ role: 'uncertainty-analyst', next: 'WHY_NOT', purpose: 'Explore uncertainty, missing information, and competing explanations.' }),
  WHY_NOT: Object.freeze({ role: 'innovation-architect', next: 'DONT_DO_THAT', purpose: 'Generate unconventional but testable alternatives.' }),
  DONT_DO_THAT: Object.freeze({ role: 'red-team-safety-engineer', next: null, purpose: 'Identify foreseeable failures, prohibited actions, and required controls.' }),
  I_TOLD_YOU_NOT_TO_DO_THAT: Object.freeze({ role: 'incident-forensics-recovery-engineer', next: null, purpose: 'Analyze failure evidence and create a recovery and regression requirement.' })
});

function requireString(value, field) {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error(`Quantum sandbox field must be a nonempty string: ${field}`);
  }
  return value.trim();
}

function createSandboxPacket({ packet_id, sandbox, objective, prompt_module_id, prompt_version, inputs, incident = false }) {
  const packetId = requireString(packet_id, 'packet_id');
  const sandboxKey = requireString(sandbox, 'sandbox');
  const promptModuleId = requireString(prompt_module_id, 'prompt_module_id');
  const promptVersion = requireString(prompt_version, 'prompt_version');

  if (!/^\d+\.\d+\.\d+$/.test(promptVersion)) {
    throw new Error('Quantum sandbox prompt_version must use semantic versioning');
  }
  if (!Object.prototype.hasOwnProperty.call(SANDBOXES, sandboxKey)) {
    throw new Error(`Unknown Quantum sandbox: ${sandboxKey}`);
  }
  if (!Array.isArray(inputs) || inputs.length === 0) {
    throw new Error('Quantum sandbox requires at least one input reference');
  }
  for (let i = 0; i < inputs.length; i += 1) {
    if (!Object.prototype.hasOwnProperty.call(inputs, i)) {
      throw new Error(`Quantum sandbox input at index ${i} is missing`);
    }
  }

  const inputRefs = inputs.map((item, index) => requireString(item, `inputs[${index}]`));

  if (sandboxKey === 'I_TOLD_YOU_NOT_TO_DO_THAT' && incident !== true) {
    throw new Error('I Told You Not To Do That sandbox requires an incident or explicit failure review');
  }

  const spec = SANDBOXES[sandboxKey];
  return Object.freeze({
    packet_id: packetId,
    sandbox: sandboxKey,
    role: spec.role,
    objective: requireString(objective, 'objective'),
    prompt_module_id: promptModuleId,
    prompt_version: promptVersion,
    input_references: Object.freeze(inputRefs),
    state: 'draft',
    handoff_to: spec.next,
    production_activation: false,
    network_fetch_performed: false,
    model_call_performed: false,
    runtime_integration_enabled: false,
    evidence_required: true,
    human_approval_required: true,
    regression_required_on_failure: true,
    purpose: spec.purpose
  });
}

function handoffSandboxPacket(packet, nextSandbox) {
  if (!packet || typeof packet !== 'object') throw new Error('Quantum sandbox packet is required');

  const target = requireString(nextSandbox, 'nextSandbox');
  if (!Object.prototype.hasOwnProperty.call(SANDBOXES, target)) {
    throw new Error(`Unknown Quantum sandbox: ${target}`);
  }
  if (packet.production_activation !== false) {
    throw new Error('Quantum sandbox packet must remain non-production');
  }

  return Object.freeze({
    from_packet_id: requireString(packet.packet_id, 'packet.packet_id'),
    from_sandbox: requireString(packet.sandbox, 'packet.sandbox'),
    to_sandbox: target,
    prompt_module_id: requireString(packet.prompt_module_id, 'packet.prompt_module_id'),
    prompt_version: requireString(packet.prompt_version, 'packet.prompt_version'),
    evidence_preserved: true,
    provenance_preserved: true,
    production_activation: false,
    note: 'Handoff descriptor only; no model execution or deployment occurs.'
  });
}

module.exports = { SANDBOXES, createSandboxPacket, handoffSandboxPacket };
