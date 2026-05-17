#!/usr/bin/env bash
# R288 (E4.M8) — mobile-friendly dashboard CSS L3 test.
#
# Operator-named (§1b mandate row): "Mobile-friendly card layout
# (CSS only, no JS framework)". Also addresses the broader §1b
# directive "Everything via dashboard/UInterface or terminal tools
# OR AI" — the dashboard needs to work on the operator's phone.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SERVE="${REPO_ROOT}/scripts/dashboard/serve.py"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# Render once.
HTML="$(python3 "${SERVE}" --render-only)" || fail "render-only invocation"

# ── 1. Viewport meta-tag present (responsive sine qua non) ────
if ! grep -q 'name="viewport"' <<<"${HTML}"; then
    fail "missing <meta name=viewport>"
fi
if ! grep -q 'width=device-width' <<<"${HTML}"; then
    fail "viewport must include width=device-width"
fi
if ! grep -q 'initial-scale=1' <<<"${HTML}"; then
    fail "viewport must include initial-scale=1"
fi
pass "1. viewport meta-tag (width=device-width, initial-scale=1)"

# ── 2. Charset declared + lang attribute on <html> ───────────
if ! grep -q 'charset="utf-8"' <<<"${HTML}"; then
    fail "missing <meta charset=utf-8>"
fi
if ! grep -q '<html lang="en"' <<<"${HTML}"; then
    fail "missing <html lang=en> attribute"
fi
pass "2. charset utf-8 + html lang attribute"

# ── 3. Responsive grid container present ─────────────────────
if ! grep -q '<div class="cards">' <<<"${HTML}"; then
    fail "cards must be wrapped in <div class=cards>"
fi
if ! grep -q 'display:grid' <<<"${HTML}"; then
    fail "missing display:grid (cards container)"
fi
if ! grep -q 'grid-template-columns:repeat(auto-fit' <<<"${HTML}"; then
    fail "missing auto-fit grid (responsive layout)"
fi
if ! grep -q 'minmax(320px' <<<"${HTML}"; then
    fail "grid must use minmax(320px,...) for phone-fit"
fi
pass "3. responsive CSS grid (auto-fit + minmax 320px)"

# ── 4. Phone media query collapses to single column ──────────
if ! grep -q '@media (max-width:480px)' <<<"${HTML}"; then
    fail "missing @media (max-width:480px) phone breakpoint"
fi
# Brace-balanced extraction of the phone-mq block.
phone_block="$(python3 -c "
import sys
html = sys.stdin.read()
needle = '@media (max-width:480px){'
i = html.find(needle)
if i < 0:
    sys.exit(1)
depth = 0
j = i + len(needle) - 1   # position of the opening brace
end = -1
for k in range(j, len(html)):
    c = html[k]
    if c == '{':
        depth += 1
    elif c == '}':
        depth -= 1
        if depth == 0:
            end = k + 1
            break
if end < 0:
    sys.exit(2)
print(html[i:end])
" <<<"${HTML}")"
if [[ -z "${phone_block}" ]]; then
    fail "could not extract phone @media block"
fi
if ! grep -q 'grid-template-columns:1fr' <<<"${phone_block}"; then
    fail "phone media query must collapse cards to single column (grid-template-columns:1fr)"
fi
pass "4. phone breakpoint (≤480px) collapses to single column"

# ── 5. Touch-friendly tap targets (≥32px line-height on phone) ──
if ! grep -q 'min-height:32px' <<<"${phone_block}"; then
    fail "phone breakpoint missing touch-friendly tap target (min-height:32px)"
fi
pass "5. touch-friendly tap-target sizing on phone"

# ── 6. No JS framework imported (operator-named: CSS only) ───
if grep -qE 'src=["'"'"']https?://[^"'"'"']*\.js' <<<"${HTML}"; then
    fail "no external JS allowed (operator-named: CSS only, no JS framework)"
fi
if grep -qiE 'react|vue|angular|svelte|jquery' <<<"${HTML}"; then
    fail "no JS framework references allowed"
fi
pass "6. no external JS framework imported (CSS-only contract)"

# ── 7. Print media query (operator can print snapshot) ───────
if ! grep -q '@media print' <<<"${HTML}"; then
    fail "missing @media print for snapshot printing"
fi
pass "7. print media query present"

# ── 8. CSS custom properties (CSS-vars) used for the palette ──
# Phone overrides + print overrides + dark/print share a palette.
if ! grep -q '\--bg:' <<<"${HTML}"; then
    fail "missing CSS custom properties (palette indirection)"
fi
if ! grep -q 'var(--bg)' <<<"${HTML}"; then
    fail "palette must use var(--bg) etc, not hard-coded hex everywhere"
fi
pass "8. CSS custom properties used for palette (palette indirection)"

# ── 9. Long content wrap-breakers (no horizontal scroll on phone) ──
if ! grep -q 'word-wrap:break-word' <<<"${HTML}"; then
    fail "missing word-wrap:break-word — long content overflows on phone"
fi
if ! grep -q 'overflow-x:auto' <<<"${HTML}"; then
    fail "missing overflow-x:auto on <pre> — JSON blocks can't scroll on phone"
fi
pass "9. wrap-breakers + overflow-x:auto (no horizontal page scroll)"

# ── 10. Existing dashboard surface intact ────────────────────
# Existing cards must still be there — the R288 CSS rewrite must
# not have dropped any card. Spot-check a few seed-card IDs.
for cid in card-gpu card-network card-cpu card-fs; do
    if ! grep -q "id=\"${cid}\"" <<<"${HTML}"; then
        fail "missing existing card id=${cid} (CSS rewrite must not drop cards)"
    fi
done
pass "10. existing dashboard cards still present (no regression)"

echo "ALL OK"
