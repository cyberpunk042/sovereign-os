#!/usr/bin/env bash
# scripts/claude-code-env/apply.sh
#
# Idempotently install the bulletproof Claude Code user-environment
# (~/.claude/{settings.json, CLAUDE.md, stop-hook-git-check.sh,
#  validate-stop-hook-fix.sh}) from the templates in this directory.
#
# Why this exists: Claude Code's cloud/remote execution harness ships
# opinionated defaults (draft-PR-by-default, env-runner re-staging of
# the stop-hook script, low default caps for blocking_limit / max_turns /
# prompt_too_long stop-reasons) that can break long-running /goal
# sessions and inject behaviors the operator never authorized. This
# script materializes the operator-side overrides as a single
# idempotent install so they can be reapplied in seconds after any
# container rebuild, fresh clone, or settings drift.
#
# Source-of-truth lesson:
#   wiki/lessons/01_drafts/claude-code-env-runner-restages-stop-hook-
#   script-from-baked-template-at-every-session-start.md
#
# Behavior:
#   - For each template, compare against the live target.
#   - If absent: install.
#   - If present + identical: skip (idempotent).
#   - If present + differs: back up live to
#       ${HOME}/.claude/backups/<file>.<UTC-timestamp>.bak
#     then install template.
#   - Set perms: 600 settings.json (Claude Code default), 644 CLAUDE.md,
#     755 *.sh.
#   - Run the validator at the end. Exit 0 on validator pass; the
#     validator's exit code is propagated.
#
# Usage:
#   bash scripts/claude-code-env/apply.sh                    # apply
#   bash scripts/claude-code-env/apply.sh --dry-run          # report-only
#   bash scripts/claude-code-env/apply.sh --no-validate      # skip post-validator
#   bash scripts/claude-code-env/apply.sh --help

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TEMPLATES_DIR="${SCRIPT_DIR}/templates"
readonly TARGET_DIR="${HOME}/.claude"
readonly BACKUP_DIR="${TARGET_DIR}/backups"
readonly TIMESTAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"

# file:perms triples — perms are the canonical mode for each installed file
readonly -a FILES=(
  "settings.json:600"
  "CLAUDE.md:644"
  "stop-hook-git-check.sh:755"
  "validate-stop-hook-fix.sh:755"
  "post-compact-reorient.sh:755"
)

readonly BOOTSTRAP_DIR="${TARGET_DIR}/env-bootstrap"

dry_run=false
run_validator=true
quiet=false
for arg in "$@"; do
  case "${arg}" in
    --dry-run) dry_run=true ;;
    --no-validate) run_validator=false ;;
    --quiet) quiet=true ;;
    -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
    *) echo "unknown arg: ${arg}" >&2; exit 2 ;;
  esac
done

# When --quiet, route all stdout (but not stderr) to /dev/null. Validator
# is still invoked with --quiet so its exit code propagates.
if [ "${quiet}" = "true" ]; then
  exec > /dev/null
fi

mark() { [ "$1" = "ok" ] && printf "  ✓ " || printf "  ✗ "; }

if [ ! -d "${TEMPLATES_DIR}" ]; then
  echo "FATAL: templates dir not found at ${TEMPLATES_DIR}" >&2
  exit 2
fi

mkdir -p "${TARGET_DIR}" "${BACKUP_DIR}"

echo "── apply.sh: install Claude Code user-environment ──"
[ "${dry_run}" = "true" ] && echo "  MODE: dry-run (no changes will be made)"
echo "  templates: ${TEMPLATES_DIR}"
echo "  target:    ${TARGET_DIR}"
echo

installed=0
skipped=0
backed_up=0

