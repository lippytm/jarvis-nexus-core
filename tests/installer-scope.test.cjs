const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.join(__dirname, '..');
const script = fs.readFileSync(path.join(root, 'jarvis-all-install.sh'), 'utf8');
const ecosystem = fs.readFileSync(path.join(root, 'ecosystem.config.js'), 'utf8');

test('installer does not delete every PM2 application', () => {
  assert.doesNotMatch(script, /^\s*pm2\s+(?:delete|kill|stop|restart)\s+all\b/m);
  const deletion = script.match(/for SERVICE in ([^\n]+); do\r?\n\s+pm2 delete "\$\{SERVICE\}" 2>\/dev\/null \|\| true\r?\ndone/);
  assert.ok(deletion, 'PM2 deletion must be confined to the explicit service loop');
  const targets = deletion[1].trim().split(/\s+/);
  const declared = [...ecosystem.matchAll(/name:\s*'([^']+)'/g)].map(m => m[1]);
  assert.equal(targets.length, 4);
  assert.deepEqual([...targets].sort(), [...declared].sort());
  assert.ok(!targets.includes('unrelated-website'));
  const outsideLoop = script.replace(deletion[0], '');
  assert.doesNotMatch(outsideLoop, /^\s*pm2\s+delete\b/m);
});
