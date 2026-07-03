/* webapp/_shared/control-surface.js — SDD-045 shared control-surface renderer.
 *
 * Renders the control-systems registry (config/control-systems.yaml, served
 * as GET /control-systems) — the operator's "everything can be turned on and
 * off + tons of modes and profiles" — as a grid of control cards. Reused by
 * every dashboard so each becomes a CONTROL surface.
 *
 * Web is READ-ONLY: each control shows its options and copies its exact
 * `change_cli` for the operator to run. It NEVER mutates privileged state
 * (§1g / hardening lint). No framework, no CDN — a single same-origin file.
 *
 * Usage:
 *   const n = SovereignControlSurface.render(el, systems, {
 *     filterSlug: 'runtime-modes',   // only global + systems governing this slug
 *     onCopy: (cmd) => showToast(cmd) // optional copy callback
 *   });
 */
(function (global) {
  "use strict";

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function render(containerEl, systems, opts) {
    opts = opts || {};
    var slug = opts.filterSlug || null;
    var list = (systems || []).filter(function (s) {
      if (!slug) return true;                       // no filter → all systems
      return s.scope === "global" ||                // globals show everywhere
        (s.applies_to || []).indexOf(slug) >= 0;    // + systems governing slug
    });
    var html = list.map(function (s) {
      var pills = (s.options || []).map(function (o) {
        return '<span class="cs-opt">' + esc(o) + "</span>";
      }).join("");
      var change = esc(s.change_cli || "");
      return '<div class="cs-card cs-' + esc(s.kind) + '">'
        + '<div class="cs-head">'
        + '<span class="cs-label">' + esc(s.label) + "</span>"
        + '<span class="cs-kind">' + esc(s.kind) + "</span>"
        + (s.scope === "global" ? '<span class="cs-global">global</span>' : "")
        + "</div>"
        + '<div class="cs-desc">' + esc(s.description) + "</div>"
        + '<div class="cs-opts">' + pills + "</div>"
        + (change
            ? '<button class="cs-cmd" data-cmd="' + change
              + '" title="click to copy the operator command">$ ' + change + "</button>"
            : "")
        + "</div>";
    }).join("");
    containerEl.innerHTML = html || '<div class="cs-empty">(no controls for this surface)</div>';
    Array.prototype.forEach.call(containerEl.querySelectorAll(".cs-cmd"), function (b) {
      b.addEventListener("click", function () {
        var cmd = b.getAttribute("data-cmd");
        if (navigator.clipboard) navigator.clipboard.writeText(cmd);
        if (typeof opts.onCopy === "function") opts.onCopy(cmd);
      });
    });
    return list.length;
  }

  // Convenience: fetch /control-systems (same-origin) and render.
  function load(containerEl, opts) {
    return fetch("/control-systems", { headers: { Accept: "application/json" } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data && data.error) {
          containerEl.innerHTML = '<div class="cs-empty">controls unavailable: '
            + esc(data.error) + "</div>";
          return 0;
        }
        return render(containerEl, (data && data.systems) || [], opts);
      })
      .catch(function (e) {
        containerEl.innerHTML = '<div class="cs-empty">controls unavailable: '
          + esc(e && e.message) + "</div>";
        return 0;
      });
  }

  global.SovereignControlSurface = { render: render, load: load };
})(window);
