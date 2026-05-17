#!/usr/bin/env bash
# R289 (E4.M9) — dashboard editable forms for module configuration L3 test.
#
# Operator-named (§1b mandate row): "Dashboard editable forms for
# module configuration". The form composes SD-R99 (E2.M6) + SD-R100
# (E2.M7) module-features lifecycle with R288 mobile-friendly CSS.
#
# IMPORTANT: the dashboard NEVER writes — submissions compute the
# equivalent `selfdefctl modules feature-set` commands for the
# operator to run. Tests verify the diff/command emission, the
# graceful-degradation when selfdefctl isn't on PATH, and the safety
# guarantees around slug + key validation.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SERVE="${REPO_ROOT}/scripts/dashboard/serve.py"

fail() { echo "FAIL: $*" >&2; kill "${SERVER_PID:-}" 2>/dev/null || true; exit 1; }
pass() { echo "PASS: $*"; }

# Pick an ephemeral port.
PORT=$(python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', 0)); print(s.getsockname()[1]); s.close()")
URL="http://127.0.0.1:${PORT}"

# ── Spin up the server in a sub-shell ─────────────────────────
# Force selfdefctl absence by giving the subprocess a minimal PATH
# (so we test the graceful-degradation path; the real-binary path
# is tested at the SD-R99/R100 L3 level, not at the dashboard).
env PATH="/usr/bin:/bin" python3 "${SERVE}" --bind "127.0.0.1:${PORT}" \
    >/tmp/r289-serve.log 2>&1 &
SERVER_PID=$!
trap 'kill ${SERVER_PID} 2>/dev/null || true' EXIT

# Wait for the server to come up (up to ~2s).
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    if curl -sf "${URL}/" -o /dev/null 2>/dev/null; then
        break
    fi
    sleep 0.1
done
curl -sf "${URL}/" -o /dev/null \
    || fail "server did not come up; log: $(cat /tmp/r289-serve.log)"

# ── 1. /dashboard.css route serves mobile-friendly stylesheet ────
css="$(curl -sf "${URL}/dashboard.css")" || fail "/dashboard.css fetch"
grep -q 'grid-template-columns:repeat(auto-fit' <<<"${css}" \
    || fail "dashboard.css missing responsive grid"
grep -q '@media (max-width:480px)' <<<"${css}" \
    || fail "dashboard.css missing phone breakpoint"
# Field-specific styling for the form route.
grep -q '.field' <<<"${css}" \
    || fail "dashboard.css missing .field form styles"
pass "1. /dashboard.css serves mobile-friendly CSS with form field styles"

# ── 2. /modules route gracefully degrades when selfdefctl absent ──
body="$(curl -sf "${URL}/modules")" || fail "/modules fetch"
grep -q 'selfdefctl unavailable' <<<"${body}" \
    || fail "/modules must report selfdefctl-unavailable when not on PATH"
grep -q 'selfdef-cli crate' <<<"${body}" \
    || fail "/modules must include the install hint"
# Page must still link the shared CSS so it's mobile-friendly even
# in the degraded state.
grep -q 'href="/dashboard.css"' <<<"${body}" \
    || fail "/modules must link /dashboard.css"
grep -q '<meta name="viewport"' <<<"${body}" \
    || fail "/modules must have viewport meta for mobile"
pass "2. /modules degrades gracefully when selfdefctl absent + stays mobile-friendly"

# ── 3. /modules/<slug> degrades gracefully too ────────────────
# Expect 503 (service unavailable) when selfdefctl is off PATH — but
# the body should still render the operator-readable error + the
# mobile-friendly viewport so the operator can read it on the phone.
http_code=$(curl -s -o /tmp/r289-slug-body -w "%{http_code}" "${URL}/modules/some-slug")
if [[ "${http_code}" != "503" ]]; then
    fail "expected 503 for /modules/<slug> with selfdefctl absent; got ${http_code}"
fi
grep -q 'selfdefctl' /tmp/r289-slug-body \
    || fail "/modules/<slug> must surface selfdefctl-related error in body"
grep -q '<meta name="viewport"' /tmp/r289-slug-body \
    || fail "/modules/<slug> must have viewport meta even in error state"
rm -f /tmp/r289-slug-body
pass "3. /modules/<slug> → 503 with mobile-friendly error body"

# ── 4. Slug validation — reject path-traversal / weird chars ──
# curl's URL parsing prevents some of these client-side, so test
# the ones that can reach the handler.
http_code=$(curl -s -o /tmp/r289-body -w "%{http_code}" "${URL}/modules/bad..slug")
if [[ "${http_code}" != "400" ]]; then
    fail "expected 400 for slug with '..'; got ${http_code}"
fi
grep -q 'invalid module slug' /tmp/r289-body \
    || fail "400 response body missing error message"
rm -f /tmp/r289-body
pass "4. invalid slugs (path traversal etc) → 400"

# Now stop the live server — the remaining checks are CLI-level
# unit-style tests of the diff/command emission, which we can do
# without HTTP at all.
kill "${SERVER_PID}" 2>/dev/null || true
wait "${SERVER_PID}" 2>/dev/null || true
trap - EXIT

# ── 5. Diff-command emission for boolean toggle ────────────────
python3 - <<'PY'
import sys, pathlib
sys.path.insert(0, str(pathlib.Path("scripts/dashboard").resolve()))
# Import the serve module's diff helpers directly.
import importlib.util
spec = importlib.util.spec_from_file_location("serve", "scripts/dashboard/serve.py")
serve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve)

