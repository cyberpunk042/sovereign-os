#!/usr/bin/env bash
# scripts/install/bootstrap-host.sh — ONE command to make a fresh Debian
# host ready to BUILD and RUN sovereign-os. No manual apt, ever.
#
#   ⚡ YOU RUN:   scripts/install/bootstrap-host.sh
#               (self-elevates via sudo; --dry-run to preview, changes nothing)
#
# What it does, idempotently (safe to re-run):
#   1. Enables the apt components a fresh Debian host is missing —
#      contrib + non-free + non-free-firmware. THIS is why plain
#      `apt install zfsutils-linux` fails with "no installation
#      candidate": zfsutils-linux is in contrib, nvidia-* in non-free,
#      and a stock install ships main only. Debian-mirror lines only;
#      third-party repos (e.g. Microsoft VS Code) are never touched.
#   2. apt-get update.
#   3. Installs the full BUILD-HOST toolchain in one shot: kernel forge
#      (gcc-14 + build-essential + pahole …), image build (mkosi,
#      dosfstools), secure-boot signing (sbsigntool), the QEMU smoke test
#      (qemu-system-x86 + ovmf), and the ZFS userland (zfsutils-linux)
#      the zfs-tiered profile's preflight demands.
#   4. Runs the operator-deps overlay (apt/pip/npm) — best-effort; a
#      failure there is reported, not fatal to the host toolchain.
#
# After this, `make preflight` passes and `make dry-run` / a real build
# run with zero manual package steps.
#
# Tunable env:
#   BOOTSTRAP_DRY_RUN=1                 same as --dry-run
#   BOOTSTRAP_SKIP_OPERATOR_DEPS=1      skip step 4 (toolchain only)
#   BOOTSTRAP_SOURCES_LIST=<path>       override /etc/apt/sources.list (tests)
#   BOOTSTRAP_SOURCES_DIR=<path>        override /etc/apt/sources.list.d (tests)

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

DRY_RUN="${BOOTSTRAP_DRY_RUN:-}"
SKIP_OPERATOR_DEPS="${BOOTSTRAP_SKIP_OPERATOR_DEPS:-}"
SOURCES_LIST="${BOOTSTRAP_SOURCES_LIST:-/etc/apt/sources.list}"
SOURCES_DIR="${BOOTSTRAP_SOURCES_DIR:-/etc/apt/sources.list.d}"
WANT_COMPONENTS="contrib non-free non-free-firmware"

for arg in "$@"; do
  case "${arg}" in
    --dry-run) DRY_RUN=1 ;;
    --skip-operator-deps) SKIP_OPERATOR_DEPS=1 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown arg: ${arg} (see --help)" >&2; exit 2 ;;
  esac
done

bold='\033[1m'; red='\033[31m'; green='\033[32m'; yellow='\033[33m'; cyan='\033[36m'; reset='\033[0m'
say()  { echo -e "$@"; }
step() { echo -e "\n${bold}$*${reset}"; }
ok()   { echo -e "  ${green}✓${reset} $*"; }
warn() { echo -e "  ${yellow}!${reset} $*"; }
# run: echo the command in dry-run, else execute it. The string form is
# deliberate — callers pass env-prefixed command strings (DEBIAN_FRONTEND=
# … apt-get …), so eval-as-string is the intent, not an array mistake.
# shellcheck disable=SC2294
run()  { if [ -n "${DRY_RUN}" ]; then echo -e "  ${cyan}dry-run\$${reset} $*"; else eval "$*"; fi; }

command -v dpkg >/dev/null 2>&1 || { say "${red}This is not a Debian/Ubuntu host (no dpkg).${reset}"; exit 1; }

# ── self-elevate: the ONE command is this script; it sudo's itself. ──
if [ -z "${DRY_RUN}" ] && [ "$(id -u)" -ne 0 ]; then
  say "${bold}sovereign-os host bootstrap${reset} needs root for apt — elevating via sudo…"
  exec sudo -E "$0" "$@"
fi

say "${bold}sovereign-os · host bootstrap${reset}${DRY_RUN:+  ${yellow}(dry-run — nothing will change)${reset}}"

