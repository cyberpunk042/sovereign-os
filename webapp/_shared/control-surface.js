/* webapp/_shared/control-surface.js — SDD-045 shared control-surface renderer.
 *
 * Renders the control-systems registry (config/control-systems.yaml, served
 * as GET /control-systems) — the operator's "everything can be turned on and
 * off + tons of modes and profiles" — as a grid of control cards. Reused by
 * every dashboard so each becomes a CONTROL surface.
 *
 * R10274 — functional cockpit: a control is now EXECUTED from the card. Each
 * change_cli placeholder becomes an input (enum → segmented buttons keyed
 * `verb`/`verbN`; free `<name>` → a datalist input seeded from `options`,
 * matching the server's _action_exec.resolve_argv keying). Execute POSTs
 * {control_id, args, confirm} to the sanctioned same-origin control-exec-api
 * (POST /api/control/execute); the copyable command is demoted to a labelled
 * fallback, and any 405 / unreachable exec front degrades gracefully to Copy.
 *
 * R10212 is preserved: the web still never *arbitrarily* mutates. Proxy-only
 * controls (selfdef / perimeter — mirrors _action_exec.SELFDEF_OWNED, drift-
 * guarded by tests/lint/test_control_surface_execute_boundary.py) render NO
 * execute affordance (signed-proxy badge + copy only). Every per-panel daemon
 * stays read-only (405 on writes); the ONE write path is the dedicated exec
 * daemon, where every action is allowlisted + options-validated + confirm/
 * key-gated + OCSF-5001 audited + DRY_RUN by default.
 *
 * Usage:
 *   const n = SovereignControlSurface.render(el, systems, {
 *     filterSlug: 'runtime-modes',      // only global + systems governing slug
 *     executeUrl: '/api/control/execute', // same-origin sanctioned write daemon
 *     onCopy: (cmd) => showToast(cmd)     // optional copy callback
 *   });
 */
