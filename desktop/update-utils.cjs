'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

function isValidUpdateFeed(value, allowLocal = false) {
  if (typeof value !== 'string') return false;
  try {
    const url = new URL(value);
    if (url.username || url.password || url.hash || url.search) return false;
    if (url.protocol === 'https:') return !!url.hostname;
    return allowLocal && url.protocol === 'http:' && ['localhost','127.0.0.1'].includes(url.hostname);
  } catch { return false; }
}
function safeReport(value) {
  return String(value ?? '')
    .replace(/(authorization\s*[:=]\s*bearer\s+)\S+/ig, '$1[REDACTED]')
    .replace(/(cookie\s*[:=]\s*)[^\r\n]+/ig, '$1[REDACTED]')
    .replace(/([?&](?:token|auth|password|key|signature|api_key|access_token)=)[^\s&]+/ig, '$1[REDACTED]')
    .replace(/(--cookies?\s+)[^\s]+/ig, '$1[REDACTED]')
    .slice(-12000);
}
function writeAtomic(filename, value) {
  fs.mkdirSync(path.dirname(filename), {recursive: true});
  const tmp = filename + '.' + process.pid + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(value, null, 2), {encoding:'utf8', mode:0o600});
  fs.renameSync(tmp, filename);
}
function readJSON(filename, fallback = {}) {
  try { return JSON.parse(fs.readFileSync(filename, 'utf8')); } catch { return fallback; }
}
function sha512(filename) {
  return crypto.createHash('sha512').update(fs.readFileSync(filename)).digest('base64');
}
module.exports = {isValidUpdateFeed, safeReport, writeAtomic, readJSON, sha512};
