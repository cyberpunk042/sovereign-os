#!/usr/bin/env bash
# local model — profiles.provisioning.model, reconciled against loader capability
# gate: IAC_ENABLE_MODEL
#
# THE PROFILE ASKS FOR SOMETHING THIS RUNTIME CANNOT LOAD.
#
#   provisioning.model.repo = nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16
#   provisioning.model.local_dir = /mnt/vault/models/...   (min_free_gb: 80)
#
# Three independent blockers, verified 2026-07-30:
#
#   1. /mnt/vault does not exist and cannot without reclaiming the Debian 13
#      disk or adding hardware — both NVMe devices are fully partitioned.
#   2. A 30B BF16 checkpoint ships SHARDED (model-0000N-of-0000M.safetensors +
#      model.safetensors.index.json). Nothing in crates/ handles a shard index:
#          grep -rl 'safetensors.index|model-.*-of-' crates/   -> no matches
#      and scripts/intelligence/fetch-model.sh fetches exactly three files
#      (config.json, tokenizer.json, model.safetensors) — single-file only.
#   3. The gateway generates on CPU. No crate in sovereign-gatewayd's dependency
#      tree links CUDA (only sovereign-nvfp4-runtime does, and it is not a dep).
#      A 30B BF16 forward pass on CPU is not interactive, whatever the RAM.
#
# So the profile's model is ASPIRATIONAL — it describes where this is going, not
# what today's gateway can serve. Converge does not pretend otherwise and does
# not silently substitute: it reports the gap, and serves the model the runtime
# actually supports, declared as a machine truth in converge.conf.
#
# When the loader grows shard + GPU support, drop IAC_MODEL_REPO from
# converge.conf and this module follows the profile again.
#
# shellcheck shell=bash

_prof_repo="$(profile_get provisioning.model.repo)"
_prof_dir="$(profile_get provisioning.model.local_dir)"
_minfree="$(profile_get provisioning.model.min_free_gb 0)"

# Machine truth wins where the profile outruns the runtime (same pattern as the
# GPU power floor). Empty override ⇒ follow the profile verbatim.
_repo="${IAC_MODEL_REPO:-${_prof_repo}}"
_dir="${IAC_MODEL_DIR:-${_prof_dir}}"

if [ -z "${_repo}" ] || [ -z "${_dir}" ]; then
  skip "no model declared (profile provisioning.model + no converge.conf override)"
  return 0 2>/dev/null || exit 0
fi

if [ "${_repo}" != "${_prof_repo}" ]; then
  iac_info "profile asks for : ${_prof_repo}"
  iac_info "serving instead  : ${_repo}"
  iac_info "reason: the gateway loads single-file safetensors on CPU; see this module's header"
fi
iac_info "dir=${_dir}"

# ---- the gateway must ADVERTISE the id its clients ask for ----
# profiles.provisioning.open_computer.model_id and .openclaw.model_id both say
# "local-oracle", but the gateway defaults its primary id to "primary"
# (SOVEREIGN_GATEWAY_MODEL_ID, lib.rs:1969). The serving path treats any name
# that is not primary_id as a SECONDARY model and, finding none registered,
# returns "no local model loaded" — indistinguishable from having no model at
# all. Both clients would have failed that way against a perfectly loaded model.
#
# Align the daemon with the profile via a drop-in (never by editing the shipped
# unit), so the id the clients request is the id the gateway answers to.
_client_model_id="$(profile_get provisioning.open_computer.model_id)"
[ -n "${_client_model_id}" ] || _client_model_id="$(profile_get provisioning.openclaw.model_id)"

if [ -n "${_client_model_id}" ]; then
  _cur_id="$(systemctl show sovereign-gatewayd -p Environment --value 2>/dev/null \
             | tr ' ' '\n' | sed -n 's/^SOVEREIGN_GATEWAY_MODEL_ID=//p')"
  : "${_cur_id:=primary}"
  if [ "${_cur_id}" = "${_client_model_id}" ]; then
    ok "gateway advertises '${_client_model_id}' (matches profile clients)"
  else
    iac_info "gateway advertises '${_cur_id}' but clients ask for '${_client_model_id}'"
    ensure_dropin sovereign-gatewayd.service 20-model-id <<EOF
