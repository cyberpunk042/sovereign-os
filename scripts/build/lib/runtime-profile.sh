#!/usr/bin/env bash
# scripts/build/lib/runtime-profile.sh — runtime-profile lookup helpers.
#
# R151 closure: start scripts (start-pulse · start-logic-engine ·
# start-oracle-core) source this lib to honor the active runtime
# profile's per-tier allocation. Per master spec § 18 the runtime
# profile defines core_mask, vram_limit, engine, model, and the
# verbatim runtime_invocation. Until R150 these were hard-coded in
# the start scripts; R151 makes them honor the operator's pick.

# Source guard
if [ -n "${__SOVEREIGN_OS_RUNTIME_PROFILE_LOADED:-}" ]; then return 0; fi
__SOVEREIGN_OS_RUNTIME_PROFILE_LOADED=1

# Find the active runtime profile YAML path (or empty if none active).
# Resolution: /etc/sovereign-os/active-runtime-profile → file content
# is the id; we then resolve to profiles/runtime/<id>.yaml.
runtime_profile_active_file() {
  local active_id="${SOVEREIGN_OS_RUNTIME_PROFILE:-}"
  if [ -z "${active_id}" ]; then
    for cand in "/etc/sovereign-os/active-runtime-profile" \
                "${HOME}/.sovereign-os/active-runtime-profile"; do
      if [ -r "${cand}" ]; then
        active_id="$(cat "${cand}")"
        break
      fi
    done
  fi
  [ -z "${active_id}" ] && return 1

  # Resolve the repo root via the script's own location
  local lib_dir; lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local repo_root; repo_root="$(cd "${lib_dir}/../../.." && pwd)"
  local yaml="${repo_root}/profiles/runtime/${active_id}.yaml"
  if [ ! -f "${yaml}" ]; then
    return 1
  fi
  echo "${yaml}"
}

# Get a field from a tier's allocation in the active runtime profile.
# Usage: runtime_profile_get_tier_field <tier> <field>
# Returns: the field value on stdout, or empty if no active profile
#          or no matching tier.
runtime_profile_get_tier_field() {
  local tier="$1" field="$2"
  local yaml; yaml="$(runtime_profile_active_file)" || return 0

  YAML_FILE="${yaml}" TIER="${tier}" FIELD="${field}" python3 - <<'PY'
import os, yaml
from pathlib import Path


def _resolve_intent(alloc):
    """SDD-043 Phase 2/3: an allocation may bind its model by tier_intent
    instead of a literal `model`. Resolve it at launch via the VRAM-aware
    selector so intent-driven (generated) profiles actually start."""
    intent = alloc.get("tier_intent")
    if not intent:
        return None
    repo_root = Path(os.environ["YAML_FILE"]).resolve().parents[2]
    sel_path = repo_root / "scripts" / "models" / "select-by-intent.py"
    if not sel_path.is_file():
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location("select_by_intent", sel_path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    chosen = m.select(m.load_catalog(), intent, tier=alloc.get("tier"))
    return chosen["id"] if chosen else None


try:
    with open(os.environ["YAML_FILE"]) as f:
        data = yaml.safe_load(f) or {}
    rp = data.get("runtime_profile", {})
    for alloc in rp.get("allocations") or []:
        if alloc.get("tier") == os.environ["TIER"]:
            v = alloc.get(os.environ["FIELD"])
            if v is not None:
                print(v)
            elif os.environ["FIELD"] == "model":
                # No literal model → resolve tier_intent (Phase 2/3).
                r = _resolve_intent(alloc)
                if r:
                    print(r)
            break
except Exception:
    pass
PY
}

# Override an env var with the active-runtime-profile value IF the
# env var isn't already set AND the active profile has a value.
# Usage: runtime_profile_override <ENV_VAR> <tier> <field>
runtime_profile_override() {
  local env_var="$1" tier="$2" field="$3"
  # Bail if already set
  if [ -n "${!env_var:-}" ]; then
    return 0
  fi
  local v; v="$(runtime_profile_get_tier_field "${tier}" "${field}")"
  if [ -n "${v}" ]; then
    eval "${env_var}=\"${v}\""
    # Dynamic export by NAME: env_var holds the target variable's name (set
    # via the eval above), so `export "${env_var}"` exporting that name is
    # intentional, not the SC2163 "export $var exports the value" mistake.
    # shellcheck disable=SC2163
    export "${env_var}"
  fi
}

# Log the active runtime profile (or "none active") — for start scripts
# to surface in their log header.
runtime_profile_log_active() {
  local yaml; yaml="$(runtime_profile_active_file)" || {
    if command -v log_info >/dev/null 2>&1; then
      log_info "  runtime profile:  (none active; using start-script defaults)"
    fi
    return 0
  }
  local id; id="$(basename "${yaml}" .yaml)"
  if command -v log_info >/dev/null 2>&1; then
    log_info "  runtime profile:  ${id} (master spec § 18; ${yaml})"
  fi
}
