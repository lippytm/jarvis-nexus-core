/**
 * JARVIS-FLOW — AI-Native Workflow Engine
 * Replaces n8n: workflows created from natural language, self-healing, self-improving
 * Part of: AI Jarvis Assistants Swarms Systems — Intergalactic Corporate Services LLC
 * Author: Lippy Killjoy (lippytm) | AI Builds AI
 * Port: 3002
 */

const express = require('express');
const { v4: uuidv4 } = require('uuid');
const cron = require('node-cron');
const fs = require('fs').promises;
const path = require('path');

const app = express();
app.use(express.json());

// ============================================================
// WORKFLOW STORAGE
// ============================================================
const WORKFLOWS_DIR = path.join(process.env.HOME || '/root', '.jarvis-flow', 'workflows');

async function ensureDir() {
  await fs.mkdir(WORKFLOWS_DIR, { recursive: true });
}

async function saveWorkflow(wf) {
  await ensureDir();
  await fs.writeFile(
    path.join(WORKFLOWS_DIR, `${wf.id}.json`),
    JSON.stringify(wf, null, 2)
  );
}

async function loadWorkflow(id) {
  const data = await fs.readFile(path.join(WORKFLOWS_DIR, `${id}.json`), 'utf8');
  return JSON.parse(data);
}

async function listWorkflows() {
  await ensureDir();
  const files = await fs.readdir(WORKFLOWS_DIR);
  const workflows = [];
  for (const f of files.filter(f => f.endsWith('.json'))) {
    const data = await fs.readFile(path.join(WORKFLOWS_DIR, f), 'utf8');
    workflows.push(JSON.parse(data));
  }
  return workflows;
}

// ============================================================
// AI WORKFLOW GENERATOR — Claude designs, ChatGPT codes nodes
// ============================================================
async function generateWorkflowFromNaturalLanguage(prompt, persona = 'jarvis') {
  const Anthropic = require('@anthropic-ai/sdk');
  const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

  const systemPrompt = `You are Jarvis-Flow's AI Workflow Architect.
Convert the user's plain English request into a structured workflow JSON.

A workflow has this shape:
{
  "name": "descriptive name",
  "description": "what this workflow does",
  "trigger": {
    "type": "cron|webhook|manual|event",
    "config": { "schedule": "0 9 * * *" }
  },
  "nodes": [
    {
      "id": "node_1",
      "type": "ai_call|http|github|blotato|sheets|transform|condition",
      "name": "human readable name",
      "config": { ... node-specific config ... },
      "next": "node_2",
      "on_error": "node_error_handler"
    }
  ],
  "persona": "${persona}"
}

Available node types and their configs:
- ai_call: { model: "jarvis-hub", task: "write|code|search|format|summarize", prompt_template: "..." }
- http: { method: "GET|POST", url: "...", headers: {}, body_template: "..." }
- github: { action: "commit|create_issue|open_pr|read_file", repo: "lippytm/...", ... }
- social: { action: "post", platforms: ["twitter","linkedin","instagram","bluesky","discord","telegram","reddit","mastodon","slack",...], content_template: "...", persona: "lippytmai|jarvis|..." }
- sheets: { action: "append|read|update", spreadsheet_id: "...", range: "...", values: [] }
- transform: { operation: "js_expression", code: "return input.text.slice(0, 500)" }
- condition: { expression: "input.status === 'success'", true_next: "...", false_next: "..." }

Respond with ONLY valid JSON — no markdown, no explanation.`;

  const response = await client.messages.create({
    model: 'claude-opus-4-5',
    max_tokens: 2000,
    system: systemPrompt,
    messages: [{ role: 'user', content: prompt }]
  });

  const jsonText = response.content[0].text.trim();
  return JSON.parse(jsonText);
}

// ============================================================
// WORKFLOW EXECUTOR — runs each node in sequence
// ============================================================
const activeJobs = new Map();