# Managed by scripts/iac/modules/70-local-model.sh — do not edit by hand.
# provisioning.open_computer.model_id / .openclaw.model_id = ${_client_model_id}
# The gateway's default primary id is "primary"; a request for any other name is
# treated as a secondary model and fails with "no local model loaded" even when
# the primary is loaded and healthy. Make the daemon answer to what its own
# clients are configured to ask for.
[Service]
Environment=SOVEREIGN_GATEWAY_MODEL_ID=${_client_model_id}
EOF
    if [ "${IAC_DRY_RUN}" != 1 ]; then
      systemctl daemon-reload 2>/dev/null || true
      if systemctl is-active --quiet sovereign-gatewayd 2>/dev/null; then
        if run "restart-gateway-id" systemctl restart sovereign-gatewayd; then
          changed "sovereign-gatewayd restarted to advertise '${_client_model_id}'"
        else
          fail "could not restart sovereign-gatewayd after model-id change"
        fi
      fi
    fi
  fi
fi

# ---- point the gateway at the directory this module manages ----
# The shipped unit hardcodes SOVEREIGN_GATEWAY_MODEL=/var/lib/sovereign-os/
# models/smollm-135m. Earlier this module only WARNED when the managed dir
# differed, which meant a model could be fetched correctly and never served —
# the download succeeds, converge reports ok, and the gateway keeps loading
# something else (or nothing). Assert it instead, via a drop-in so the shipped
# unit is untouched and an apt upgrade cannot silently repoint it.
_gw_model="$(systemctl show sovereign-gatewayd -p Environment --value 2>/dev/null \
             | tr ' ' '\n' | sed -n 's/^SOVEREIGN_GATEWAY_MODEL=//p')"
if [ "${_gw_model}" = "${_dir}" ]; then
  ok "gateway model path = ${_dir}"
else
  iac_info "gateway looks at '${_gw_model:-unset}', managed dir is '${_dir}'"
  ensure_dropin sovereign-gatewayd.service 30-model-path <<EOF
# Managed by scripts/iac/modules/70-local-model.sh — do not edit by hand.
# The shipped unit points at a directory this module does not manage. A model
# fetched anywhere else is downloaded and never served.
[Service]
Environment=SOVEREIGN_GATEWAY_MODEL=${_dir}
EOF
  if [ "${IAC_DRY_RUN}" != 1 ]; then
    systemctl daemon-reload 2>/dev/null || true
    _gw_needs_restart=1
  fi
fi

# ---- storage ----
_parent="$(dirname "${_dir}")"
if [ ! -d "${_parent}" ]; then
  _mnt="$(printf '%s' "${_dir}" | cut -d/ -f1-3)"
  if printf '%s' "${_dir}" | grep -q '^/mnt/' && ! mountpoint -q "${_mnt}" 2>/dev/null; then
    fail "${_mnt} is not a mounted filesystem — create the vault storage first, or set IAC_MODEL_DIR"
    return 0 2>/dev/null || exit 0
  fi
  ensure_dir "${_parent}" 0755 root:root
fi

if [ "${_minfree}" -gt 0 ] 2>/dev/null; then
  _avail_gb="$(df -BG --output=avail "${_parent}" 2>/dev/null | tail -1 | tr -dc '0-9')"
  if [ -n "${_avail_gb}" ] && [ "${_avail_gb}" -lt "${_minfree}" ] 2>/dev/null; then
    fail "only ${_avail_gb}GB free at ${_parent}, profile requires min_free_gb=${_minfree}"
    return 0 2>/dev/null || exit 0
  fi
  ok "free space at ${_parent}: ${_avail_gb:-?}GB (profile wants ${_minfree}GB)"
