// webapp/_shared/cockpit-runtime.js — the sanctioned shared cockpit-crate runtime.
//
// The ~418 typed sovereign-cockpit-* crates model the cockpit's UX-state logic,
// but the panels are self-contained HTML that never used them (audit F-2026-001).
// This is the one external module a panel loads to actually RUN those crates: it
// lazy-loads the full cockpit-wasm bridge (built on demand — make cockpit-wasm)
// and computes real, per-panel results with the REAL crates the daemon trusts —
// no hand-rolled JS copy that can drift.
//
// A panel adopts it with one additive line near </body>:
//     <script type="module">
//       import { enhance } from '/_shared/cockpit-runtime.js';
//       enhance(document).catch(() => {});    // graceful: no-op if the bridge is absent
//     </script>
// enhance() is dispatched by the panel's x-sovereign-module meta tag, so each panel
// gets the crate work that fits it. Every step is isolated + try/caught, so a
// missing/unserved bridge simply does nothing — it can never break a panel.

const BRIDGE_URL = '/_shared/cockpit-wasm/cockpit_wasm_full.js';

let _mod = null, _loading = null;
export async function bridge() {
  if (_mod) return _mod;
  if (!_loading) _loading = (async () => {
    try { const m = await import(BRIDGE_URL); await m.default(); _mod = m; return m; }
    catch (_) { return null; }
  })();
  return _loading;
}

const J = (s) => { try { return JSON.parse(s); } catch (_) { return null; } };
const el = (tag, css, txt) => { const e = document.createElement(tag); if (css) e.style.cssText = css; if (txt != null) e.textContent = txt; return e; };

// ---- CSS-color -> rgb (handles #rgb, #rrggbb, rgb()) via a canvas fallback -----
let _probe;
function toRgb(color) {
  const c = (color || '').trim();
  let m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(c);
  if (m) return { r: parseInt(m[1], 16), g: parseInt(m[2], 16), b: parseInt(m[3], 16) };
  m = /^#([0-9a-f])([0-9a-f])([0-9a-f])$/i.exec(c);
  if (m) return { r: parseInt(m[1] + m[1], 16), g: parseInt(m[2] + m[2], 16), b: parseInt(m[3] + m[3], 16) };
  m = /rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)/i.exec(c);
  if (m) return { r: +m[1], g: +m[2], b: +m[3] };
  try {
    _probe = _probe || document.createElement('canvas').getContext('2d');
    _probe.fillStyle = c; const h = _probe.fillStyle; // normalised to #rrggbb
    m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(h);
    if (m) return { r: parseInt(m[1], 16), g: parseInt(m[2], 16), b: parseInt(m[3], 16) };
  } catch (_) { /* ignore */ }
  return null;
}
const cssVar = (root, name) => { try { return getComputedStyle(root.documentElement || document.documentElement).getPropertyValue(name).trim(); } catch (_) { return ''; } };

// ---- crate wrappers (each degrades to null if the bridge is absent) -----------

/** WCAG verdict for two CSS colors, via sovereign-cockpit-color-contrast. */
export async function contrast(fg, bg, large = false) {
  const m = await bridge(); if (!m) return null;
  const f = toRgb(fg), b = toRgb(bg); if (!f || !b) return null;
  return J(m.color_contrast_verdict(JSON.stringify(f), JSON.stringify(b), !!large));
}
/** "5 minutes ago" for an epoch-ms instant, via sovereign-cockpit-relative-time. */
export async function relTime(itemMs, nowMs = Date.now()) {
  const m = await bridge(); if (!m) return null;
  const r = J(m.relative_time_format(nowMs, itemMs)); return r ? (r.value ?? r) : null;
}
/** Word/reading stats for text, via sovereign-cockpit-word-count. */
export async function wordCount(text, wpm = 200) {
  const m = await bridge(); if (!m) return null;
  const r = J(m.word_count_count(String(text || ''), Math.max(1, wpm | 0)));
  return r && r.ok ? r.value : null;
}
/** Char-aware truncation via sovereign-cockpit-text-truncation ("end"/"middle"/"start"). */
export async function truncate(text, max, where = 'middle') {
  const m = await bridge(); if (!m) return null;
  const r = J(m.text_truncation_truncate(String(text || ''), Math.max(1, max | 0), where, '…'));
  return r && r.ok ? r.value : null;
}
/** Run any uniform crate's real validate() on a candidate state JSON. */
export async function validate(fn, json) {
  const m = await bridge(); if (!m || typeof m[fn] !== 'function') return null;
  return J(m[fn](json));
}
/** Call any exported crate compute fn by name; parsed result or null. */
async function bcall(fn, ...args) {
  const m = await bridge(); if (!m || typeof m[fn] !== 'function') return null;
  return J(m[fn](...args));
}

