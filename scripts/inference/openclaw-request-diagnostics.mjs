// Opt-in, bounded metadata only. Never retains prompts, headers, credentials or answers.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createHmac, randomBytes, randomUUID } from 'node:crypto';

const key = randomBytes(32); // Process-local: hashes cannot be compared across restarts.
const epoch = randomUUID();
const directory = path.join(os.homedir(), '.openclaw', 'diagnostics');
const logfile = path.join(directory, 'requests.jsonl');
const digest = value => createHmac('sha256', key).update(JSON.stringify(value ?? null)).digest('hex');
const numeric = value => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;

export function summarizePayload(payload) {
  const messages = Array.isArray(payload.messages) ? payload.messages : [];
  const tools = Array.isArray(payload.tools) ? payload.tools : [];
  return {
    messages: messages.map(message => ({
      role: ['system','developer','user','assistant','tool'].includes(message.role) ? message.role : 'other',
      hash: digest(message),
      // Fixed-size chunks locate divergence without exposing section titles or text.
      chunks: ['system','developer'].includes(message.role)
        ? (JSON.stringify(message.content ?? '').match(/[\s\S]{1,1024}/g) ?? []).slice(0,512).map(digest) : undefined,
    })),
    tools: tools.map(digest),
    settings_hash: digest(Object.fromEntries(Object.entries(payload).filter(([name]) =>
      !['messages','tools'].includes(name)))),
    message_count: messages.length, tool_count: tools.length,
  };
}

function enabled() {
  try {
    const dir = fs.lstatSync(directory);
    return dir.isDirectory() && !dir.isSymbolicLink() && dir.uid === process.getuid()
      && (dir.mode & 0o077) === 0 && fs.existsSync(path.join(directory, 'request-hashes.enabled'));
  } catch { return false; }
}

function record(row) {
  try {
    if (!enabled()) return;
    if (fs.existsSync(logfile)) {
      const st = fs.lstatSync(logfile);
      if (!st.isFile() || st.isSymbolicLink() || st.uid !== process.getuid()) return;
      if (st.size > 5 * 1024 * 1024) fs.renameSync(logfile, logfile + '.previous');
    }
    const fd = fs.openSync(logfile, fs.constants.O_WRONLY | fs.constants.O_APPEND | fs.constants.O_CREAT | fs.constants.O_NOFOLLOW, 0o600);
    try { fs.writeSync(fd, JSON.stringify({at: new Date().toISOString(), epoch, ...row}) + '\n'); }
    finally { fs.closeSync(fd); }
  } catch { /* Diagnostics must not break inference. */ }
}

export function traceManagedRequest(model, options, invoke) {
  if (model.provider !== 'sovereign' || !['gpu-oracle','gpu-logic'].includes(model.id) || !enabled()) return invoke(options);
  const id = randomUUID(), started = performance.now();
  const capture = payload => {
    try { record({event: 'request', id, route: model.id, ...summarizePayload(payload)}); } catch {}
  };
  const traced = {...options, onPayload(payload, ...rest) {
    const value = options?.onPayload?.(payload, ...rest);
    if (value && typeof value.then === 'function') value.then(result => capture(result ?? payload), () => {});
    else capture(value ?? payload);
    return value;
  }};
  const stream = invoke(traced);
  // result() observes the independently resolved final result; never consumes the event iterator.
  Promise.resolve(stream).then(s => s.result()).then(result => {
    const usage = result?.usage ?? {};
    record({event: 'result', id, route: model.id, ms: Math.round(performance.now() - started),
      input: numeric(usage.input), output: numeric(usage.output),
      cacheRead: numeric(usage.cacheRead), cacheWrite: numeric(usage.cacheWrite),
      error: result?.stopReason === 'error'});
  }, () => record({event: 'result', id, route: model.id, error: true, ms: Math.round(performance.now() - started)}));
  return stream;
}
