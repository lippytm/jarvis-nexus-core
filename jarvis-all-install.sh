#!/bin/bash
# ============================================================
# JARVIS SWARM — Master Install Script
# Installs: Flow (3002) + Hub (3003) + Nexus (3004) + Blast (3005)
# AI Jarvis Assistants Swarms Systems
# Intergalactic Corporate Services LLC
# AI Builds AI — lippytm
# ============================================================
set -e

JARVIS_DIR="${HOME}/jarvis-swarm"
GITHUB_RAW="https://raw.githubusercontent.com/lippytm/jarvis-nexus-core/main"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║     JARVIS SWARM — AI Builds AI Install              ║"
echo "║     Flow + Hub + Nexus + Blast                       ║"
echo "║     Intergalactic Corporate Services LLC             ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Phase 1: System Dependencies ────────────────────────────
echo "▶ Phase 1: System dependencies..."
apt-get update -qq 2>/dev/null || true
which node &>/dev/null || {
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
}
which pm2 &>/dev/null || npm install -g pm2
which git  &>/dev/null || apt-get install -y git
echo "✓ Node $(node -v) | PM2 $(pm2 -v)"

# ── Phase 2: Create directories ──────────────────────────────
echo "▶ Phase 2: Creating Jarvis directory..."
mkdir -p "${JARVIS_DIR}"
mkdir -p "${HOME}/.jarvis-flow/workflows"
mkdir -p "${HOME}/.jarvis-hub"
mkdir -p "${HOME}/.jarvis-nexus"
mkdir -p "${HOME}/.jarvis-blast/queue"
echo "✓ Directories created"

# ── Phase 3: Download server files ──────────────────────────
echo "▶ Phase 3: Downloading Jarvis service files..."
cd "${JARVIS_DIR}"

for FILE in \
  jarvis-flow-server.js \
  jarvis-hub-server.js \
  jarvis-nexus-core.js \
  jarvis-blast-server.js \
  package.json \
  ecosystem.config.js; do
  echo "  ↓ ${FILE}"
  curl -fsSL "${GITHUB_RAW}/${FILE}" -o "${FILE}" || {
    echo "  ⚠ Could not fetch ${FILE} from GitHub — skipping"
  }
done
echo "✓ Files downloaded"

# ── Phase 4: Install Node dependencies ───────────────────────
echo "▶ Phase 4: Installing npm dependencies..."
npm install --omit=dev
echo "✓ Dependencies installed"

# ── Phase 5: .env setup ──────────────────────────────────────
ENV_FILE="${JARVIS_DIR}/.env"
echo "▶ Phase 5: Setting up .env..."

if [ ! -f "${ENV_FILE}" ]; then
  cat > "${ENV_FILE}" << 'ENVEOF'
# ── AI Provider Keys ─────────────────────────────────────────
ANTHROPIC_API_KEY=your_anthropic_key_here
OPENAI_API_KEY=your_openai_key_here
GEMINI_API_KEY=your_gemini_key_here

# ── GitHub ───────────────────────────────────────────────────
GITHUB_TOKEN=your_github_token_here

# ── Social Media (Jarvis-Blast) ──────────────────────────────
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
LINKEDIN_ACCESS_TOKEN=your_linkedin_access_token
LINKEDIN_PERSON_URN=urn:li:person:YOUR_ID
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_DEFAULT_CHANNEL=your_channel_id
BLUESKY_ACCESS_TOKEN=your_bluesky_token
BLUESKY_DID=did:plc:your_did
INSTAGRAM_ACCESS_TOKEN=your_instagram_token
REDDIT_ACCESS_TOKEN=your_reddit_token
REDDIT_DEFAULT_SUBREDDIT=your_subreddit
MASTODON_ACCESS_TOKEN=your_mastodon_token
MASTODON_INSTANCE=mastodon.social
TELEGRAM_BOT_TOKEN=your_telegram_token
TELEGRAM_DEFAULT_CHAT=your_chat_id
SLACK_BOT_TOKEN=your_slack_token
SLACK_DEFAULT_CHANNEL=#general
FACEBOOK_ACCESS_TOKEN=your_facebook_page_access_token
FACEBOOK_PAGE_ID=your_facebook_page_id
THREADS_ACCESS_TOKEN=your_threads_access_token
THREADS_USER_ID=your_threads_user_id
SUBSTACK_URL=https://yourblog.substack.com
SUBSTACK_TOKEN=your_substack_session_token
SUBSTACK_ZAPIER_WEBHOOK=your_zapier_webhook_for_substack

# ── ChatGPT Business / OpenAI Enterprise ─────────────────────
CHATGPT_BUSINESS_API_KEY=your_chatgpt_business_api_key
OPENAI_ORG_ID=your_openai_org_id
ZAPIER_WEBHOOK_URL=your_zapier_catch_hook_url

