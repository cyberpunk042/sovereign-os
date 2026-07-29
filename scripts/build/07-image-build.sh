#!/usr/bin/env bash
# scripts/build/07-image-build.sh — invoke the substrate to produce the
# bootable image artifact.
#
# mkosi: 'mkosi build' from the prepared config tree (step 05 + 06).
# live-build: 'lb build' from the prepared config tree (step 05 + 06).
# rpm-ostree, nixos: deferred to Stage 2+ (ALT paths).

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib/common.sh
. "${__SCRIPT_DIR}/lib/common.sh"
# shellcheck source=./lib/observability.sh
. "${__SCRIPT_DIR}/lib/observability.sh"
# shellcheck source=./lib/distro.sh
. "${__SCRIPT_DIR}/lib/distro.sh"

STEP_ID="07-image-build"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

env_substrate="${SOVEREIGN_OS_STATE_DIR}/env-substrate.sh"
require_file "${env_substrate}"
# The handoff `export`s SOVEREIGN_OS_SUBSTRATE, so sourcing it OVERRIDES what
# the orchestrator chose. When a stale file survives from a previous run with a
# different substrate, this step silently builds the WRONG artifact and reports
# success (2026-07-26: step 05 ran installer-cdd, step 07 ran live-build,
# "Skipping binary_iso, already done", stale ISO shipped). Remember what was
# asked for, and let it win — loudly.
_substrate_requested="${SOVEREIGN_OS_SUBSTRATE:-}"
# shellcheck disable=SC1090
. "${env_substrate}"
if [ -n "${_substrate_requested}" ] && [ "${_substrate_requested}" != "${SOVEREIGN_OS_SUBSTRATE}" ]; then
  log_warn "env handoff says substrate=${SOVEREIGN_OS_SUBSTRATE} but this run asked for ${_substrate_requested}"
  log_warn "  the handoff is STALE — honouring the requested substrate (${_substrate_requested})"
  SOVEREIGN_OS_SUBSTRATE="${_substrate_requested}"
fi

env_debs="${SOVEREIGN_OS_STATE_DIR}/env-kernel-debs.sh"
if [ -f "${env_debs}" ]; then
  # shellcheck disable=SC1090
  . "${env_debs}"
fi

# Signature of the repo working tree baked into the image (mkosi.extra →
# /opt/sovereign-os). Step 05 re-stages it; step 07 must ALSO re-run to actually
# rebuild the image, or an edited baked file (hooks/units/scripts) never reaches
# the .raw. Git-based + gitignore-aware (ignores build/ + target/); 'nogit' for a
# non-git tarball build (operator falls back to `orchestrate.sh rewind`).
# safe.directory: build runs as root over the operator-owned repo (see step 05).
_gitr() { git -c safe.directory="${SOVEREIGN_OS_ROOT}" -C "${SOVEREIGN_OS_ROOT}" "$@" 2>/dev/null; }
repo_sig="nogit"
if command -v git >/dev/null 2>&1 && _gitr rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  repo_sig="$( { _gitr rev-parse HEAD; _gitr status --porcelain; _gitr diff HEAD; } \
               | sha256sum | cut -d' ' -f1)"
fi
# artifact + substrate ARE inputs. Without them, switching from the appliance to
# the installer did not invalidate this step: it reported "already completed with
# matching inputs", skipped, and the pipeline exited 0 having built NOTHING — the
# operator flashed a 5-hour-old ISO twice believing it was fresh (2026-07-26).
# Step 05 already folds in the artifact, which is why 05 re-ran while 07 did not.
inputs_hash="$(state_inputs_hash "${BASH_SOURCE[0]}" "${SOVEREIGN_OS_PROFILE_FILE}" \
  "artifact=${SOVEREIGN_OS_ARTIFACT:-image}" \
  "substrate=${SOVEREIGN_OS_SUBSTRATE:-mkosi}" \
  "distro=${SOVEREIGN_OS_DISTRO:-debian}" \
  "suite=$(distro_suite)" \
  "repo_sig=${repo_sig}")"

