#!/usr/bin/env bash
# tests/nspawn/test_notify_dispatch.sh — R228 (SDD-026 Z-6) notification
# fan-out reading R226 health-scan + delivering to channels (file /
# webhook / ntfy). Tests with the `file` channel — no external service
# required.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/notify/dispatch.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"
HEALTH="${__REPO_ROOT}/scripts/hardware/health-scan.py"
EXAMPLE="${__REPO_ROOT}/config/notify.toml.example"

echo "tests/nspawn/test_notify_dispatch.sh"
echo

# ---- shipped + wired ----
[ -x "${SCRIPT}" ] && ok "dispatch.py executable" \
  || { ko "missing dispatch.py"; exit 1; }
[ -f "${EXAMPLE}" ] && ok "config/notify.toml.example shipped" \
  || ko "missing notify.toml.example"
grep -q "^  notify)" "${OSCTL}" \
  && ok "osctl bridges 'notify'" || ko "osctl bridge missing"
grep -q "R228" "${OSCTL}" \
  && ok "osctl cites R228" || ko "R228 citation missing"
grep -q "notify dispatch" "${OSCTL}" \
  && ok "osctl help documents 'notify dispatch'" || ko "help missing"

# ---- prepare a synthetic health-scan with mixed severities ----
cat > /tmp/r228-scan.json <<'JSON'
{
  "round": "R226",
  "vector": "SDD-026 Z-6 (scan layer)",
  "started_at": "2026-05-17T00:00:00Z",
  "probes": [
    {"probe":"gpu","round":"R219","vector":"Z-5","rc":0,"severity":"ok","detail":"healthy","flagged_items":[]},
    {"probe":"network","round":"R220","vector":"Z-7","rc":1,"severity":"attention","detail":"docker down","flagged_items":[{"id":"docker","status":"down"}]},
    {"probe":"cpu_mode","round":"R221","vector":"Z-4","rc":0,"severity":"informational","detail":"vm","flagged_items":[]},
    {"probe":"fs_usage","round":"R222","vector":"Z-10","rc":1,"severity":"attention","detail":"/ at 90%","flagged_items":[{"id":"/","use_pct":90}]},
    {"probe":"raid","round":"R223","vector":"Z-9","rc":0,"severity":"informational","detail":"no md","flagged_items":[]},
    {"probe":"flex","round":"R224","vector":"Z-3","rc":0,"severity":"informational","detail":"3 deltas","flagged_items":[]}
  ],
  "summary": {"total":6,"ok":1,"attention":2,"informational":3},
  "needs_attention": true
}
JSON

# ---- isolated config + state for this test ----
cat > /tmp/r228-cfg.toml <<'TOML'
[channels.file]
enabled = true
path = "/tmp/r228-events.jsonl"
[channels.webhook]
enabled = false
url = "env:R228_TEST_WEBHOOK_URL"
TOML
rm -f /tmp/r228-state.json /tmp/r228-events.jsonl

export SOVEREIGN_OS_NOTIFY_CONFIG=/tmp/r228-cfg.toml
export SOVEREIGN_OS_NOTIFY_STATE=/tmp/r228-state.json

# ---- list-channels ----
out="$(python3 "${SCRIPT}" list-channels --json 2>&1)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R228', d
names={c['name'] for c in d['channels']}
assert {'file','webhook','ntfy'} <= names, names
file_ch=[c for c in d['channels'] if c['name']=='file'][0]
assert file_ch['enabled'] is True
wh=[c for c in d['channels'] if c['name']=='webhook'][0]
assert wh['enabled'] is False
" \
  && ok "list-channels JSON: file=on webhook=off ntfy present" \
  || ko "list-channels JSON shape wrong"

# ---- dispatch first run: 2 events transition new ----
out="$(python3 "${SCRIPT}" dispatch --from-file /tmp/r228-scan.json --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['events_emitted']==2, d
assert d['scan_needs_attention'] is True, d
probes={e['probe'] for e in d['events']}
assert probes=={'network','fs_usage'}, probes
for e in d['events']:
    assert e['transition']=='new', e
    assert e['severity']=='attention', e
deliveries=d['deliveries']
assert any(x['channel']=='file' and x['ok'] for x in deliveries), deliveries
" \
  && ok "first dispatch: 2 new-transition events to file channel" \
  || ko "first dispatch shape wrong: ${out}"

# ---- file sink wrote 2 lines ----
[ -f /tmp/r228-events.jsonl ] && [ "$(wc -l < /tmp/r228-events.jsonl)" -eq 2 ] \
  && ok "file sink wrote 2 JSONL lines" \
  || ko "expected 2 lines in /tmp/r228-events.jsonl, got $(wc -l < /tmp/r228-events.jsonl 2>/dev/null || echo none)"

# Each JSONL line must be valid JSON with the documented shape.
python3 - <<'PY' \
  && ok "JSONL lines parse + carry probe/severity/transition" \
  || ko "JSONL shape wrong"
import json
lines=open('/tmp/r228-events.jsonl').read().splitlines()
assert len(lines)==2
for l in lines:
    e=json.loads(l)
    assert e['severity']=='attention'
    assert e['transition']=='new'
    assert e['probe'] in {'network','fs_usage'}
    assert 'detail' in e and 'emitted_at' in e
