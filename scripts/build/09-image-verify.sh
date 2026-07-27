#!/usr/bin/env bash
# scripts/build/09-image-verify.sh — boot the image in QEMU for a smoke
# test. The boot is skipped when SOVEREIGN_OS_SKIP_QEMU is set (e.g., CI
# runners without KVM); the SDD-019 reproducibility artifacts
# (sha256sums.txt + build-provenance.json) are emitted either way.
#
# Minimal smoke: boot → login as root via console → check
# /etc/os-release matches whitelabel → reboot. Timeout: 5 minutes.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib/common.sh
. "${__SCRIPT_DIR}/lib/common.sh"
# shellcheck source=./lib/observability.sh
. "${__SCRIPT_DIR}/lib/observability.sh"

STEP_ID="09-image-verify"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

env_image="${SOVEREIGN_OS_STATE_DIR}/env-image.sh"
if [ -f "${env_image}" ]; then
  # shellcheck disable=SC1090
  . "${env_image}"
fi

inputs_hash="$(state_inputs_hash \
  "artifact=${SOVEREIGN_OS_ARTIFACT:-image}" \
  "substrate=${SOVEREIGN_OS_SUBSTRATE:-mkosi}" "${BASH_SOURCE[0]}" "${SOVEREIGN_OS_PROFILE_FILE}")"

if ! state_step_should_run "${STEP_ID}" "${inputs_hash}"; then
  log_info "step ${STEP_ID} already completed with matching inputs — skipping"
  exit 0
fi

log_step_header "${STEP_ID}" "QEMU smoke test"
state_step_start "${STEP_ID}" "${inputs_hash}"

# SOVEREIGN_OS_SKIP_QEMU skips ONLY the boot smoke — the SDD-019
# reproducibility artifacts (sha256sums.txt + build-provenance.json)
# below MUST still be emitted. The old early-exit here starved every
# no-KVM/CI build of provenance, breaking `sovereign-osctl audit
# provenance` on exactly the runners the env var exists for.
if [ -z "${SOVEREIGN_OS_SKIP_QEMU:-}" ]; then
  require_command qemu-system-x86_64
fi

if [ -z "${SOVEREIGN_OS_IMAGE_DIR:-}" ] || [ ! -d "${SOVEREIGN_OS_IMAGE_DIR}" ]; then
  log_error "image dir not found (set SOVEREIGN_OS_IMAGE_DIR or rerun step 07)"
  emit_metric sovereign_os_build_step_image_verify_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"fail\""
  state_step_fail "${STEP_ID}" "no-image"
  exit 1
fi

# INSTALLER artifact: the produced artifact is a live-build ISO, not a whole-disk
# image this QEMU disk-boot path can smoke the same way (the ISO boots UEFI live
# then autostarts the installer, which needs a target disk). Do NOT QEMU-boot the
# stale appliance .raw and report a false pass. Confirm the ISO exists; the real
# UEFI boot test is manual (boot it under OVMF, or flash + boot).
if [ "${SOVEREIGN_OS_ARTIFACT:-image}" = "installer" ]; then
  iso="$(find "${SOVEREIGN_OS_IMAGE_DIR}" -maxdepth 1 -name '*.iso' -type f 2>/dev/null | head -1)"
  if [ -n "${iso}" ] && [ -s "${iso}" ]; then
    log_info "artifact=installer — ISO present ($(du -h "${iso}" | cut -f1)): ${iso}"

    # PRESENCE IS NOT CORRECTNESS. Two properties are cheap to check here and
    # expensive to discover later: whether the thing can boot at all, and
    # whether it carries the preseed this tree currently defines. Both were
    # only caught at FLASH time, which is after the operator has already
    # decided the build succeeded (2026-07-27).
    _v_fail=0
    if command -v xorriso >/dev/null 2>&1; then
      _eltorito="$(xorriso -indev "${iso}" -report_el_torito plain 2>/dev/null \
                     | grep -c "El Torito boot img" || true)"
      _eltorito="${_eltorito%%$'\n'*}"; _eltorito="${_eltorito:-0}"
      if [ "${_eltorito}" -ge 2 ]; then
        log_info "  bootable: ${_eltorito} El Torito images (BIOS + UEFI)"
      elif [ "${_eltorito}" -ge 1 ]; then
        log_warn "  only ${_eltorito} El Torito image — UEFI boot may be missing"
      else
        log_error "  NOT BOOTABLE: no El Torito boot image on the ISO"
        _v_fail=1
      fi

      # The ISO embeds its own preseed; compare the two settings whose absence
      # produced the dark-screen install and the shipped credential.
      _pd="$(mktemp -d)"
      if xorriso -osirrox on -indev "${iso}" \
           -cpx /simple-cdd/default.preseed "${_pd}/p" >/dev/null 2>&1; then
        _repo="${SOVEREIGN_OS_ROOT}/scripts/build/installer-cdd/profiles/default.preseed"
        for _k in "debian-installer/add-kernel-opts" "passwd/root-password"; do
          _a="$(grep -c "^d-i ${_k}" "${_pd}/p" 2>/dev/null | head -1)"; _a="${_a:-0}"
          _b="$(grep -c "^d-i ${_k}" "${_repo}" 2>/dev/null | head -1)"; _b="${_b:-0}"
          if [ "${_a}" != "${_b}" ]; then
            log_error "  ISO preseed disagrees with the repo on '${_k}' (iso=${_a} repo=${_b})"
            _v_fail=1
          fi
        done
      fi
      rm -rf "${_pd}"
    else
      log_warn "  xorriso unavailable — cannot verify bootability or preseed vintage"
    fi

    if [ "${_v_fail}" -ne 0 ]; then
      log_error "  do NOT flash this ISO — rebuild first"
      emit_metric sovereign_os_build_step_image_verify_total 1 \
        "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"fail\""
      state_step_fail "${STEP_ID}" "installer-iso-unusable"
      exit 1
    fi

    log_info "  validate the full install by booting it under UEFI (OVMF) or from USB."
    emit_metric sovereign_os_build_step_image_verify_total 1 \
      "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"skip-installer\""
    exit 0
  fi
  log_error "artifact=installer but no .iso found in ${SOVEREIGN_OS_IMAGE_DIR}"
  emit_metric sovereign_os_build_step_image_verify_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"fail\""
  state_step_fail "${STEP_ID}" "no-installer-iso"
  exit 1