fi

# ---- already fetched? the loader needs all three ----
_complete=1
for f in config.json tokenizer.json model.safetensors; do
  [ -s "${_dir}/${f}" ] || _complete=0
done
if [ "${_complete}" = 1 ]; then
  ok "model present at ${_dir}"

  # ---- the chat template is optional to FETCH but decisive for instruct models ----
  # sovereign-gatewayd reads tokenizer_config.json out of the model dir
  # (lib.rs:1312) for chat_template + eos_token. Without it the prompt falls back
  # to plain role concatenation, an instruction-tuned model never sees the markers
  # it was trained on, never emits its end-of-turn token, and runs past the answer.
  # It is not part of the completeness check — plenty of base models have no
  # template — but a model already on disk from before this was fetched needs it
  # backfilled rather than silently degrading every reply.
  _tmpl_added=0
  if [ ! -s "${_dir}/tokenizer_config.json" ] && [ "${IAC_DRY_RUN}" != 1 ]; then
    if curl -fsSL --retry 3 --max-time 120 \
         "https://huggingface.co/${_repo}/resolve/main/tokenizer_config.json" \
         -o "${_dir}/tokenizer_config.json.part" 2>/dev/null; then
      mv "${_dir}/tokenizer_config.json.part" "${_dir}/tokenizer_config.json"
      if grep -q '"chat_template"' "${_dir}/tokenizer_config.json" 2>/dev/null; then
        changed "backfilled tokenizer_config.json (chat_template present)"
        _tmpl_added=1
      else
        changed "backfilled tokenizer_config.json (no chat_template — base model)"
      fi
    else
      rm -f "${_dir}/tokenizer_config.json.part"
      skip "no tokenizer_config.json published for ${_repo}"
    fi
  elif [ -s "${_dir}/tokenizer_config.json" ]; then
    if grep -q '"chat_template"' "${_dir}/tokenizer_config.json" 2>/dev/null; then
      ok "chat_template present"
    else
      ok "tokenizer_config.json present (no chat_template)"
    fi
  fi

  # ---- does the RUNNING gateway actually serve this model? ----
  # Config being right proves nothing: the daemon reads SOVEREIGN_GATEWAY_MODEL
  # once, at startup. An earlier version checked only that the drop-in existed
  # and the files were on disk, then reported "machine already matches profile"
  # while the process served a completely different model — unit env pointing at
  # a 1.7B, gateway still holding the 135M it loaded 40 minutes earlier.
  #
  # So compare the LIVE geometry against the configured checkpoint. /v1/models
  # reports the architecture the daemon actually built; config.json says what it
  # should be. Two numbers, no inference from configuration state.
  _cfg_l="$(python3 -c "import json;print(json.load(open('${_dir}/config.json'))['num_hidden_layers'])" 2>/dev/null)"
  _cfg_d="$(python3 -c "import json;print(json.load(open('${_dir}/config.json'))['hidden_size'])" 2>/dev/null)"
  _live="$(curl -s --max-time 5 http://127.0.0.1:8787/v1/models 2>/dev/null \
           | python3 -c "import json,sys;a=json.load(sys.stdin).get('architecture',{});print(f\"{a.get('layers')} {a.get('model_dim')}\")" 2>/dev/null)"
  _live_l="${_live%% *}"; _live_d="${_live##* }"

  if [ -z "${_live}" ] || [ "${_live}" = "None None" ]; then
    skip "gateway not serving a model yet — cannot compare geometry"
  elif [ "${_tmpl_added:-0}" = 1 ]; then
    # Geometry is unchanged, so the check below would say "serving this model"
    # and skip the restart — but the daemon read tokenizer_config.json at
    # startup and does not have the template we just backfilled.
    iac_info "chat_template backfilled — gateway must reload to pick it up"
    if run "restart-gateway" systemctl restart sovereign-gatewayd; then
      changed "sovereign-gatewayd restarted to load the chat template"
    else
      fail "could not restart sovereign-gatewayd"
    fi
  elif [ "${_live_l}" = "${_cfg_l}" ] && [ "${_live_d}" = "${_cfg_d}" ]; then
    ok "gateway serving this model (layers=${_cfg_l} dim=${_cfg_d})"
  elif [ "${IAC_DRY_RUN}" = 1 ]; then
    changed "restart gateway: serving layers=${_live_l} dim=${_live_d}, configured layers=${_cfg_l} dim=${_cfg_d}"
  else
    iac_info "gateway serves layers=${_live_l} dim=${_live_d}, configured is layers=${_cfg_l} dim=${_cfg_d}"
    if run "restart-gateway" systemctl restart sovereign-gatewayd; then
      # Verify the restart achieved it, rather than assuming.
      sleep 3
      _live2="$(curl -s --max-time 10 http://127.0.0.1:8787/v1/models 2>/dev/null \
                | python3 -c "import json,sys;a=json.load(sys.stdin).get('architecture',{});print(f\"{a.get('layers')} {a.get('model_dim')}\")" 2>/dev/null)"
      if [ "${_live2}" = "${_cfg_l} ${_cfg_d}" ]; then
        changed "sovereign-gatewayd restarted onto ${_dir} (layers=${_cfg_l} dim=${_cfg_d})"
      else
        fail "restarted but gateway reports '${_live2:-nothing}' — expected layers=${_cfg_l} dim=${_cfg_d}"
      fi
    else
      fail "could not restart sovereign-gatewayd"
    fi
  fi
  return 0 2>/dev/null || exit 0