// ---- the WCAG audit: every meaningful token pair, judged by the real crate -----

const PAIRS = [
  ['body text', '--fg', '--bg'], ['muted text', '--muted', '--bg'],
  ['accent / links', '--accent', '--bg'], ['heading on panel', '--accent', '--panel'],
  ['text on panel', '--fg', '--panel'], ['ok status', '--good', '--panel'],
  ['bad status', '--bad', '--panel'], ['warn status', '--warn', '--panel'],
];
export async function auditPalette(root = document) {
  const out = [];
  for (const [label, fgv, bgv] of PAIRS) {
    const fg = cssVar(root, fgv), bg = cssVar(root, bgv);
    if (!fg || !bg) continue;
    const v = await contrast(fg, bg); if (!v) continue;
    out.push({ label, fg, bg, ratio: v.ratio, aa: v.passes_aa, aaa: v.passes_aaa });
  }
  return out;
}

function a11yBadge(root, audit) {
  if (root.getElementById('cockpit-crates-badge')) return;
  const fails = audit.filter(r => !r.aa).length;
  const ok = fails === 0;
  const b = el('button', 'position:fixed;bottom:.4rem;right:.5rem;z-index:9998;'
    + 'font:11px ui-monospace,Menlo,Consolas,monospace;padding:.15rem .55rem;border-radius:10px;'
    + `opacity:.8;border:1px solid;cursor:pointer;color:${ok ? '#7ad17a' : '#e6c062'};`
    + `border-color:${ok ? '#7ad17a' : '#e6c062'};background:rgba(0,0,0,.4)`);
  b.id = 'cockpit-crates-badge';
  b.textContent = `cockpit-crates · WCAG ${audit.length - fails}/${audit.length} AA`;
  b.title = 'This panel’s palette audited by the real sovereign-cockpit-color-contrast crate (wasm). Click for detail.';
  b.onclick = () => {
    let ov = root.getElementById('cockpit-crates-ov');
    if (ov) { ov.remove(); return; }
    ov = el('div', 'position:fixed;bottom:2.2rem;right:.5rem;z-index:9999;max-width:22rem;'
      + 'font:11px ui-monospace,Menlo,Consolas,monospace;padding:.6rem .7rem;border-radius:6px;'
      + 'background:#111;color:#e6e6e6;border:1px solid #333;box-shadow:0 6px 24px rgba(0,0,0,.5)');
    ov.id = 'cockpit-crates-ov';
    ov.appendChild(el('div', 'font-weight:600;margin-bottom:.35rem;color:#9bd1ff', 'WCAG contrast (sovereign-cockpit-color-contrast)'));
    for (const r of audit) {
      const row = el('div', 'display:flex;justify-content:space-between;gap:1rem;padding:.05rem 0');
      row.appendChild(el('span', '', r.label));
      row.appendChild(el('span', `color:${r.aa ? '#7ad17a' : '#ff7676'}`, `${r.ratio.toFixed(1)}:1 ${r.aa ? 'AA' : '✗'}${r.aaa ? 'A' : ''}`));
      ov.appendChild(row);
    }
    (root.body || document.body).appendChild(ov);
  };
  (root.body || document.body).appendChild(b);
}

// ---- best-effort relative-time on visible ISO timestamps ----------------------
async function applyRelTime(root) {
  const ISO = /^\s*(\d{4}-\d{2}-\d{2}T[\d:.]+Z?)\s*$/;
  const w = document.createTreeWalker(root.body || document.body, NodeFilter.SHOW_TEXT);
  const hits = [];
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    const m = ISO.exec(n.nodeValue);
    if (m && n.parentElement && !n.parentElement.dataset.ccRel) hits.push([n, m[1]]);
  }
  for (const [node, iso] of hits) {
    const t = Date.parse(iso); if (!Number.isFinite(t)) continue;
    const rel = await relTime(t); if (!rel) continue;
    node.parentElement.dataset.ccRel = '1'; node.parentElement.title = iso; node.nodeValue = ` ${rel} `;
  }
}

