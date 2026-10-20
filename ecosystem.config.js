/**
 * PM2 Ecosystem — All Jarvis Services
 * AI Jarvis Assistants Swarms Systems — Intergalactic Corporate Services LLC
 */
module.exports = {
  apps: [
    {
      name: 'jarvis-flow',
      script: 'jarvis-flow-server.js',
      env: { JARVIS_FLOW_PORT: 3002, NODE_ENV: 'production' },
      watch: false,
      max_restarts: 10,
      restart_delay: 5000,
      log_date_format: 'YYYY-MM-DD HH:mm:ss'
    },
    {
      name: 'jarvis-hub',
      script: 'jarvis-hub-server.js',
      env: { JARVIS_HUB_PORT: 3003, NODE_ENV: 'production' },
      watch: false,
      max_restarts: 10,
      restart_delay: 5000
    },
    {
      name: 'jarvis-nexus',
      script: 'jarvis-nexus-core.js',
      env: { JARVIS_NEXUS_PORT: 3004, NODE_ENV: 'production' },
      watch: false,
      max_restarts: 10,
      restart_delay: 5000
    },
    {
      name: 'jarvis-blast',
      script: 'jarvis-blast-server.js',
      env: { JARVIS_BLAST_PORT: 3005, NODE_ENV: 'production' },
      watch: false,
      max_restarts: 10,
      restart_delay: 5000
    }
  ]
};
