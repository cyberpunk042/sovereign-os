#!/usr/bin/env bash
# scripts/verify/control-word-daemon.sh — live end-to-end verification of the
# M002/M007/M008 gateway routes against the REAL running daemon binary.
#
# Every increment of the control-word / branch-scheduler / bit-cheats work was
# unit-tested as a pure request→response function. This script closes the loop:
# it builds + runs the actual `sovereign-gatewayd --http` binary, curls each
# route over a real TCP socket, and asserts the responses — including the live
# avx-mode hot-swap (write the state file, the next request sees it, no restart).
#
# Requires cargo + curl + python3. Not part of the pytest lint gate (which has
# no cargo); run it manually or from a cargo-capable CI job.
#
# Usage: scripts/verify/control-word-daemon.sh [PORT]
set -euo pipefail

PORT="${1:-8987}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"

STATE="$(mktemp -d)/avx-mode.active"
LOG="$(mktemp)"
fail=0
ok()   { echo "  ✓ $1"; }
bad()  { echo "  ✗ $1"; fail=1; }

echo "building sovereign-gatewayd…"
cargo build -q -p sovereign-gatewayd --bin sovereign-gatewayd
BIN="target/debug/sovereign-gatewayd"

echo "starting daemon on 127.0.0.1:$PORT (state file: $STATE)…"
SOVEREIGN_GATEWAY_ADDR="127.0.0.1:$PORT" SOVEREIGN_OS_AVX_MODE_STATE="$STATE" \
  "$BIN" --http >"$LOG" 2>&1 &
DPID=$!
trap 'kill $DPID 2>/dev/null || true' EXIT

B="http://127.0.0.1:$PORT"
for _ in $(seq 1 50); do curl -s -o /dev/null "$B/health" && break; sleep 0.2; done

jq_get() { python3 -c "import sys,json;print(eval('d'+sys.argv[1],{'d':json.load(sys.stdin)}))" "$1"; }

echo "── health ──"
curl -s "$B/health" | grep -q '"kind":"health"' && ok "/health" || bad "/health"

echo "── M002 control-word round (avx_mode=custom) ──"
RESP=$(curl -s -X POST "$B/v1/control-word/round" -H 'content-type: application/json' \
  -d '{"state":{"state":[1,2,3,4,5,6,7,8],"memory":[1,2,3,4,5,6,7,8],"rule":[1,2,3,4,5,6,7,8],"random":[1,2,3,4,5,6,7,8]},"rounds":3,"avx_mode":"custom"}')
[ "$(echo "$RESP" | jq_get '["engine_active"]')" = "True" ] && ok "engine_active" || bad "engine_active"
[ "$(echo "$RESP" | jq_get '["result"]["state"][0]')" = "8" ] && ok "parity state[0]=8" || bad "parity state[0]"
SPS=$(echo "$RESP" | jq_get '["metrics"]["round_update_steps_per_sec"]')
python3 -c "import sys; sys.exit(0 if float('$SPS')>0 else 1)" && ok "live steps/sec=$SPS" || bad "steps/sec"

echo "── M002 builtin/off returns engine-off envelope ──"
OFF=$(curl -s -X POST "$B/v1/control-word/round" -H 'content-type: application/json' \
  -d '{"state":{"state":[1,2,3,4,5,6,7,8],"memory":[1,2,3,4,5,6,7,8],"rule":[1,2,3,4,5,6,7,8],"random":[1,2,3,4,5,6,7,8]},"rounds":3,"avx_mode":"off"}')
[ "$(echo "$OFF" | jq_get '["engine_active"]')" = "False" ] && ok "off → engine_active false" || bad "off envelope"

echo "── M007 branch-scheduler tick ──"
T=$(curl -s -X POST "$B/v1/branch-scheduler/tick" -H 'content-type: application/json' \
  -d '{"batch":{"id":[0,1,2,3,4,5,6,7],"control":[1,1,1,1,0,0,0,0],"budget":[1,1,1,1,1,1,1,1],"score":[100,100,100,100,100,100,100,100],"grammar":[1,1,1,1,1,1,1,1],"memory":[0,0,0,0,0,0,0,0],"route":[0,0,0,0,0,0,0,0]},"verify_min_score":50}')
[ "$(echo "$T" | jq_get '["result"]["committed"]')" = "15" ] && ok "committed=0b1111" || bad "tick committed"

