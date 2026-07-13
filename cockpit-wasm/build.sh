#!/usr/bin/env bash
# Build the cockpit-wasm bridge artifacts (audit F-2026-001 / SDD-974).
#
# Default (no args): builds the COMMITTED demo artifact — banner-only, small —
#   webapp/_shared/cockpit-wasm/{cockpit_wasm.js, cockpit_wasm_bg.wasm}
#   (default features; the demo.html panel loads this).
#
# `--smoke`: default build + EXECUTE the banner exports in node (proof).
#
# `--verify-all`: builds the FULL bridge (`--features bridges`, all ~398 cockpit
#   crates, ~4.4 MB) into a TEMP dir, executes a sample of the generated
#   `<slug>_validate` exports in node, then discards it. Proves the whole family
#   compiles + runs WITHOUT committing a multi-MB binary. This is what CI runs.
#
# Requires: rustup wasm32-unknown-unknown target + wasm-bindgen-cli 0.2.100.
#   rustup target add wasm32-unknown-unknown
#   cargo install wasm-bindgen-cli --version 0.2.100
# Regenerate the bridge set first if crates changed:
#   python3 cockpit-wasm/gen-bridges.py --count all
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "${HERE}/.." && pwd)"
OUT="${REPO}/webapp/_shared/cockpit-wasm"
REL="${HERE}/target/wasm32-unknown-unknown/release/cockpit_wasm.wasm"

# wasm-opt feature flags matching wasm-bindgen output (else it fails validation).
WOPT="-Oz --enable-reference-types --enable-bulk-memory --enable-mutable-globals --enable-nontrapping-float-to-int --enable-sign-ext"

_wasmopt() {  # shrink in place if wasm-opt is present; no-op otherwise
  command -v wasm-opt >/dev/null 2>&1 && wasm-opt ${WOPT} "$1" -o "$1" 2>/dev/null || true
}

build_demo() {
  echo "==> demo: cargo build --release --target wasm32-unknown-unknown (default features)"
  ( cd "${HERE}" && cargo build --release --target wasm32-unknown-unknown )
  rm -f "${OUT}"/cockpit_wasm.js "${OUT}"/cockpit_wasm_bg.wasm
  mkdir -p "${OUT}"
  wasm-bindgen --target web --out-dir "${OUT}" "${REL}"
  rm -f "${OUT}"/cockpit_wasm.d.ts "${OUT}"/cockpit_wasm_bg.wasm.d.ts
  echo "    committed demo: $(du -h "${OUT}/cockpit_wasm_bg.wasm" | cut -f1) (banner-only, crates.html loads the full bridge)"
}

build_full() {
  echo "==> full: cargo build --release --features bridges (all ~418 crates)"
  ( cd "${HERE}" && cargo build --release --target wasm32-unknown-unknown --features bridges )
  wasm-bindgen --target web --out-name cockpit_wasm_full --out-dir "${OUT}" "${REL}"
  rm -f "${OUT}"/cockpit_wasm_full.d.ts "${OUT}"/cockpit_wasm_full_bg.wasm.d.ts
  _wasmopt "${OUT}/cockpit_wasm_full_bg.wasm"
  echo "    committed full bridge: $(du -h "${OUT}/cockpit_wasm_full_bg.wasm" | cut -f1) wasm + $(du -h "${OUT}/cockpit_wasm_full.js" | cut -f1) glue"
}

case "${1:-}" in
  --verify-all)
    echo "==> verify-all: cargo build --release --features bridges (the whole cockpit family)"
    ( cd "${HERE}" && cargo build --release --target wasm32-unknown-unknown --features bridges )
    SM="$(mktemp -d)"; trap 'rm -rf "${SM}"' EXIT
    wasm-bindgen --target nodejs --out-dir "${SM}" "${REL}"
    N=$(grep -oE '\w+_validate' "${SM}/cockpit_wasm.js" | sort -u | wc -l)
    echo "    full bridge: $(du -h "${REL}" | cut -f1) wasm, ${N} *_validate exports"
    node -e "
      const w=require('${SM}/cockpit_wasm.js');
      const sample=['accordion_validate','action_bar_validate','tree_view_validate','item_pin_validate'];
      for (const f of sample) { if (typeof w[f]!=='function') { console.error('MISSING',f); process.exit(1); } }
      if (JSON.parse(w.item_pin_validate(JSON.stringify({schema_version:'1.0.0',max_pins:5,pinned:['a']}))).ok!==true) { console.error('valid FAIL'); process.exit(1); }
      if (JSON.parse(w.item_pin_validate(JSON.stringify({schema_version:'9.9',max_pins:5,pinned:[]}))).ok!==false) { console.error('invalid FAIL'); process.exit(1); }
      if (JSON.parse(w.accordion_validate('garbage')).ok!==false) { console.error('parse-guard FAIL'); process.exit(1); }
      // a bespoke bridge runs the crate's real compute (WCAG contrast black-on-white = 21:1)
      if (JSON.parse(w.color_contrast_verdict('{\"r\":0,\"g\":0,\"b\":0}','{\"r\":255,\"g\":255,\"b\":255}',false)).ratio!==21.0) { console.error('bespoke color-contrast FAIL'); process.exit(1); }
      console.log('    verify-all smoke: '+sample.length+' generated exports callable + item_pin valid/invalid/parse-guard + bespoke color-contrast OK');
    "
    ;;
  --smoke)
    build_demo
    SM="$(mktemp -d)"; trap 'rm -rf "${SM}"' EXIT
    wasm-bindgen --target nodejs --out-dir "${SM}" "${REL}"
    cat > "${SM}/smoke.cjs" <<'JS'
const w = require('./cockpit_wasm.js');
const cases = [['plan','cool',0,'calm'],['execute','cool',0,'notice'],['plan','throttle',0,'warn'],['plan','shutdown',0,'critical']];
let ok=0; for (const [m,t,a,exp] of cases){ if(w.banner_severity(m,t,a)===exp) ok++; else console.error('FAIL',m,t,a); }
const st=w.banner_state('execute','fast','warm',2,'2026-05-19T03:00:00Z');
if(JSON.parse(w.banner_validate(st)).ok!==true){console.error('validate FAIL');process.exit(1);}
if(JSON.parse(w.banner_validate(st.replace('"severity":"warn"','"severity":"calm"'))).ok!==false){console.error('tamper FAIL');process.exit(1);}
console.log(`    demo smoke: ${ok}/${cases.length} banner cases + validate + tamper-detect OK`); process.exit(ok===cases.length?0:1);
JS
    node "${SM}/smoke.cjs"
    ;;
  --demo)
    build_demo
    ;;
  *)
    build_demo
    build_full
    ;;
esac
echo "==> done"
