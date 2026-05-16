# scripts/build/lib/selfdef-tune.sh
#
# Sourceable shell library — closes the cross-repo flag-derivation loop
# with selfdef SD-R19 (`selfdefctl hardware tune --format env-file`).
#
# Use:
#   . scripts/build/lib/selfdef-tune.sh
#   selfdef_tune_load                  # populates SELFDEF_HARDWARE_*
#   echo "${SELFDEF_HARDWARE_MARCH}"   # → znver5 on SAIN-01, native elsewhere
#
# Source-order preference (caller wins if it pre-sets a var):
#   1. selfdefctl on PATH                              → preferred (SD-R19)
#   2. /var/lib/selfdef/hardware-capabilities.json     → fallback (SD-R10)
#   3. local probe via scripts/hardware/sain01-match.py → final fallback
#
# Variables set (only if not already set by caller):
#   SELFDEF_HARDWARE_MARCH
#   SELFDEF_HARDWARE_CFLAGS
#   SELFDEF_HARDWARE_KCFLAGS
#   SELFDEF_HARDWARE_AVX512_VNNI       # "true" or "false"
#   SELFDEF_HARDWARE_AVX512_BF16
#   SELFDEF_HARDWARE_TUNE_SOURCE       # which path produced the vars
#
# R179 — also surfaces the SD-R30 Wasm-AOT block when present:
#   SELFDEF_HARDWARE_WASM_AOT_TARGET_TRIPLE
#   SELFDEF_HARDWARE_WASM_AOT_TARGET_CPU
#   SELFDEF_HARDWARE_WASM_AOT_TARGET_FEATURES
# Empty strings on hosts without the new field (forward-compat).
#
# Idempotent: calling selfdef_tune_load twice is a no-op when the first
# call succeeded (SELFDEF_HARDWARE_MARCH is set).

selfdef_tune__set_default() {
  # If $1 is already exported, leave it alone; else export with $2.
  local var="$1" def="$2"
  if [ -z "${!var:-}" ]; then
    export "${var}=${def}"
  fi
}

selfdef_tune__try_selfdefctl() {
  if ! command -v selfdefctl >/dev/null 2>&1; then
    return 1
  fi
  local out rc
  out="$(selfdefctl hardware tune --format env-file 2>/dev/null)"
  rc=$?
  if [ "${rc}" -ne 0 ] || [ -z "${out}" ]; then
    return 1
  fi
  # Each line is `KEY=value` (no `export` prefix in env-file format).
  while IFS='=' read -r k v; do
    [ -z "${k}" ] && continue
    case "${k}" in
      SELFDEF_HARDWARE_*)
        # Strip leading/trailing whitespace
        v="${v#"${v%%[![:space:]]*}"}"
        export "${k}=${v}"
        ;;
    esac
  done <<< "${out}"
  export SELFDEF_HARDWARE_TUNE_SOURCE="selfdefctl"
  return 0
}

