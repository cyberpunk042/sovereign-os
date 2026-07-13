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

/** Route a tab activation through the REAL sovereign-cockpit-tab-strip crate: it validates
 *  the id (rejecting an unknown tab) and returns the resolved active id — or null if the
 *  bridge is unavailable, so a panel can fall back to its own logic. Used by panels that
 *  make the crate the source of truth for their tab bar (F-2026-001, invasive adoption). */
export async function tabActivate(stateJson, id) {
  const r = await bcall('tab_strip_activate', stateJson, id);
  return (r && r.ok) ? r.active_id : null;
}

/** SYNC command-palette highlight navigation via the REAL sovereign-cockpit-autocomplete-list
 *  crate (wrap-around). `op` is "down" | "up". Returns the new highlight index, or null when the
 *  bridge isn't loaded yet (so the caller keeps its own fallback). Sync on purpose — it uses the
 *  already-loaded module (populated by bridge()/enhance()), so a keydown handler stays instant.
 *  Used by the shared Ctrl-K palette (F-2026-001, invasive adoption across all panels). */
export function autocompleteNav(stateJson, op) {
  if (!_mod || typeof _mod.autocomplete_nav !== 'function') return null;
  const r = J(_mod.autocomplete_nav(stateJson, op));
  return (r && r.ok && typeof r.highlight === 'number') ? r.highlight : null;
}

/** SYNC keyboard-chord resolution via the REAL sovereign-cockpit-keystroke-map crate: given a
 *  keymap (JSON) and a `key`, return the bound `action_id` for a Ctrl/Cmd chord in `global`
 *  scope, or null when the bridge isn't loaded (so the caller keeps its own fallback). Used by
 *  the shared app-shell shortcuts (F-2026-001, invasive adoption across all panels). */
export function keystrokeResolve(mapJson, key) {
  if (!_mod || typeof _mod.keystroke_map_resolve !== 'function') return null;
  const r = J(_mod.keystroke_map_resolve(mapJson, 'global', true, false, false, false, key));
  return (r && r.ok) ? (r.action_id || null) : null;
}

