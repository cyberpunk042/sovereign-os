#!/usr/bin/env bash
# scripts/build/lib/state.sh — build-pipeline state tracking
#
# Per the operator's IaC bar (verbatim, sacrosanct):
# "local tracking of the progress of a build in multi-steps that can
#  only ever re-happen locally"
# "easily tweakable and configurable and customisation and even via env
#  vars when needed, or other pre-existing config or temporary file
#  detected and restarting from there"
#
# This library implements restart-from-state semantics for the build
# pipeline. Source from any step script; do not run standalone.

# Source guard
if [ -n "${__SOVEREIGN_OS_STATE_LIB_LOADED:-}" ]; then
  return 0
fi
__SOVEREIGN_OS_STATE_LIB_LOADED=1

# Environment-overridable state location. Default lives in the
# operator's home so a crash + restart doesn't lose progress when the
# build tree is cleaned.
: "${SOVEREIGN_OS_STATE_DIR:=${HOME}/.sovereign-os/build-state}"
: "${SOVEREIGN_OS_STATE_FILE:=${SOVEREIGN_OS_STATE_DIR}/state.yaml}"
: "${SOVEREIGN_OS_BUILD_ID:=$(date -u +%Y%m%dT%H%M%SZ)}"

state_init() {
  # Idempotent state-store init. Called once at orchestrator start.
  mkdir -p "${SOVEREIGN_OS_STATE_DIR}"

  if [ ! -f "${SOVEREIGN_OS_STATE_FILE}" ]; then
    cat > "${SOVEREIGN_OS_STATE_FILE}" <<EOF
# sovereign-os build state — RESUMABLE
# Each completed step records its name + completion timestamp + a
# hash of its inputs. Orchestrator skips steps already-completed
# with matching input hashes; reruns steps whose inputs changed.
#
# Edit by hand only if you know what you're doing. The orchestrator
# does NOT delete entries; use 'sovereign-os-build reset' to wipe.

build_id: "${SOVEREIGN_OS_BUILD_ID}"
created_at: "$(date -u --iso-8601=seconds)"
steps: {}
EOF
  fi
}

state_step_status() {
  # state_step_status <step-id> → emits one of: pending | running | completed | failed
  local step="$1"
  if ! [ -f "${SOVEREIGN_OS_STATE_FILE}" ]; then
    echo "pending"
    return 0
  fi
  # Naive parse: look for "<step>: { status: <X> }" line. yq-free for
  # zero-dep guarantee; supports the limited shape we write.
  local result
  result="$(awk -v step="${step}" '
    $0 ~ "  " step ":" { in_step = 1; next }
    in_step && /^    status:/ { gsub(/[" ,]/,"",$2); print $2; exit }
    in_step && /^  [a-z]/ { exit }
  ' "${SOVEREIGN_OS_STATE_FILE}")"
  # awk exits 0 on no-match (with empty output); default to "pending"
  echo "${result:-pending}"
}

state_step_start() {
  # state_step_start <step-id> <inputs-hash>
  local step="$1" inputs_hash="${2:-}"
  state_init
  # Append step entry; non-destructive. If the step was completed and
  # inputs_hash changed, the entry is overwritten with a fresh
  # 'running' record.
  local now
  now="$(date -u --iso-8601=seconds)"
  # Remove any prior entry for this step + the next 3 lines (status,
  # started_at, inputs_hash, completed_at) — kept simple.
  sed -i "/^  ${step}:/,/^  [a-z]/{ /^  ${step}:/d ; /^  [a-z]/!d ; }" "${SOVEREIGN_OS_STATE_FILE}" 2>/dev/null || true

  # Append the new running entry, before the closing line or at end.
  cat >> "${SOVEREIGN_OS_STATE_FILE}" <<EOF
  ${step}:
    status: running
    started_at: "${now}"
    inputs_hash: "${inputs_hash}"
EOF
}

state_step_complete() {
  # state_step_complete <step-id>
  local step="$1"
  local now
  now="$(date -u --iso-8601=seconds)"
  # Update the 'status:' line for this step from 'running' to 'completed'
  # AND append a completed_at line.
  python3 -c "
import sys, re, pathlib
p = pathlib.Path('${SOVEREIGN_OS_STATE_FILE}')
txt = p.read_text()
pat = re.compile(r'(  ${step}:\n    status: )running(\n    started_at: \"[^\"]+\"\n    inputs_hash: \"[^\"]*\")(.*?)(\n  [a-z]|\Z)', re.S)
def sub(m):
    return m.group(1) + 'completed' + m.group(2) + '\n    completed_at: \"${now}\"' + m.group(3) + m.group(4)
out = pat.sub(sub, txt, count=1)
p.write_text(out)
"
}

state_step_fail() {
  # state_step_fail <step-id> <error-message>
  local step="$1" error_msg="${2:-unknown}"
  local now
  now="$(date -u --iso-8601=seconds)"
  python3 -c "
import sys, re, pathlib
p = pathlib.Path('${SOVEREIGN_OS_STATE_FILE}')
txt = p.read_text()
pat = re.compile(r'(  ${step}:\n    status: )running(\n    started_at: \"[^\"]+\"\n    inputs_hash: \"[^\"]*\")(.*?)(\n  [a-z]|\Z)', re.S)
def sub(m):
    return m.group(1) + 'failed' + m.group(2) + '\n    failed_at: \"${now}\"\n    error: \"${error_msg}\"' + m.group(3) + m.group(4)
out = pat.sub(sub, txt, count=1)
p.write_text(out)
"
}

state_step_should_run() {
  # state_step_should_run <step-id> <inputs-hash> → returns 0 if should run
  # Skips step if status=completed AND inputs_hash matches.
  local step="$1" current_hash="${2:-}"
  local recorded_status recorded_hash
  recorded_status="$(state_step_status "${step}")"
  if [ "${recorded_status}" != "completed" ]; then
    return 0  # not yet completed → run
  fi
  # Completed; check inputs_hash
  recorded_hash="$(awk -v step="${step}" '
    $0 ~ "  " step ":" { in_step = 1; next }
    in_step && /^    inputs_hash:/ { gsub(/[" ]/,"",$2); print $2; exit }
    in_step && /^  [a-z]/ { exit }
  ' "${SOVEREIGN_OS_STATE_FILE}")"
  if [ "${recorded_hash}" != "${current_hash}" ]; then
    return 0  # inputs changed → rerun
  fi
  return 1  # already done with same inputs → skip
}

state_inputs_hash() {
  # state_inputs_hash <files...> → emits sha256 hex
  # Used by step scripts to compute a content-fingerprint of their
  # inputs (profile yaml, whitelabel yaml, schema file, etc.).
  local files=("$@")
  if command -v sha256sum >/dev/null 2>&1; then
    cat -- "${files[@]}" 2>/dev/null | sha256sum | awk '{print $1}'
  else
    cat -- "${files[@]}" 2>/dev/null | shasum -a 256 | awk '{print $1}'
  fi
}

state_reset() {
  # state_reset — wipe all step records; keep state file structure.
  # Operator-invoked via `sovereign-os-build reset`. Destructive — see
  # orchestrator's confirmation prompt.
  rm -f "${SOVEREIGN_OS_STATE_FILE}"
  state_init
}

state_summary() {
  # state_summary — operator-facing dump of where the build is.
  if ! [ -f "${SOVEREIGN_OS_STATE_FILE}" ]; then
    echo "No build state. Run 'sovereign-os-build run' to begin."
    return 0
  fi
  echo "Build state at ${SOVEREIGN_OS_STATE_FILE}:"
  echo
  cat "${SOVEREIGN_OS_STATE_FILE}"
}