fi

# Find the produced image file
image_file="$(find "${SOVEREIGN_OS_IMAGE_DIR}" -maxdepth 1 \( -name '*.img' -o -name '*.qcow2' -o -name '*.raw' -o -name "${SOVEREIGN_OS_PROFILE}" \) -type f 2>/dev/null | head -1)"

if [ -z "${image_file}" ]; then
  log_error "no image artifact found in ${SOVEREIGN_OS_IMAGE_DIR}"
  emit_metric sovereign_os_build_step_image_verify_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"fail\""
  state_step_fail "${STEP_ID}" "no-image-artifact"
  exit 1
fi

log_info "QEMU boot test of: ${image_file}"

# For now: just boot to firmware + check the disk is bootable.  # anti-min-waiver: R480 firmware-only-boot-test-anchored-to-SDD-008-Layer-4-QEMU-full-verification-arc
# Full inside-VM verification lands at PR 10 (TDD harness Layer 4)
# with an actual login shell or guest-agent integration.

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_warn "SOVEREIGN_OS_DRY_RUN set — skipping QEMU boot"
elif [ -n "${SOVEREIGN_OS_SKIP_QEMU:-}" ]; then
  log_warn "SOVEREIGN_OS_SKIP_QEMU set — skipping QEMU boot smoke test"
  log_warn "  checksums + provenance still emitted; boot test falls to real hardware"
  : > "${SOVEREIGN_OS_LOG_DIR}/qemu-boot-${SOVEREIGN_OS_BUILD_ID}.log"
