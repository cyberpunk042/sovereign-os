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

  function toolWarning(stdout) {
    // Best-effort: the sanctioned exec-api echoes the tool's stdout; if it is
    // JSON carrying a truthy `warning`, return it for the result line (e.g.
    // model-warm's dtype/state drift, SDD-049 Stage 4). Never throws — a
    // non-JSON / warning-less tool just yields no banner.
    if (!stdout) return null;
    try { var j = JSON.parse(stdout); return (j && j.warning) ? String(j.warning) : null; }
    catch (e) { return null; }
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

  // Inline type-to-confirm gate for privileged controls (replaces window.prompt
  // — accessible, on-palette, non-blocking). Type the control id, Confirm →
  // re-execute with confirm:true; Cancel/mismatch → no execution.
  function askConfirm(card, sys, opts) {
    var result = card.querySelector(".cs-result");
    var host = card.querySelector(".cs-confirm");
    if (!host) {
      host = document.createElement("div");
      host.className = "cs-confirm";
      card.insertBefore(host, result);
    }
    host.innerHTML =
      '<span class="cs-confirm-msg">privileged — type <code>' + esc(sys.id) + "</code> to confirm</span>"
      + '<input class="cs-arg cs-confirm-in" placeholder="' + esc(sys.id) + '" aria-label="type ' + esc(sys.id) + ' to confirm">'
      + '<button type="button" class="cs-exec cs-confirm-ok">Confirm</button>'
      + '<button type="button" class="cs-cmd cs-confirm-cancel">Cancel</button>';
    var inp = host.querySelector(".cs-confirm-in");
    if (inp.focus) inp.focus();
    function done(ok) {
      var typed = (inp.value || "").trim();
      if (host.parentNode) host.parentNode.removeChild(host);
      if (ok && typed === sys.id) execAction(card, sys, opts, true);
      else setResult(result, "warn", "confirmation " + (ok ? "mismatch" : "cancelled") + " — not executed");
    }
    host.querySelector(".cs-confirm-ok").addEventListener("click", function () { done(true); });
    host.querySelector(".cs-confirm-cancel").addEventListener("click", function () { done(false); });
    inp.addEventListener("keydown", function (e) { if (e.key === "Enter") done(true); });
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
        else {
          // A live exec echoes the tool's JSON on stdout; surface a tool-level
          // `warning` (model-warm's dtype/state drift, SDD-049 Stage 4) so it
          // reaches the operator instead of hiding behind a bare "exit 0".
          var warn = toolWarning(b.stdout);
          setResult(result, warn ? "warn" : "ok",
            "executed ✓ exit " + (b.exit_code != null ? b.exit_code : 0) + (warn ? " — ⚠ " + warn : ""));
        }
      } else if (res.status === 403) {
        if (confirmed) {
          // already type-confirmed → 403 is a server-side gate (e.g. the
          // operator key is not loaded). Surface the reason; do NOT re-prompt.
          setResult(result, "warn", b.error || "not permitted (operator key required)");
        } else {
          // privileged control — inline type-to-confirm gate, ONCE
          askConfirm(card, sys, opts);
        }
      } else if (res.status === 409) {
        if (b.compat) {
          // compat pre-change gate refusal (the ⚖ registry, NOT the R10212
          // boundary): surface the RULE + remediation at the point of
          // rejection, and offer the server-verified fix plan inline —
          // "force something else off in order to enable one thing".
          setResult(result, "err",
            "⚖ " + (b.error || "compat gate refused")
            + " INSTEAD: " + (b.remediation || "open the ⚖ Compatibility pane"));
          fixPlan(result, b.resolution, url);
        } else if (b.boundary) {
          setResult(result, "warn", "signed-proxy only (R10212) — command copied");
          copy(assembleCmd(sys.change_cli, args), opts);
        } else {
          // the remaining 409: single-flight lock (another action running)
          setResult(result, "warn", b.error || "another cockpit action is already running");
        }
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

  // The server-verified compat RESOLUTION plan riding a 409 refusal — one
  // "Force: <label>" button per step; each executes through the SAME
  // sanctioned rail (dry-run until live). Mirrors the app-shell ⚖ pane's
  // shared renderer so both surfaces offer the identical way out.
  function fixPlan(result, resolution, url) {
    if (!result || !resolution || !(resolution.plan || []).length) return;
    var head = document.createElement("div");
    head.className = "cs-fix-head";
    head.textContent = resolution.resolved_all
      ? "Verified fix plan — applying these clears ALL findings:"
      : (resolution.clean_after
        ? "Verified fix plan — clears every gating finding (advisories may remain):"
        : "Fix plan (partial — force findings would remain):");
    result.appendChild(head);
    resolution.plan.forEach(function (stp) {
      var row = document.createElement("div");
      row.className = "cs-fix-row";
      var btn = document.createElement("button");
      btn.type = "button"; btn.className = "cs-exec cs-fix";
      btn.textContent = "Force: " + stp.label;
      btn.title = stp.rule_id + " — executes control " + stp.system + " via the exec rail";
      var out = document.createElement("span");
      out.className = "cs-result muted";
      btn.addEventListener("click", function () {
        out.textContent = "executing…";
        execute(url, stp.system, stp.args || {}, false).then(function (r) {
          var rb = r.body || {};
          if (r.status === 200) {
            out.textContent = rb.dry_run
              ? "dry-run ✓ would run: " + ((rb.would_run || []).join(" ") || stp.system)
              : "executed ✓ exit " + (rb.exit_code != null ? rb.exit_code : 0);
          } else out.textContent = rb.error || ("error " + r.status);
        }).catch(function () { out.textContent = "exec endpoint unreachable"; });
      });
      row.appendChild(btn); row.appendChild(out); result.appendChild(row);
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
    // Options already rendered as one-click buttons must NOT ALSO appear as inert
    // grey pills — a duplicated value reads as clickable-but-dead. Keep pills only
    // for options with no button (free-input controls where the pill is the sole
    // hint, or a semantic label like a toggle's on/off vs its enable/disable verb).
    var buttonVals = {};
    parseTemplate(sys.change_cli).forEach(function (t) {
      if (t.kind === "enum") { t.alts.forEach(function (a) { buttonVals[a] = true; }); }
    });
    var pills = (sys.options || [])
      .filter(function (o) { return !buttonVals[String(o)]; })
      .map(function (o) { return '<span class="cs-opt">' + esc(o) + "</span>"; }).join("");
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

  // Per-option compat greying (mirrors the app-shell's soCompatMark): the
  // READ-ONLY per-option preview (GET /api/control/compat?control_id=, same
  // loopback daemon) greys force-incompatible enum verbs (⛔ disabled +
  // rule/reason/remediation tooltip) and annotates warn/suggest (⚠) — the
  // SAME registry truth as the execute() pre-change gate, so a greyed option
  // is exactly one the gate would refuse. Toggle verbs map onto their state
  // options via the gate's own verb map ({enable→on, disable→off}). Inert
  // option pills get the same mark. Silent no-op when the exec API is absent
  // (static / per-port read-only serving) — the rail stays fully usable.
  var COMPAT_VERB_MAP = { on: "enable", off: "disable" }; // option → toggle verb
  function markCompat(card, sys) {
    fetch("/api/control/compat?control_id=" + encodeURIComponent(sys.id),
          { headers: { Accept: "application/json" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (p) {
        if (!p || !p.available || !p.options) return;
        p.options.forEach(function (row) {
          var f = (row.findings && row.findings[0]) || null;
          if (!row.gating && !f) return;
          var tip = f ? (f.rule_id + ": " + f.reason + " — " + f.remediation) : "";
          var verbAlias = COMPAT_VERB_MAP[row.option] || null;
          Array.prototype.forEach.call(card.querySelectorAll(".cs-verb"), function (btn) {
            var val = btn.getAttribute("data-val");
            if (val !== row.option && val !== verbAlias) return;
            if (row.gating) {
              btn.disabled = true;
              if (btn.textContent.indexOf("⛔") !== 0) btn.textContent = "⛔ " + btn.textContent;
            } else if (btn.textContent.indexOf("⚠") !== 0) {
              btn.textContent = "⚠ " + btn.textContent;
            }
            if (tip) btn.title = tip;
          });
          Array.prototype.forEach.call(card.querySelectorAll(".cs-opt"), function (pill) {
            if (pill.textContent.replace(/^[⛔⚠] /, "") !== row.option) return;
            var mark = row.gating ? "⛔" : "⚠";
            if (pill.textContent.indexOf(mark) !== 0) pill.textContent = mark + " " + pill.textContent;
            if (tip) pill.title = tip;
          });
        });
      }, function () { /* exec API absent — stay silent */ })
      .catch(function () {});
  }

  function render(containerEl, systems, opts) {
    opts = opts || {};
    var slug = opts.filterSlug || null;
    var list = (systems || []).filter(function (s) {
      if (!slug) return true;                       // no filter → all systems
      // SRP: a panel shows ONLY the controls that GOVERN it (its applies_to) —
      // no "global" controls bleeding onto every dashboard.
      return (s.applies_to || []).indexOf(slug) >= 0;
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
    // compat greying — annotate every executable card's options against the
    // box's current state (read-only preview; silent when the API is absent)
    Array.prototype.forEach.call(containerEl.querySelectorAll(".cs-card"), function (card) {
      var sys = byId[card.getAttribute("data-cid")];
      if (sys && !isProxyOnly(sys) && sys.change_cli) markCompat(card, sys);
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
      var n = render(containerEl, systems, opts);
      // SRP: no control governs this panel -> hide the section (heading too)
      var h = containerEl.previousElementSibling;
      containerEl.style.display = n ? "" : "none";
      if (h && /^H[1-6]$/.test(h.tagName)) h.style.display = n ? "" : "none";
      return n;
    });
  }

  global.SovereignControlSurface = { render: render, load: load };
})(window);
