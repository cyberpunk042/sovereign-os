#!/usr/bin/env bash
# R286 (E7.M5) — cross-repo MCP-tool aggregator L3 test.
#
# Operator-named (§1b mandate row): "Cross-repo MCP-tool aggregator
# (sovereign-os surfaces selfdef tools too)". Also closes Q-019
# ("lifecycle-management MCP for sovereign-os") referenced in SDD-002.
#
# Validates:
#   1. `mcp-aggregate manifest --json` emits valid JSON with the
#      expected schema (round, schema_version, sources, tools[]).
#   2. The local tool set covers EVERY axis the operator named in §1b
#      (hardware, GPU 3090 + RTX PRO 6000, CPU mode, PSU/UPS, XMP,
#      BIOS / ASUS X870E, network/DNS/reverse-proxy, kernel, pcie,
#      health/insights, dashboard, AVX-512/ZMM ternary). Missing axis
#      = failed test = future-round forcing function.
#   3. `--upstream-selfdef host:port` adds a selfdef-namespace source.
#   4. `probe-upstream` returns reachable=false for a closed port and
#      reachable=true for a real listener (uses Python -m http.server
#      as the listener since it accepts TCP connects).
#   5. Operator overlay (extra_tools + exclude_tools) is honoured.
#   6. `sovereign-osctl mcp-aggregate` dispatches to the script.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/interop/mcp-aggregate.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. Manifest is valid JSON with expected envelope ────────────
out="$(python3 "${SCRIPT}" manifest --json)"
echo "${out}" | python3 -c "import json,sys; json.loads(sys.stdin.read())" \
    || fail "manifest --json must be valid JSON"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R286', d['round']
assert d['schema_version'] == '1.0.0', d['schema_version']
assert isinstance(d['sources'], list) and len(d['sources']) >= 1
assert isinstance(d['tools'], list)
assert d['tool_count'] == len(d['tools'])
assert d['upstream_selfdef'] is None
" || fail "manifest envelope schema"
pass "1. manifest envelope schema"

# ── 2. Cross-axis coverage — every named axis must have ≥1 tool ──
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
cats = set()
for t in d['tools']:
    for c in t.get('categories', []):
        cats.add(c)
# Operator-named axes from §1b 'all the angles' mandate:
must_have = {
    'hardware', 'gpu', 'cpu', 'memory', 'power', 'psu', 'ups',
    'bios', 'board', 'avx512', 'network', 'dns', 'kernel', 'pcie',
    'storage', 'services', 'health', 'observability', 'dashboard',
    'notify', 'modules', 'install', 'thermal', 'lifecycle',
    'ahead-of-time', 'advisor', 'virt', 'audit', 'security',
}
missing = must_have - cats
if missing:
    print(f'MISSING AXES: {sorted(missing)}', file=sys.stderr)
    print(f'Have axes: {sorted(cats)}', file=sys.stderr)
    sys.exit(1)
" || fail "cross-axis coverage gap"
pass "2. cross-axis coverage (every §1b-named axis has ≥1 MCP tool)"

# Hardware-specific name-level checks (so renaming a tool breaks
# the test on purpose, not silently).
for name in hardware-inventory gpu-watch gpu-card-advisor cpu-mode bios-info \
            ram-advisor power-status zmm-ternary wasm-aot \
            memory-pressure pcie-policy virt-info kernel \
            network dns-advisor reverse-proxy perimeter \
            health insights services service-deps events \
            dashboard-grid notify-list; do
    echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {t['name'] for t in d['tools']}
assert '${name}' in names, f'missing tool: ${name} in {sorted(names)}'
" || fail "missing tool: ${name}"
done
pass "3. all named tools present (24 anchor names)"

# ── 4. Upstream-selfdef descriptor lands in manifest ────────────
out_up="$(python3 "${SCRIPT}" manifest --upstream-selfdef 127.0.0.1:9999 --json)"
echo "${out_up}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['upstream_selfdef'] is not None
u = d['upstream_selfdef']
assert u['host'] == '127.0.0.1', u
assert u['port'] == 9999, u
assert u['transport'] == 'tcp', u
assert 'SD-R94' in u['protocol'], u
ns = {s['namespace'] for s in d['sources']}
assert 'selfdef' in ns, ns
" || fail "upstream descriptor schema"
pass "4. --upstream-selfdef adds selfdef namespace"

