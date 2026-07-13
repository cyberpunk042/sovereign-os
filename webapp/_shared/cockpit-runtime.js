// webapp/_shared/cockpit-runtime.js — the sanctioned shared cockpit-crate runtime.
//
// The ~418 typed sovereign-cockpit-* crates model the cockpit's UX-state logic,
// but the panels are self-contained HTML that never used them (audit F-2026-001).
// This is the one external module a panel may load to actually RUN those crates:
// it lazy-loads the full cockpit-wasm bridge (built on demand — make cockpit-wasm)
// and exposes clean wrappers, so a panel's behaviour is computed by the REAL crate
// the daemon trusts, not a hand-rolled JS copy that can drift.
//
// Adoption is one additive line near a panel's </body>:
//     <script type="module">
//       import { enhance } from '/_shared/cockpit-runtime.js';
//       enhance(document).catch(() => {});   // graceful: no-op if the bridge is absent
//     </script>
// Everything here is wrapped so a missing bridge / unserved wasm degrades to a
// no-op — it can never break the panel.

const BRIDGE_URL = '/_shared/cockpit-wasm/cockpit_wasm_full.js';

let _mod = null;
let _loading = null;

// Lazy-load + init the full bridge exactly once. Returns null if unavailable.
export async function bridge() {
  if (_mod) return _mod;
  if (!_loading) {
    _loading = (async () => {
      try {
        const m = await import(BRIDGE_URL);
        await m.default();          // wasm-bindgen init
        _mod = m;
        return m;
      } catch (e) {
        return null;                // bridge not built/served — callers degrade
      }
    })();
  }
  return _loading;
}

const J = (s) => { try { return JSON.parse(s); } catch (_) { return null; } };
const hexRgb = (h) => {
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec((h || '').trim());
  return m ? { r: parseInt(m[1], 16), g: parseInt(m[2], 16), b: parseInt(m[3], 16) } : null;
};

// --- clean crate wrappers (each returns null/degrades if the bridge is absent) ---

/** WCAG contrast verdict for two CSS colors, via sovereign-cockpit-color-contrast. */
export async function contrast(fgHex, bgHex, largeText = false) {
  const m = await bridge(); if (!m) return null;
  const fg = hexRgb(fgHex), bg = hexRgb(bgHex); if (!fg || !bg) return null;
  return J(m.color_contrast_verdict(JSON.stringify(fg), JSON.stringify(bg), !!largeText));
}

/** "5 minutes ago" for an epoch-ms instant, via sovereign-cockpit-relative-time. */
export async function relTime(itemMs, nowMs = Date.now()) {
  const m = await bridge(); if (!m) return null;
  const r = J(m.relative_time_format(nowMs, itemMs)); return r ? (r.value ?? r) : null;
}

/** Reading-time / word stats for text, via sovereign-cockpit-word-count. */
export async function wordCount(text, wpm = 200) {
  const m = await bridge(); if (!m) return null;
  const r = J(m.word_count_count(String(text || ''), Math.max(1, wpm | 0)));
  return r && r.ok ? r.value : null;
}

/** Run any uniform crate's real validate() on a candidate state JSON. */
export async function validate(crateFn, json) {
  const m = await bridge(); if (!m || typeof m[crateFn] !== 'function') return null;
  return J(m[crateFn](json));
}

// --- deterministic, visible, additive enhancement -----------------------------

function readVar(root, name) {
  try { return getComputedStyle(root.documentElement || root).getPropertyValue(name).trim(); }
  catch (_) { return ''; }
}

/**
 * Additive, graceful enhancement of a panel:
 *  - computes the panel's own fg/bg WCAG contrast via the color-contrast crate and
 *    pins a small a11y badge (deterministic — reads the panel's CSS vars, not its DOM);
 *  - best-effort: turns visible ISO-8601 timestamps into "x ago" via relative-time.
 * Every step is isolated + try/caught: if the bridge is absent it simply does nothing.
 */
export async function enhance(root = document) {
  const m = await bridge();
  if (!m) return false;

  // 1) a11y contrast badge — the panel's real palette, judged by the real crate.
  try {
    const fg = readVar(root, '--fg') || '#e6e6e6';
    const bg = readVar(root, '--bg') || '#0e0e0e';
    const v = await contrast(fg, bg);
    if (v && !root.getElementById('cockpit-crates-badge')) {
      const b = document.createElement('div');
      b.id = 'cockpit-crates-badge';
      const pass = v.passes_aa;
      b.textContent = `cockpit-crates · a11y ${pass ? 'AA ✓' : 'AA ✗'} ${v.ratio.toFixed(1)}:1`;
      b.title = 'WCAG contrast of this panel’s fg/bg, computed by the real '
        + 'sovereign-cockpit-color-contrast crate (wasm). F-2026-001.';
      b.style.cssText = 'position:fixed;bottom:.4rem;right:.5rem;z-index:9998;'
        + 'font:11px ui-monospace,Menlo,Consolas,monospace;padding:.15rem .5rem;'
        + 'border-radius:10px;opacity:.7;pointer-events:auto;border:1px solid;'
        + `color:${pass ? '#7ad17a' : '#ff7676'};border-color:${pass ? '#7ad17a' : '#ff7676'};`
        + 'background:rgba(0,0,0,.35)';
      (root.body || document.body).appendChild(b);
    }
  } catch (_) { /* isolated — never breaks the panel */ }

  // 2) best-effort relative-time on visible ISO timestamps (title keeps the original).
  try {
    const ISO = /^\s*(\d{4}-\d{2}-\d{2}T[\d:.]+Z?)\s*$/;
    const walker = document.createTreeWalker(root.body || document.body, NodeFilter.SHOW_TEXT);
    const hits = [];
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const mm = ISO.exec(n.nodeValue);
      if (mm && n.parentElement && !n.parentElement.dataset.ccRel) hits.push([n, mm[1]]);
    }
    for (const [node, iso] of hits) {
      const t = Date.parse(iso); if (!Number.isFinite(t)) continue;
      const rel = await relTime(t); if (!rel) continue;
      node.parentElement.dataset.ccRel = '1';
      node.parentElement.title = iso;
      node.nodeValue = ` ${rel} `;
    }
  } catch (_) { /* isolated */ }

  return true;
}

export default { bridge, contrast, relTime, wordCount, validate, enhance };