async function executeNode(node, context) {
  console.log(`[Jarvis-Flow] Executing node: ${node.name} (${node.type})`);

  try {
    switch (node.type) {
      case 'ai_call': {
        // Route through Jarvis-Hub for smart model selection
        const response = await fetch(`http://localhost:3003/hub/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            task: node.config.task,
            prompt: interpolate(node.config.prompt_template, context),
            persona: context.persona || 'lippytmai',
            priority: node.config.priority || 'quality'
          })
        });
        const result = await response.json();
        return { ...context, [node.id]: result.output, last_output: result.output };
      }

      case 'github': {
        const { Octokit } = require('@octokit/rest');
        const octokit = new Octokit({ auth: process.env.GITHUB_TOKEN });
        const [owner, repo] = node.config.repo.split('/');

        if (node.config.action === 'commit') {
          const content = Buffer.from(interpolate(node.config.content_template, context)).toString('base64');
          const existing = await octokit.repos.getContent({ owner, repo, path: node.config.path }).catch(() => null);
          await octokit.repos.createOrUpdateFileContents({
            owner, repo,
            path: node.config.path,
            message: interpolate(node.config.message || 'Jarvis-Flow auto-commit', context),
            content,
            sha: existing?.data?.sha
          });
        } else if (node.config.action === 'create_issue') {
          await octokit.issues.create({
            owner, repo,
            title: interpolate(node.config.title, context),
            body: interpolate(node.config.body_template, context),
            labels: node.config.labels || ['ai-build']
          });
        }
        return { ...context, [node.id]: 'success', last_output: 'github_action_complete' };
      }

      case 'social': {
        // Routes to Jarvis-Blast — our own social media publisher (beats Blotato)
        const content = interpolate(node.config.content_template, context);
        const response = await fetch(`${process.env.JARVIS_BLAST_URL || 'http://localhost:3005'}/blast/post`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            content,
            platforms: node.config.platforms || ['twitter', 'linkedin'],
            persona: node.config.persona || context.persona || 'lippytmai',
            media_urls: node.config.media_urls || []
          })
        });
        const result = await response.json();
        return { ...context, [node.id]: result, last_output: 'posted_to_social' };
      }

      // Legacy alias — keep 'blotato' key working but route to Jarvis-Blast
      case 'blotato': {
        const content = interpolate(node.config.content_template, context);
        const response = await fetch(`${process.env.JARVIS_BLAST_URL || 'http://localhost:3005'}/blast/post`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            content,
            platforms: node.config.platforms || ['twitter', 'linkedin'],
            persona: node.config.persona || context.persona || 'lippytmai'
          })
        });
        const result = await response.json();
        return { ...context, [node.id]: result, last_output: 'posted_to_social' };
      }

      case 'http': {
        const response = await fetch(node.config.url, {
          method: node.config.method || 'GET',
          headers: node.config.headers || {},
          body: node.config.method !== 'GET' ? JSON.stringify(interpolate(node.config.body_template, context)) : undefined
        });
        const result = await response.json();
        return { ...context, [node.id]: result, last_output: result };
      }

      case 'transform': {
        const fn = new Function('input', node.config.code);
        const output = fn(context);
        return { ...context, [node.id]: output, last_output: output };
      }

      default:
        console.warn(`[Jarvis-Flow] Unknown node type: ${node.type}`);
        return context;
    }
  } catch (err) {
    console.error(`[Jarvis-Flow] Node ${node.name} failed:`, err.message);
    // Self-healing: log error for nightly analysis
    await logError({ workflow_id: context._workflow_id, node_id: node.id, error: err.message, timestamp: new Date().toISOString() });
    throw err;
  }
}

function interpolate(template, context) {
  if (typeof template !== 'string') return template;
  return template.replace(/\{\{(\w+)\}\}/g, (_, key) => context[key] || '');
}

async function logError(entry) {
  const logFile = path.join(process.env.HOME || '/root', '.jarvis-flow', 'errors.jsonl');
  await fs.appendFile(logFile, JSON.stringify(entry) + '\n').catch(() => {});
}

async function runWorkflow(workflow) {
  console.log(`[Jarvis-Flow] Running workflow: ${workflow.name}`);
  let context = { _workflow_id: workflow.id, persona: workflow.persona, started_at: new Date().toISOString() };

  for (const node of workflow.nodes) {
    try {
      context = await executeNode(node, context);
    } catch (err) {
      console.error(`[Jarvis-Flow] Workflow ${workflow.name} failed at node ${node.name}`);
      // Update workflow status
      workflow.last_run = { status: 'error', node: node.id, error: err.message, timestamp: new Date().toISOString() };
      await saveWorkflow(workflow);
      return;
    }
  }

  workflow.last_run = { status: 'success', timestamp: new Date().toISOString() };
  workflow.run_count = (workflow.run_count || 0) + 1;
  await saveWorkflow(workflow);
  console.log(`[Jarvis-Flow] Workflow ${workflow.name} completed successfully`);
}

function scheduleWorkflow(workflow) {
  if (workflow.trigger?.type === 'cron' && workflow.trigger.config?.schedule) {
    if (cron.validate(workflow.trigger.config.schedule)) {
      const job = cron.schedule(workflow.trigger.config.schedule, () => runWorkflow(workflow));
      activeJobs.set(workflow.id, job);
      console.log(`[Jarvis-Flow] Scheduled: ${workflow.name} @ ${workflow.trigger.config.schedule}`);
    }
  }
}

// ============================================================
// REST API
// ============================================================

// POST /flow/create — generate workflow from natural language
app.post('/flow/create', async (req, res) => {
  try {
    const { prompt, persona, active = false, trigger_override } = req.body;
    if (!prompt) return res.status(400).json({ error: 'prompt required' });

    const generated = await generateWorkflowFromNaturalLanguage(prompt, persona);
    const workflow = {
      id: uuidv4(),
      ...generated,
      persona: persona || 'jarvis',
      active,
      created_at: new Date().toISOString(),
      run_count: 0,
      prompt_used: prompt
    };

    if (trigger_override) workflow.trigger = trigger_override;
    await saveWorkflow(workflow);
    if (active) scheduleWorkflow(workflow);

    res.json({ success: true, workflow });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /flow/list - list all workflows
app.get('/flow/list', async (req, res) => {
  try {
    const workflows = await listWorkflows();
    res.json({ workflows, total: workflows.length });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /flow/run/:id - run a workflow immediately
app.post('/flow/run/:id', async (req, res) => {
  try {
    const workflow = await loadWorkflow(req.params.id);
    runWorkflow(workflow); // fire and forget
    res.json({ success: true, message: `Workflow ${workflow.name} started`, id: workflow.id });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// DELETE /flow/kill/:id - stop a scheduled workflow
app.delete('/flow/kill/:id', async (req, res) => {
  try {
    const job = activeJobs.get(req.params.id);
    if (job) { job.stop(); activeJobs.delete(req.params.id); }
    const workflow = await loadWorkflow(req.params.id);
    workflow.active = false;
    await saveWorkflow(workflow);
    res.json({ success: true, message: 'Workflow stopped' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /flow/health
app.get('/flow/health', (req, res) => {
  res.json({
    status: 'running',
    active_jobs: activeJobs.size,
    version: '1.0.0',
    system: 'Jarvis-Flow — AI Workflow Engine',
    beats: 'n8n'
  });
});

// ============================================================
// STARTUP — load and schedule all active workflows
// ============================================================
async function startup() {
  await ensureDir();
  const PORT = process.env.JARVIS_FLOW_PORT || 3002;
  app.listen(PORT, () => {
    console.log(`\n⡡ Jarvis-Flow running on port ${PORT}`);
    console.log(`   AI Jarvis Assistants Swarms Systems`);
    console.log(`   Intergalactic Corporate Services LLC\n`);
  });

  // Load and schedule all active workflows
  try {
    const workflows = await listWorkflows();
    for (const wf of workflows.filter(w => w.active)) {
      scheduleWorkflow(wf);
    }
    console.log(`[Jarvis-Flow] Loaded ${workflows.length} workflows, ${activeJobs.size} scheduled`);
  } catch (e) {
    console.log('[Jarvis-Flow] No existing workflows found — starting fresh');
  }
}

startup();
