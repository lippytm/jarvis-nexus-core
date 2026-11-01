'use strict';

function requireString(value, field) {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error(`Prompt #11 composition field must be a nonempty string: ${field}`);
  }
  return value.trim();
}

function freezeModule(module) {
  return Object.freeze({
    module_id: requireString(module.module_id, 'module_id'),
    version: requireString(module.version, 'version'),
    source_repo: requireString(module.source_repo, 'source_repo'),
    source_path: requireString(module.source_path, 'source_path'),
    source_ref: module.source_ref == null ? null : requireString(module.source_ref, 'source_ref'),
    approval_audit_reference: requireString(module.approval_audit_reference, 'approval_audit_reference'),
    approver: requireString(module.approver, 'approver')
  });
}

function composePrompt11Package({ composition_id, task_class, target_role, modules }) {
  const compositionId = requireString(composition_id, 'composition_id');
  const taskClass = requireString(task_class, 'task_class');
  const targetRole = requireString(target_role, 'target_role');

  if (!Array.isArray(modules) || modules.length === 0) {
    throw new Error('Prompt #11 composition requires at least one validated module');
  }
  for (let i = 0; i < modules.length; i += 1) {
    if (!Object.prototype.hasOwnProperty.call(modules, i)) {
      throw new Error(`Prompt #11 composition module at index ${i} is missing`);
    }
  }

  const seen = new Set();
  const frozenModules = modules.map((module, index) => {
    if (!module || typeof module !== 'object' || Array.isArray(module)) {
      throw new Error(`Prompt #11 composition module at index ${index} is invalid`);
    }
    const frozen = freezeModule(module);
    if (seen.has(frozen.module_id)) {
      throw new Error(`Prompt #11 composition contains duplicate module_id: ${frozen.module_id}`);
    }
    seen.add(frozen.module_id);
    return frozen;
  });

  const manifest = {
    composition_id: compositionId,
    task_class: taskClass,
    target_role: targetRole,
    activation_state: 'inactive',
    composition_order: Object.freeze(frozenModules.map(m => m.module_id)),
    modules: Object.freeze(frozenModules),
    provenance_complete: true,
    network_fetch_performed: false,
    model_call_performed: false,
    runtime_integration_enabled: false,
    note: 'Reference-only composition manifest. No prompt text is fetched, injected, executed, or deployed.'
  };

  return Object.freeze(manifest);
}

module.exports = {
  composePrompt11Package
};
