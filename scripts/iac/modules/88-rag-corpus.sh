#!/usr/bin/env bash
# stage the RAG corpus and switch retrieval on
# gate: IAC_ENABLE_RAG_CORPUS
#
# WHY
#   The gateway has carried a hybrid retriever (BM25 fused with char-n-gram
#   embeddings by RRF, coverage-reranked) the whole time, plus /v1/corpus/reload
#   to re-index without a restart. None of it has ever run here:
#   SOVEREIGN_GATEWAY_CORPUS is unset, so load_corpus_from_env() returns None on
#   every start and RAG is simply off. A capability the code supports and the
#   machine never had.
#
#   So the Code Console answers from the model's weights alone. Ask it how
#   gatewayd resolves an alias and it will guess, with 244 SDDs describing the
#   answer sitting on the same disk.
#
# WHY COPIES AND NOT SYMLINKS
#   gatewayd runs ProtectHome=true, so it cannot read the checkout under
#   /home at all — a symlink farm pointing there would resolve to nothing and RAG
#   would silently stay empty. The corpus is ~3 MB of markdown; copying it into
#   /var/lib/sovereign-os is cheaper than relaxing the daemon's sandbox.
#
# WHY THE NAMES ARE FLATTENED WITH A PREFIX
#   build_corpus_from() reads ONE directory, non-recursively, and ids each chunk
#   as `{file_name}#{i}`. Two sources are being merged, so a bare basename would
#   let docs/src/INDEX.md and docs/sdd/INDEX.md collide into one id — the second
#   silently shadowing the first in every lookup. The prefix keeps provenance in
#   the id, which also means a cited passage says which tree it came from.
#
# shellcheck shell=bash

_corpus="${IAC_RAG_CORPUS_DIR:-/var/lib/sovereign-os/corpus}"
_src_root="${IAC_SOURCE_RESOLVED_DIR:-${IAC_SOURCE_DIR:-}}"
if [ -z "${_src_root}" ] || [ ! -d "${_src_root}" ]; then
  skip "no source checkout — nothing to build a corpus from"
  return 0 2>/dev/null || exit 0
fi

# "<prefix>:<relative-dir>" — prefix becomes the filename namespace.
_SOURCES="${IAC_RAG_CORPUS_SOURCES:-src:docs/src sdd:docs/sdd}"

ensure_dir "${_corpus}" 0755 root:root

# ─── stage ────────────────────────────────────────────────────────────────────
# Content-compared, not timestamp-compared, so a converge that changes nothing
# reports nothing. Every staged name is recorded so the prune below can tell a
# current document from one that was deleted upstream.
_want_list="$(mktemp)"
_copied=0
_failed=0
for _entry in ${_SOURCES}; do
  _prefix="${_entry%%:*}"
  _rel="${_entry#*:}"
  _dir="${_src_root}/${_rel}"
  if [ ! -d "${_dir}" ]; then
    skip "corpus source ${_rel} is not a directory — skipped"
    continue
  fi
  while IFS= read -r _f; do
    [ -n "${_f}" ] || continue
    # RECURSIVE, with the relative path folded into the name. A maxdepth-1 sweep
    # dropped 28 files — all of docs/src/ops and docs/src/whitelabel, which is
    # manage / run-on-host / build / profiles / cockpit: precisely the
    # operator-facing pages a console gets asked about. The path becomes part of
    # the id (src__ops__manage.md), so nothing collides and a cited passage still
    # says where it came from.
    _relpath="${_f#"${_dir}"/}"
    _name="${_prefix}__${_relpath//\//__}"
    _dst="${_corpus}/${_name}"
    printf '%s\n' "${_name}" >> "${_want_list}"
    if [ -f "${_dst}" ] && cmp -s "${_f}" "${_dst}"; then
      continue
    fi
    if [ "${IAC_DRY_RUN}" = 1 ]; then
      _copied=$((_copied + 1))
      continue
    fi
    if install -m 0644 -o root -g root "${_f}" "${_dst}" 2>/dev/null; then
      _copied=$((_copied + 1))
    else
      _failed=$((_failed + 1))
    fi
  done <<< "$(find "${_dir}" -type f -name '*.md' 2>/dev/null | sort)"
done

if [ "${_failed}" -gt 0 ]; then
  fail "could not stage ${_failed} corpus file(s) into ${_corpus}"
