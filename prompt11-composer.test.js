'use strict';

const assert = require('assert');
const { composePrompt11Package } = require('./prompt11-composer');

const modules = [
  {
    module_id: 'P-011-XPIO-001',
    version: '1.0.0',
    source_repo: 'lippytm/Prompt-11-',
    source_path: 'prompts/P011-XPIO-001-master-operating-prompt.md',
    source_ref: 'approved-ref-1',
    approval_audit_reference: 'TEST-AUDIT-1',
    approver: 'synthetic-owner'
  },
  {
    module_id: 'P-011-PEE-001',
    version: '0.1.0',
    source_repo: 'lippytm/Prompt-11-',
    source_path: 'docs/P011-PEE-001-prompt-engineering-evolution-engine.md',
    source_ref: 'approved-ref-2',
    approval_audit_reference: 'TEST-AUDIT-2',
    approver: 'synthetic-owner'
  }
];

const result = composePrompt11Package({
  composition_id: 'CMP-TEST-001',
  task_class: 'software-engineering',
  target_role: 'jarvis-copilot-engineer',
  modules
});

assert.strictEqual(result.activation_state, 'inactive');
assert.deepStrictEqual(result.composition_order, ['P-011-XPIO-001', 'P-011-PEE-001']);
assert.strictEqual(result.network_fetch_performed, false);
assert.strictEqual(result.model_call_performed, false);
assert.strictEqual(result.runtime_integration_enabled, false);
assert.ok(Object.isFrozen(result));
assert.ok(Object.isFrozen(result.modules));
assert.ok(Object.isFrozen(result.modules[0]));
assert.ok(Object.isFrozen(result.composition_order));

const duplicate = [...modules, { ...modules[1] }];
assert.throws(
  () => composePrompt11Package({
    composition_id: 'CMP-TEST-002',
    task_class: 'software-engineering',
    target_role: 'jarvis',
    modules: duplicate
  }),
  /duplicate module_id/
);

const malformed = [{ ...modules[0], approval_audit_reference: '' }];
assert.throws(
  () => composePrompt11Package({
    composition_id: 'CMP-TEST-003',
    task_class: 'software-engineering',
    target_role: 'jarvis',
    modules: malformed
  }),
  /approval_audit_reference/
);

assert.throws(
  () => composePrompt11Package({
    composition_id: 'CMP-TEST-004',
    task_class: 'software-engineering',
    target_role: 'jarvis',
    modules: []
  }),
  /at least one/
);

console.log('Prompt #11 composer tests passed');
