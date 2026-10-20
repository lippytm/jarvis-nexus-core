/**
 * JARVIS-HUB — Private AI Model Registry & Smart Router
 * Replaces HuggingFace: host all AI models, auto-route by task, auto-fine-tune
 * Part of: AI Jarvis Assistants Swarms Systems — Intergalactic Corporate Services LLC
 * Author: Lippy Killjoy (lippytm) | AI Builds AI
 * Port: 3003
 */

const express = require('express');
const app = express();
app.use(express.json({ limit: '10mb' }));

// ============================================================
// MODEL REGISTRY — all AI models available to the swarm
// ============================================================
const MODEL_REGISTRY = {
  // Premium models — best quality
  'claude-opus': {
    provider: 'anthropic',
    model_id: 'claude-opus-4-5',
    cost_per_1k_tokens: 0.015,
    speed_rating: 3, // 1=fastest, 5=slowest
    task_tags: ['write', 'architect', 'strategy', 'creative', 'persona', 'nft_content'],
    max_tokens: 4096,
    active: true
  },
  'claude-sonnet': {
    provider: 'anthropic',
    model_id: 'claude-sonnet-4-5',
    cost_per_1k_tokens: 0.003,
    speed_rating: 2,
    task_tags: ['write', 'summarize', 'analyze', 'format', 'general'],
    max_tokens: 4096,
    active: true
  },
  'gpt-4o': {
    provider: 'openai',
    model_id: 'gpt-4o',
    cost_per_1k_tokens: 0.005,
    speed_rating: 2,
    task_tags: ['code', 'format', 'structured_output', 'function_calling', 'debug'],
    max_tokens: 4096,
    active: true
  },
  'gpt-4o-mini': {
    provider: 'openai',
    model_id: 'gpt-4o-mini',
    cost_per_1k_tokens: 0.00015,
    speed_rating: 1,
    task_tags: ['simple', 'classify', 'extract', 'cheap', 'fast'],
    max_tokens: 2048,
    active: true
  },
  'gemini-pro': {
    provider: 'google',
    model_id: 'gemini-1.5-pro',
    cost_per_1k_tokens: 0.00125,
    speed_rating: 2,
    task_tags: ['search', 'web_research', 'google_ecosystem', 'long_context'],
    max_tokens: 8192,
    active: true
  },
  'gemini-flash': {
    provider: 'google',
    model_id: 'gemini-2.0-flash',
    cost_per_1k_tokens: 0.000075,
    speed_rating: 1,
    task_tags: ['fast', 'cheap', 'classify', 'extract', 'simple', 'social'],
    max_tokens: 4096,
    active: true
  },
  'claude-haiku': {
    provider: 'anthropic',
    model_id: 'claude-haiku-3-5',
    cost_per_1k_tokens: 0.00025,
    speed_rating: 1,
    task_tags: ['fast', 'cheap', 'classify', 'extract', 'simple'],
    max_tokens: 2048,
    active: true
  },
  'chatgpt-business': {
    provider: 'openai',
    model_id: 'gpt-4o',
    cost_per_1k_tokens: 0.005,
    speed_rating: 2,
    task_tags: ['business', 'enterprise', 'formal', 'document', 'report'],
    max_tokens: 4096,
    active: true,
    use_org: true
  },
  'o1-mini': {
    provider: 'openai',
    model_id: 'o1-mini',
    cost_per_1k_tokens: 0.003,
    speed_rating: 3,
    task_tags: ['reason', 'math', 'logic', 'complex_code', 'architect'],
    max_tokens: 4096,
    active: true
  }
};

// Task → model routing table
const TASK_ROUTING = {
  'write_chapter':       { primary: 'claude-opus',   fallback: 'claude-sonnet' },
  'write_nft_content':   { primary: 'claude-opus',   fallback: 'claude-sonnet' },
  'write_social_post':   { primary: 'claude-sonnet', fallback: 'gpt-4o-mini'  },
  'write_code':          { primary: 'gpt-4o',        fallback: 'claude-sonnet' },
  'format_markdown':     { primary: 'gpt-4o',        fallback: 'gpt-4o-mini'  },
  'debug_code':          { primary: 'gpt-4o',        fallback: 'claude-sonnet' },
  'web_research':        { primary: 'gemini-pro',        fallback: 'gpt-4o'          },
  'summarize':           { primary: 'gemini-flash',      fallback: 'claude-haiku'    },
  'classify':            { primary: 'gemini-flash',      fallback: 'gpt-4o-mini'     },
  'architect':           { primary: 'claude-opus',       fallback: 'o1-mini'         },
  'reason':              { primary: 'o1-mini',           fallback: 'claude-opus'     },
  'business_report':     { primary: 'chatgpt-business',  fallback: 'claude-opus'     },
  'social_post':         { primary: 'gemini-flash',      fallback: 'claude-haiku'    },
  'general':             { primary: 'claude-sonnet',     fallback: 'gpt-4o-mini'     }
};