fi
if [ "${_copied}" -gt 0 ]; then
  changed "staged ${_copied} corpus document(s) → ${_corpus}"
else
  ok "corpus current: ${_corpus} ($(find "${_corpus}" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l) documents)"
fi

# ─── prune ────────────────────────────────────────────────────────────────────
# A document deleted upstream must leave the corpus, or retrieval keeps grounding
# answers in text the project has removed — the stale-claim problem again, in the
# one place where a stale claim is quoted back as fact.
_pruned=0
while IFS= read -r _have; do
  [ -n "${_have}" ] || continue
  if ! grep -qxF "${_have}" "${_want_list}" 2>/dev/null; then
    if [ "${IAC_DRY_RUN}" = 1 ]; then
      _pruned=$((_pruned + 1))
    elif rm -f "${_corpus}/${_have}" 2>/dev/null; then
      _pruned=$((_pruned + 1))
    fi
  fi
done <<< "$(find "${_corpus}" -maxdepth 1 -type f -name '*.md' -printf '%f\n' 2>/dev/null | sort)"
rm -f "${_want_list}"
[ "${_pruned}" -gt 0 ] && changed "pruned ${_pruned} corpus document(s) no longer in the sources"

# ─── switch retrieval on ─────────────────────────────────────────────────────
_dropin=/etc/systemd/system/sovereign-gatewayd.service.d/40-rag-corpus.conf
_before="$(cat "${_dropin}" 2>/dev/null | sha256sum)"
ensure_dropin sovereign-gatewayd.service 40-rag-corpus <<EOF
# Managed by scripts/iac — do not edit by hand.
[Service]
Environment=SOVEREIGN_GATEWAY_CORPUS=${_corpus}
EOF
iac_daemon_reload
_after="$(cat "${_dropin}" 2>/dev/null | sha256sum)"

# The corpus is read at START (load_corpus_from_env), so a changed drop-in — or
# changed documents — only reaches the running daemon on a restart or an explicit
# reload. Reload is the cheaper of the two and needs no downtime; the restart is
# only for the case where the daemon has no corpus configured yet.
if [ "${IAC_DRY_RUN}" = 1 ]; then
  :
elif [ "${_before}" != "${_after}" ]; then
  systemctl reset-failed sovereign-gatewayd.service >/dev/null 2>&1 || true
  if run "restart-gatewayd" systemctl restart sovereign-gatewayd.service; then
    changed "restarted sovereign-gatewayd with SOVEREIGN_GATEWAY_CORPUS set"
  else
    fail "corpus configured but sovereign-gatewayd would not restart"
  fi
elif [ "${_copied}" -gt 0 ] || [ "${_pruned}" -gt 0 ]; then
  # Documents moved under a daemon that is already pointed at the corpus.
  _gw="${IAC_GATEWAY_URL:-http://127.0.0.1:8787}"
  if _resp="$(curl -fsS --max-time 30 -X POST "${_gw}/v1/corpus/reload" 2>&1)"; then
    changed "re-indexed the corpus in place (${_resp})"
  else
    fail "corpus changed but /v1/corpus/reload failed: ${_resp}"
  fi
fi

# ─── verify retrieval is actually ON ─────────────────────────────────────────
# A corpus staged on disk and a daemon that never loaded it look identical from
# the filesystem. The manifest reports what the RUNNING daemon indexed, so ask it
# rather than infer from the files just written.
if [ "${IAC_DRY_RUN}" != 1 ]; then
  _gw="${IAC_GATEWAY_URL:-http://127.0.0.1:8787}"
  _docs=""
  for _i in $(seq 1 "${IAC_RAG_WAIT_TRIES:-30}"); do
    _docs="$(curl -fsS --max-time 5 "${_gw}/manifest" 2>/dev/null \
      | python3 -c "
import sys, json
try: print(json.load(sys.stdin).get('rag_corpus_docs', ''))
except Exception: print('')
" 2>/dev/null)"
    [ -n "${_docs}" ] && break
    [ "${_i}" = 1 ] && iac_info "waiting for gatewayd to come back and index the corpus"
    sleep 2
  done
  case "${_docs}" in
    "")  fail "gatewayd is not reporting a manifest — cannot confirm RAG is on" ;;
    0)   fail "gatewayd indexed 0 documents from ${_corpus} — RAG is configured but empty" ;;
    *)   ok "RAG on: gatewayd indexed ${_docs} passage(s) from ${_corpus}" ;;
  esac
fi