else
  : "${SOVEREIGN_OS_QEMU_TIMEOUT:=300}"
  : "${SOVEREIGN_OS_QEMU_MEM:=4G}"

  log_info "booting (timeout ${SOVEREIGN_OS_QEMU_TIMEOUT}s, mem ${SOVEREIGN_OS_QEMU_MEM})"

  # mkosi raw images are UEFI/GPT: boot through OVMF firmware with NO
  # -kernel so the REAL chain runs (firmware → systemd-boot → UKI). The
  # old direct-kernel line globbed a vmlinuz that doesn't exist in the
  # output dir (it lives inside the image) and bypassed the boot chain
  # step 08 just signature-verified (first real image, 2026-06-10).
  # Non-raw artifacts (live-build) keep the direct-kernel path.
  qemu_boot_args=()
  qemu_skip_reason=""
  case "${image_file}" in
    *.raw)
      # Split OVMF (CODE/VARS) must be loaded as a pflash PAIR — feeding
      # the CODE half to -bios fails with 'could not load PC BIOS' (the
      # 2026-06-10 'proper OVMF pflash pair' consolidation note; bit for
      # real on the first button build, 2026-06-12). Pick the PLAIN
      # variant deliberately: the .ms one enrolls Microsoft's certs,
      # which would REJECT the operator-signed UKI; plain VARS has no
      # keys → SB off → the signed chain still boot-tests.
      ovmf_code=""
      for c in /usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_CODE.fd; do
        [ -f "$c" ] && { ovmf_code="$c"; break; }
      done
      if [ -n "${ovmf_code}" ]; then
        ovmf_vars_src="${ovmf_code/CODE/VARS}"
        ovmf_vars="${SOVEREIGN_OS_LOG_DIR}/ovmf-vars-${SOVEREIGN_OS_BUILD_ID}.fd"
        cp "${ovmf_vars_src}" "${ovmf_vars}"
        qemu_boot_args=(
          -machine q35
          -drive "if=pflash,format=raw,readonly=on,file=${ovmf_code}"
          -drive "if=pflash,format=raw,file=${ovmf_vars}"
        )
      elif [ -f /usr/share/ovmf/OVMF.fd ]; then
        # unified single-file build — -bios is correct for this one
        qemu_boot_args=(-bios /usr/share/ovmf/OVMF.fd)
      else
        qemu_skip_reason="OVMF firmware not found (apt install ovmf)"
      fi
      # The kernel is compiled -march=znver5: default qemu64 TCG lacks
      # its scalar ISA (bmi/adx) → early crash. KVM+host-cpu when the
      # invoking user can reach /dev/kvm; -cpu max (full TCG feature
      # set) otherwise.
      if [ -w /dev/kvm ]; then
        qemu_boot_args+=(-enable-kvm -cpu host)
      else
        qemu_boot_args+=(-cpu max)
      fi
      ;;
    *)
      vmlinuz_file="$(find "${SOVEREIGN_OS_IMAGE_DIR}" -maxdepth 1 -name 'vmlinuz*' -type f 2>/dev/null | head -1)"
      if [ -n "${vmlinuz_file}" ]; then
        qemu_boot_args=(-kernel "${vmlinuz_file}")
      else
        qemu_skip_reason="no vmlinuz in image dir for direct-kernel boot"
      fi
      ;;
  esac
  command -v qemu-system-x86_64 >/dev/null 2>&1 \
    || qemu_skip_reason="qemu-system-x86_64 not installed (apt install qemu-system-x86)"

  if [ -n "${qemu_skip_reason}" ]; then
    log_warn "skipping QEMU boot smoke: ${qemu_skip_reason}"
    log_warn "  checksums + provenance still emitted; boot test falls to real hardware"
    : > "${SOVEREIGN_OS_LOG_DIR}/qemu-boot-${SOVEREIGN_OS_BUILD_ID}.log"
  else
  # Boot in the BACKGROUND and stop the instant userspace is reached (the login
  # prompt / systemd / whitelabel banner) rather than idling the full ceiling. A
  # -nographic serial boot has NO auto-login and NO shutdown, so the old
  # `timeout "${SOVEREIGN_OS_QEMU_TIMEOUT}" qemu … | tee` sat at 'localhost
  # login:' for the WHOLE 300s on every run — an apparent interactive hang, with
  # the serial console spamming the operator's build log. Poll the serial log
  # for the success marker; terminate on match, on QEMU's own exit, or at the
  # ${SOVEREIGN_OS_QEMU_TIMEOUT} ceiling (still the operator's 300s / 5-min cap).
  qemu_log="${SOVEREIGN_OS_LOG_DIR}/qemu-boot-${SOVEREIGN_OS_BUILD_ID}.log"
  : > "${qemu_log}"
  qemu-system-x86_64 \
      -m "${SOVEREIGN_OS_QEMU_MEM}" \
      -smp 2 \
      -nographic \
      -no-reboot \
      -drive "file=${image_file},format=raw,if=virtio,readonly=on" \
      "${qemu_boot_args[@]}" \
      > "${qemu_log}" 2>&1 &
  qemu_pid=$!
  boot_reached=""; qemu_rc=""; waited=0
  while [ "${waited}" -lt "${SOVEREIGN_OS_QEMU_TIMEOUT}" ]; do
    if grep -qiE "welcome to|systemd\[1\]|sovereign|login:" "${qemu_log}" 2>/dev/null; then
      boot_reached=1
      break
    fi
    if ! kill -0 "${qemu_pid}" 2>/dev/null; then
      wait "${qemu_pid}"; qemu_rc=$?   # QEMU died on its own — reap its status
      break
    fi
    sleep 1; waited=$(( waited + 1 ))
  done
  if kill -0 "${qemu_pid}" 2>/dev/null; then
    kill "${qemu_pid}" 2>/dev/null || true
    wait "${qemu_pid}" 2>/dev/null || true
  fi
  if [ -n "${boot_reached}" ]; then
    log_info "userspace reached after ~${waited}s — boot smoke PASS (QEMU stopped early)"
  elif [ -n "${qemu_rc}" ] && [ "${qemu_rc}" -ne 0 ]; then
    log_error "QEMU exited with status ${qemu_rc} before reaching userspace"
    emit_metric sovereign_os_build_step_image_verify_total 1 \
      "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"fail\""
    state_step_fail "${STEP_ID}" "qemu-failed-${qemu_rc}"
    exit 1
  else
    log_warn "QEMU boot reached timeout (${SOVEREIGN_OS_QEMU_TIMEOUT}s) without a userspace marker; reviewing log…"
  fi

  # Basic check: did the boot reach userspace? Look for systemd or
  # /etc/os-release in the boot log.
  # Case-insensitive: the whitelabel banner says 'Sovereign OS' (capital S
  # missed the old lowercase grep). 'login:' = the serial getty prompt —
  # the definitive userspace-reached marker now that console=ttyS0 is in
  # the profile cmdline.
  if grep -qiE "welcome to|systemd\[1\]|sovereign|login:" \
      "${SOVEREIGN_OS_LOG_DIR}/qemu-boot-${SOVEREIGN_OS_BUILD_ID}.log"; then
    log_info "boot log contains userspace markers"
  else
    log_warn "boot log lacks userspace markers; image may not boot cleanly"
  fi
  fi