# Invalid --upstream-selfdef rejected.
if python3 "${SCRIPT}" manifest --upstream-selfdef "bad-no-port" --json >/dev/null 2>&1; then
    fail "must reject malformed --upstream-selfdef"
fi
if python3 "${SCRIPT}" manifest --upstream-selfdef "host:notanint" --json >/dev/null 2>&1; then
    fail "must reject non-numeric port"
fi
if python3 "${SCRIPT}" manifest --upstream-selfdef "host:0" --json >/dev/null 2>&1; then
    fail "must reject port 0"
fi
pass "5. --upstream-selfdef validation"

# ── 6. probe-upstream against closed port → reachable=false, rc=1 ──
PORT_CLOSED=1
out_probe="$(python3 "${SCRIPT}" probe-upstream 127.0.0.1:1 --json 2>&1)" || PORT_CLOSED=$?
# Even on rc≠0 the JSON is on stdout — capture and parse.
echo "${out_probe}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['reachable'] is False, d
assert d['port'] == 1, d
" || fail "probe-upstream closed-port schema"
[[ "${PORT_CLOSED}" == "1" ]] || fail "probe-upstream closed-port must exit 1, got ${PORT_CLOSED}"
pass "6. probe-upstream closed → reachable=false, rc=1"

# probe-upstream against an actual listener → reachable=true, rc=0
# Spin up a one-shot Python HTTP listener on an ephemeral port.
LISTEN_PORT=$(python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', 0)); print(s.getsockname()[1]); s.close()")
python3 -m http.server "${LISTEN_PORT}" --bind 127.0.0.1 >/dev/null 2>&1 &
LISTEN_PID=$!
trap 'kill ${LISTEN_PID} 2>/dev/null || true' EXIT
# Give the listener a moment to come up.
for _ in 1 2 3 4 5 6 7 8 9 10; do
    python3 -c "
import socket, sys
s = socket.socket()
s.settimeout(0.2)
try:
    s.connect(('127.0.0.1', ${LISTEN_PORT}))
    sys.exit(0)
except OSError:
    sys.exit(1)
finally:
    s.close()
" && break
    sleep 0.1
done
python3 "${SCRIPT}" probe-upstream "127.0.0.1:${LISTEN_PORT}" --json | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['reachable'] is True, d
" || fail "probe-upstream open-port must report reachable=true"
pass "7. probe-upstream open → reachable=true"
kill ${LISTEN_PID} 2>/dev/null || true

# ── 8. Operator overlay (extra_tools + exclude_tools) ───────────
overlay_file="$(mktemp --suffix=.toml)"
cat > "${overlay_file}" <<'TOML'
exclude_tools = ["notify-list"]

[[extra_tools]]
name = "operator-custom-tool"
summary = "Operator-pull custom MCP tool, added via overlay."
argv = ["my-custom-script", "--json"]
categories = ["operator-custom"]
TOML

out_ov="$(python3 "${SCRIPT}" manifest --config "${overlay_file}" --json)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {t['name'] for t in d['tools']}
assert 'operator-custom-tool' in names, f'overlay add not honoured: {sorted(names)}'
assert 'notify-list' not in names, f'overlay exclude not honoured: {sorted(names)}'
# _source field is the resolved overlay file path; _overlay_keys
# advertises which dotted-paths were overridden.
ovkeys = set(d['overlay']['_overlay_keys'])
assert 'extra_tools' in ovkeys, ovkeys
assert 'exclude_tools' in ovkeys, ovkeys
" || fail "operator overlay (extra_tools + exclude_tools) not honoured"
rm -f "${overlay_file}"
pass "8. operator overlay honoured (extra_tools + exclude_tools)"

# ── 9. sovereign-osctl dispatch surface ─────────────────────────
out_disp="$(bash "${OSCTL}" mcp-aggregate manifest --json)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R286'
assert d['tool_count'] >= 25, d['tool_count']
" || fail "sovereign-osctl mcp-aggregate dispatch broken"
pass "9. sovereign-osctl mcp-aggregate dispatches to the script"

echo "ALL OK"
