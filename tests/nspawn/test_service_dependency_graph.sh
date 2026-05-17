#!/usr/bin/env bash
# tests/nspawn/test_service_dependency_graph.sh — R277 (E2.M9).
# Service-dependency graph + topo-sorted drain order.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/services/dependency-graph.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_service_dependency_graph.sh"
echo

[ -x "${SCRIPT}" ] && ok "dependency-graph.py executable" \
  || { ko "missing"; exit 1; }
grep -q "R277\|E2.M9" "${SCRIPT}" && ok "script cites R277/E2.M9" \
  || ko "R277 missing"
grep -q "^  service-deps)" "${OSCTL}" \
  && ok "osctl bridges 'service-deps'" || ko "osctl dispatch missing"

# ---- graph --json: builds DAG from in-repo systemd units ----
out="$(python3 "${SCRIPT}" graph --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R277', d
# 30+ sovereign-* units shipped in repo.
assert d['node_count'] >= 20, d
for n in d['nodes']:
    assert 'unit' in n and 'deps' in n
    for k in ('After','Before','Wants','Requires','BindsTo','WantedBy'):
        assert k in n['deps'], k
" \
  && ok "graph --json: ≥20 nodes, every node has After/Wants/Requires/etc. slots" \
  || ko "graph shape wrong"

# ---- drain --json: produces topologically ordered list ----
out="$(python3 "${SCRIPT}" drain --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R277', d
assert d['drain_order_count'] == d['input_unit_count'] - len(d['cycle_nodes']), d
assert isinstance(d['drain_order'], list)
assert isinstance(d['cycle_present'], bool)
" \
  && ok "drain --json: drain_order_count == input_count − cycle_count" \
  || ko "drain shape wrong"

# ---- dot output: graphviz syntax ----
out_dot="$(python3 "${SCRIPT}" dot)"
echo "${out_dot}" | grep -q "digraph sovereign_services" \
  && ok "dot: emits digraph header" || ko "dot header missing"
echo "${out_dot}" | grep -q "rankdir=BT" \
  && ok "dot: bottom-up layout (stop-first at bottom)" || ko "rankdir missing"

# ---- in-process: explicit cycle detection ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('dg','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# Synthetic cycle: a → b → c → a
graph = {
    'nodes': [{'unit':'a.service','deps':{}},
              {'unit':'b.service','deps':{}},
              {'unit':'c.service','deps':{}}],
    'edges': [
        {'from':'a.service','to':'b.service','kind':'after'},
        {'from':'b.service','to':'c.service','kind':'after'},
        {'from':'c.service','to':'a.service','kind':'after'},
    ],
}
res = m.topo_sort_drain(graph)
assert res['cycle_present'] is True
assert set(res['cycle_nodes']) == {'a.service','b.service','c.service'}, res
" \
  && ok "topo_sort_drain: 3-node cycle detected (a→b→c→a)" \
  || ko "cycle detection wrong"

# ---- in-process: linear chain topo order ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('dg','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# A is preq of B which is preq of C; drain order: leaves first
# After-edge from A to B means B depends on A (A started first).
# During drain, B stops BEFORE A.
# Edge encoding: a→b means 'a is needed by b' so b stops first.
graph = {
    'nodes': [{'unit':'a.service','deps':{}},
              {'unit':'b.service','deps':{}},
              {'unit':'c.service','deps':{}}],
    'edges': [
        {'from':'a.service','to':'b.service','kind':'after'},
        {'from':'b.service','to':'c.service','kind':'after'},
    ],
}
res = m.topo_sort_drain(graph)
assert res['cycle_present'] is False
# c stops first (no one depends on c), then b, then a.
assert res['drain_order'] == ['c.service', 'b.service', 'a.service'], res
" \
  && ok "topo_sort_drain: linear a→b→c chain → drain order [c, b, a]" \
  || ko "linear chain wrong"

# ---- in-process: --unit override ----
python3 -c "
import importlib.util, argparse, io, contextlib, json as j
spec = importlib.util.spec_from_file_location('dg','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
args = argparse.Namespace(unit='one.service,two.service', prefix='', json=True)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = m.cmd_graph(args)
report = j.loads(buf.getvalue())
assert report['units'] == ['one.service', 'two.service'], report
" \
  && ok "--unit override: only specified units enter the graph" \
  || ko "--unit override wrong"

# ---- parse_unit_file_dependencies: file-based fallback ----
python3 -c "
import importlib.util
from pathlib import Path
import tempfile
spec = importlib.util.spec_from_file_location('dg','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
with tempfile.NamedTemporaryFile(suffix='.service', mode='w', delete=False) as fh:
    fh.write('''[Unit]
Description=test
After=foo.service bar.service
Requires=foo.service
[Service]
ExecStart=/bin/true
''')
    p = Path(fh.name)
d = m.parse_unit_file_dependencies(p)
assert 'foo.service' in d['After'], d
assert 'bar.service' in d['After'], d
assert 'foo.service' in d['Requires'], d
p.unlink()
" \
  && ok "parse_unit_file_dependencies: After/Requires extracted from raw file" \
  || ko "file parse wrong"

# ---- human render: banner ----
out_h="$(python3 "${SCRIPT}" drain 2>&1)"
echo "${out_h}" | grep -q "R277 service-dependency-graph drain order" \
  && ok "drain human banner present" || ko "banner missing"
echo "${out_h}" | grep -q "STOP-FIRST" \
  && ok "drain human has STOP-FIRST marker" || ko "STOP-FIRST marker missing"

# ---- osctl bridge ----
TMP="$(mktemp -d -t r277.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
set +e
"${OSCTL}" service-deps drain --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "osctl service-deps drain rc ∈ {0,1}"
else
  ko "osctl bridge rc=${rc}"
fi
python3 -c "
import json
d = json.load(open('${TMP}/osctl.out'))
assert d['round'] == 'R277', d
" \
  && ok "osctl bridge surfaces R277 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" service-deps nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown service-deps subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_service_dependency_graph: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