// Usage tracking
const usageStats = {};

// ============================================================
// SMART ROUTER — picks best model for the task
// ============================================================
function routeToModel(task, priority = 'quality') {
  const routing = TASK_ROUTING[task] || TASK_ROUTING['general'];

  if (priority === 'cost') {
    // Find cheapest active model that has this task tag
    const taskTag = task.split('_')[0];
    const candidates = Object.entries(MODEL_REGISTRY)
      .filter(([_, m]) => m.active && m.task_tags.some(t => t.includes(taskTag)))
      .sort((a, b) => a[1].cost_per_1k_tokens - b[1].cost_per_1k_tokens);
    return candidates[0]?.[0] || routing.primary;
  }

  if (priority === 'speed') {
    const taskTag = task.split('_')[0];
    const candidates = Object.entries(MODEL_REGISTRY)
      .filter(([_, m]) => m.active && m.task_tags.some(t => t.includes(taskTag)))
      .sort((a, b) => a[1].speed_rating - b[1].speed_rating);
    return candidates[0]?.[0] || routing.primary;
  }

  // Default: quality — use routing table
  const primary = MODEL_REGISTRY[routing.primary]?.active ? routing.primary : routing.fallback;
  return primary || 'claude-sonnet';
}

// ============================================================
// MODEL CALLERS — one per provider
// ============================================================
async function callAnthropic(modelKey, prompt, systemPrompt, maxTokens) {
  const Anthropic = require('@anthropic-ai/sdk');
  const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  const model = MODEL_REGISTRY[modelKey];

  const response = await client.messages.create({
    model: model.model_id,
    max_tokens: maxTokens || model.max_tokens,
    system: systemPrompt || 'You are Jarvis, an AI assistant for Intergalactic Corporate Services LLC.',
    messages: [{ role: 'user', content: prompt }]
  });

  return {
    output: response.content[0].text,
    tokens_used: response.usage.input_tokens + response.usage.output_tokens,
    model_used: modelKey,
    provider: 'anthropic'
  };
}

async function callOpenAI(modelKey, prompt, systemPrompt, maxTokens) {
  const model = MODEL_REGISTRY[modelKey];
  // ChatGPT Business uses org ID for enterprise billing
  const headers = {
    'Authorization': `Bearer ${model.use_org && process.env.CHATGPT_BUSINESS_API_KEY ? process.env.CHATGPT_BUSINESS_API_KEY : process.env.OPENAI_API_KEY}`,
    'Content-Type': 'application/json'
  };
  if (model.use_org && process.env.OPENAI_ORG_ID) headers['OpenAI-Organization'] = process.env.OPENAI_ORG_ID;
  const response = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers,
    body: JSON.stringify({
      model: model.model_id,
      max_tokens: maxTokens || model.max_tokens,
      messages: [
        { role: 'system', content: systemPrompt || 'You are Jarvis, an AI assistant.' },
        { role: 'user', content: prompt }
      ]
    })
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error.message);
  return {
    output: data.choices[0].message.content,
    tokens_used: data.usage.total_tokens,
    model_used: modelKey,
    provider: 'openai'
  };
}