for entry in "${FILES[@]}"; do
  fname="${entry%:*}"
  perms="${entry#*:}"
  src="${TEMPLATES_DIR}/${fname}"
  dst="${TARGET_DIR}/${fname}"

  if [ ! -f "${src}" ]; then
    mark fail; echo "${fname}: template missing at ${src}"
    exit 2
  fi

  if [ ! -e "${dst}" ]; then
    if [ "${dry_run}" = "true" ]; then
      mark ok; echo "${fname}: WOULD INSTALL (absent) → ${dst} (mode ${perms})"
    else
      cp "${src}" "${dst}"
      chmod "${perms}" "${dst}"
      mark ok; echo "${fname}: installed (was absent) → ${dst} (mode ${perms})"
      installed=$((installed + 1))
    fi
    continue
  fi

  if cmp -s "${src}" "${dst}"; then
    # Identical content; verify perms.
    current_perms="$(stat -c '%a' "${dst}")"
    if [ "${current_perms}" = "${perms}" ]; then
      mark ok; echo "${fname}: identical + perms ok (skip)"
      skipped=$((skipped + 1))
    else
      if [ "${dry_run}" = "true" ]; then
        mark ok; echo "${fname}: content identical, WOULD CHMOD ${current_perms}→${perms}"
      else
        chmod "${perms}" "${dst}"
        mark ok; echo "${fname}: content identical, chmod ${current_perms}→${perms}"
        installed=$((installed + 1))
      fi
    fi
    continue
  fi

  # Content differs — back up + install.
  bak="${BACKUP_DIR}/${fname}.${TIMESTAMP}.bak"
  if [ "${dry_run}" = "true" ]; then
    mark ok; echo "${fname}: differs, WOULD back up → ${bak} and install template"
  else
    cp "${dst}" "${bak}"
    cp "${src}" "${dst}"
    chmod "${perms}" "${dst}"
    mark ok; echo "${fname}: differed; backed up → ${bak}; installed template (mode ${perms})"
    installed=$((installed + 1))
    backed_up=$((backed_up + 1))
  fi
done

echo
echo "  installed/updated: ${installed}"
echo "  skipped (already current): ${skipped}"
echo "  backed up: ${backed_up}"

# --- Bootstrap mirror: copy apply.sh + templates/ to ~/.claude/env-bootstrap/ ---
# The SessionStart hook (wired in settings.json) invokes the bootstrap copy,
# so it works even on fresh containers where the info-hub repo isn't cloned
# (after the first successful apply.sh run from any location).
echo
echo "── bootstrap mirror → ${BOOTSTRAP_DIR} ──"
if [ "${dry_run}" = "true" ]; then
  mark ok; echo "WOULD mkdir -p ${BOOTSTRAP_DIR}/templates"
  mark ok; echo "WOULD copy apply.sh → ${BOOTSTRAP_DIR}/apply.sh (mode 755)"
  mark ok; echo "WOULD mirror ${TEMPLATES_DIR}/* → ${BOOTSTRAP_DIR}/templates/"
else
  mkdir -p "${BOOTSTRAP_DIR}/templates"
  # apply.sh self-copy
  if ! cmp -s "${SCRIPT_DIR}/apply.sh" "${BOOTSTRAP_DIR}/apply.sh" 2>/dev/null; then
    cp "${SCRIPT_DIR}/apply.sh" "${BOOTSTRAP_DIR}/apply.sh"
    chmod 755 "${BOOTSTRAP_DIR}/apply.sh"
    mark ok; echo "apply.sh installed → ${BOOTSTRAP_DIR}/apply.sh"
  else
    mark ok; echo "apply.sh: identical (skip)"
  fi
  # templates mirror
  for entry in "${FILES[@]}"; do
    tname="${entry%:*}"
    tsrc="${TEMPLATES_DIR}/${tname}"
    tdst="${BOOTSTRAP_DIR}/templates/${tname}"
    if [ -f "${tsrc}" ] && ! cmp -s "${tsrc}" "${tdst}" 2>/dev/null; then
      cp "${tsrc}" "${tdst}"
      # Match perms convention: scripts 755, others 644 (bootstrap templates
      # are READ by apply.sh; live mode is set by the install step above).
      case "${tname}" in
        *.sh) chmod 755 "${tdst}" ;;
        *)    chmod 644 "${tdst}" ;;
      esac
      mark ok; echo "templates/${tname}: mirrored"
    fi
  done
  mark ok; echo "bootstrap mirror complete (${BOOTSTRAP_DIR})"
fi

if [ "${run_validator}" = "false" ]; then
  echo "  (post-install validator skipped per --no-validate)"
  exit 0
fi

if [ "${dry_run}" = "true" ]; then
  echo "  (post-install validator skipped in dry-run)"
  exit 0
fi

echo
echo "── post-install validator ──"
if [ -x "${TARGET_DIR}/validate-stop-hook-fix.sh" ]; then
  if [ "${quiet}" = "true" ]; then
    "${TARGET_DIR}/validate-stop-hook-fix.sh" --quiet
  else
    "${TARGET_DIR}/validate-stop-hook-fix.sh"
  fi
  rc=$?
  exit "${rc}"
else
  echo "  ✗ validator not executable at ${TARGET_DIR}/validate-stop-hook-fix.sh" >&2
  exit 1
fi