if ! state_step_should_run "${STEP_ID}" "${inputs_hash}"; then
  log_info "step ${STEP_ID} already completed with matching inputs — skipping"
  exit 0
fi

log_step_header "${STEP_ID}" "build image (substrate=${SOVEREIGN_OS_SUBSTRATE})"
state_step_start "${STEP_ID}" "${inputs_hash}"

emit_build_metric() {
  emit_metric sovereign_os_build_step_image_build_total 1 \
    "substrate=\"${SOVEREIGN_OS_SUBSTRATE}\",profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"$1\""
}

# Stage compiled kernel .debs into substrate-specific cache (mkosi:
# mkosi.extra/...; live-build: config/packages.chroot/...)
stage_kernel_debs() {
  local cache_dir="$1"
  if [ -n "${SOVEREIGN_OS_KERNEL_DEBS_DIR:-}" ] && [ -d "${SOVEREIGN_OS_KERNEL_DEBS_DIR}" ]; then
    mkdir -p "${cache_dir}"
    # Idempotent re-stage: drop leftovers from prior runs (a previously
    # staged -dbg deb would otherwise ship 984M into the image).
    rm -f "${cache_dir}"/*.deb
    # -dbg deb excluded: 984M of debug symbols that would otherwise ship
    # INSIDE the final image filesystem via mkosi.extra. Newest revision
    # per package only: the forge accumulates a .deb per rebuild
    # (6.12.0-1.. -7 after the first real build's fix iterations) and
    # dpkg would otherwise unpack every one of them in sequence.
    local deb base name
    declare -A latest=()
    while IFS= read -r deb; do
      [ -e "${deb}" ] || continue
      case "${deb}" in *-dbg_*) continue ;; esac
      base="$(basename "${deb}")"
      name="${base%%_*}"
      latest["${name}"]="${deb}"   # sort -V order → last seen wins
    done < <(printf '%s\n' "${SOVEREIGN_OS_KERNEL_DEBS_DIR}"/*.deb | sort -V)
    if [ "${#latest[@]}" -gt 0 ]; then
      cp "${latest[@]}" "${cache_dir}/"
      log_info "staged ${#latest[@]} kernel .deb(s) (newest revision each): ${!latest[*]}"
    else
      log_warn "no kernel .debs to copy (dry-run mode? substrate-default kernel?)"
    fi
  fi
}

# Stage the selfdef SOURCE into the image (mkosi.extra → /opt/selfdef) so
# the postinst can build+install it — the operator's "ready after flash,
# no manual compile" (SOVEREIGN_OS_BAKE_SELFDEF). Excludes the heavy
# target/ + .git; the emit's postinst runs `make build` in /opt/selfdef.
stage_selfdef_source() {
  local dest="$1"
  local src="${SOVEREIGN_OS_SELFDEF_DIR:-${HOME}/selfdef}"
  [ -n "${SOVEREIGN_OS_BAKE_SELFDEF:-}" ] || return 0
  if [ ! -d "${src}/.git" ] && [ ! -f "${src}/Cargo.toml" ]; then
    log_warn "SOVEREIGN_OS_BAKE_SELFDEF set but no selfdef checkout at ${src} — skipping stage"
    return 0
  fi
  log_info "staging selfdef source → ${dest} (baked build at postinst)"
  mkdir -p "${dest}"
  ( cd "${src}" && tar --exclude=./target --exclude=./.git -cf - . ) \
    | ( cd "${dest}" && tar -xf - )
}

# Stage the COMPILED intelligence layer (crates/ → daemon binaries) into the
# image (mkosi.extra → /usr/local/bin). Built on the BUILD HOST, not in the bake
# container: the bake has NO external network (snapshot mirror only) and apt
# cargo is older than the pinned 1.89, so rustup cannot fetch the toolchain there
# — an in-container build is impossible. The host carries rustup 1.89 and the
# image is the same arch/distro (trixie/x86_64), so the binaries run as-is. This
# is the same "STAGED from the build host" pattern as Claude Code.
# Gated on SOVEREIGN_OS_BAKE_INTELLIGENCE (opt-in, like BAKE_SELFDEF).
stage_intelligence_binaries() {
  local dest="$1"   # mkosi.extra/usr/local/bin
  [ -n "${SOVEREIGN_OS_BAKE_INTELLIGENCE:-}" ] || return 0
  if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
    log_info "dry-run — skipping intelligence-layer host build/stage"
    return 0
  fi
  log_info "building intelligence layer on host → staging daemons to ${dest}"
  mkdir -p "${dest}"
  if SOVEREIGN_OS_RUST_BINDIR="${dest}" "${__SCRIPT_DIR}/build-intelligence.sh"; then
    log_info "staged $(find "${dest}" -maxdepth 1 -type f 2>/dev/null | wc -l) intelligence daemon(s) → image /usr/local/bin"
  else
    log_warn "intelligence host build failed — flashed image falls back to a provision-time build (non-fatal)"
  fi
}

# Stage a small REAL model into the image (mkosi.extra → /var/lib/sovereign-os/
# models/<name>) so sovereign-gatewayd generates out of the box on first boot
# (its unit points SOVEREIGN_GATEWAY_MODEL here). Fetched on the host (network
# available). Gated on SOVEREIGN_OS_BAKE_MODEL (opt-in — adds ~0.5 GB to the
# image). The gateway degrades to decision-only if this is skipped.
stage_intelligence_model() {
  local dest="$1"   # mkosi.extra/var/lib/sovereign-os/models/smollm-135m
  [ -n "${SOVEREIGN_OS_BAKE_MODEL:-}" ] || return 0
  if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
    log_info "dry-run — skipping model fetch/stage"
    return 0
  fi
  local repo="${SOVEREIGN_OS_BAKE_MODEL_REPO:-HuggingFaceTB/SmolLM-135M}"
  log_info "fetching ${repo} on host → staging model to ${dest}"
  mkdir -p "${dest}"
  if MODEL_REPO="${repo}" "${__SCRIPT_DIR}/../intelligence/fetch-model.sh" "${dest}"; then
    log_info "staged model ${repo} → image (gateway generates on first boot)"
  else
    log_warn "model fetch failed — gateway runs decision-only until a model is fetched (non-fatal)"
  fi
}

# Derive the intelligence/model bake toggles from the profile when the build-host
# env does not force them — the same env-OR-profile pattern mkosi-emit uses. So a
# profile that declares provisioning.bake.intelligence:true bakes the compiled brain
# into the image with no manual flag, and the panel/operator can still override:
# '1' forces on, '0' forces off, unset/empty inherits the profile. (The staging
# functions above gate on a NON-EMPTY value, so '0' must normalise to empty.)
_bake_from_profile() {  # $1 = env var name, $2 = provisioning.bake.<key>
  case "${!1:-}" in
    1) export "$1=1"; return 0 ;;
    0) export "$1=";  return 0 ;;
  esac
  if [ "$(profile_field "provisioning.bake.$2")" = "True" ]; then
    export "$1=1"
  else
    export "$1="
  fi
}
_bake_from_profile SOVEREIGN_OS_BAKE_INTELLIGENCE intelligence
_bake_from_profile SOVEREIGN_OS_BAKE_MODEL model

case "${SOVEREIGN_OS_SUBSTRATE}" in
  mkosi)
    stage_kernel_debs "${SOVEREIGN_OS_BUILD_OUT}/mkosi.extra/var/cache/local-debs"
    stage_selfdef_source "${SOVEREIGN_OS_BUILD_OUT}/mkosi.extra/opt/selfdef"
    # The sovereign brain: compiled daemons + (optionally) a real model, staged
    # from the host so the flashed image ships them ready (the bake can't build
    # the 1.89-pinned crates offline).
    stage_intelligence_binaries "${SOVEREIGN_OS_BUILD_OUT}/mkosi.extra/usr/local/bin"
    stage_intelligence_model "${SOVEREIGN_OS_BUILD_OUT}/mkosi.extra/var/lib/sovereign-os/models/smollm-135m"
    cd "${SOVEREIGN_OS_BUILD_OUT}" || exit 1
    if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
      log_warn "SOVEREIGN_OS_DRY_RUN — skipping 'mkosi build'"
      emit_build_metric skip
      # Record 'dry-run', NOT 'completed' — resume-poisoning guard.
      state_step_dry_run "${STEP_ID}"
      exit 0
    fi
    require_command mkosi
    log_info "running 'mkosi --force build' in ${SOVEREIGN_OS_BUILD_OUT}"
    # --force: without it mkosi sees an existing output and exits 0 doing
    # NOTHING — step 07 then reports success over a stale image (caught
    # on the first real rebuild, 2026-06-10). Rebuild decisions belong to
    # the orchestrator's state machine, not mkosi's output cache.
    if mkosi --force build 2>&1 | tee "${SOVEREIGN_OS_LOG_DIR}/image-build-${SOVEREIGN_OS_BUILD_ID}.log"; then
      emit_build_metric success
    else
      rc=${PIPESTATUS[0]}
      log_error "mkosi build failed (rc=${rc})"
      emit_build_metric fail
      state_step_fail "${STEP_ID}" "mkosi-build-failed-${rc}"
      exit 1
    fi
    ;;

  installer-cdd)
    # THE standard debian-installer ISO (SDD-013 amended path). The operator
    # wants "the normal Debian 13 installer", not a bespoke TUI — the live-build
    # artifact produced a whiptail launcher nobody asked for, and this builder
    # existed but was reachable only by hand (2026-07-26).
    #
    # simple-cdd REFUSES to run as root, and a panel build runs as root via
    # pkexec — which is exactly why this was never wired. Drop to the operator
    # (SUDO_USER, else the repo owner) for this one command.
    if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
      log_warn "SOVEREIGN_OS_DRY_RUN — skipping the debian-installer ISO build"
      emit_build_metric skip
      state_step_dry_run "${STEP_ID}"
      exit 0
    fi
    # SOVEREIGN_OS_IMAGE_DIR is not exported until AFTER this case block, so
    # referencing it here is an "unbound variable" crash under `set -u`.
    # BUILD_OUT is build/<profile>; the artifacts dir is its output/ subdir,
    # exactly as the mkosi and live-build arms compute it below. Using
    # BUILD_OUT itself put the ISO one directory too high, where the flash
    # panel never looks (2026-07-26).
    _out="${SOVEREIGN_OS_BUILD_OUT}/output"
    mkdir -p "${_out}"
    require_command build-simple-cdd "sudo apt install simple-cdd — or run scripts/install/bootstrap-host.sh"
    _cdd="${SOVEREIGN_OS_ROOT}/scripts/build/installer-cdd/build.sh"
    [ -x "${_cdd}" ] || { log_error "missing ${_cdd}"; state_step_fail "${STEP_ID}" "cdd-missing"; exit 1; }
    _asuser="${SUDO_USER:-$(stat -c '%U' "${SOVEREIGN_OS_ROOT}" 2>/dev/null || echo root)}"
    if [ "$(id -u)" -eq 0 ] && [ "${_asuser}" != "root" ]; then
      log_info "running the d-i ISO build as ${_asuser} (simple-cdd refuses root)"
      # The output dir is created by root-run steps, so the dropped-privilege
      # builder cannot write its finished ISO into it. simple-cdd built a
      # perfectly good 1.2G d-i ISO and died on the last line with
      # "cp: cannot create regular file ...: Permission denied" (2026-07-26).
      # We are root here; hand the directory to the user who has to write it.
      chown "${_asuser}" "${_out}" 2>/dev/null || true
      # Owning the DIRECTORY is not enough: cp opens an EXISTING target for
      # writing, so a root-owned mode-664 artifact from a previous root-run
      # build denies the operator write access and the copy fails with
      # "Permission denied" even though the dir is now theirs (2026-07-26).
      find "${_out}" -maxdepth 1 -type f -name '*.iso' \
        -exec chown "${_asuser}" {} + 2>/dev/null || true
      # Pass ONLY what the builder needs. --preserve-environment carried
      # HOME=/root in from pkexec, so gpg — running as ${_asuser} — tried to
      # create /root/.gnupg and build-simple-cdd died at read_configuration()
      # (2026-07-26). runuser must hand over that user's OWN home.
      _uhome="$(getent passwd "${_asuser}" | cut -d: -f6)"
      [ -n "${_uhome}" ] || _uhome="/home/${_asuser}"
      _run_cdd=(runuser -u "${_asuser}" -- env
                "HOME=${_uhome}" "USER=${_asuser}" "LOGNAME=${_asuser}"
                "SOVEREIGN_OS_BUILD_OUT=${_out}"
                "SOVEREIGN_OS_PROFILE=${SOVEREIGN_OS_PROFILE}"
                bash "${_cdd}")
    elif [ "$(id -u)" -eq 0 ]; then
      log_error "simple-cdd refuses to run as root and no non-root operator could be determined."
      log_error "  re-run the build as your normal user, or set SUDO_USER."
      state_step_fail "${STEP_ID}" "cdd-needs-nonroot"; exit 1
    else
      # Pass the artifacts dir EXPLICITLY, exactly as the root branch above
      # does. Without it the builder inherits the orchestrator's
      # SOVEREIGN_OS_BUILD_OUT (build/<profile>) and its own default appends
      # nothing, so a perfectly good 1.4G ISO landed at
      # build/sain-01/sain-01-installer.iso — one directory above where the
      # flash panel and this step's own discovery look. The step then failed
      # with "exited 0 but produced NO .iso", after an hour of building
      # (2026-07-29). The root path was correct; only this branch was not.
      _run_cdd=(env "SOVEREIGN_OS_BUILD_OUT=${_out}" bash "${_cdd}")
    fi
    # Fingerprint the existing ISO FIRST. A build that produces nothing must
    # never report success: the operator's build "finished with exit 0", left
    # the 5-hour-old live-build ISO untouched in output/, and they flashed that
    # same stale file a second time (2026-07-26). Exit status is not evidence of
    # an artifact.
    # Match THIS distro's artifact, not any *.iso. Since Ubuntu became a second
    # target both distros write into the same output/ dir, so a bare *.iso glob
    # matched the OTHER distro's image: a Debian build that produced nothing
    # reported "the .iso ... is UNCHANGED" while naming
    # sain-01-ubuntu-installer.iso (2026-07-29). It refused correctly — the
    # guard did its job — but the message pointed at the wrong file.
    # Derived from the SINGLE naming rule (lib/distro.sh), which always puts
    # the distro in the name. The old form hardcoded sain-01 with a special
    # case bolted on, and could not distinguish the two distros at all.
    # The legacy pre-2026-07-29 Debian name is still matched so a build that
    # predates the rule is not reported missing.
    _iso_glob="$(distro_artifact_basename "${SOVEREIGN_OS_PROFILE}" installer).iso"
    _iso_glob_legacy="${SOVEREIGN_OS_PROFILE}-installer.iso"
    _iso_before=""
    _iso_path="$(find "${_out}" -maxdepth 1 \( -name "${_iso_glob}" -o -name "${_iso_glob_legacy}" \) -type f 2>/dev/null | head -1)"
    [ -n "${_iso_path}" ] && _iso_before="$(stat -c '%Y:%s' "${_iso_path}" 2>/dev/null || true)"

    if "${_run_cdd[@]}" 2>&1 | tee "${SOVEREIGN_OS_LOG_DIR}/installer-cdd-${SOVEREIGN_OS_BUILD_ID}.log"; then
      # PROVE it: a NEW .iso must exist, and it must not be the one we started
      # with. Otherwise the step lies and the operator flashes yesterday's image.
      _iso_now="$(find "${_out}" -maxdepth 1 -name "${_iso_glob}" -type f -newermt '-6 hours' 2>/dev/null | head -1)"
      if [ -z "${_iso_now}" ]; then
        log_error "the d-i builder exited 0 but produced NO .iso in ${_out}"
        log_error "  do NOT flash — anything already in that directory is from an earlier build."
        emit_build_metric fail
        state_step_fail "${STEP_ID}" "installer-cdd-no-artifact"
        exit 1
      fi
      _iso_after="$(stat -c '%Y:%s' "${_iso_now}" 2>/dev/null || true)"
      if [ -n "${_iso_before}" ] && [ "${_iso_after}" = "${_iso_before}" ]; then
        log_error "the .iso in ${_out} is UNCHANGED (${_iso_now})"
        log_error "  the build claimed success without writing a new image — do NOT flash it."
        emit_build_metric fail
        state_step_fail "${STEP_ID}" "installer-cdd-stale-artifact"
        exit 1
      fi
      log_info "d-i ISO produced: ${_iso_now} ($(du -h "${_iso_now}" 2>/dev/null | cut -f1))"
      # The ISO must be able to satisfy its OWN install list. pkgsel/include is
      # fatal in d-i: one package missing from the offline pool and the install
      # aborts AFTER partitioning, formatting and unpacking. A stock Debian
      # installer never hits this because it resolves against a network mirror;
      # ours cannot. Check it here, where failing costs seconds (2026-07-27).
      _vchk="${SOVEREIGN_OS_ROOT}/scripts/build/installer-cdd/verify-iso-has-packages.sh"
      _vpre="${SOVEREIGN_OS_ROOT}/scripts/build/installer-cdd/profiles/default.preseed"
      if [ -x "${_vchk}" ] && [ -r "${_vpre}" ]; then
        if ! "${_vchk}" "${_iso_now}" "${_vpre}"; then
          log_error "the ISO cannot install its own package list — do NOT flash it"
          emit_build_metric fail
          state_step_fail "${STEP_ID}" "installer-cdd-incomplete-pool"
          exit 1
        fi
      else
        log_warn "pool completeness check unavailable (${_vchk}) — skipping"
      fi
      emit_build_metric success
    else
      rc=${PIPESTATUS[0]}
      log_error "debian-installer ISO build failed (rc=${rc})"
      emit_build_metric fail
      state_step_fail "${STEP_ID}" "installer-cdd-failed-${rc}"
      exit 1
    fi
    ;;

  ubuntu-autoinstall)
    # THE standard Ubuntu installer ISO: the official 26.04 LTS image remastered
    # with an autoinstall answer file, driven by Subiquity.
    #
    # This is a SEPARATE arm from installer-cdd rather than a shared one because
    # almost none of that arm applies: xorriso is happy as root (simple-cdd is
    # not, hence all the runuser plumbing above), and the pool-completeness check
    # reads a preseed, which Subiquity does not use. What IS shared is the part
    # that was learned the hard way — proving a NEW artifact exists before
    # reporting success.
    if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
      log_warn "SOVEREIGN_OS_DRY_RUN — skipping the Ubuntu autoinstall ISO build"
      emit_build_metric skip
      state_step_dry_run "${STEP_ID}"
      exit 0
    fi
    _out="${SOVEREIGN_OS_BUILD_OUT}/output"
    mkdir -p "${_out}"
    require_command xorriso "sudo apt install xorriso — or run scripts/install/bootstrap-host.sh"
    _uai="${SOVEREIGN_OS_ROOT}/scripts/build/ubuntu-autoinstall/build.sh"
    [ -x "${_uai}" ] || { log_error "missing ${_uai}"; state_step_fail "${STEP_ID}" "ubuntu-autoinstall-missing"; exit 1; }

    # Fingerprint FIRST — exit status is not evidence of an artifact. An earlier
    # build "finished with exit 0", left a 5-hour-old ISO untouched, and the
    # operator flashed that stale file twice (2026-07-26). Same guard here.
    _iso_before=""
    _iso_path="$(find "${_out}" -maxdepth 1 -name '*-ubuntu-installer.iso' -type f 2>/dev/null | head -1)"
    [ -n "${_iso_path}" ] && _iso_before="$(stat -c '%Y:%s' "${_iso_path}" 2>/dev/null || true)"

    if env "SOVEREIGN_OS_BUILD_OUT=${_out}" \
           "SOVEREIGN_OS_PROFILE=${SOVEREIGN_OS_PROFILE}" \
           "SOVEREIGN_OS_DISTRO=${SOVEREIGN_OS_DISTRO}" \
           "SOVEREIGN_OS_SUITE=$(distro_suite)" \
           bash "${_uai}" 2>&1 \
         | tee "${SOVEREIGN_OS_LOG_DIR}/ubuntu-autoinstall-${SOVEREIGN_OS_BUILD_ID}.log"; then
      _iso_now="$(find "${_out}" -maxdepth 1 -name '*-ubuntu-installer.iso' -type f -newermt '-6 hours' 2>/dev/null | head -1)"
      if [ -z "${_iso_now}" ]; then
        log_error "the Ubuntu builder exited 0 but produced NO *-ubuntu-installer.iso in ${_out}"
        log_error "  do NOT flash — anything already there is from an earlier build."
        emit_build_metric fail
        state_step_fail "${STEP_ID}" "ubuntu-autoinstall-no-artifact"
        exit 1
      fi
      _iso_after="$(stat -c '%Y:%s' "${_iso_now}" 2>/dev/null || true)"
      if [ -n "${_iso_before}" ] && [ "${_iso_after}" = "${_iso_before}" ]; then
        log_error "the .iso in ${_out} is UNCHANGED (${_iso_now})"
        log_error "  the build claimed success without writing a new image — do NOT flash it."
        emit_build_metric fail
        state_step_fail "${STEP_ID}" "ubuntu-autoinstall-stale-artifact"
        exit 1
      fi
      log_info "Ubuntu autoinstall ISO produced: ${_iso_now} ($(du -h "${_iso_now}" 2>/dev/null | cut -f1))"
      emit_build_metric success
    else
      rc=${PIPESTATUS[0]}
      log_error "Ubuntu autoinstall ISO build failed (rc=${rc})"
      emit_build_metric fail
      state_step_fail "${STEP_ID}" "ubuntu-autoinstall-failed-${rc}"
      exit 1
    fi
    ;;

  live-build)
    stage_kernel_debs "${SOVEREIGN_OS_BUILD_OUT}/config/packages.chroot"
    cd "${SOVEREIGN_OS_BUILD_OUT}" || exit 1
    if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
      log_warn "SOVEREIGN_OS_DRY_RUN — skipping 'lb build'"
      emit_build_metric skip
      # Record 'dry-run', NOT 'completed' — resume-poisoning guard.
      state_step_dry_run "${STEP_ID}"
      exit 0
    fi
    require_command lb
    # live-build has TWO stages: `lb config` materializes the config tree (runs
    # config/auto/config), then `lb build` bootstraps + builds. Running only
    # `lb build` fails at the chroot stage ("the following stage is required to
    # be done first: config"). The adapter emits config/auto/config; run it now.
    log_info "running 'lb config' in ${SOVEREIGN_OS_BUILD_OUT}"
    if ! lb config 2>&1 | tee "${SOVEREIGN_OS_LOG_DIR}/image-config-${SOVEREIGN_OS_BUILD_ID}.log"; then
      rc=${PIPESTATUS[0]}
      log_error "lb config failed (rc=${rc})"
      emit_build_metric fail
      state_step_fail "${STEP_ID}" "lb-config-failed-${rc}"
      exit 1
    fi
    log_info "running 'lb build' in ${SOVEREIGN_OS_BUILD_OUT}"
    if lb build 2>&1 | tee "${SOVEREIGN_OS_LOG_DIR}/image-build-${SOVEREIGN_OS_BUILD_ID}.log"; then
      emit_build_metric success
      # Place the ISO where flash discovers it (build/<profile>/output/), named
      # by artifact so the flash panel can tell installer from OS image.
      mkdir -p "${SOVEREIGN_OS_BUILD_OUT}/output"
      # live-build writes its ISO at the top of BUILD_OUT with its own name;
      # output/ may already hold the OTHER distro's artifact, so restrict the
      # search to the build root and never descend into output/.
      _iso="$(find "${SOVEREIGN_OS_BUILD_OUT}" -maxdepth 1 -name '*.iso' -type f 2>/dev/null | head -1 || true)"
      if [ -n "${_iso}" ]; then
        # Distro-qualified: live-build can target EITHER distro, and this used
        # to emit <profile>-installer.iso — byte-identical in name to the
        # Debian d-i ISO, so one silently overwrote the other (2026-07-29).
        _dest="${SOVEREIGN_OS_BUILD_OUT}/output/$(distro_artifact_basename \
          "${SOVEREIGN_OS_PROFILE}" "${SOVEREIGN_OS_ARTIFACT:-image}").iso"
        mv -f "${_iso}" "${_dest}"
        log_info "iso → ${_dest}"
      fi
    else
      rc=${PIPESTATUS[0]}
      log_error "lb build failed (rc=${rc})"
      emit_build_metric fail
      state_step_fail "${STEP_ID}" "lb-build-failed-${rc}"
      exit 1
    fi
    ;;

  rpm-ostree|nixos)
    log_error "substrate '${SOVEREIGN_OS_SUBSTRATE}' image-build not yet implemented (Stage 2+ ALT path)"
    emit_build_metric not-implemented
    state_step_fail "${STEP_ID}" "substrate-image-build-not-implemented"
    exit 1
    ;;

  *)
    log_error "unknown substrate: ${SOVEREIGN_OS_SUBSTRATE}"
    emit_build_metric unknown
    state_step_fail "${STEP_ID}" "unknown-substrate"
    exit 1
    ;;
esac

# Discover output (per substrate)
case "${SOVEREIGN_OS_SUBSTRATE}" in
  mkosi)         output_dir="${SOVEREIGN_OS_BUILD_OUT}/output" ;;
  live-build)    output_dir="${SOVEREIGN_OS_BUILD_OUT}/output" ;;  # ISO moved here above
  installer-cdd) output_dir="${SOVEREIGN_OS_BUILD_OUT}/output" ;;
  ubuntu-autoinstall) output_dir="${SOVEREIGN_OS_BUILD_OUT}/output" ;;
  # A substrate missing from THIS case left output_dir unset and the step
  # died on "output_dir: unbound variable" AFTER building a good 1.2G ISO.
  *)             output_dir="${SOVEREIGN_OS_BUILD_OUT}/output" ;;
esac

if [ -d "${output_dir}" ] && [ -z "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "image artifacts in ${output_dir}:"
  find "${output_dir}" -maxdepth 1 -type f \( -name '*.raw' -o -name '*.img' -o -name '*.iso' -o -name '*.qcow2' \) \
    -exec ls -lh {} \; | while read -r line; do
    log_info "  ${line}"
  done
fi

env_file="${SOVEREIGN_OS_STATE_DIR}/env-image.sh"
cat > "${env_file}" <<EOF
# auto-generated by ${STEP_ID}
export SOVEREIGN_OS_IMAGE_DIR="${output_dir}"
EOF
log_info "env handoff: ${env_file}"

state_step_complete "${STEP_ID}"
log_info "step ${STEP_ID} complete"