// ---- per-panel deep sections (dispatched by x-sovereign-module) ----------------

function section(title) {
  const s = el('section', 'margin:1.2rem auto;max-width:1000px;padding:.9rem 1rem;'
    + 'border:1px solid var(--border,#262626);border-radius:4px;background:var(--panel,#171717)');
  s.dataset.cockpitCrates = '1';
  s.appendChild(el('h2', 'font-size:1rem;margin:0 0 .5rem;color:var(--accent,#9bd1ff)', title));
  return s;
}

// ux-design-audit: a full WCAG matrix of the design tokens — the panel's own job.
async function enhanceUxDesignAudit(root, audit) {
  if (root.querySelector('[data-cockpit-crates="uxa"]')) return;
  const s = section('Live WCAG contrast — computed by sovereign-cockpit-color-contrast (wasm)');
  s.setAttribute('data-cockpit-crates', 'uxa');
  const tbl = el('table', 'width:100%;border-collapse:collapse;font-size:.82rem');
  const head = el('tr'); ['pair', 'fg', 'bg', 'ratio', 'AA', 'AAA'].forEach(h => {
    const th = el('th', 'text-align:left;color:var(--muted,#888);border-bottom:1px solid var(--border,#262626);padding:.2rem .4rem', h); head.appendChild(th);
  }); tbl.appendChild(head);
  for (const r of audit) {
    const tr = el('tr');
    const cells = [r.label, r.fg, r.bg, `${r.ratio.toFixed(2)}:1`, r.aa ? '✓' : '✗', r.aaa ? '✓' : '✗'];
    cells.forEach((c, i) => {
      const td = el('td', 'padding:.2rem .4rem;border-bottom:1px solid var(--border,#1c1c1c)', c);
      if (i === 4) td.style.color = r.aa ? '#7ad17a' : '#ff7676';
      if (i === 5) td.style.color = r.aaa ? '#7ad17a' : '#888';
      tr.appendChild(td);
    });
    tbl.appendChild(tr);
  }
  s.appendChild(tbl);
  s.appendChild(el('p', 'font-size:.74rem;color:var(--muted,#888);margin:.5rem 0 0',
    'Every ratio + AA/AAA verdict is the crate’s own computation (F-2026-001), not a JS copy.'));
  (root.body || document.body).appendChild(s);
}

// personalization: warn (live) if the operator's chosen theme is not accessible.
async function enhancePersonalization(root, audit) {
  if (root.querySelector('[data-cockpit-crates="pers"]')) return;
  const fails = audit.filter(r => !r.aa);
  const s = section('Accessibility of your theme — live (sovereign-cockpit-color-contrast)');
  s.setAttribute('data-cockpit-crates', 'pers');
  if (fails.length === 0) {
    s.appendChild(el('div', 'color:#7ad17a', `✓ all ${audit.length} text/background pairs pass WCAG AA (${Math.min(...audit.map(r => r.ratio)).toFixed(1)}:1 worst).`));
  } else {
    s.appendChild(el('div', 'color:#ff7676;font-weight:600', `✗ ${fails.length} pair(s) fail WCAG AA — the crate flags:`));
    fails.forEach(r => s.appendChild(el('div', 'color:var(--muted,#888)', `   ${r.label}: ${r.ratio.toFixed(1)}:1`)));
  }
  s.appendChild(el('p', 'font-size:.74rem;color:var(--muted,#888);margin:.5rem 0 0',
    'Change your colors above and this re-checks them with the real crate.'));
  (root.body || document.body).appendChild(s);
}

// doc-coverage: real word/reading stats for the page content, via word-count.
async function enhanceDocCoverage(root) {
  if (root.querySelector('[data-cockpit-crates="doc"]')) return;
  const text = (root.body || document.body).innerText || '';
  const stats = await wordCount(text); if (!stats) return;
  const s = section('Page content stats — sovereign-cockpit-word-count (wasm)');
  s.setAttribute('data-cockpit-crates', 'doc');
  s.appendChild(el('div', '', `${stats.words} words · ${stats.chars} chars · ~${(stats.reading_time_ms / 1000).toFixed(0)}s to read`));
  (root.body || document.body).appendChild(s);
}