# Current effective features (what `selfdefctl modules features <slug>`
# would have returned).
features = {
    "auditd": True,
    "fail2ban": True,
    "limits": {"warn": 100, "critical": 200},
    "notes": "default",
}
# Submitted form values — disable auditd, lower warn, leave others.
submitted = [
    ("auditd", "false"),          # was True, will diff
    ("fail2ban", "false"),        # hidden=false from unchecked checkbox …
    ("fail2ban", "true"),         # … then the real checkbox value (kept)
    ("limits.warn", "50"),        # int diff
    ("limits.critical", "200"),   # unchanged — must NOT appear
    ("notes", "default"),         # unchanged — must NOT appear
]
cmds = serve.diff_commands_for("probe-mod", features, submitted)

# auditd was True → form sent false → command must set it to false.
assert any("auditd false" in c for c in cmds), cmds
# limits.warn changed from 100 → 50.
assert any("limits.warn 50" in c for c in cmds), cmds
# fail2ban stayed True → must NOT appear.
assert not any("fail2ban" in c for c in cmds), cmds
# limits.critical unchanged → must NOT appear.
assert not any("limits.critical" in c for c in cmds), cmds
# notes unchanged → must NOT appear.
assert not any("notes" in c for c in cmds), cmds
# Every emitted command must start with the slug-bearing prefix.
for c in cmds:
    assert c.startswith("selfdefctl modules feature-set probe-mod "), c
print("PASS")
PY
pass "5. diff_commands_for emits the right set of feature-set commands"

# ── 6. TOML-scalar coercion for known types ────────────────────
python3 - <<'PY'
import importlib.util
spec = importlib.util.spec_from_file_location("serve", "scripts/dashboard/serve.py")
serve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve)

assert serve._toml_scalar_for(True) == "true"
assert serve._toml_scalar_for(False) == "false"
assert serve._toml_scalar_for(42) == "42"
assert serve._toml_scalar_for(3.14) == "3.14"
# Strings round-trip through TOML quoting + escape backslashes/quotes.
assert serve._toml_scalar_for("hello") == '"hello"', serve._toml_scalar_for("hello")
assert serve._toml_scalar_for('with "quote"') == r'"with \"quote\""'
assert serve._toml_scalar_for('back\\slash') == r'"back\\slash"'
print("PASS")
PY
pass "6. _toml_scalar_for produces valid TOML scalars for every type"

# ── 7. Coerce-for-compare matches existing types ────────────────
python3 - <<'PY'
import importlib.util
spec = importlib.util.spec_from_file_location("serve", "scripts/dashboard/serve.py")
serve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve)

assert serve._coerce_for_compare("true", True) is True
assert serve._coerce_for_compare("false", True) is False
assert serve._coerce_for_compare("on", False) is True
assert serve._coerce_for_compare("", True) is False  # blank → false
assert serve._coerce_for_compare("42", 0) == 42
assert serve._coerce_for_compare("3.5", 1.0) == 3.5
assert serve._coerce_for_compare("free text", "default") == "free text"
print("PASS")
PY
pass "7. _coerce_for_compare matches existing field types"

# ── 8. Flatten produces dotted-path keys ────────────────────────
python3 - <<'PY'
import importlib.util
spec = importlib.util.spec_from_file_location("serve", "scripts/dashboard/serve.py")
serve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve)

flat = serve._flatten({
    "a": 1,
    "b": {"c": 2, "d": {"e": 3}},
    "f": True,
})
assert flat == {"a": 1, "b.c": 2, "b.d.e": 3, "f": True}, flat
print("PASS")
PY
pass "8. _flatten emits dotted-path key/value pairs"

# ── 9. render_module_features_form_html emits a form with fields ─
python3 - <<'PY'
import importlib.util
spec = importlib.util.spec_from_file_location("serve", "scripts/dashboard/serve.py")
serve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve)

features_doc = {
    "source": "/etc/selfdef/modules/probe-mod.toml",
    "features": {
        "auditd": True,
        "retry": 5,
        "limits": {"warn": 100},
        "label": "default",
    },
}
html = serve.render_module_features_form_html(
    "probe-mod", features_doc, None, None,
)
# Form posts to itself via GET.
assert '<form method="GET" action="/modules/probe-mod">' in html, html
# Boolean → hidden + checkbox.
assert 'name="auditd" value="false"' in html
assert 'type="checkbox"' in html
# Int → number input.
assert 'type="number"' in html
# String → text input.
assert 'type="text"' in html
# Submit button present.
assert '<button type="submit">' in html
# Mobile-friendly meta tag.
assert 'name="viewport"' in html
# Source field surfaced.
assert '/etc/selfdef/modules/probe-mod.toml' in html
# Dotted-path label rendered.
assert 'limits.warn' in html
print("PASS")
PY
pass "9. render_module_features_form_html emits form with typed inputs + mobile meta"

# ── 10. Form with diff commands shows the copy-block ────────────
python3 - <<'PY'
import importlib.util
spec = importlib.util.spec_from_file_location("serve", "scripts/dashboard/serve.py")
serve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve)

html = serve.render_module_features_form_html(
    "probe-mod",
    {"source": "(defaults)", "features": {"x": True}},
    None,
    ["selfdefctl modules feature-set probe-mod x false"],
)
assert "Commands to apply your changes" in html
assert "selfdefctl modules feature-set probe-mod x false" in html
# Empty diff path: no-changes message.
html_empty = serve.render_module_features_form_html(
    "probe-mod",
    {"source": "(defaults)", "features": {"x": True}},
    None,
    [],
)
assert "No changes detected" in html_empty
print("PASS")
PY
pass "10. form renders diff-command copy-block + no-changes path"

echo "ALL OK"