fi

_fetch=/opt/sovereign-os/scripts/intelligence/fetch-model.sh
[ -x "${_fetch}" ] || _fetch="${IAC_SOURCE_RESOLVED_DIR:-/home/jfortin/sovereign-os}/scripts/intelligence/fetch-model.sh"
if [ ! -x "${_fetch}" ]; then
  fail "fetch script not found"
  return 0 2>/dev/null || exit 0
fi

if [ "${IAC_DRY_RUN}" = 1 ]; then
  changed "fetch ${_repo} → ${_dir}"
  return 0 2>/dev/null || exit 0
fi

# The script reads MODEL_REPO. (An earlier version of this module exported
# SOVEREIGN_MODEL_REPO, which fetch-model.sh ignores — it would have silently
# downloaded the DEFAULT model while reporting the requested one.)
iac_info "fetching — network download"
if MODEL_REPO="${_repo}" "${_fetch}" "${_dir}" >/dev/null 2>&1; then
  _missing=""
  for f in config.json tokenizer.json model.safetensors; do
    [ -s "${_dir}/${f}" ] || _missing="${_missing} ${f}"
  done
  if [ -n "${_missing}" ]; then
    # Sharded repos "succeed" with a 404-free partial set — catch that here
    # rather than handing the gateway an unloadable directory.
    fail "fetch incomplete, missing:${_missing} (is ${_repo} sharded? this loader needs a single model.safetensors)"
  else
    changed "model fetched → ${_dir}"
    # The gateway loads its model at STARTUP ONLY, so a fresh fetch always needs
    # a restart. This used to be guarded on [ "${_gw_model}" = "${_dir}" ] —
    # but _gw_model is captured near the top of the module, BEFORE the
    # 30-model-path drop-in is written, so on the run that repoints the gateway
    # it still held the OLD path, the comparison failed, and no restart
    # happened: the unit env said the new model while the running process
    # served the old one. Reading a value, then changing the thing it described,
    # then testing the stale copy.
    if systemctl is-active --quiet sovereign-gatewayd 2>/dev/null; then
      if run "restart-gateway" systemctl restart sovereign-gatewayd; then
        changed "sovereign-gatewayd restarted to load the model"
      else
        fail "could not restart sovereign-gatewayd"
      fi
    fi
  fi
else
  fail "model fetch failed — MODEL_REPO=${_repo} ${_fetch} ${_dir}"
fi
