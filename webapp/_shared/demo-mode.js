/* webapp/_shared/demo-mode.js — SDD-116 shared DEMO-mode helper (opt-in sample data).
 *
 * Reads the `sovereign-os.demo` localStorage flag (schema-guarded) and renders a
 * persistent DEMO badge. Demo-capable panels call `soDemo.on()` to branch to their
 * clearly-labelled sample data. The SB-077 reconciliation: DEMO is opt-in (off by
 * default; never self-enables), ALWAYS badged, and makes ZERO network calls
 * (R10212 strengthened — the demo render path never fetches). Inlined verbatim into
 * demo-capable panels alongside demo-mode.css. */
(function () {
  "use strict";
  var DKEY = 'sovereign-os.demo', DSCHEMA = 1;
  function on() {
    try {
      var r = localStorage.getItem(DKEY); var p = r ? JSON.parse(r) : null;
      return !!(p && p.schema === DSCHEMA && p.on);
    } catch (e) { return false; }
  }
  function set(v) {
    try { localStorage.setItem(DKEY, JSON.stringify({ schema: DSCHEMA, on: !!v })); } catch (e) {}
  }
  function badge() {
    var b = document.getElementById('so-demo-badge');
    if (on()) {
      if (!b) {
        b = document.createElement('div'); b.id = 'so-demo-badge';
        b.innerHTML = 'DEMO <span class="sub">· sample data — not real telemetry</span>';
        b.setAttribute('role', 'status');
        (document.body || document.documentElement).appendChild(b);
      }
    } else if (b) { b.remove(); }
  }
  window.soDemo = { on: on, set: set, badge: badge, KEY: DKEY, SCHEMA: DSCHEMA };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', badge);
  else badge();
})();
