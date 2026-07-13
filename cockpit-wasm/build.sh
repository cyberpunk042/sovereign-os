#!/usr/bin/env bash
# Build the cockpit-wasm bridge artifact (audit F-2026-001 / SDD-969).
#
# Compiles the wasm-bindgen facade over the typed sovereign-cockpit-* crates to
# wasm32 and emits the browser-loadable artifact the panel imports:
#   webapp/_shared/cockpit-wasm/{cockpit_wasm.js, cockpit_wasm_bg.wasm}
#
# Reproduces exactly what is committed. Requires: rustup wasm32-unknown-unknown
# target + wasm-bindgen-cli 0.2.100 (matching cockpit-wasm/Cargo.toml's pin).
#   rustup target add wasm32-unknown-unknown
#   cargo install wasm-bindgen-cli --version 0.2.100
#
# `--smoke` also builds nodejs glue in a temp dir and EXECUTES the exports to
# prove the browser bridge returns the crate's real answers (no browser needed).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "${HERE}/.." && pwd)"
OUT="${REPO}/webapp/_shared/cockpit-wasm"
WASM="${HERE}/target/wasm32-unknown-unknown/release/cockpit_wasm.wasm"

echo "==> cargo build --release --target wasm32-unknown-unknown"
( cd "${HERE}" && cargo build --release --target wasm32-unknown-unknown )

echo "==> wasm-bindgen --target web -> ${OUT#"${REPO}/"}"
rm -rf "${OUT}"; mkdir -p "${OUT}"
wasm-bindgen --target web --out-dir "${OUT}" "${WASM}"
# Runtime files only — drop the TypeScript .d.ts dev aids.
rm -f "${OUT}"/*.d.ts
echo "    artifact: $(du -h "${OUT}/cockpit_wasm_bg.wasm" | cut -f1) wasm + $(du -h "${OUT}/cockpit_wasm.js" | cut -f1) glue"

if [ "${1:-}" = "--smoke" ]; then
  echo "==> smoke: build nodejs glue + EXECUTE the exports"
  SM="$(mktemp -d)"; trap 'rm -rf "${SM}"' EXIT
  wasm-bindgen --target nodejs --out-dir "${SM}" "${WASM}"
  cat > "${SM}/smoke.cjs" <<'JS'
const w = require('./cockpit_wasm.js');
const cases = [['plan','cool',0,'calm'],['execute','cool',0,'notice'],['plan','warm',0,'notice'],
  ['plan','throttle',0,'warn'],['plan','cool',1,'warn'],['plan','cool',6,'critical'],['plan','shutdown',0,'critical']];
let ok = 0;
for (const [m,t,a,exp] of cases) { if (w.banner_severity(m,t,a) === exp) ok++; else console.error('FAIL',m,t,a); }
const st = w.banner_state('execute','fast','warm',2,'2026-05-19T03:00:00Z');
if (JSON.parse(w.banner_validate(st)).ok !== true) { console.error('validate(good) FAIL'); process.exit(1); }
if (JSON.parse(w.banner_validate(st.replace('"severity":"warn"','"severity":"calm"'))).ok !== false) { console.error('tamper FAIL'); process.exit(1); }
console.log(`smoke: ${ok}/${cases.length} severity cases + validate + tamper-detect OK`);
process.exit(ok === cases.length ? 0 : 1);
JS
  node "${SM}/smoke.cjs"
fi
echo "==> done"
