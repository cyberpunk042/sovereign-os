/* HELPERS:BEGIN M073 — canonical per-panel JS helpers
 *
 * SDD-073: the deduplicated helper surface. These functions are copy-pasted
 * into every panel that adopts them (sovereignty-clean doctrine: no shared
 * runtime asset). The canonical source lives here; drift is enforced by
 * tests/lint/test_helpers_contract.py and kept in sync by
 * scripts/webapp/sync-helpers.py.
 *
 * Adopted panels MUST remove their local definitions of these helpers so
 * the canonical block is the single source of truth.
 */
function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
function fmtBytes(b) { if (!b && b !== 0) return '—'; const u=['B','K','M','G','T']; let i=0; while(b>=1024&&i<u.length-1){b/=1024;i++;} return `${b.toFixed(b<10?1:0)} ${u[i]}`; }
function fmtNum(v) { return v == null ? '—' : Number(v).toLocaleString(); }
/* HELPERS:END M073 */