# ── (1) enable apt components ────────────────────────────────────────
step "[1/4] apt components (contrib · non-free · non-free-firmware)"
# Robust, format-aware, idempotent rewrite in Python: handles both
# one-line (deb …) and deb822 (.sources) styles, and ONLY Debian mirrors.
components_changed=0
enable_out="$(BOOTSTRAP_WANT="${WANT_COMPONENTS}" \
              BOOTSTRAP_LIST="${SOURCES_LIST}" \
              BOOTSTRAP_DIR="${SOURCES_DIR}" \
              BOOTSTRAP_APPLY="$([ -z "${DRY_RUN}" ] && echo 1 || echo 0)" \
  python3 - <<'PY'
import os, re, pathlib

want = os.environ["BOOTSTRAP_WANT"].split()
apply = os.environ["BOOTSTRAP_APPLY"] == "1"
list_path = pathlib.Path(os.environ["BOOTSTRAP_LIST"])
dir_path = pathlib.Path(os.environ["BOOTSTRAP_DIR"])

DEBIAN_HOST = re.compile(r"(deb\.debian\.org|security\.debian\.org|ftp\.[a-z]+\.debian\.org|deb\.debian\.org)")
changed = []

def merge(existing_components):
    out = list(existing_components)
    for c in want:
        if c not in out:
            out.append(c)
    return out

# --- one-line style: /etc/apt/sources.list ---
if list_path.is_file():
    lines = list_path.read_text().splitlines()
    new_lines = []
    dirty = False
    for line in lines:
        s = line.strip()
        # match: [deb|deb-src] [options] URI suite comp1 comp2 ...
        if (s.startswith("deb ") or s.startswith("deb-src ")) and DEBIAN_HOST.search(s):
            # split off any [ options ] block
            m = re.match(r"^(deb(?:-src)?)\s+(\[[^\]]*\]\s+)?(\S+)\s+(\S+)\s+(.*)$", s)
            if m:
                kind, opts, uri, suite, comps = m.groups()
                comps_list = comps.split()
                merged = merge(comps_list)
                if merged != comps_list:
                    dirty = True
                    changed.append(f"{uri} {suite}: {' '.join(comps_list)} -> {' '.join(merged)}")
                    new_lines.append(f"{kind} {opts or ''}{uri} {suite} {' '.join(merged)}")
                    continue
        new_lines.append(line)
    if dirty and apply:
        bak = list_path.with_suffix(list_path.suffix + ".pre-sovereign.bak")
        if not bak.exists():
            bak.write_text("\n".join(lines) + "\n")
        list_path.write_text("\n".join(new_lines) + "\n")

# --- deb822 style: /etc/apt/sources.list.d/*.sources (Debian only) ---
if dir_path.is_dir():
    for src in sorted(dir_path.glob("*.sources")):
        text = src.read_text()
        if not DEBIAN_HOST.search(text):
            continue  # third-party (e.g. Microsoft) — never touch
        out_lines = []
        dirty = False
        for line in text.splitlines():
            m = re.match(r"^(Components:\s*)(.*)$", line, re.I)
            if m:
                comps_list = m.group(2).split()
                merged = merge(comps_list)
                if merged != comps_list:
                    dirty = True
                    changed.append(f"{src.name}: {' '.join(comps_list)} -> {' '.join(merged)}")
                    out_lines.append(m.group(1) + " ".join(merged))
                    continue
            out_lines.append(line)
        if dirty and apply:
            bak = src.with_suffix(".sources.pre-sovereign.bak")
            if not bak.exists():
                bak.write_text(text)
            src.write_text("\n".join(out_lines) + "\n")

for c in changed:
    print("CHANGE " + c)
PY
)"
if [ -n "${enable_out}" ]; then
  components_changed=1
  # shellcheck disable=SC2001  # line-prefix rewrite; sed is clearest here
  echo "${enable_out}" | sed 's/^CHANGE /  → /'
  if [ -n "${DRY_RUN}" ]; then
    warn "would edit apt sources (backups: *.pre-sovereign.bak)"
  else
    ok "apt components enabled (backups: *.pre-sovereign.bak)"
  fi
