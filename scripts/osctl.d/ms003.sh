# shellcheck shell=bash
# scripts/osctl.d/ms003.sh — sovereign-osctl `ms003` verb module.
# Sourced by the main sovereign-osctl dispatcher; do not run directly.
#
# Operator surface for the MS003 mutation-record signing chain
# (F-2026-034). The signing (producer) half is scripts/lib/ms003.py's
# sign(); this exposes the verifier half — key/anchor provisioning +
# on-demand ledger verification — so an operator can prove the durable
# decision/mutation ledgers on THIS box are signed + untampered.
#
# Verbs:
#   status                     signing/anchor summary (default)
#   gen-key                    mint the operator ed25519 signing key
#   pubkey                     print this node's public trust anchor
#   anchor-add <b64|--from-key> install a trust anchor for verification
#   anchor-list                list installed trust anchors
#   verify [--strict] [root]   sweep ledgers + report per-status counts
#                              (exit 2 on tamper/unknown-signer;
#                               3 with --strict when unsigned present)

_ms003_py() {
  "${PYTHON3:-python3}" "${__REPO_ROOT}/scripts/lib/ms003.py" "$@"
}

cmd_ms003() {
  local sub="${1:-status}"
  shift || true
  case "${sub}" in
    status)      _ms003_py status ;;
    gen-key)     _ms003_py gen-key ;;
    pubkey)      _ms003_py pubkey ;;
    anchor-add)  _ms003_py anchor-add "$@" ;;
    anchor-list) _ms003_py anchor-list ;;
    verify)      _ms003_py verify-sweep "$@" ;;
    help|--help|-h)
      cat <<'EOF'
sovereign-osctl ms003 — MS003 mutation-record signing + verification (F-2026-034)

  ms003 status                       signing state + trust-anchor summary
  ms003 gen-key                      mint the operator ed25519 signing key
  ms003 pubkey                       print this node's public trust anchor
  ms003 anchor-add <pubkey-b64url>   install a trust anchor (for verify)
  ms003 anchor-add --from-key        install THIS node's own key as an anchor
  ms003 anchor-list                  list installed trust anchors
  ms003 verify [--strict] [root]     verify ledger signatures under root
                                     (default /var/lib/sovereign-os)
                                     exit 2 = tamper / unknown signer
                                     exit 3 = --strict + unsigned present

The daily recurrent sweep is scripts/hooks/recurrent/ms003-verify.sh
(sovereign-ms003-verify.timer); this verb is its on-demand equivalent.
EOF
      ;;
    *)
      log_error "unknown ms003 subcommand: ${sub}"
      cmd_ms003 help
      return 2 ;;
  esac
}