echo "── M007 tick-v2 (rule-table + recall + predictor + microcode) ──"
T2=$(curl -s -X POST "$B/v1/branch-scheduler/tick-v2" -H 'content-type: application/json' \
  -d '{"batch":{"id":[0,1,2,3,4,5,6,7],"control":[1,1,1,1,1,1,1,1],"budget":[1,1,1,1,1,1,1,1],"score":[100,100,100,100,100,100,100,100],"grammar":[1,1,1,1,1,1,1,1],"memory":[15,0,255,0,0,0,0,0],"route":[0,0,1,1,0,1,0,1]},"rule_table":[[0],[1]],"event_class":[0,0,0,0,0,0,0,0],"memory_bank":[255],"verify_min_score":50}')
[ "$(echo "$T2" | jq_get '["result"]["rule_verified"]')" = "172" ] && ok "rule_verified=0b10101100" || bad "tick-v2 rule"
[ "$(echo "$T2" | jq_get '["result"]["recall"][2]')" = "8" ] && ok "recall[2]=8" || bad "tick-v2 recall"

echo "── M008 token-law + microcode ──"
TL=$(curl -s -X POST "$B/v1/token-law/allowed-mask" -H 'content-type: application/json' \
  -d '{"laws":[[255],[127],[254],[191],[252]],"combine":"and"}')
[ "$(echo "$TL" | jq_get '["allowed_tokens"]')" = "4" ] && ok "token-law allowed=4" || bad "token-law"
MC=$(curl -s -X POST "$B/v1/microcode/decode" -H 'content-type: application/json' \
  -d "{\"control_word\": $((1 | (8 << 48)))}")
[ "$(echo "$MC" | jq_get '["outcome"]["commit"]')" = "True" ] && ok "microcode commit" || bad "microcode"

echo "── M007 tick-v2 stateful (predictor learns across requests) ──"
V2='{"batch":{"id":[0,1,2,3,4,5,6,7],"control":[1,1,1,1,1,1,1,1],"budget":[1,1,1,1,1,1,1,1],"score":[100,100,100,100,100,100,100,100],"grammar":[1,1,1,1,1,1,1,1],"memory":[0,0,0,0,0,0,0,0],"route":[0,0,0,0,0,0,0,0]},"verify_min_score":50,"session_id":"verify-sess"}'
FIRST=$(curl -s -X POST "$B/v1/branch-scheduler/tick-v2" -H 'content-type: application/json' -d "$V2")
[ "$(echo "$FIRST" | jq_get '["result"]["predicted_commit"]')" = "0" ] && ok "fresh predictor predicts 0" || bad "v2 fresh"
for _ in 1 2 3 4; do LASTV2=$(curl -s -X POST "$B/v1/branch-scheduler/tick-v2" -H 'content-type: application/json' -d "$V2"); done
[ "$(echo "$LASTV2" | jq_get '["result"]["predicted_commit"]')" = "255" ] && ok "predictor learned → 0xFF across requests" || bad "v2 learn"

echo "── M085 math tiers (VNNI dot + VPTERNLOG attention-fuse) ──"
D=$(curl -s -X POST "$B/v1/math/dot-i8" -H 'content-type: application/json' -d '{"a":[1,2,3,4],"b":[1,1,1,1]}')
[ "$(echo "$D" | jq_get '["dot"]')" = "10" ] && ok "VNNI dot=10" || bad "dot-i8"
AF=$(curl -s -X POST "$B/v1/math/attention-fuse" -H 'content-type: application/json' -d '{"query":[255],"key":[60],"causal":[15]}')
[ "$(echo "$AF" | jq_get '["allow"][0]')" = "12" ] && ok "attention-fuse allow=0x0C" || bad "attention-fuse"

echo "── live avx-mode HOT-SWAP (write the state file, no restart) ──"
echo custom > "$STATE"
[ "$(curl -s "$B/v1/control-word/config" | jq_get '["avx_mode"]')" = "custom" ] && ok "custom → active" || bad "hot-swap custom"
echo off > "$STATE"
[ "$(curl -s "$B/v1/control-word/config" | jq_get '["engine_active"]')" = "False" ] && ok "off → inactive" || bad "hot-swap off"

echo
if [ "$fail" = "0" ]; then echo "ALL LIVE ROUTES VERIFIED ✓"; else echo "FAILURES ✗"; cat "$LOG"; fi
exit "$fail"