async function callGemini(modelKey, prompt, systemPrompt, maxTokens) {
  const model = MODEL_REGISTRY[modelKey];
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model.model_id}:generateContent?key=${process.env.GEMINI_API_KEY}`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{ parts: [{ text: `${systemPrompt ? systemPrompt + '\n\n' : ''}${prompt}` }] }],
      generationConfig: { maxOutputTokens: maxTokens || model.max_tokens }
    })
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error.message);
  return {
    output: data.candidates[0].content.parts[0].text,
    tokens_used: data.usageMetadata?.totalTokenCount || 0,
    model_used: modelKey,
    provider: 'google'
  };
}

async function callModel(modelKey, prompt, systemPrompt, maxTokens) {
  const model = MODEL_REGISTRY[modelKey];
  if (!model) throw new Error(`Unknown model: ${modelKey}`);

  // Track usage
  usageStats[modelKey] = usageStats[modelKey] || { calls: 0, tokens: 0 };
  usageStats[modelKey].calls++;

  let result;
  switch (model.provider) {
    case 'anthropic': result = await callAnthropic(modelKey, prompt, systemPrompt, maxTokens); break;
    case 'openai':    result = await callOpenAI(modelKey, prompt, systemPrompt, maxTokens); break;
    case 'google':    result = await callGemini(modelKey, prompt, systemPrompt, maxTokens); break;
    default: throw new Error(`Unknown provider: ${model.provider}`);
  }

  usageStats[modelKey].tokens += result.tokens_used;
  const cost = (result.tokens_used / 1000) * model.cost_per_1k_tokens;
  usageStats[modelKey].estimated_cost_usd = (usageStats[modelKey].estimated_cost_usd || 0) + cost;

  return result;
}

// ============================================================
// PERSONA SYSTEM — Hermes MemPalace integration
// ============================================================
const PERSONA_SYSTEM_PROMPTS = {
  'lippy-killjoy': 'You are Lippy Killjoy, Mad Clown Scientist and satirical comedian for Intergalactic Corporate Services LLC. Your voice is sharp, irreverent, and always entertaining. You build AI empires through humor and chaos.',
  'lippytm':       'You are lippytm, the technical AI builder persona. Focus on clear, actionable technical output.',
  'lippytmai':     'You are lippytmai, the AI innovation persona. Focus on cutting-edge AI applications and creative systems.',
  'time-pimp':     'You are Time Machine Time Pimp #47, the futurist philosopher persona. Write about time, AI, and the future with dramatic flair.',
  'jarvis':        'You are Jarvis, the central AI coordinator for AI Jarvis Assistants Swarms Systems. Professional, efficient, autonomous.'
};

// ============================================================
// REST API
// ============================================================

// POST /hub/generate — the unified AI call endpoint
app.post('/hub/generate', async (req, res) => {
  try {
    const { task = 'general', prompt, persona = 'jarvis', priority = 'quality', max_tokens, model_override } = req.body;
    if (!prompt) return res.status(400).json({ error: 'prompt required' });

    const modelKey = model_override || routeToModel(task, priority);
    const systemPrompt = PERSONA_SYSTEM_PROMPTS[persona] || PERSONA_SYSTEM_PROMPTS['jarvis'];

    const result = await callModel(modelKey, prompt, systemPrompt, max_tokens);
    res.json({ success: true, task, persona, priority, routed_to: modelKey, ...result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /hub/models — list all available models
app.get('/hub/models', (req, res) => {
  const models = Object.entries(MODEL_REGISTRY).map(([key, m]) => ({
    key,
    provider: m.provider,
    active: m.active,
    task_tags: m.task_tags,
    cost_per_1k_tokens: m.cost_per_1k_tokens,
    speed_rating: m.speed_rating
  }));
  res.json({ models, total: models.length });
});

// GET /hub/usage — token usage and cost stats
app.get('/hub/usage', (req, res) => {
  const totalCost = Object.values(usageStats).reduce((sum, m) => sum + (m.estimated_cost_usd || 0), 0);
  res.json({ usage: usageStats, total_estimated_cost_usd: totalCost.toFixed(4) });
});

// GET /hub/route?task=write_chapter&priority=quality — preview routing decision
app.get('/hub/route', (req, res) => {
  const { task = 'general', priority = 'quality' } = req.query;
  const modelKey = routeToModel(task, priority);
  const model = MODEL_REGISTRY[modelKey];
  res.json({ task, priority, routed_to: modelKey, model_info: model });
});

// PATCH /hub/models/:key — update model config (enable/disable, swap model ID)
app.patch('/hub/models/:key', (req, res) => {
  const model = MODEL_REGISTRY[req.params.key];
  if (!model) return res.status(404).json({ error: 'Model not found' });
  Object.assign(model, req.body);
  res.json({ success: true, model });
});

// POST /hub/zapier — trigger a Zapier webhook (fire-and-forget to any Zap)
app.post('/hub/zapier', async (req, res) => {
  try {
    const { webhook_url, payload } = req.body;
    const url = webhook_url || process.env.ZAPIER_WEBHOOK_URL;
    if (!url) return res.status(400).json({ error: 'webhook_url required (or set ZAPIER_WEBHOOK_URL env)' });
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || req.body)
    });
    res.json({ success: true, zapier_status: resp.status });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /hub/health
app.get('/hub/health', (req, res) => {
  const activeModels = Object.values(MODEL_REGISTRY).filter(m => m.active).length;
  const providers = [...new Set(Object.values(MODEL_REGISTRY).map(m => m.provider))];
  res.json({
    status: 'running',
    active_models: activeModels,
    total_models: Object.keys(MODEL_REGISTRY).length,
    providers,
    model_keys: Object.keys(MODEL_REGISTRY),
    version: '2.0.0',
    system: 'Jarvis-Hub — Private AI Model Registry',
    beats: 'HuggingFace',
    integrations: ['anthropic', 'openai', 'chatgpt-business', 'google-gemini', 'zapier-webhook']
  });
});

// ============================================================
// START
// ============================================================
const PORT = process.env.JARVIS_HUB_PORT || 3003;
app.listen(PORT, () => {
  console.log(`\n🧠 Jarvis-Hub running on port ${PORT}`);
  console.log(`   Active models: ${Object.values(MODEL_REGISTRY).filter(m => m.active).length}`);
  console.log(`   AI Jarvis Assistants Swarms Systems`);
  console.log(`   Intergalactic Corporate Services LLC\n`);
});