# ── Blockchain / NFT ─────────────────────────────────────────
OPENSEA_API_KEY=your_opensea_key
ALCHEMY_API_KEY=your_alchemy_key
MORALIS_API_KEY=your_moralis_key

# ── Payment / E-Commerce ─────────────────────────────────────
STRIPE_SECRET_KEY=your_stripe_key
SHOPIFY_ACCESS_TOKEN=your_shopify_token
SHOPIFY_STORE_DOMAIN=your-store.myshopify.com

# ── Cloud / Infra ────────────────────────────────────────────
CLOUDFLARE_API_TOKEN=your_cloudflare_token
VERCEL_TOKEN=your_vercel_token

# ── Communication ────────────────────────────────────────────
SENDGRID_API_KEY=your_sendgrid_key
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token

# ── Data / CMS ───────────────────────────────────────────────
AIRTABLE_API_KEY=your_airtable_key
NOTION_API_KEY=your_notion_key
WORDPRESS_URL=https://your-site.com
WORDPRESS_USER=your_wp_user
WORDPRESS_APP_PASSWORD=your_wp_app_password

# ── Audio / Video AI ─────────────────────────────────────────
ELEVENLABS_API_KEY=your_elevenlabs_key
ASSEMBLYAI_API_KEY=your_assemblyai_key

# ── Image AI ─────────────────────────────────────────────────
STABILITY_API_KEY=your_stability_key
REPLICATE_API_TOKEN=your_replicate_token

# ── Jarvis Service URLs ───────────────────────────────────────
JARVIS_FLOW_PORT=3002
JARVIS_HUB_PORT=3003
JARVIS_NEXUS_PORT=3004
JARVIS_BLAST_PORT=3005
JARVIS_HUB_URL=http://localhost:3003
JARVIS_BLAST_URL=http://localhost:3005
ENVEOF
  echo "✓ Created .env — EDIT IT: nano ${ENV_FILE}"
else
  echo "✓ .env already exists — skipping (edit manually if needed)"
fi

# ── Phase 6: Load .env into PM2 ecosystem ────────────────────
echo "▶ Phase 6: Injecting .env into ecosystem.config.js..."
node -e "
const fs = require('fs');
const env = {};
const lines = fs.readFileSync('${ENV_FILE}', 'utf8').split('\n');
for (const l of lines) {
  const m = l.match(/^([A-Z_][A-Z0-9_]*)=(.+)/);
  if (m) env[m[1]] = m[2];
}
const eco = require('${JARVIS_DIR}/ecosystem.config.js');
for (const app of eco.apps) app.env = { ...app.env, ...env };
fs.writeFileSync('${JARVIS_DIR}/ecosystem.config.js',
  'module.exports = ' + JSON.stringify(eco, null, 2));
" 2>/dev/null && echo "✓ .env merged into ecosystem" || echo "⚠ Could not auto-merge .env — set vars manually in ecosystem.config.js"

# ── Phase 7: Start all services ──────────────────────────────
echo "▶ Phase 7: Starting all Jarvis services with PM2..."
cd "${JARVIS_DIR}"
pm2 delete all 2>/dev/null || true
pm2 start ecosystem.config.js
pm2 save
pm2 startup 2>/dev/null || true
echo "✓ All services started"

# ── Phase 8: Health check ────────────────────────────────────
echo "▶ Phase 8: Health checks..."
sleep 3
for PORT_NAME in "3002:Jarvis-Flow" "3003:Jarvis-Hub" "3004:Jarvis-Nexus" "3005:Jarvis-Blast"; do
  PORT="${PORT_NAME%%:*}"
  NAME="${PORT_NAME##*:}"
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:${PORT}/${NAME,,}/health 2>/dev/null || echo "000")
  if [ "${HTTP}" = "200" ]; then
    echo "  ✓ ${NAME} (port ${PORT}) — UP"
  else
    echo "  ⚠ ${NAME} (port ${PORT}) — ${HTTP} (check: pm2 logs ${NAME,,})"
  fi
done

# ── Done ─────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  JARVIS SWARM INSTALLED                              ║"
echo "║                                                      ║"
echo "║  Jarvis-Flow  → http://localhost:3002/flow/health    ║"
echo "║  Jarvis-Hub   → http://localhost:3003/hub/health     ║"
echo "║  Jarvis-Nexus → http://localhost:3004/nexus/health   ║"
echo "║  Jarvis-Blast → http://localhost:3005/blast/health   ║"
echo "║                                                      ║"
echo "║  NEXT: nano ${HOME}/jarvis-swarm/.env               ║"
echo "║        (add your API keys, then: pm2 restart all)   ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
