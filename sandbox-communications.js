'use strict';

const SENDER_TYPES = Object.freeze(new Set([
  'CHATGPT','CHATGPT_BUSINESS','CLAUDE','GEMINI','GITHUB','JARVIS_SPECIALIST','DETERMINISTIC_TOOL'
]));
const PHASES = Object.freeze(new Set(['FIRST_PASS','EVIDENCE_EXCHANGE','REBUTTAL','ARBITRATION','REVIEW']));

function requireString(value, field) {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error(`AI sandbox communication field must be a nonempty string: ${field}`);
  }
  return value.trim();
}

function createCommunicationEnvelope(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    throw new Error('AI sandbox communication envelope is required');
  }

  const senderType = requireString(input.sender_type, 'sender_type');
  if (!SENDER_TYPES.has(senderType)) throw new Error(`Unknown sender_type: ${senderType}`);

  const phase = requireString(input.phase, 'phase');
  if (!PHASES.has(phase)) throw new Error(`Unknown communication phase: ${phase}`);

  if (!Array.isArray(input.recipients) || input.recipients.length === 0) {
    throw new Error('AI sandbox communication requires recipients');
  }

  const recipients = [];
  const seen = new Set();
  for (let i = 0; i < input.recipients.length; i += 1) {
    if (!Object.prototype.hasOwnProperty.call(input.recipients, i)) {
      throw new Error(`AI sandbox recipient at index ${i} is missing`);
    }
    const value = requireString(input.recipients[i], `recipients[${i}]`);
    if (seen.has(value)) throw new Error(`Duplicate recipient: ${value}`);
    seen.add(value);
    recipients.push(value);
  }

  if (input.production_activation !== false) {
    throw new Error('AI sandbox communication must remain non-production');
  }

  if (phase === 'FIRST_PASS' && input.independence_preserved !== true) {
    throw new Error('FIRST_PASS communication must preserve independence');
  }

  const version = requireString(input.prompt_version, 'prompt_version');
  if (!/^\d+\.\d+\.\d+$/.test(version)) {
    throw new Error('prompt_version must use semantic versioning');
  }

  return Object.freeze({
    message_id: requireString(input.message_id, 'message_id'),
    work_packet_id: requireString(input.work_packet_id, 'work_packet_id'),
    sender_id: requireString(input.sender_id, 'sender_id'),
    sender_type: senderType,
    recipients: Object.freeze(recipients),
    phase,
    prompt_module_id: requireString(input.prompt_module_id, 'prompt_module_id'),
    prompt_version: version,
    payload_type: requireString(input.payload_type, 'payload_type'),
    payload_summary: requireString(input.payload_summary, 'payload_summary'),
    claim_refs: Object.freeze(Array.isArray(input.claim_refs) ? input.claim_refs.map((v,i)=>requireString(v,`claim_refs[${i}]`)) : []),
    evidence_refs: Object.freeze(Array.isArray(input.evidence_refs) ? input.evidence_refs.map((v,i)=>requireString(v,`evidence_refs[${i}]`)) : []),
    independence_preserved: input.independence_preserved === true,
    production_activation: false
  });
}

module.exports = { createCommunicationEnvelope };
