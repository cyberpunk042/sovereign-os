# shellcheck shell=bash
# scripts/osctl.d/maintenance.sh — sovereign-osctl `maintenance` verb module (F-2026-025).
# Sourced by the main sovereign-osctl dispatcher; do not run directly.
#
# maintenance-window controls (list/enable/disable).
# Extracted verbatim from the sovereign-osctl monolith — behavior is
# byte-identical (same shell, same globals: __REPO_ROOT / PYTHON3 /
# log_* / common.sh helpers are all resident before dispatch sources this).

cmd_maintenance() {
  local sub="${1:-list}"
  shift || true
  case "${sub}" in
    list)
      cat <<EOF
Maintenance subverbs (each runs the matching recurrent hook on demand):

  list                   This list.
  scrub                  Trigger ZFS scrub of the tank pool now.
  arc-status             Show ZFS ARC stats (size + c + c_min + c_max).
  log-rotate             Manually rotate ~/.sovereign-os/log/*.jsonl now.
  snapshot               Manually take a tank/context ZFS snapshot now.
  security-check         Manually scan for pending security updates now.
  models-sync            Manually verify the resident model catalog now.
  perimeter-check        Manually verify Tetragon perimeter policy now.
  alerts-check           Derive alerts + emit meta-counters now (hourly timer).

All of these run via the matching systemd timer (daily/weekly cadence);
this surface gives operators on-demand control when they need it.

Most subverbs require root; honor SOVEREIGN_OS_DRY_RUN=1.
EOF
      ;;
    scrub)
      "${__REPO_ROOT}/scripts/hooks/recurrent/zfs-scrub.sh"
      ;;
    arc-status)
      if [ -r /proc/spl/kstat/zfs/arcstats ]; then
        grep -E "^(size|c$|c_min|c_max)" /proc/spl/kstat/zfs/arcstats
      else
        echo "ARC stats not available (ZFS not loaded)"
      fi
      ;;
    log-rotate)
      "${__REPO_ROOT}/scripts/hooks/recurrent/log-rotate.sh"
      ;;
    snapshot)
      "${__REPO_ROOT}/scripts/hooks/recurrent/backup-snapshot.sh"
      ;;
    security-check)
      "${__REPO_ROOT}/scripts/hooks/recurrent/security-update-check.sh"
      ;;
    models-sync)
      "${__REPO_ROOT}/scripts/hooks/recurrent/model-catalog-sync.sh"
      ;;
    perimeter-check)
      "${__REPO_ROOT}/scripts/hooks/recurrent/tetragon-policy-verify.sh"
      ;;
    alerts-check)
      "${__REPO_ROOT}/scripts/hooks/recurrent/alerts-check.sh"
      ;;
    *)
      log_error "unknown maintenance subcommand: ${sub}"
      log_error "  available: list / scrub / arc-status / log-rotate / snapshot / security-check / models-sync / perimeter-check / alerts-check"
      exit 2
      ;;
  esac
}