// d-06-pending-approvals: roll up the live approvals by severity with the REAL
// sovereign-cockpit-alert-group crate (replacing the panel's hand-rolled sort).
const SEV = { critical: 'critical', high: 'error', medium: 'warning', low: 'info' };
async function enhanceApprovals(root) {
  if (root.querySelector('[data-cockpit-crates="appr"]')) return;
  let data; try { data = await (await fetch('/api/approvals/pending', { cache: 'no-store' })).json(); } catch (_) { return; }
  const list = Array.isArray(data) ? data : (data.approvals || data.pending || []);
  if (!list.length) return;
  const events = list.map(a => ({
    tag: a.kind || a.type || a.severity || 'approval',
    severity: SEV[a.severity] || 'info',
    ts_ms: Date.parse(a.ts || a.created_at || a.created || '') || 0,
  }));
  const r = await bcall('alert_group_rollup', JSON.stringify(events));
  if (!r || !r.ok) return;
  const s = section('Pending approvals rolled up — sovereign-cockpit-alert-group (wasm)');
  s.setAttribute('data-cockpit-crates', 'appr');
  s.appendChild(el('div', '', `${r.total} pending across ${r.groups.length} group(s) — grouped + severity-ordered by the crate, not the panel's JS:`));
  for (const g of r.groups) s.appendChild(el('div', 'color:var(--muted,#888)', `   ${g.tag}: ${g.count} · worst ${g.max_severity}`));
  (root.body || document.body).appendChild(s);
}

// models-catalog: facet the live model list with the REAL sovereign-cockpit-facet-counts crate.
async function enhanceModelsCatalog(root) {
  if (root.querySelector('[data-cockpit-crates="mcat"]')) return;
  let data; try { data = await (await fetch('/api/models-catalog/catalog', { cache: 'no-store' })).json(); } catch (_) { return; }
  const models = data.models || (data.catalog && data.catalog.models) || (Array.isArray(data) ? data : []);
  if (!models.length) return;
  const counts = {};
  const bump = (f, b) => { if (b == null || b === '') return; (counts[f] = counts[f] || {})[b] = (counts[f][b] || 0) + 1; };
  for (const mdl of models) { bump('class', mdl.class); bump('tier', mdl.tier || mdl.srp_tier); bump('quant', mdl.quantization || mdl.quant); }
  const r = await bcall('facet_counts_top', JSON.stringify(counts), 6);
  if (!r || r.ok === false) return;
  const s = section('Model-catalog facets — sovereign-cockpit-facet-counts (wasm)');
  s.setAttribute('data-cockpit-crates', 'mcat');
  for (const [facet, top] of Object.entries(r)) s.appendChild(el('div', '', `${facet}: ` + top.map(([b, n]) => `${b} (${n})`).join(' · ')));
  (root.body || document.body).appendChild(s);
}

const ENHANCERS = {
  'ux-design-audit-webapp': enhanceUxDesignAudit,
  'personalization-webapp': enhancePersonalization,
  'doc-coverage-webapp': enhanceDocCoverage,
  'd-06-pending-approvals-webapp': enhanceApprovals,
  'models-catalog-webapp': enhanceModelsCatalog,
};

/**
 * Additive, graceful per-panel crate integration:
 *   - every panel: a real WCAG audit of its palette (color-contrast) as a badge +
 *     click-through detail, plus relative-time on visible ISO timestamps;
 *   - matched panels: a deep section computed by the crate that fits them.
 * All isolated + try/caught — no-op if the bridge is absent, never breaks a panel.
 */
export async function enhance(root = document) {
  const m = await bridge();
  if (!m) return false;
  let audit = [];
  try { audit = await auditPalette(root); if (audit.length) a11yBadge(root, audit); } catch (_) {}
  try { await applyRelTime(root); } catch (_) {}
  try {
    const mod = (root.querySelector?.('meta[name="x-sovereign-module"]') || {}).content;
    const fn = ENHANCERS[mod];
    if (fn) await fn(root, audit);
  } catch (_) {}
  return true;
}

export default { bridge, contrast, relTime, wordCount, truncate, validate, auditPalette, enhance };