// --- panel widget adoption helpers (F-2026-001) — a panel drives its own widget through the
//     crate; each returns the crate's new state, or null when the bridge is absent (fall back). ---
/** Advance a Stepper through the crate (op: complete/back/next/skip/fail). Returns new state or null. */
export async function stepperAdvance(stateJson, op) {
  const r = await bcall('stepper_advance', stateJson, op);
  return (r && r.ok) ? r.value : null;
}
/** Toggle a collapsible section through the crate. Returns {collapsed, value} or null. */
export async function collapsibleToggle(stateJson, id) {
  const r = await bcall('collapsible_toggle', stateJson, id);
  return (r && r.ok) ? { collapsed: r.collapsed, value: r.value } : null;
}
/** Toggle a checklist item through the crate. Returns {done, total, percent, value} or null. */
export async function checklistToggle(stateJson, id, tsMs, currentlyDone) {
  const r = await bcall('checklist_toggle', stateJson, id, tsMs, currentlyDone);
  return (r && r.ok) ? { done: r.done, total: r.total, percent: r.percent, value: r.value } : null;
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

// A rollup section: group a panel's live rows by tag, keeping the WORST severity
// per group, via the REAL sovereign-cockpit-alert-group crate. Additive + graceful.
function alertRollupEnhancer({ endpoint, pick, tag, severity, ts, sevMap, title, marker, unit = 'rows' }) {
  return async function (root) {
    if (root.querySelector(`[data-cockpit-crates="${marker}"]`)) return;
    let data; try { data = await (await fetch(endpoint, { cache: 'no-store' })).json(); } catch (_) { return; }
    const list = pick(data); if (!Array.isArray(list) || !list.length) return;
    const map = sevMap || (x => x);
    const events = list.map(it => ({ tag: String(tag(it) || '—'), severity: map(severity(it)) || 'info', ts_ms: Date.parse(ts ? ts(it) : '') || 0 }));
    const r = await bcall('alert_group_rollup', JSON.stringify(events));
    if (!r || !r.ok) return;
    const s = section(title); s.setAttribute('data-cockpit-crates', marker);
    s.appendChild(el('div', '', `${r.total} ${unit} across ${r.groups.length} group(s) — worst severity per group, computed by the crate:`));
    for (const g of r.groups) s.appendChild(el('div', 'color:var(--muted,#888)', `   ${g.tag}: ${g.count} · worst ${g.max_severity}`));
    (root.body || document.body).appendChild(s);
  };
}

// An inheritance/hierarchy outline: flatten a panel's parent/child rows to visible
// DFS order via the REAL sovereign-cockpit-tree-view crate. Roots = missing/unknown parent.
function treeOutlineEnhancer({ endpoint, pick, id, parent, label, title, marker }) {
  return async function (root) {
    if (root.querySelector(`[data-cockpit-crates="${marker}"]`)) return;
    let data; try { data = await (await fetch(endpoint, { cache: 'no-store' })).json(); } catch (_) { return; }
    const rows = pick(data); if (!Array.isArray(rows) || !rows.length) return;
    const ids = new Set(rows.map(it => String(id(it))));
    const nodes = rows.map(it => {
      const p = parent(it); const ps = p != null ? String(p) : null;
      return { id: String(id(it)), label: String(label ? label(it) : id(it)), parent_id: ps && ids.has(ps) ? ps : null, expanded: true };
    });
    const r = await bcall('tree_view_visible', JSON.stringify({ schema_version: '1.0.0', nodes, selected: null }));
    if (!Array.isArray(r) || !r.length) return;
    const s = section(title); s.setAttribute('data-cockpit-crates', marker);
    s.appendChild(el('div', 'color:var(--muted,#888);font-size:.8rem;margin-bottom:.3rem', `${r.length} nodes flattened to visible order by the crate:`));
    for (const n of r) s.appendChild(el('div', '', `${'· '.repeat(n.depth)}${n.id}${n.has_children ? ' ▾' : ''}`));
    (root.body || document.body).appendChild(s);
  };
}

// A mean-progress aggregate over a panel's rows via the REAL sovereign-cockpit-progress-tracker crate.
function progressAggEnhancer({ endpoint, pick, progress, title, marker, unit = 'items' }) {
  return async function (root) {
    if (root.querySelector(`[data-cockpit-crates="${marker}"]`)) return;
    let data; try { data = await (await fetch(endpoint, { cache: 'no-store' })).json(); } catch (_) { return; }
    const rows = pick(data); if (!Array.isArray(rows) || !rows.length) return;
    const tasks = rows.map((it, i) => ({ id: 't' + i, label: 't' + i, kind: 'determinate', progress: Math.max(0, Math.min(100, Math.round(progress(it) || 0))), eta_seconds: 0, started_at: '2026-01-01T00:00:00Z' }));
    const r = await bcall('progress_summary', JSON.stringify(tasks));
    if (!r || !r.ok) return;
    const s = section(title); s.setAttribute('data-cockpit-crates', marker);
    s.appendChild(el('div', '', `crate-computed mean progress: ${r.average}% across ${r.tasks.length} ${unit}`));
    (root.body || document.body).appendChild(s);
  };
}

// Run several enhancers on one panel; each guards its own marker, so all are idempotent.
const compose = (...fns) => async (root) => { for (const f of fns) { try { await f(root); } catch (_) {} } };

// d-06-pending-approvals: roll up the live approvals by severity with the REAL alert-group crate.
const SEV = { critical: 'critical', high: 'error', medium: 'warning', low: 'info' };
const enhanceApprovals = alertRollupEnhancer({
  endpoint: '/api/approvals/pending',
  pick: d => Array.isArray(d) ? d : (d.approvals || d.pending || []),
  tag: a => a.kind || a.type || a.severity || 'approval',
  severity: a => a.severity, sevMap: x => SEV[x] || 'info',
  ts: a => a.ts || a.created_at || a.created,
  title: 'Pending approvals rolled up — sovereign-cockpit-alert-group (wasm)', marker: 'appr', unit: 'pending',
});
// Quarantine severity tokens -> the alert-group crate's info/warning/error/critical.
const SEV17 = { critical: 'critical', major: 'error', minor: 'warning', informational: 'info' };

// Generic facet rollup: fetch a panel's live rows, count its categorical fields,
// and run the REAL sovereign-cockpit-facet-counts crate to pick the top buckets —
// the same "group + count" the panels otherwise hand-roll in JS. Additive + graceful:
// a missing bridge, dead endpoint, or empty data is a silent no-op.
function facetEnhancer({ endpoint, pick, facets, title, marker, top = 6 }) {
  return async function (root) {
    if (root.querySelector(`[data-cockpit-crates="${marker}"]`)) return;
    let data; try { data = await (await fetch(endpoint, { cache: 'no-store' })).json(); } catch (_) { return; }
    const items = pick(data);
    if (!Array.isArray(items) || !items.length) return;
    const counts = {};
    const bump = (f, b) => { if (b == null || b === '') return; (counts[f] = counts[f] || {})[String(b)] = (counts[f][String(b)] || 0) + 1; };
    for (const it of items) for (const f in facets) bump(f, facets[f](it));
    if (!Object.keys(counts).length) return;
    const r = await bcall('facet_counts_top', JSON.stringify(counts), top);
    if (!r || r.ok === false || !Object.keys(r).length) return;
    const s = section(title);
    s.setAttribute('data-cockpit-crates', marker);
    s.appendChild(el('div', 'color:var(--muted,#888);font-size:.8rem;margin-bottom:.3rem', `${items.length} rows, faceted + ranked by the crate:`));
    for (const [facet, buckets] of Object.entries(r)) s.appendChild(el('div', '', `${facet}: ` + buckets.map(([b, n]) => `${b} (${n})`).join(' · ')));
    (root.body || document.body).appendChild(s);
  };
}

// Group a panel's timeline/event rows into day buckets (today / yesterday / earlier-this-week
// / older) via the REAL sovereign-cockpit-day-divider crate, computed against the live clock.
function dayGroupEnhancer({ endpoint, pick, ts, title, marker }) {
  return async function (root) {
    if (root.querySelector(`[data-cockpit-crates="${marker}"]`)) return;
    let data; try { data = await (await fetch(endpoint, { cache: 'no-store' })).json(); } catch (_) { return; }
    const rows = pick(data); if (!Array.isArray(rows) || !rows.length) return;
    const stamps = rows.map(r => Date.parse(ts(r) || '') || 0).filter(Boolean).sort((a, b) => b - a);
    if (!stamps.length) return;
    const r = await bcall('day_divider_group', Date.now(), JSON.stringify(stamps));
    if (!Array.isArray(r) || !r.length) return;
    const sec = section(title); sec.setAttribute('data-cockpit-crates', marker);
    sec.appendChild(el('div', 'color:var(--muted,#888);font-size:.8rem;margin-bottom:.3rem', `${stamps.length} events bucketed by day by the crate:`));
    for (const pair of r) sec.appendChild(el('div', '', `${pair[0]}: ${(pair[1] || []).length}`));
    (root.body || document.body).appendChild(sec);
  };
}

const enhanceModelsCatalog = facetEnhancer({
  endpoint: '/api/models-catalog/catalog',
  pick: d => d.models || (d.catalog && d.catalog.models) || (Array.isArray(d) ? d : []),
  facets: { class: m => m.class, tier: m => m.tier || m.srp_tier, quant: m => m.quantization || m.quant },
  title: 'Model-catalog facets — sovereign-cockpit-facet-counts (wasm)', marker: 'mcat',
});

// Universal: every panel renders only the control-systems that GOVERN it (matched by
// applies_to == the panel slug). Facet that per-panel control set by kind / scope /
// access via the REAL facet-counts crate — the crate section for the many panels whose
// only structured data is their governing controls. Skips when <2 controls apply.
async function enhanceControlSystems(root, slug) {
  if (!slug || root.querySelector('[data-cockpit-crates="cs"]')) return;
  let data; try { data = await (await fetch('/control-systems', { headers: { Accept: 'application/json' }, cache: 'no-store' })).json(); } catch (_) { return; }
  const mine = ((data && data.systems) || []).filter(s => (s.applies_to || []).indexOf(slug) >= 0);
  if (mine.length < 2) return;
  const counts = {};
  const bump = (f, b) => { if (b == null || b === '') return; (counts[f] = counts[f] || {})[String(b)] = (counts[f][String(b)] || 0) + 1; };
  for (const s of mine) { bump('kind', s.kind); bump('scope', s.scope); bump('access', s.privileged ? 'privileged' : 'open'); }
  const r = await bcall('facet_counts_top', JSON.stringify(counts), 6);
  if (!r || r.ok === false || !Object.keys(r).length) return;
  const sec = section('Controls governing this panel — sovereign-cockpit-facet-counts (wasm)');
  sec.setAttribute('data-cockpit-crates', 'cs');
  sec.appendChild(el('div', 'color:var(--muted,#888);font-size:.8rem;margin-bottom:.3rem', `${mine.length} controls apply to this surface, faceted by the crate:`));
  for (const [facet, buckets] of Object.entries(r)) sec.appendChild(el('div', '', `${facet}: ` + buckets.map(([b, n]) => `${b} (${n})`).join(' · ')));
  (root.body || document.body).appendChild(sec);
}

// runtime-modes: a FUNCTIONAL segmented control built from the panel's real modes, whose
// selection is computed by the REAL sovereign-cockpit-segmented-control crate (next / prev /
// select). A read-only preview — it explores the modes, it does NOT switch the live mode
// (that stays a signed action elsewhere). Additive + graceful.
async function enhanceRuntimeModes(root) {
  if (root.querySelector('[data-cockpit-crates="rm"]')) return;
  let list; try { list = await (await fetch('/api/runtime-modes/list', { cache: 'no-store' })).json(); } catch (_) { return; }
  const modes = (list && list.modes) || [];
  if (modes.length < 2) return;
  let active = null; try { const a = await (await fetch('/api/runtime-modes/active', { cache: 'no-store' })).json(); active = a && a.active; } catch (_) {}
  const segments = modes.map(mo => ({ id: String(mo.id), label: String(mo.name || mo.id), enabled: !mo.absent }));
  let state = { schema_version: '1.0.0', segments, active: segments.some(s => s.id === active) ? String(active) : segments[0].id };
  const sec = section('Mode navigator — sovereign-cockpit-segmented-control (wasm)');
  sec.setAttribute('data-cockpit-crates', 'rm');
  sec.appendChild(el('div', 'color:var(--muted,#888);font-size:.78rem;margin-bottom:.45rem', 'preview: the crate computes the selection — it does not switch the live mode'));
  const rowEl = el('div', 'display:flex;gap:.3rem;flex-wrap:wrap;margin-bottom:.4rem');
  const navEl = el('div', 'display:flex;gap:.3rem;margin-bottom:.4rem');
  const outEl = el('div', 'font-size:.85rem');
  const paint = () => {
    rowEl.innerHTML = '';
    for (const s of state.segments) {
      const on = s.id === state.active;
      const b = el('button', 'padding:.25rem .6rem;border:1px solid var(--border,#333);border-radius:3px;cursor:pointer;font:inherit;'
        + 'background:' + (on ? 'var(--accent,#9bd1ff)' : 'transparent') + ';color:' + (on ? '#000' : 'inherit'), s.label);
      b.disabled = !s.enabled;
      b.addEventListener('click', () => move('select:' + s.id));
      rowEl.appendChild(b);
    }
    outEl.textContent = 'crate-selected: ' + state.active;
  };
  const move = async (op) => {
    const r = await bcall('segmented_control_move', JSON.stringify(state), op);
    if (r && r.ok && r.value) { state = r.value; paint(); }
  };
  ['◀ prev', 'next ▶'].forEach((lbl, i) => {
    const b = el('button', 'padding:.2rem .55rem;border:1px solid var(--border,#333);border-radius:3px;cursor:pointer;font:inherit;background:transparent;color:inherit', lbl);
    b.addEventListener('click', () => move(i === 0 ? 'prev' : 'next'));
    navEl.appendChild(b);
  });
  sec.append(rowEl, navEl, outEl);
  (root.body || document.body).appendChild(sec);
  paint();
}

// Universal: the panels' filter chips follow a `.filter.on` convention, each carrying one
// data-<facet> value. Reflect the operator's ACTIVE filter through the REAL search-filter
// crate — validate + canonicalize it (dedupe/sort facet values) — and keep it live as they
// toggle. Skips panels with no such chips. Additive + graceful.
async function enhanceActiveFilterSpec(root) {
  const chips = Array.from((root.querySelectorAll && root.querySelectorAll('.filter.on')) || []);
  const facets = {};
  for (const chip of chips) {
    const e = Object.entries(chip.dataset || {})[0]; if (!e) continue;
    const [k, v] = e; if (v == null || v === '') continue;
    facets[k] = facets[k] || []; if (facets[k].indexOf(String(v)) < 0) facets[k].push(String(v));
  }
  const nFacets = Object.keys(facets).length;
  let sec = root.querySelector && root.querySelector('[data-cockpit-crates="fs"]');
  if (!nFacets) { if (sec) sec.remove(); return; }  // nothing selected → no section
  const r = await bcall('search_filter_spec', JSON.stringify({ schema_version: '1.0.0', query_text: '', facets, sort_key: '', sort_direction: 'asc' }));
  if (!r || !r.ok || !r.spec) return;
  if (!sec) { sec = section('Active filter, canonicalized — sovereign-cockpit-search-filter (wasm)'); sec.setAttribute('data-cockpit-crates', 'fs'); (root.body || document.body).appendChild(sec); }
  while (sec.childNodes.length > 1) sec.removeChild(sec.lastChild);  // keep the <h2>, refresh body
  const parts = Object.entries(r.spec.facets).map(([k, vs]) => `${k}: ${vs.join(', ')}`);
  sec.appendChild(el('div', '', `${chips.length} active chips across ${nFacets} facet(s), crate-validated — ` + parts.join(' · ')));
}

// d-01-active-sessions: render a real session's M057 lifecycle as a step bar built + validated
// by the REAL sovereign-cockpit-stepper crate; complete/back preview the crate's own transitions
// (it does NOT advance the real session). Additive + graceful.
const LIFECYCLE = ['Intake', 'Normalize', 'Profile', 'Map', 'Plan', 'Route', 'Execute', 'Observe', 'Evaluate', 'Commit', 'Learn', 'Archive'];
async function enhanceSessionSteps(root) {
  if (root.querySelector('[data-cockpit-crates="d01st"]')) return;
  let data; try { data = await (await fetch('/api/sessions/active', { cache: 'no-store' })).json(); } catch (_) { return; }
  const sessions = (data && data.sessions) || [];
  if (!sessions.length) return;
  const sess = sessions[0];
  const cur = Math.max(1, Math.min(LIFECYCLE.length, (sess.step | 0) || 1));
  let state = {
    schema_version: '1.0.0', active: cur - 1,
    steps: LIFECYCLE.map((label, i) => ({ id: 's' + (i + 1), label, skippable: false, status: (i + 1) < cur ? 'done' : ((i + 1) === cur ? 'active' : 'not-started') })),
  };
  const sec = section('Session lifecycle — sovereign-cockpit-stepper (wasm)');
  sec.setAttribute('data-cockpit-crates', 'd01st');
  sec.appendChild(el('div', 'color:var(--muted,#888);font-size:.78rem;margin-bottom:.4rem', `preview of session ${sess.id || ''} — the crate drives the steps, it does not advance the real session`));
  const barEl = el('div', 'display:flex;gap:.2rem;flex-wrap:wrap;margin-bottom:.4rem');
  const navEl = el('div', 'display:flex;gap:.3rem');
  const paint = () => {
    barEl.innerHTML = '';
    state.steps.forEach((s, i) => {
      const bg = s.status === 'done' ? 'var(--good,#7ad17a)' : (s.status === 'active' ? 'var(--accent,#9bd1ff)' : 'var(--border,#333)');
      const cell = el('span', `padding:.15rem .4rem;border-radius:3px;font-size:.72rem;background:${bg};color:${s.status === 'not-started' ? 'var(--muted,#888)' : '#000'}`, s.label);
      if (i === state.active) cell.style.outline = '2px solid var(--fg,#ddd)';
      barEl.appendChild(cell);
    });
  };
  const step = async (op) => { const r = await bcall('stepper_advance', JSON.stringify(state), op); if (r && r.ok && r.value) { state = r.value; paint(); } };
  [['✓ complete', 'complete'], ['◀ back', 'back']].forEach(([lbl, op]) => {
    const b = el('button', 'padding:.2rem .55rem;border:1px solid var(--border,#333);border-radius:3px;cursor:pointer;font:inherit;background:transparent;color:inherit', lbl);
    b.addEventListener('click', () => step(op)); navEl.appendChild(b);
  });
  sec.append(barEl, navEl);
  (root.body || document.body).appendChild(sec);
  paint();
}

// d-21-lm-orchestration: a functional radio-group over the FETCHED orchestration profiles,
// selection computed by the REAL sovereign-cockpit-radio-group crate (click + arrow wrap). Preview.
async function enhanceOrchestrationRadio(root) {
  if (root.querySelector('[data-cockpit-crates="d21rg"]')) return;
  let data; try { data = await (await fetch('/api/lm-orchestration/profiles', { cache: 'no-store' })).json(); } catch (_) { return; }
  const profiles = (data && data.profiles) || [];
  if (profiles.length < 2) return;
  const options = profiles.map(p => ({ id: String(p.id || p.mode_id), label: String(p.name || p.id || p.mode_id), enabled: true }));
  let state = { schema_version: '1.0.0', options, selected: options[0].id, required: true };
  const sec = section('Orchestration profile selector — sovereign-cockpit-radio-group (wasm)');
  sec.setAttribute('data-cockpit-crates', 'd21rg');
  sec.appendChild(el('div', 'color:var(--muted,#888);font-size:.78rem;margin-bottom:.4rem', 'preview: the crate computes the selection (arrows wrap) — it does not apply a profile'));
  const rowEl = el('div', 'display:flex;flex-direction:column;gap:.25rem;margin-bottom:.4rem');
  const navEl = el('div', 'display:flex;gap:.3rem');
  const paint = () => {
    rowEl.innerHTML = '';
    for (const o of state.options) {
      const b = el('button', 'text-align:left;padding:.2rem .5rem;border:1px solid var(--border,#333);border-radius:3px;cursor:pointer;font:inherit;background:transparent;color:inherit', (o.id === state.selected ? '● ' : '○ ') + o.label);
      b.addEventListener('click', () => sel(o.id)); rowEl.appendChild(b);
    }
  };
  const sel = async (target) => { const r = await bcall('radio_group_select', JSON.stringify(state), target); if (r && r.ok && r.value) { state = r.value; paint(); } };
  [['▲ up', 'up'], ['▼ down', 'down']].forEach(([lbl, op]) => {
    const b = el('button', 'padding:.2rem .55rem;border:1px solid var(--border,#333);border-radius:3px;cursor:pointer;font:inherit;background:transparent;color:inherit', lbl);
    b.addEventListener('click', () => sel(op)); navEl.appendChild(b);
  });
  sec.append(rowEl, navEl);
  (root.body || document.body).appendChild(sec);
  paint();
}

// Panels with a staged (pending) vs applied filter (edit fields + an Apply button) — reflect
// that pending->applied commit through the REAL sovereign-cockpit-filter-state crate: show how
// many edits are pending, and on Apply run filter_state_apply. Additive + graceful.
function filterStateEnhancer({ inputs, applyBtn, title, marker }) {
  return async function (root) {
    if (root.querySelector(`[data-cockpit-crates="${marker}"]`)) return;
    const q = sel => (root.querySelector ? root.querySelector(sel) : null);
    const readVals = () => { const o = {}; for (const k in inputs) { const e = q(inputs[k]); if (e && e.value != null && e.value !== '') o[k] = String(e.value); } return o; };
    const btn = q(applyBtn);
    if (!btn) return;  // this panel doesn't have the staged-filter UI
    let applied = readVals();
    const sec = section(title); sec.setAttribute('data-cockpit-crates', marker);
    const out = el('div', 'font-size:.85rem'); sec.appendChild(out);
    (root.body || document.body).appendChild(sec);
    const refresh = async (commit) => {
      const pending = readVals();
      if (commit) { const r = await bcall('filter_state_apply', JSON.stringify({ schema_version: '1.0.0', pending, applied })); if (r && r.ok && r.value) applied = r.value.applied || pending; }
      const keys = Object.keys(Object.assign({}, pending, applied));
      const dirty = keys.filter(k => pending[k] !== applied[k]);
      out.textContent = dirty.length
        ? `${dirty.length} pending filter edit(s) not yet applied: ${dirty.join(', ')}`
        : ('filter applied (crate-committed): ' + (Object.keys(applied).map(k => `${k}=${applied[k]}`).join(', ') || '(defaults)'));
    };
    if (btn) btn.addEventListener('click', () => setTimeout(() => refresh(true), 0));
    for (const k in inputs) { const e = q(inputs[k]); if (e) { e.addEventListener('input', () => refresh(false)); e.addEventListener('change', () => refresh(false)); } }
    refresh(false);
  };
}

// d-04-costs: the real budget gauge (cost-meter: Normal/Warning/Critical/Exceeded from
// spend vs budget) + the spend trend (stat-trend: direction + %, cost is lower-better).
async function enhanceCosts(root) {
  if (root.querySelector('[data-cockpit-crates="d04cm"]')) return;
  let data; try { data = await (await fetch('/api/costs/summary', { cache: 'no-store' })).json(); } catch (_) { return; }
  const sec = section('Budget gauge + spend trend — cost-meter / stat-trend (wasm)');
  sec.setAttribute('data-cockpit-crates', 'd04cm');
  let any = false;
  const today = data && data.today;
  if (today && today.budget > 0) {
    const r = await bcall('cost_meter_level', today.budget, today.spend || 0, 8000, 9500);
    if (r && r.ok) { sec.appendChild(el('div', '', `budget gauge: ${(r.usage_bp / 100).toFixed(1)}% used · ${r.level} · ${r.remaining} remaining (crate)`)); any = true; }
  }
  const trend = (data && data.trend30d) || [];
  if (trend.length >= 2) {
    const prev = Number(trend[trend.length - 2].spend) || 0, cur = Number(trend[trend.length - 1].spend) || 0;
    const t = await bcall('stat_trend_compute', prev, cur, 50, 'lower-better');
    if (t && t.ok) { sec.appendChild(el('div', '', `spend trend: ${t.direction} ${(t.percent_change_x100 / 100).toFixed(1)}% · ${t.color_hint} (crate)`)); any = true; }
  }
  if (any) (root.body || document.body).appendChild(sec);
}

// d-20-peace-machine-health: roll the property statuses into one headline + a percentage
// breakdown with the REAL status-aggregator crate (worst-wins).
const D20_STATUS = { healthy: 'ok', degraded: 'degraded', failing: 'down', unknown: 'unknown' };
async function enhancePeaceHealth(root) {
  if (root.querySelector('[data-cockpit-crates="d20sa"]')) return;
  let data; try { data = await (await fetch('/api/d-20/snapshot', { cache: 'no-store' })).json(); } catch (_) { return; }
  const props = (data && data.properties) || [];
  if (!props.length) return;
  const subs = props.map((p, i) => ({ id: 'p' + (i + 1), name: 'property ' + (i + 1), status: D20_STATUS[p.status] || 'unknown' }));
  const r = await bcall('status_aggregator_headline', JSON.stringify(subs));
  if (!r || !r.ok) return;
  const p = r.percentages || {};
  const sec = section('Overall health — sovereign-cockpit-status-aggregator (wasm)');
  sec.setAttribute('data-cockpit-crates', 'd20sa');
  sec.appendChild(el('div', '', `headline: ${r.headline} — ${p.ok}% ok · ${p.degraded}% degraded · ${p.down}% down · ${p.unknown}% unknown (crate)`));
  (root.body || document.body).appendChild(sec);
}

// d-09-hardware-pressure: total ZFS usage across datasets, rendered by the REAL
// byte-size-formatter crate (returns a bare string, so call it directly, not via bcall).
async function enhanceZfsSizes(root) {
  if (root.querySelector('[data-cockpit-crates="d09bs"]')) return;
  let data; try { data = await (await fetch('/api/hardware/pressure', { cache: 'no-store' })).json(); } catch (_) { return; }
  const ds = (data && data.zfs && data.zfs.datasets) || [];
  if (!ds.length) return;
  const total = ds.reduce((a, d) => a + (Number(d.used_bytes) || 0), 0);
  if (total <= 0) return;
  const m = await bridge(); if (!m || typeof m.byte_size_format !== 'function') return;
  const fmt = m.byte_size_format(total, 'iec', 1);
  if (typeof fmt !== 'string' || fmt.charAt(0) === '{') return;
  const sec = section('ZFS usage total — sovereign-cockpit-byte-size-formatter (wasm)');
  sec.setAttribute('data-cockpit-crates', 'd09bs');
  sec.appendChild(el('div', '', `${ds.length} datasets · ${fmt} used total (crate-formatted)`));
  (root.body || document.body).appendChild(sec);
}

const ENHANCERS = {
  'ux-design-audit-webapp': enhanceUxDesignAudit,
  'personalization-webapp': enhancePersonalization,
  'doc-coverage-webapp': enhanceDocCoverage,
  'd-06-pending-approvals-webapp': enhanceApprovals,
  'runtime-modes-webapp': enhanceRuntimeModes,
  'models-catalog-webapp': enhanceModelsCatalog,
  'd-23-models-catalog-webapp': enhanceModelsCatalog,
  // Audit spans: faceted + bucketed by day (closed_at).
  'd-16-audit-webapp': compose(
    facetEnhancer({
      endpoint: '/api/d-16/snapshot', pick: d => d.spans || [],
      facets: { category: s => s.ocsf_category, policy: s => s.policy_result, profile: s => s.profile, provider: s => s.provider },
      title: 'Audit spans faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'd16',
    }),
    dayGroupEnhancer({
      endpoint: '/api/d-16/snapshot', pick: d => d.spans || [], ts: s => s.closed_at,
      title: 'Audit spans by day — sovereign-cockpit-day-divider (wasm)', marker: 'd16dd',
    }),
  ),
  // Adapter inventory grouped by status / precision / training.
  'd-11-adapter-status-webapp': facetEnhancer({
    endpoint: '/api/adapters/inventory', pick: d => d.adapters || [],
    facets: { status: a => a.status, precision: a => a.precision, training: a => a.training },
    title: 'Adapter inventory faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'd11',
  }),
  // Sandbox allocations grouped by tier / state / isolation / profile.
  'd-15-sandboxes-webapp': facetEnhancer({
    endpoint: '/api/d-15/snapshot', pick: d => d.allocations || [],
    facets: { tier: a => a.tier, state: a => a.state, isolation: a => a.isolation, profile: a => a.profile },
    title: 'Sandbox allocations faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'd15',
  }),
  // Capability tokens: faceted + the crate-flattened token inheritance tree (parent_token_id).
  'd-14-capability-tokens-webapp': compose(
    facetEnhancer({
      endpoint: '/api/d-14/snapshot', pick: d => d.tokens || [],
      facets: { ring: t => t.trust_ring, authority: t => t.authority_level, state: t => t.state, tier: t => t.sandbox_tier },
      title: 'Capability tokens faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'd14',
    }),
    treeOutlineEnhancer({
      endpoint: '/api/d-14/snapshot', pick: d => d.tokens || [],
      id: t => t.token_id, parent: t => t.parent_token_id,
      title: 'Token inheritance outline — sovereign-cockpit-tree-view (wasm)', marker: 'd14tv',
    }),
  ),
  // Quarantine: faceted + per-tool worst-severity rollup (alert-group).
  'd-17-quarantine-webapp': compose(
    facetEnhancer({
      endpoint: '/api/d-17/snapshot', pick: d => d.entries || [],
      facets: { severity: e => e.max_severity, state: e => e.state, tool: e => e.tool },
      title: 'Quarantine entries faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'd17',
    }),
    alertRollupEnhancer({
      endpoint: '/api/d-17/snapshot', pick: d => d.entries || [],
      tag: e => e.tool, severity: e => e.max_severity, sevMap: x => SEV17[x] || 'info', ts: e => e.blocked_at,
      title: 'Quarantine by tool — sovereign-cockpit-alert-group (wasm)', marker: 'd17ag', unit: 'entries',
    }),
  ),
  // Active sessions: faceted + mean lifecycle progress (step 1..12 -> progress-tracker).
  'd-01-active-sessions-webapp': compose(
    facetEnhancer({
      endpoint: '/api/sessions/active', pick: d => d.sessions || [],
      facets: { kind: s => s.kind, profile: s => s.profile, state: s => s.state },
      title: 'Active sessions faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'd01',
    }),
    progressAggEnhancer({
      endpoint: '/api/sessions/active', pick: d => d.sessions || [],
      progress: s => (s.step / 12) * 100,
      title: 'Session lifecycle progress — sovereign-cockpit-progress-tracker (wasm)', marker: 'd01pg', unit: 'sessions',
    }),
    enhanceSessionSteps,
  ),
  // Trust scores: faceted + crate-computed mean score (0..1000 -> progress-tracker).
  'd-18-trust-scores-webapp': compose(
    facetEnhancer({
      endpoint: '/api/d-18/snapshot', pick: d => d.tools || [],
      facets: { band: t => t.band, score: t => t.current_score >= 800 ? 'high (>=800)' : t.current_score >= 500 ? 'mid (500-799)' : 'low (<500)' },
      title: 'Trust scores faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'd18',
    }),
    progressAggEnhancer({
      endpoint: '/api/d-18/snapshot', pick: d => d.tools || [],
      progress: t => t.current_score / 10,
      title: 'Mean trust score — sovereign-cockpit-progress-tracker (wasm)', marker: 'd18pg', unit: 'tools',
    }),
  ),
  // Firewall rules grouped by ring / disposition / chain.
  'd-12-networking-webapp': facetEnhancer({
    endpoint: '/api/d-12/snapshot', pick: d => d.rules || [],
    facets: { ring: r => r.ring, disposition: r => r.disposition, chain: r => r.chain },
    title: 'Firewall rules faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'd12',
  }),
  // Filesystem grants grouped by kind / state / profile.
  'd-13-filesystem-grants-webapp': facetEnhancer({
    endpoint: '/api/d-13/snapshot', pick: d => d.grants || [],
    facets: { kind: g => g.kind, state: g => g.state, profile: g => g.profile },
    title: 'Filesystem grants faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'd13',
  }),
  // Super-model milestones grouped by status / family / tag.
  'd-19-super-model-manifest-webapp': facetEnhancer({
    endpoint: '/api/d-19/snapshot', pick: d => d.milestones || [],
    facets: { status: m => m.status, family: m => m.family, tag: m => m.tag },
    title: 'Milestones faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'd19',
  }),
  // Peace-machine properties faceted + rolled into one headline (status-aggregator).
  'd-20-peace-machine-health-webapp': compose(
    facetEnhancer({
      endpoint: '/api/d-20/snapshot', pick: d => d.properties || [],
      facets: { status: p => p.status },
      title: 'Peace-machine properties faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'd20',
    }),
    enhancePeaceHealth,
  ),
  // Pending memory changes grouped by op / memory-type / scope.
  'd-07-memory-changes-webapp': facetEnhancer({
    endpoint: '/api/d-07/snapshot', pick: d => d.pending || [],
    facets: { op: p => p.op, mtype: p => p.mtype, scope: p => p.scope },
    title: 'Pending memory changes faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'd07',
  }),
  // Eval tasks grouped by intervention class + a derived pass-rate bucket.
  'd-10-eval-history-webapp': compose(
    facetEnhancer({
      endpoint: '/api/evals/summary', pick: d => d.tasks || [],
      facets: { class: t => t.intervention_class, pass: t => t.pass_pct >= 80 ? 'pass (>=80)' : t.pass_pct >= 50 ? 'mid (50-79)' : 'low (<50)' },
      title: 'Eval tasks faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'd10',
    }),
    filterStateEnhancer({
      inputs: { task: '#task-filter', class: '#class-filter', window: '#window-filter' }, applyBtn: '#apply-btn',
      title: 'Staged filter — sovereign-cockpit-filter-state (wasm)', marker: 'd10fs',
    }),
  ),
  // Traces: staged (pending -> Apply) filter committed through the filter-state crate.
  'd-05-traces-webapp': filterStateEnhancer({
    inputs: { q: '#search-input', severity: '#severity-select', ocsf_class: '#ocsf-class-select', window: '#window-select' }, applyBtn: '#apply-btn',
    title: 'Staged filter — sovereign-cockpit-filter-state (wasm)', marker: 'd05fs',
  }),
  // Orchestration: a functional radio-group over the fetched profiles (radio-group crate).
  'd-21-lm-orchestration-webapp': enhanceOrchestrationRadio,
  // Model health grouped by role / precision.
  'd-03-model-health-webapp': facetEnhancer({
    endpoint: '/api/models/health', pick: d => d.models || [],
    facets: { role: m => m.role, precision: m => m.precision },
    title: 'Model health faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'd03',
  }),
  // Project spend faceted + the crate budget gauge & spend trend.
  'd-04-costs-webapp': compose(
    facetEnhancer({
      endpoint: '/api/costs/summary', pick: d => d.projects || [],
      facets: { profile: p => p.profile, route: p => p.dominant_route },
      title: 'Project spend faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'd04',
    }),
    enhanceCosts,
  ),
  // Rollback snapshots faceted (by kind/dataset) + the activity timeline bucketed by day.
  'd-08-rollback-points-webapp': compose(
    facetEnhancer({
      endpoint: '/api/d-08/snapshot', pick: d => d.snapshots || [],
      facets: { kind: s => s.kind, dataset: s => s.dataset },
      title: 'Rollback snapshots faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'd08',
    }),
    dayGroupEnhancer({
      endpoint: '/api/d-08/snapshot', pick: d => d.timeline || [], ts: e => e.ts,
      title: 'Rollback timeline by day — sovereign-cockpit-day-divider (wasm)', marker: 'd08dd',
    }),
  ),
  // ZFS datasets faceted (sync/recordsize) + crate-formatted total usage.
  'd-09-hardware-pressure-webapp': compose(
    facetEnhancer({
      endpoint: '/api/hardware/pressure', pick: d => (d.zfs && d.zfs.datasets) || [],
      facets: { sync: z => z.sync, recordsize: z => z.recordsize },
      title: 'ZFS datasets faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'd09',
    }),
    enhanceZfsSizes,
  ),
  // Profile transitions grouped by from / to profile.
  'd-02-profile-choices-webapp': facetEnhancer({
    endpoint: '/api/profile/show', pick: d => d.history || [],
    facets: { from: h => h.from, to: h => h.to },
    title: 'Profile transitions faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'd02',
  }),
  // Master dashboard catalog grouped by status / category.
  'master-dashboard-webapp': facetEnhancer({
    endpoint: '/catalog', pick: d => d.dashboards || [],
    facets: { status: c => c.status, category: c => c.category },
    title: 'Dashboard catalog faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'md',
  }),
  // Code-console jobs: faceted by state/kind/device + mean job progress.
  'code-console-webapp': compose(
    facetEnhancer({
      endpoint: '/api/code-console/jobs', pick: d => d.jobs || [],
      facets: { state: j => j.state, kind: j => j.kind, device: j => j.device },
      title: 'Jobs faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'cc',
    }),
    progressAggEnhancer({
      endpoint: '/api/code-console/jobs', pick: d => d.jobs || [],
      progress: j => j.progress,
      title: 'Mean job progress — sovereign-cockpit-progress-tracker (wasm)', marker: 'ccpg', unit: 'jobs',
    }),
  ),
  // Global history events: faceted (source/action) + bucketed by day (timestamp).
  'global-history-webapp': compose(
    facetEnhancer({
      endpoint: '/recent?limit=200', pick: d => d.events || [],
      facets: { source: e => e.source, action: e => e.action },
      title: 'History events faceted — sovereign-cockpit-facet-counts (wasm)', marker: 'gh',
    }),
    dayGroupEnhancer({
      endpoint: '/recent?limit=200', pick: d => d.events || [], ts: e => e.timestamp,
      title: 'History events by day — sovereign-cockpit-day-divider (wasm)', marker: 'ghdd',
    }),
  ),
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
  const mod = (root.querySelector?.('meta[name="x-sovereign-module"]') || {}).content;
  try {
    const fn = ENHANCERS[mod];
    if (fn) await fn(root, audit);
  } catch (_) {}
  try { if (mod) await enhanceControlSystems(root, mod.replace(/-webapp$/, '')); } catch (_) {}
  try {
    await enhanceActiveFilterSpec(root);
    // keep the canonical-filter section live as the operator toggles chips (bind once)
    const host = root.body || (root.ownerDocument && root.ownerDocument.body) || (typeof document !== 'undefined' && document.body);
    if (host && !host.__csFilterBound) {
      host.__csFilterBound = true;
      host.addEventListener('click', (e) => {
        if (e.target && e.target.closest && e.target.closest('.filter')) {
          setTimeout(() => { enhanceActiveFilterSpec(root).catch(() => {}); }, 0);
        }
      });
    }
  } catch (_) {}
  return true;
}

export default { bridge, contrast, relTime, wordCount, truncate, validate, auditPalette, enhance, tabActivate, autocompleteNav, keystrokeResolve, stepperAdvance, collapsibleToggle, checklistToggle };