(function (global) {
  "use strict";

  // R10212 boundary — mirrors _action_exec.SELFDEF_OWNED. selfdef/perimeter are
  // signed-proxy ONLY: never executed locally. (drift-guarded by lint.)
  var PROXY_ONLY = ["selfdef", "perimeter"];
  var EXECUTE_URL = "/api/control/execute";

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function isProxyOnly(sys) {
    if (typeof sys.execute_local === "boolean") return !sys.execute_local;
    return PROXY_ONLY.indexOf(sys.id) >= 0;
  }

  // Parse a change_cli template, mirroring _action_exec.resolve_argv:
  //   {a|b}  → enum, arg-key 'verb' (first) / 'verb1' / 'verb2' ...
  //   <name> → free, arg-key name
  //   else   → literal token
  function parseTemplate(changeCli) {
    var toks = String(changeCli || "").trim().split(/\s+/).filter(Boolean);
    var out = [], enumSeen = 0;
    toks.forEach(function (t) {
      var em = /^\{([a-z0-9|_-]+)\}$/.exec(t);
      if (em) {
        out.push({ kind: "enum", key: enumSeen === 0 ? "verb" : "verb" + enumSeen,
                   alts: em[1].split("|") });
        enumSeen += 1; return;
      }
      var fm = /^<([a-z0-9_-]+)>$/.exec(t);
      if (fm) { out.push({ kind: "free", key: fm[1] }); return; }
      out.push({ kind: "lit", text: t });
    });
    return out;
  }

  // Reassemble the concrete command from the template + collected args (for the
  // Copy fallback + result echo); unfilled placeholders stay as <name>/{a|b}.
  function assembleCmd(changeCli, args) {
    return parseTemplate(changeCli).map(function (t) {
      if (t.kind === "lit") return t.text;
      if (t.kind === "enum") return args[t.key] || ("{" + t.alts.join("|") + "}");
      return args[t.key] || ("<" + t.key + ">");
    }).join(" ");
  }

  function collectArgs(card) {
    var args = {};
    Array.prototype.forEach.call(card.querySelectorAll(".cs-verbs"), function (grp) {
      var pressed = grp.querySelector('.cs-verb[aria-pressed="true"]');
      if (pressed) args[grp.getAttribute("data-argkey")] = pressed.getAttribute("data-val");
    });
    Array.prototype.forEach.call(card.querySelectorAll("input.cs-arg"), function (inp) {
      var v = (inp.value || "").trim();
      if (v) args[inp.getAttribute("data-argkey")] = v;
    });
    return args;
  }

  function copy(text, opts) {
    if (navigator.clipboard) { try { navigator.clipboard.writeText(text); } catch (e) { /* noop */ } }
    if (opts && typeof opts.onCopy === "function") opts.onCopy(text);
  }

  function setResult(el, cls, msg) {
    if (!el) return;
    el.className = "cs-result " + cls;
    el.textContent = msg;
  }

  function execute(url, controlId, args, confirmed) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ control_id: controlId, args: args, confirm: !!confirmed })
    }).then(function (r) {
      return r.json().then(
        function (j) { return { status: r.status, body: j || {} }; },
        function () { return { status: r.status, body: {} }; });
    });
  }

  function execAction(card, sys, opts, confirmed) {
    var result = card.querySelector(".cs-result");
    var args = collectArgs(card);
    var url = (opts && opts.executeUrl) || EXECUTE_URL;
    setResult(result, "muted", "executing…");
    execute(url, sys.id, args, confirmed).then(function (res) {
      var b = res.body || {};
      if (res.status === 200) {
        if (b.dry_run) setResult(result, "dry", "dry-run ✓ would run: " + ((b.would_run || []).join(" ") || assembleCmd(sys.change_cli, args)));
        else setResult(result, "ok", "executed ✓ exit " + (b.exit_code != null ? b.exit_code : 0));
      } else if (res.status === 403) {
        if (confirmed) {
          // already type-confirmed → 403 is a server-side gate (e.g. the
          // operator key is not loaded). Surface the reason; do NOT re-prompt.
          setResult(result, "warn", b.error || "not permitted (operator key required)");
        } else {
          // privileged control — type-to-confirm ONCE, then re-execute confirm:true
          var typed = global.prompt
            ? global.prompt('Privileged control "' + sys.label + '". Type "' + sys.id + '" to confirm:')
            : null;
          if (typed && typed.trim() === sys.id) execAction(card, sys, opts, true);
          else setResult(result, "warn", "confirmation required — not executed");
        }
      } else if (res.status === 409) {
        setResult(result, "warn", "signed-proxy only (R10212) — command copied");
        copy(assembleCmd(sys.change_cli, args), opts);
      } else if (res.status === 400) {
        setResult(result, "warn", b.error || "invalid arguments — pick a value");
      } else if (res.status === 404) {
        setResult(result, "err", b.error || "unknown control");
      } else if (res.status === 405) {
        setResult(result, "muted", "execution not available on this origin — command copied");
        copy(assembleCmd(sys.change_cli, args), opts);
      } else {
        setResult(result, "err", b.error || ("error " + res.status));
      }
    }).catch(function () {
      // exec daemon unreachable (per-port-direct read-only front) → copy fallback
      setResult(result, "muted", "exec endpoint unreachable — command copied");
      copy(assembleCmd(sys.change_cli, collectArgs(card)), opts);
    });
  }

  function argsRailHtml(sys) {
    var opts = (sys.options || []).map(String);
    var html = parseTemplate(sys.change_cli).map(function (t) {
      if (t.kind === "lit") return "";                 // literals live in the Copy line
      if (t.kind === "enum") {
        return '<span class="cs-verbs" data-argkey="' + esc(t.key) + '">'
          + t.alts.map(function (a, i) {
              return '<button type="button" class="cs-verb" data-val="' + esc(a)
                + '" aria-pressed="' + (i === 0 ? "true" : "false") + '">' + esc(a) + "</button>";
            }).join("") + "</span>";
      }
      var listId = "csl-" + esc(sys.id) + "-" + esc(t.key);
      var dl = opts.length
        ? '<datalist id="' + listId + '">'
            + opts.map(function (o) { return '<option value="' + esc(o) + '"></option>'; }).join("")
            + "</datalist>"
        : "";
      return '<input class="cs-arg" data-argkey="' + esc(t.key) + '" placeholder="' + esc(t.key) + '"'
        + (opts.length ? ' list="' + listId + '"' : "") + ">" + dl;
    }).join("");
    return html ? '<div class="cs-args">' + html + "</div>" : "";
  }

  function cardHtml(sys) {
    var proxy = isProxyOnly(sys);
    var pills = (sys.options || []).map(function (o) {
      return '<span class="cs-opt">' + esc(o) + "</span>"; }).join("");
    var change = sys.change_cli || "";
    var actions = change
      ? '<div class="cs-actions">'
          + (proxy ? "" : '<button type="button" class="cs-exec">Execute</button>')
          + '<button type="button" class="cs-cmd cs-copy" data-cmd="' + esc(change)
            + '" title="copy the operator command (fallback)">$ ' + esc(change) + "</button>"
          + "</div>"
      : "";
    return '<div class="cs-card cs-' + esc(sys.kind) + '" data-cid="' + esc(sys.id) + '">'
      + '<div class="cs-head">'
      + '<span class="cs-label">' + esc(sys.label) + "</span>"
      + '<span class="cs-kind">' + esc(sys.kind) + "</span>"
      + (sys.scope === "global" ? '<span class="cs-global">global</span>' : "")
      + (proxy ? '<span class="cs-proxy" title="R10212: signed-proxy only — never executed locally">signed proxy</span>' : "")
      + "</div>"
      + '<div class="cs-desc">' + esc(sys.description) + "</div>"
      + (pills ? '<div class="cs-opts">' + pills + "</div>" : "")
      + argsRailHtml(sys)
      + actions
      + '<div class="cs-result muted"></div>'
      + "</div>";
  }

  function render(containerEl, systems, opts) {
    opts = opts || {};
    var slug = opts.filterSlug || null;
    var list = (systems || []).filter(function (s) {
      if (!slug) return true;                       // no filter → all systems
      return s.scope === "global" ||                // globals show everywhere
        (s.applies_to || []).indexOf(slug) >= 0;    // + systems governing slug
    });
    var byId = {};
    list.forEach(function (s) { byId[s.id] = s; });
    containerEl.innerHTML = list.map(cardHtml).join("")
      || '<div class="cs-empty">(no controls for this surface)</div>';

    // segmented enum toggles
    Array.prototype.forEach.call(containerEl.querySelectorAll(".cs-verbs"), function (grp) {
      grp.addEventListener("click", function (e) {
        var btn = e.target && e.target.classList && e.target.classList.contains("cs-verb") ? e.target : null;
        if (!btn) return;
        Array.prototype.forEach.call(grp.querySelectorAll(".cs-verb"), function (b) {
          b.setAttribute("aria-pressed", b === btn ? "true" : "false");
        });
      });
    });
    // copy fallback — copies the concrete command assembled from current args
    Array.prototype.forEach.call(containerEl.querySelectorAll(".cs-copy"), function (b) {
      b.addEventListener("click", function () {
        var card = b.parentNode.parentNode;
        var cmd = assembleCmd(b.getAttribute("data-cmd"), collectArgs(card));
        copy(cmd, opts);
        setResult(card.querySelector(".cs-result"), "muted", "copied: " + cmd);
      });
    });
    // execute — the sanctioned R10274 write path
    Array.prototype.forEach.call(containerEl.querySelectorAll(".cs-exec"), function (b) {
      b.addEventListener("click", function () {
        var card = b.parentNode.parentNode;
        var sys = byId[card.getAttribute("data-cid")];
        if (sys) execAction(card, sys, opts, false);
      });
    });
    return list.length;
  }

  // Convenience: load the control registry (same-origin) and render.
  // Full display data comes from the panel's own read-only /control-systems;
  // the authoritative execute-local/live overlay comes from /api/control/registry
  // when the origin is fronted by the exec daemon (else copy-first per PROXY_ONLY).
  function load(containerEl, opts) {
    opts = opts || {};
    var base = fetch("/control-systems", { headers: { Accept: "application/json" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
    var reg = fetch("/api/control/registry", { headers: { Accept: "application/json" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
    return Promise.all([base, reg]).then(function (res) {
      var b = res[0], g = res[1];
      if (!b || b.error) {
        containerEl.innerHTML = '<div class="cs-empty">controls unavailable'
          + (b && b.error ? ": " + esc(b.error) : "") + "</div>";
        return 0;
      }
      var systems = (b.systems || []).slice();
      if (g && g.controls) {
        var execMap = {};
        g.controls.forEach(function (c) { execMap[c.id] = c.execute_local; });
        systems.forEach(function (s) { if (s.id in execMap) s.execute_local = execMap[s.id]; });
        opts.live = !!g.live;
      }
      return render(containerEl, systems, opts);
    });
  }

  global.SovereignControlSurface = { render: render, load: load };
})(window);