PY

# ---- second dispatch: dedup → 0 events, file sink unchanged ----
out="$(python3 "${SCRIPT}" dispatch --from-file /tmp/r228-scan.json --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['events_emitted']==0, d
assert d['deliveries']==[], d
" \
  && ok "second dispatch dedups to 0 events" \
  || ko "dedup failed: ${out}"
[ "$(wc -l < /tmp/r228-events.jsonl)" -eq 2 ] \
  && ok "file sink still 2 lines (no spam)" \
  || ko "file sink grew after dedup"

# ---- transition escalation: network ok→attention→down emits new event ----
python3 - <<'PY'
import json
d=json.load(open('/tmp/r228-scan.json'))
for p in d['probes']:
    if p['probe']=='network':
        p['severity']='down'
        p['detail']='docker + tailscale both down'
json.dump(d, open('/tmp/r228-scan.json','w'))
PY
out="$(python3 "${SCRIPT}" dispatch --from-file /tmp/r228-scan.json --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['events_emitted']==1, d
e=d['events'][0]
assert e['probe']=='network', e
assert e['severity']=='down', e
assert e['transition']=='attention->down', e
" \
  && ok "escalation attention→down fires 1 event" \
  || ko "escalation event wrong: ${out}"

# ---- dry-run does not update state and does not write to sink ----
# Reset state + sink, then run dry-run and ensure nothing happens.
rm -f /tmp/r228-state.json /tmp/r228-events.jsonl
out="$(python3 "${SCRIPT}" dispatch --from-file /tmp/r228-scan.json --dry-run --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['dry_run'] is True, d
assert d['events_emitted']>0, d
for x in d['deliveries']:
    assert 'would' in x['detail'].lower(), x
" \
  && ok "--dry-run reports events without delivering" \
  || ko "dry-run report wrong"
[ ! -f /tmp/r228-events.jsonl ] && ok "dry-run did not write file sink" \
  || ko "dry-run wrote sink: $(cat /tmp/r228-events.jsonl)"
[ ! -f /tmp/r228-state.json ] && ok "dry-run did not write state" \
  || ko "dry-run wrote state"

# ---- test command: synthetic event lands in file sink ----
rm -f /tmp/r228-events.jsonl
python3 "${SCRIPT}" test --channel file > /tmp/r228-test.out 2>&1
rc=$?
[ "${rc}" -eq 0 ] && ok "test --channel file rc=0" || ko "test channel rc=${rc}: $(cat /tmp/r228-test.out)"
[ "$(wc -l < /tmp/r228-events.jsonl 2>/dev/null || echo 0)" -eq 1 ] \
  && ok "test --channel file wrote 1 synthetic event" \
  || ko "test --channel file did not write"
grep -q '"probe": "synthetic"' /tmp/r228-events.jsonl \
  && ok "synthetic event carries probe=synthetic marker" \
  || ko "synthetic event missing marker"

# ---- test with bad channel → rc=2 ----
set +e
python3 "${SCRIPT}" test --channel bogus > /tmp/r228-bad.out 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "test --channel bogus → rc=2" \
  || ko "expected rc=2 on bogus channel, got ${rc}"

# ---- state verb dumps dedup state ----
out="$(python3 "${SCRIPT}" state --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R228', d
assert d['state_path']=='/tmp/r228-state.json', d
" \
  && ok "state --json shape ok" \
  || ko "state JSON wrong"

# ---- webhook channel: env-var unresolved → ok=False, rc=1 ----
cat > /tmp/r228-cfg-wh.toml <<'TOML'
[channels.webhook]
enabled = true
url = "env:R228_NEVER_DEFINED_URL"
TOML
unset R228_NEVER_DEFINED_URL || true
rm -f /tmp/r228-state.json /tmp/r228-events.jsonl
set +e
SOVEREIGN_OS_NOTIFY_CONFIG=/tmp/r228-cfg-wh.toml \
  python3 "${SCRIPT}" dispatch --from-file /tmp/r228-scan.json --json > /tmp/r228-wh.out 2>&1
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "webhook with unresolved env-var → rc=1" \
  || ko "expected rc=1 on unresolved webhook url, got ${rc}: $(cat /tmp/r228-wh.out)"
python3 -c "
import json
d=json.load(open('/tmp/r228-wh.out'))
fails=[x for x in d['deliveries'] if x['channel']=='webhook' and not x['ok']]
assert fails, d
assert 'env-var' in fails[0]['detail'] or 'unresolved' in fails[0]['detail'], fails
" \
  && ok "webhook failure message cites env-var" \
  || ko "webhook failure msg wrong"

# ---- osctl bridge ----
set +e
"${OSCTL}" notify list-channels --json > /tmp/r228-osctl.out 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl notify list-channels rc=0" \
  || ko "osctl bridge rc=${rc}: $(cat /tmp/r228-osctl.out)"
python3 -c "
import json
d=json.load(open('/tmp/r228-osctl.out'))
assert d['round']=='R228', d
" \
  && ok "osctl bridge surfaces R228 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" notify nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown notify subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

rm -f /tmp/r228-*

echo
total=$((pass + fail))
echo "test_notify_dispatch: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
