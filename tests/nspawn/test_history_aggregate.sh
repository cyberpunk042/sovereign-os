#!/usr/bin/env bash
# tests/nspawn/test_history_aggregate.sh — R246 (SDD-026 Z-16).
# Cross-cutting operator-timeline JSONL aggregator across notify-events
# + models-eval + fine-tune + operator-supplied extras.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/history/aggregate.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_history_aggregate.sh"
echo

[ -x "${SCRIPT}" ] && ok "aggregate.py executable" \
  || { ko "missing aggregate.py"; exit 1; }
grep -q "R246" "${SCRIPT}" && ok "aggregate.py cites R246" || ko "R246 missing"
grep -q "^  events)" "${OSCTL}" \
  && ok "osctl bridges 'events'" || ko "osctl dispatch missing"
grep -q "events timeline" "${OSCTL}" \
  && ok "osctl help documents 'events'" || ko "osctl help missing"

TMP="$(mktemp -d -t r246.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
export SOVEREIGN_OS_HISTORY_STATE_DIR="${TMP}"

# Seed each source with synthetic rows.
cat > "${TMP}/notify.jsonl" <<'JSON'
{"probe":"network","severity":"attention","detail":"docker down","emitted_at":"2026-05-15T10:00:00Z"}
{"probe":"fs_usage","severity":"down","detail":"/ at 95%","emitted_at":"2026-05-16T11:00:00Z"}
JSON
cat > "${TMP}/models-eval.jsonl" <<'JSON'
{"model_id":"Phi-4-mini-instruct","benchmark":"mmlu","outcome":"ok","rc":0,"duration_s":42.5,"started_at":"2026-05-17T09:00:00Z"}
JSON
cat > "${TMP}/fine-tune.jsonl" <<'JSON'
{"base_id":"Phi-4-mini-instruct","method":"lora-unsloth","dataset":"op/ds","outcome":"dry-run","rc":0,"duration_s":0.0,"started_at":"2026-05-17T10:00:00Z"}
JSON

# ---- summary --json: counts per source ----
out="$(python3 "${SCRIPT}" summary --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R246', d
assert d['total_events']==4, d
s=d['sources']
assert s['notify-events']['event_count']==2, s
assert s['models-eval']['event_count']==1, s
assert s['fine-tune']['event_count']==1, s
" \
  && ok "summary: counts across all 3 sources sum to 4" \
  || ko "summary shape wrong"

# ---- timeline --json: 4 events sorted chronologically ----
out="$(python3 "${SCRIPT}" timeline --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['count']==4, d
# Sorted ascending.
tss=[e['timestamp'] for e in d['events']]
assert tss==sorted(tss), tss
# Sources mixed (not grouped by source).
sources=[e['source'] for e in d['events']]
assert 'notify-events' in sources and 'models-eval' in sources and 'fine-tune' in sources
" \
  && ok "timeline: 4 events sorted across all sources" \
  || ko "timeline shape wrong"

# ---- timeline --source filter ----
out="$(python3 "${SCRIPT}" timeline --source notify-events --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['count']==2, d
for e in d['events']:
    assert e['source']=='notify-events', e
" \
  && ok "timeline --source filters to one source" \
  || ko "source filter wrong"

# ---- timeline --since cutoff ----
out="$(python3 "${SCRIPT}" timeline --since 2026-05-17T00:00:00Z --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['count']==2, d  # only the 2 events on 2026-05-17
" \
  && ok "timeline --since cutoff drops earlier events" \
  || ko "since filter wrong"

# ---- timeline --limit caps result ----
out="$(python3 "${SCRIPT}" timeline --limit 1 --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['count']==1, d
" \
  && ok "timeline --limit caps result" \
  || ko "limit wrong"

# ---- kind template applied ----
out="$(python3 "${SCRIPT}" timeline --source notify-events --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=sorted(e['kind'] for e in d['events'])
assert kinds==['notify:fs_usage','notify:network'], kinds
" \
  && ok "kind template resolves per-row ({probe} → notify:probe)" \
  || ko "kind template wrong"

# ---- detail template applied ----
out="$(python3 "${SCRIPT}" timeline --source models-eval --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
e=d['events'][0]
assert 'Phi-4-mini-instruct' in e['detail'], e
assert 'ok' in e['detail'], e
assert 'rc=0' in e['detail'], e
" \
  && ok "detail template resolves per-row" \
  || ko "detail template wrong"

# ---- extras path expansion ----
cat > "${TMP}/operator-extra.jsonl" <<'JSON'
{"timestamp":"2026-05-17T14:00:00Z","note":"operator-supplied row"}
JSON
SOVEREIGN_OS_HISTORY_EXTRA_PATHS="${TMP}/operator-extra.jsonl" \
  python3 "${SCRIPT}" timeline --json > "${TMP}/extras.out"
python3 -c "
import json
d=json.load(open('${TMP}/extras.out'))
assert d['count']==5, d  # 4 base + 1 extra
sources=[e['source'] for e in d['events']]
assert any(s.startswith('extra:') for s in sources), sources
" \
  && ok "SOVEREIGN_OS_HISTORY_EXTRA_PATHS adds operator-supplied source" \
  || ko "extras expansion wrong"

# ---- empty state: graceful ----
TMP2="$(mktemp -d -t r246-empty.XXXXXX)"
SOVEREIGN_OS_HISTORY_STATE_DIR="${TMP2}" python3 "${SCRIPT}" timeline --json > "${TMP2}/empty.out"
python3 -c "
import json
d=json.load(open('${TMP2}/empty.out'))
assert d['count']==0, d
assert d['events']==[], d
" \
  && ok "empty state: timeline emits {count:0,events:[]}" \
  || ko "empty shape wrong"
rm -rf "${TMP2}"

# ---- osctl bridge ----
set +e
"${OSCTL}" events summary --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl events summary rc=0" \
  || ko "osctl bridge rc=${rc}"
python3 -c "
import json
d=json.load(open('${TMP}/osctl.out'))
assert d['round']=='R246', d
" \
  && ok "osctl bridge surfaces R246 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" events nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown events subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_history_aggregate: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