else
  ok "contrib + non-free + non-free-firmware already enabled"
fi

# ── (2) apt update ───────────────────────────────────────────────────
step "[2/4] refreshing package metadata"
if [ "${components_changed}" = 1 ] || [ -n "${DRY_RUN}" ]; then
  run "DEBIAN_FRONTEND=noninteractive apt-get update"
else
  run "DEBIAN_FRONTEND=noninteractive apt-get update -qq"
fi

# ── (3) build-host toolchain ─────────────────────────────────────────
step "[3/4] build-host toolchain"
# Union of: kernel forge (01-bootstrap-forge) + image build + signing +
# smoke test + ZFS userland. zfsutils-linux is the package the operator
# hit head-first — it lands cleanly now that contrib is on.
HOST_PACKAGES=(
  # kernel forge
  build-essential libncurses-dev bison flex libssl-dev libelf-dev bc
  rsync debhelper pahole gcc-14 g++-14 cpio kmod
  # image build + repart
  mkosi dosfstools
  # secure-boot signing (sbsign / sbverify)
  sbsigntool
  # QEMU smoke test (step 09) — emulator + UEFI firmware
  qemu-system-x86 ovmf
  # ZFS userland — required by the zfs-tiered profile's preflight
  zfsutils-linux
  # shared across scripts
  git jq curl ca-certificates python3 python3-yaml python3-jsonschema
)
missing=()
for pkg in "${HOST_PACKAGES[@]}"; do
  dpkg -l "${pkg}" 2>/dev/null | grep -q '^ii' || missing+=("${pkg}")
done
if [ "${#missing[@]}" -eq 0 ]; then
  ok "all ${#HOST_PACKAGES[@]} build-host packages already installed"
else
  say "  installing ${#missing[@]} missing: ${missing[*]}"
  run "DEBIAN_FRONTEND=noninteractive apt-get install -y ${missing[*]}"
fi

# Rust toolchain — a FIRST-CLASS build-host tool: sovereign-os's own intelligence
# layer (crates/ — the Cortex Runtime) AND selfdef are built with it. Debian ships
# 1.85, the workspace pins 1.89 (rust-toolchain.toml), so it comes from rustup, not
# apt. rust-toolchain.sh is root-aware: it installs for the invoking operator.
run "'${__REPO_ROOT}/scripts/install/rust-toolchain.sh'${DRY_RUN:+ --dry-run}"

# ── (4) operator-deps overlay (best-effort) ──────────────────────────
step "[4/4] operator deps (apt/pip/npm overlay)"
if [ -n "${SKIP_OPERATOR_DEPS}" ]; then
  warn "skipped (BOOTSTRAP_SKIP_OPERATOR_DEPS set)"
else
  deps_toml="/etc/sovereign-os/operator-deps.toml"
  [ -f "${deps_toml}" ] || deps_toml="${__REPO_ROOT}/config/operator-deps.toml.example"
  if [ -n "${DRY_RUN}" ]; then
    say "  ${cyan}dry-run\$${reset} python3 ${__REPO_ROOT}/scripts/install/operator-deps.py --deps ${deps_toml} --apply --confirm"
  elif python3 "${__REPO_ROOT}/scripts/install/operator-deps.py" \
        --deps "${deps_toml}" --apply --confirm; then
    ok "operator deps applied"
  else
    warn "operator-deps returned non-zero — build-host toolchain is still complete."
    warn "  re-run just this layer later: python3 scripts/install/operator-deps.py --deps ${deps_toml} --apply --confirm"
  fi
fi

# ── report ───────────────────────────────────────────────────────────
step "bootstrap ${DRY_RUN:+dry-run }complete"
if [ -z "${DRY_RUN}" ]; then
  for tool in zpool zfs mkosi qemu-system-x86_64 sbsign; do
    if command -v "${tool}" >/dev/null 2>&1; then
      ok "${tool} ready"
    else
      warn "${tool} still missing — check apt output above"
    fi
  done
fi
say ""
say "  Next: ${cyan}make preflight${reset}   then   ${cyan}make dry-run${reset}   then a real build."
say "  (or just hit ▶ preflight / ▶ BUILD in the configurator page)"