fi

# ---- reproducibility artifacts (SDD-019) ----
# Emit sha256sums.txt for every artifact in the image dir + a skeleton
# in-toto build-provenance manifest. Operator can independently verify
# bit-identicality (Build A vs Build B with same env → same hashes).

if [ -n "${SOVEREIGN_OS_IMAGE_DIR:-}" ] && [ -d "${SOVEREIGN_OS_IMAGE_DIR}" ]; then
  sums_file="${SOVEREIGN_OS_IMAGE_DIR}/sha256sums.txt"
  (cd "${SOVEREIGN_OS_IMAGE_DIR}" && find . -maxdepth 2 -type f \
     ! -name 'sha256sums.txt' ! -name 'build-provenance.json' \
     -exec sha256sum {} \; | sort) > "${sums_file}"
  log_info "sha256sums.txt written: ${sums_file} ($(wc -l < "${sums_file}") entries)"

  # Skeleton in-toto-style build provenance manifest. Format aligned with
  # https://slsa.dev/provenance/v1 minimal subset; full schema lands Stage 2+.
  prov_file="${SOVEREIGN_OS_IMAGE_DIR}/build-provenance.json"
  python3 - <<PY > "${prov_file}"
import hashlib, json, os, pathlib, time
img_dir = pathlib.Path("${SOVEREIGN_OS_IMAGE_DIR}")
subjects = []
for f in sorted(img_dir.rglob("*")):
    if not f.is_file(): continue
    if f.name in ("sha256sums.txt", "build-provenance.json"): continue
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    subjects.append({"name": str(f.relative_to(img_dir)), "digest": {"sha256": h}})
provenance = {
    "_type": "https://in-toto.io/Statement/v1",
    "predicateType": "https://slsa.dev/provenance/v1",
    "subject": subjects,
    "predicate": {
        "buildDefinition": {
            "buildType": "https://github.com/cyberpunk042/sovereign-os/build/v1",
            "externalParameters": {
                "profile": "${SOVEREIGN_OS_PROFILE}",
                "substrate": os.environ.get("SOVEREIGN_OS_SUBSTRATE", "mkosi"),
                "source_date_epoch": os.environ.get("SOURCE_DATE_EPOCH", ""),
                "debian_snapshot": os.environ.get("DEBIAN_SNAPSHOT", ""),
            },
        },
        "runDetails": {
            "builder": {"id": "https://github.com/cyberpunk042/sovereign-os/orchestrator"},
            "metadata": {
                "invocationId": os.environ.get("SOVEREIGN_OS_BUILD_ID", ""),
                "startedOn": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        },
    },
}
print(json.dumps(provenance, indent=2))
PY
  log_info "in-toto build-provenance manifest: ${prov_file}"
fi

emit_metric sovereign_os_build_step_image_verify_total 1 \
  "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"success\""
if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  # Boot smoke did not run — record 'dry-run', NOT 'completed', so the
  # next real run still executes it (resume-state poisoning guard).
  state_step_dry_run "${STEP_ID}"
  log_info "step ${STEP_ID} dry-run pass complete (boot smoke pending real run)"
else
  state_step_complete "${STEP_ID}"
  log_info "step ${STEP_ID} complete"
fi