selfdef_tune__try_capabilities_json() {
  : "${SELFDEF_CAPABILITIES_FILE:=/var/lib/selfdef/hardware-capabilities.json}"
  [ -f "${SELFDEF_CAPABILITIES_FILE}" ] || return 1
  if ! command -v python3 >/dev/null 2>&1; then
    return 1
  fi
  # Read march + compile-flag list + AVX-512 bools out of the JSON
  # via python3 (jq is not part of the build-host baseline). The
  # ||| sentinel keeps the parts robust against cflag whitespace.
  local out march cflags vnni bf16 zmm
  # R179: also extract the SD-R30 wasm_aot block when present.
  # Missing block → empty strings; same fail-soft semantics.
  out="$(python3 - "${SELFDEF_CAPABILITIES_FILE}" <<'PYEOF'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    cpu = d.get("cpu", {})
    march = cpu.get("recommended_march", "native")
    flags = " ".join(cpu.get("recommended_compile_flags", []))
    vnni = "true" if cpu.get("avx512vnni") else "false"
    bf16 = "true" if cpu.get("avx512bf16") else "false"
    zmm = " -mprefer-vector-width=512" if cpu.get("avx512f") else ""
    wa = d.get("wasm_aot") or {}
    wa_triple = wa.get("target_triple", "")
    wa_cpu = wa.get("target_cpu", "")
    wa_feats = wa.get("target_features", "")
    print(f"{march}|||{flags}|||{vnni}|||{bf16}|||{zmm}|||{wa_triple}|||{wa_cpu}|||{wa_feats}")
except Exception:
    sys.exit(1)
PYEOF
  )"
  [ -z "${out}" ] && return 1
  local wa_triple wa_cpu wa_feats
  march="${out%%|||*}"; out="${out#*|||}"
  cflags="${out%%|||*}"; out="${out#*|||}"
  vnni="${out%%|||*}"; out="${out#*|||}"
  bf16="${out%%|||*}"; out="${out#*|||}"
  zmm="${out%%|||*}"; out="${out#*|||}"
  wa_triple="${out%%|||*}"; out="${out#*|||}"
  wa_cpu="${out%%|||*}"; out="${out#*|||}"
  wa_feats="${out}"

  export SELFDEF_HARDWARE_MARCH="${march}"
  export SELFDEF_HARDWARE_CFLAGS="-march=${march}${zmm} ${cflags}"
  export SELFDEF_HARDWARE_KCFLAGS="-march=${march}${zmm} ${cflags}"
  export SELFDEF_HARDWARE_AVX512_VNNI="${vnni}"
  export SELFDEF_HARDWARE_AVX512_BF16="${bf16}"
  export SELFDEF_HARDWARE_WASM_AOT_TARGET_TRIPLE="${wa_triple}"
  export SELFDEF_HARDWARE_WASM_AOT_TARGET_CPU="${wa_cpu}"
  export SELFDEF_HARDWARE_WASM_AOT_TARGET_FEATURES="${wa_feats}"
  export SELFDEF_HARDWARE_TUNE_SOURCE="capabilities_json"
  return 0
}

selfdef_tune__fallback_native() {
  export SELFDEF_HARDWARE_MARCH="native"
  export SELFDEF_HARDWARE_CFLAGS="-march=native"
  export SELFDEF_HARDWARE_KCFLAGS="-march=native"
  export SELFDEF_HARDWARE_AVX512_VNNI="false"
  export SELFDEF_HARDWARE_AVX512_BF16="false"
  export SELFDEF_HARDWARE_TUNE_SOURCE="fallback_native"
}

selfdef_tune_load() {
  # If the operator pre-set SELFDEF_HARDWARE_MARCH (typical when the
  # caller wants to pin a specific march), don't run any probe. But
  # we DO populate the rest of the variables with sensible defaults
  # so callers can `${SELFDEF_HARDWARE_CFLAGS}` under `set -u` without
  # tripping over an unbound variable.
  if [ -n "${SELFDEF_HARDWARE_MARCH:-}" ]; then
    selfdef_tune__set_default SELFDEF_HARDWARE_CFLAGS \
      "-march=${SELFDEF_HARDWARE_MARCH}"
    selfdef_tune__set_default SELFDEF_HARDWARE_KCFLAGS \
      "-march=${SELFDEF_HARDWARE_MARCH}"
    selfdef_tune__set_default SELFDEF_HARDWARE_AVX512_VNNI "false"
    selfdef_tune__set_default SELFDEF_HARDWARE_AVX512_BF16 "false"
    selfdef_tune__set_default SELFDEF_HARDWARE_TUNE_SOURCE "operator-set"
    return 0
  fi
  if selfdef_tune__try_selfdefctl; then return 0; fi
  if selfdef_tune__try_capabilities_json; then return 0; fi
  selfdef_tune__fallback_native
}
