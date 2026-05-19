# M067 — Custom kernel build pipeline (-march=znver5 / GCC 14 / Linux 6.12 / bindeb-pkg)

**Parent**: sovereign-os runtime — substrate kernel layer
**Source**: `~/infohub/raw/dumps/2026-05-15-sain-01-master-spec-other-conversation-transposition.md`
- Phase II: Zen 5 Kernel Compilation Engine (lines 651-676 + dependencies)
- Toolchain + CFLAGS hard-coding (lines 498-510 — Section 9 base agent build container)
- Phase II bootstrap order (lines 651-676)
**Project boundary**: this milestone catalogs ONLY the kernel build pipeline (sovereign-os substrate); Guardian Daemon (Tetragon eBPF loop) belongs in selfdef MS044 (pending) per "Respect the projects".

## Doctrinal anchors

> "Phase II (The Engine): Build the custom Kernel 6.12 in `tmpfs` using the precise compiler flags specified in Section 2.2 (`-march=znver5`)." (dump 593)
> "ENV CFLAGS=\"-march=znver5 -mavx512f -mavx512dq -mavx512bw -mavx512vl -mavx512bf16 -mavx512fp16\"" (dump 504)
> "make -j$(nproc) KCFLAGS=\"-march=znver5 -O3\" KCPPFLAGS=\"-march=znver5 -O3\" bindeb-pkg" (dump 670)

## Epics (E0648-E0657)

| epic | name | source |
|---|---|---|
| E0648 | Phase II — Zen 5 Kernel Compilation Engine | dump 651-676 |
| E0649 | Toolchain extraction — build-essential + libncurses-dev + bison + flex + libssl-dev + libelf-dev + xz-utils + git + bc + systemd-dev + pahole + gcc-14 + g++-14 | dump 658-660 |
| E0650 | Vanilla upstream fetch — Linux 6.12+ LTS into isolated tmpfs RAM mount | dump 663 |
| E0651 | Config hardening — strip legacy drivers (amateur radio / obsolete filesystems / debug options) | dump 665-666 |
| E0652 | Compilation invocation — KCFLAGS / KCPPFLAGS with -march=znver5 -O3 | dump 668-670 |
| E0653 | Host target deployment — install custom .deb images | dump 672-674 |
| E0654 | AVX-512 instruction subset enablement — F + DQ + BW + VL + BF16 + FP16 | dump 504 |
| E0655 | GGML backend force-flags — GGML_AVX512 + GGML_AVX512_VBMI + GGML_AVX512_VNNI | dump 508-510 |
| E0656 | bindeb-pkg output — linux-image-6.12.*-znver5_*.deb + linux-headers-6.12.*-znver5_*.deb | dump 672-674 |
| E0657 | Reproducibility — every kernel build signed via MS003 + recorded in docs/decisions.md | architecture + cross-ref selfdef MS003 |

## Modules (M01122-M01138)

| module | name | source |
|---|---|---|
| M01122 | sovereign-kernel-build-toolchain-installer | dump 658-660 |
| M01123 | sovereign-kernel-vanilla-fetcher (Linux 6.12+) | dump 663 |
| M01124 | sovereign-kernel-tmpfs-build-allocator | dump 663 |
| M01125 | sovereign-kernel-config-hardener | dump 665-666 |
| M01126 | sovereign-kernel-legacy-stripper | dump 666 |
| M01127 | sovereign-kernel-make-orchestrator | dump 668-670 |
| M01128 | sovereign-kernel-bindeb-pkg-emitter | dump 670 |
| M01129 | sovereign-kernel-deb-installer | dump 672-674 |
| M01130 | sovereign-kernel-avx512-flag-validator | dump 504 |
| M01131 | sovereign-kernel-ggml-flag-emitter | dump 508-510 |
| M01132 | sovereign-kernel-build-reproducibility-engine | architecture + cross-ref selfdef MS003 |
| M01133 | sovereign-kernel-build-replay-validator | cross-ref selfdef MS009 |
| M01134 | sovereign-kernel-build-checkpoint-emitter | M063 IaC pipeline |
| M01135 | sovereign-kernel-build-resumability-coordinator | M063 IaC pipeline |
| M01136 | sovereign-kernel-build-typed-mirror | cross-ref selfdef MS007 |
| M01137 | sovereign-kernel-build-event-emitter | cross-ref M049 + selfdef MS026 |
| M01138 | sovereign-kernel-build-dashboard-binding (D-09 hardware pressure shows build progress) | cross-ref M060 |

## Features (F05611-F05695)

| feature | name | source |
|---|---|---|
| F05611 | Toolchain — build-essential | dump 658-660 |
| F05612 | Toolchain — libncurses-dev | dump 658-660 |
| F05613 | Toolchain — bison | dump 658-660 |
| F05614 | Toolchain — flex | dump 658-660 |
| F05615 | Toolchain — libssl-dev | dump 658-660 |
| F05616 | Toolchain — libelf-dev | dump 658-660 |
| F05617 | Toolchain — xz-utils | dump 658-660 |
| F05618 | Toolchain — git | dump 658-660 |
| F05619 | Toolchain — bc | dump 658-660 |
| F05620 | Toolchain — systemd-dev | dump 658-660 |
| F05621 | Toolchain — pahole | dump 658-660 |
| F05622 | Toolchain — gcc-14 (GNU 14 target AMD Zen 5 ISA natively) | dump 658-660 |
| F05623 | Toolchain — g++-14 | dump 658-660 |
| F05624 | Source — Linux 6.12+ LTS from kernel.org | dump 663 |
| F05625 | Source — clone into isolated tmpfs RAM mount | dump 663 |
| F05626 | Source — tmpfs eliminates NVMe write cycles during compilation | dump 663 |
| F05627 | Source — tmpfs allocation `>=` 32GB per build (operator-tunable) | architecture |
| F05628 | Source — tmpfs cleared on build completion | architecture |
| F05629 | Config — copy operator-tailored `.config` block | dump 665 |
| F05630 | Config — execute `make oldconfig` | dump 665 |
| F05631 | Config — strip legacy drivers: amateur radio | dump 666 |
| F05632 | Config — strip legacy drivers: obsolete filesystems | dump 666 |
| F05633 | Config — strip debug options | dump 666 |
| F05634 | Config — minimize surface vulnerability | dump 666 |
| F05635 | Config — minimize build times | dump 666 |
| F05636 | Config — operator-tailored `.config` retained in /etc/sovereign-os/kernel-config-<version>.txt | architecture |
| F05637 | Config — kernel-config signed via MS003 | cross-ref selfdef MS003 |
| F05638 | Compile — `make -j$(nproc)` parallel compilation | dump 670 |
| F05639 | Compile — KCFLAGS="-march=znver5 -O3" | dump 670 |
| F05640 | Compile — KCPPFLAGS="-march=znver5 -O3" | dump 670 |
| F05641 | Compile — `bindeb-pkg` target produces .deb images | dump 670 |
| F05642 | Compile — output: linux-image-6.12.*-znver5_*.deb | dump 672-674 |
| F05643 | Compile — output: linux-headers-6.12.*-znver5_*.deb | dump 672-674 |
| F05644 | Compile — install via `dpkg -i` | dump 672-674 |
| F05645 | Compile — verify package signatures before install | architecture + cross-ref selfdef MS003 |
| F05646 | AVX-512 enable — -mavx512f (Foundation) | dump 504 |
| F05647 | AVX-512 enable — -mavx512dq (Doubleword and Quadword) | dump 504 |
| F05648 | AVX-512 enable — -mavx512bw (Byte and Word) | dump 504 |
| F05649 | AVX-512 enable — -mavx512vl (Vector Length) | dump 504 |
| F05650 | AVX-512 enable — -mavx512bf16 (BFloat16) | dump 504 |
| F05651 | AVX-512 enable — -mavx512fp16 (FP16) | dump 504 |
| F05652 | GGML backend — GGML_AVX512=1 | dump 508 |
| F05653 | GGML backend — GGML_AVX512_VBMI=1 | dump 509 |
| F05654 | GGML backend — GGML_AVX512_VNNI=1 | dump 510 |
| F05655 | GGML backend — env-vars exported in container build (CFLAGS / CXXFLAGS) | dump 503-505 |
| F05656 | GGML backend — Dockerfile from `debian:13-slim` base | dump 501 |
| F05657 | Reproducibility — every build signed via MS003 | cross-ref selfdef MS003 |
| F05658 | Reproducibility — build inputs recorded (source hash + .config hash + compiler version) | architecture |
| F05659 | Reproducibility — build outputs recorded (.deb hashes) | architecture |
| F05660 | Reproducibility — build record retained at /var/lib/sovereign-os/kernel-builds/<ts>.json | architecture |
| F05661 | Reproducibility — build record signed via MS003 | cross-ref selfdef MS003 |
| F05662 | Reproducibility — build record retained 365 days minimum | cross-ref selfdef MS037 |
| F05663 | Reproducibility — second build with same inputs produces same outputs (bit-for-bit) | architecture |
| F05664 | Reproducibility — recorded in docs/decisions.md per L6 Persist | cross-ref selfdef MS039 + M062 dump 99 |
| F05665 | Replay validator — verifies historical kernel-build chain integrity | cross-ref selfdef MS009 |
| F05666 | Replay validator — detects build-input forgery | cross-ref selfdef MS003 + MS009 |
| F05667 | Replay validator — emits OCSF Detection 2004 on chain break | cross-ref selfdef MS026 |
| F05668 | Checkpoint — kernel-build pipeline checkpointed per major step (M063 IaC quality bar) | cross-ref M063 |
| F05669 | Checkpoint — fetch → config → compile → install all checkpoint-resumable | M063 IaC pipeline |
| F05670 | Checkpoint — `sovereign kernel-build --resume <checkpoint-id>` flag | architecture + M063 |
| F05671 | Checkpoint — checkpoint file at /var/lib/sovereign-os/kernel-build-checkpoint.json | architecture |
| F05672 | Checkpoint — checkpoint signed via MS003 | cross-ref selfdef MS003 |
| F05673 | Observability — every build step emits M049 trace | cross-ref M049 |
| F05674 | Observability — every build step emits OCSF System Activity class 1001 | cross-ref selfdef MS026 |
| F05675 | Observability — D-09 hardware pressure dashboard shows build progress + ETA | cross-ref M060 |
| F05676 | Observability — D-00 main dashboard shows current build phase | cross-ref M060 |
| F05677 | Typed mirror — sovereign-kernel-build-mirror crate under MS007 8/8 SATURATED | cross-ref selfdef MS007 |
| F05678 | Typed mirror — KernelBuildRecord struct {version, kcflags, kcppflags, config_hash, output_hashes, signature, ts} | cross-ref selfdef MS007 |
| F05679 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 |
| F05680 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 |
| F05681 | High-risk — kernel build = L6 Persist (super-model manifest update) | cross-ref selfdef MS039 + M059 |
| F05682 | High-risk — kernel build requires MS041 triple-gate (snapshot + test/eval + oracle-or-human) | cross-ref selfdef MS041 |
| F05683 | High-risk — kernel install requires ZFS snapshot pre-commit | cross-ref selfdef MS037 + M068 (pending) |
| F05684 | CLI — `sovereign kernel build --version <ver>` invokes pipeline | architecture + cross-ref selfdef MS043 |
| F05685 | CLI — `sovereign kernel show` returns current kernel build record | architecture |
| F05686 | CLI — `sovereign kernel history` returns prior builds | architecture |
| F05687 | CLI — `sovereign kernel verify <build-id>` verifies signature chain | cross-ref selfdef MS003 |
| F05688 | Boundary — Guardian Daemon (Tetragon eBPF + SIGKILL) lives in selfdef MS044 (pending) | operator standing direction "Respect the projects" |
| F05689 | Boundary — M067 scope = kernel build only | architecture + operator standing direction |
| F05690 | Boundary — kernel includes eBPF support compiled in (Tetragon dependency) | architecture |
| F05691 | Boundary — kernel build never mutates selfdef IPS state | operator standing direction | 
| F05692 | Doctrinal preservation — "-march=znver5" verbatim in M067 doc | dump 504 + 670 |
| F05693 | Doctrinal preservation — "Build the custom Kernel 6.12 in tmpfs" verbatim | dump 593 | 
| F05694 | Doctrinal preservation — operator words never paraphrased | operator standing direction |
| F05695 | Closing — M067 covers dump 498-676 verbatim kernel scope; M068 ZFS Storage Architecture next | dump 498-676 + operator standing direction |

## Requirements (R11221-R11390)

| req | description | source | feature | priority | exception | sub-reqs |
|---|---|---|---|---|---|---|
| R11221 | Doctrinal — "Build the custom Kernel 6.12 in `tmpfs` using the precise compiler flags" | dump 593 | F05625 | non-negotiable | false | 10 |
| R11222 | Doctrinal — "-march=znver5" verbatim in build flags | dump 504 + 670 | F05639 | non-negotiable | false | 10 |
| R11223 | Doctrinal — GCC 14 explicitly required (gcc-14 + g++-14) | dump 658-660 | F05622 | non-negotiable | false | 10 |
| R11224 | Doctrinal — Linux kernel 6.12+ LTS series | dump 663 | F05624 | non-negotiable | false | 10 |
| R11225 | Doctrinal — vanilla upstream fetch (not Debian-patched) | dump 663 | F05624 | non-negotiable | false | 10 |
| R11226 | Doctrinal — bindeb-pkg target output | dump 670 | F05641 | non-negotiable | false | 10 |
| R11227 | Toolchain — install build-essential | dump 658-660 | F05611 | non-negotiable | false | 10 |
| R11228 | Toolchain — install libncurses-dev | dump 658-660 | F05612 | non-negotiable | false | 10 |
| R11229 | Toolchain — install bison | dump 658-660 | F05613 | non-negotiable | false | 10 |
| R11230 | Toolchain — install flex | dump 658-660 | F05614 | non-negotiable | false | 10 |
| R11231 | Toolchain — install libssl-dev | dump 658-660 | F05615 | non-negotiable | false | 10 |
| R11232 | Toolchain — install libelf-dev | dump 658-660 | F05616 | non-negotiable | false | 10 |
| R11233 | Toolchain — install xz-utils | dump 658-660 | F05617 | non-negotiable | false | 10 |
| R11234 | Toolchain — install git | dump 658-660 | F05618 | non-negotiable | false | 10 |
| R11235 | Toolchain — install bc | dump 658-660 | F05619 | non-negotiable | false | 10 |
| R11236 | Toolchain — install systemd-dev | dump 658-660 | F05620 | non-negotiable | false | 10 |
| R11237 | Toolchain — install pahole | dump 658-660 | F05621 | non-negotiable | false | 10 |
| R11238 | Toolchain — install gcc-14 | dump 658-660 | F05622 | non-negotiable | false | 10 |
| R11239 | Toolchain — install g++-14 | dump 658-660 | F05623 | non-negotiable | false | 10 |
| R11240 | Toolchain — apt-get update first | dump 658 | F05611 | non-negotiable | false | 10 |
| R11241 | Source — clone Linux 6.12+ LTS upstream | dump 663 | F05624 | non-negotiable | false | 10 |
| R11242 | Source — into isolated tmpfs RAM mount | dump 663 | F05625 | non-negotiable | false | 10 |
| R11243 | Source — tmpfs eliminates NVMe write cycles during massive compilation sequence | dump 663 | F05626 | non-negotiable | false | 10 |
| R11244 | Source — tmpfs allocation `>=` 32GB per build | architecture | F05627 | non-negotiable | false | 10 |
| R11245 | Source — tmpfs operator-tunable | architecture | F05627 | non-negotiable | false | 10 |
| R11246 | Source — tmpfs cleared on build completion | architecture | F05628 | non-negotiable | false | 10 |
| R11247 | Source — source-tree path /mnt/tmpfs-kernel/<version>/ | architecture | F05625 | non-negotiable | false | 10 |
| R11248 | Source — source-tree integrity verified via upstream git tag signature | architecture | F05624 | non-negotiable | false | 10 |
| R11249 | Source — source-tree hash recorded in build record | architecture | F05658 | non-negotiable | false | 10 |
| R11250 | Source — fetch retry on network failure (exponential backoff 2s/4s/8s/16s) | architecture | F05624 | non-negotiable | false | 10 |
| R11251 | Config — copy operator-tailored `.config` block | dump 665 | F05629 | non-negotiable | false | 10 |
| R11252 | Config — execute `make oldconfig` | dump 665 | F05630 | non-negotiable | false | 10 |
| R11253 | Config — forcefully strip amateur radio drivers | dump 666 | F05631 | non-negotiable | false | 10 |
| R11254 | Config — forcefully strip obsolete filesystems | dump 666 | F05632 | non-negotiable | false | 10 |
| R11255 | Config — forcefully strip debug options | dump 666 | F05633 | non-negotiable | false | 10 |
| R11256 | Config — minimize surface vulnerability | dump 666 | F05634 | non-negotiable | false | 10 |
| R11257 | Config — minimize build times | dump 666 | F05635 | non-negotiable | false | 10 |
| R11258 | Config — operator-tailored .config retained at /etc/sovereign-os/kernel-config-<version>.txt | architecture | F05636 | non-negotiable | false | 10 |
| R11259 | Config — kernel-config signed via MS003 | cross-ref selfdef MS003 | F05637 | non-negotiable | false | 10 |
| R11260 | Config — eBPF support compiled in (Tetragon dependency) | architecture | F05690 | non-negotiable | false | 10 |
| R11261 | Compile — `make -j$(nproc)` parallel | dump 670 | F05638 | non-negotiable | false | 10 |
| R11262 | Compile — KCFLAGS="-march=znver5 -O3" | dump 670 | F05639 | non-negotiable | false | 10 |
| R11263 | Compile — KCPPFLAGS="-march=znver5 -O3" | dump 670 | F05640 | non-negotiable | false | 10 |
| R11264 | Compile — bindeb-pkg target | dump 670 | F05641 | non-negotiable | false | 10 |
| R11265 | Compile — output linux-image-6.12.*-znver5_*.deb in parent directory | dump 672-674 | F05642 | non-negotiable | false | 10 |
| R11266 | Compile — output linux-headers-6.12.*-znver5_*.deb in parent directory | dump 672-674 | F05643 | non-negotiable | false | 10 |
| R11267 | Install — `dpkg -i linux-image-6.12.*-znver5_*.deb linux-headers-6.12.*-znver5_*.deb` | dump 672-674 | F05644 | non-negotiable | false | 10 |
| R11268 | Install — verify .deb package signatures before install | architecture + cross-ref selfdef MS003 | F05645 | non-negotiable | false | 10 |
| R11269 | Install — install requires MS041 triple-gate (snapshot + test/eval + oracle-or-human) | cross-ref selfdef MS041 | F05682 | non-negotiable | false | 10 |
| R11270 | Install — install requires ZFS snapshot pre-commit | cross-ref selfdef MS037 + M068 (pending) | F05683 | non-negotiable | false | 10 |
| R11271 | AVX-512 — -mavx512f (Foundation) | dump 504 | F05646 | non-negotiable | false | 10 |
| R11272 | AVX-512 — -mavx512dq (Doubleword + Quadword) | dump 504 | F05647 | non-negotiable | false | 10 |
| R11273 | AVX-512 — -mavx512bw (Byte + Word) | dump 504 | F05648 | non-negotiable | false | 10 |
| R11274 | AVX-512 — -mavx512vl (Vector Length) | dump 504 | F05649 | non-negotiable | false | 10 |
| R11275 | AVX-512 — -mavx512bf16 (BFloat16) | dump 504 | F05650 | non-negotiable | false | 10 |
| R11276 | AVX-512 — -mavx512fp16 (FP16) | dump 504 | F05651 | non-negotiable | false | 10 |
| R11277 | AVX-512 — flags exported in container build CFLAGS | dump 503-504 | F05655 | non-negotiable | false | 10 |
| R11278 | AVX-512 — flags exported in container build CXXFLAGS | dump 505 | F05655 | non-negotiable | false | 10 |
| R11279 | AVX-512 — flag validator runs before compile (rejects missing flag) | architecture | F05646 | non-negotiable | false | 10 |
| R11280 | AVX-512 — flag validator emits OCSF Detection 2004 on missing flag | cross-ref selfdef MS026 | F05646 | non-negotiable | false | 10 |
| R11281 | GGML — GGML_AVX512=1 env-var | dump 508 | F05652 | non-negotiable | false | 10 |
| R11282 | GGML — GGML_AVX512_VBMI=1 env-var | dump 509 | F05653 | non-negotiable | false | 10 |
| R11283 | GGML — GGML_AVX512_VNNI=1 env-var | dump 510 | F05654 | non-negotiable | false | 10 |
| R11284 | GGML — env-vars exported to container build | dump 508-510 | F05655 | non-negotiable | false | 10 |
| R11285 | GGML — Dockerfile from debian:13-slim base | dump 501 | F05656 | non-negotiable | false | 10 |
| R11286 | GGML — flags hard-coded into build pipelines to avoid fallback emulation | dump 498-500 | F05655 | non-negotiable | false | 10 |
| R11287 | GGML — applies to llama.cpp build container | dump 498 | F05655 | non-negotiable | false | 10 |
| R11288 | GGML — applies to custom WASM/Assembly runtimes | dump 498 | F05655 | non-negotiable | false | 10 |
| R11289 | GGML — runs inside Podman infrastructure | dump 498 | F05656 | non-negotiable | false | 10 |
| R11290 | GGML — env-var validation: missing flag halts container build | architecture | F05655 | non-negotiable | false | 10 |
| R11291 | Reproducibility — every build signed via MS003 | cross-ref selfdef MS003 | F05657 | non-negotiable | false | 10 |
| R11292 | Reproducibility — record source hash (git commit sha) | architecture | F05658 | non-negotiable | false | 10 |
| R11293 | Reproducibility — record .config hash | architecture | F05658 | non-negotiable | false | 10 |
| R11294 | Reproducibility — record compiler version (gcc-14 --version) | architecture | F05658 | non-negotiable | false | 10 |
| R11295 | Reproducibility — record output .deb hashes | architecture | F05659 | non-negotiable | false | 10 |
| R11296 | Reproducibility — build record at /var/lib/sovereign-os/kernel-builds/<ts>.json | architecture | F05660 | non-negotiable | false | 10 |
| R11297 | Reproducibility — build record signed via MS003 | cross-ref selfdef MS003 | F05661 | non-negotiable | false | 10 |
| R11298 | Reproducibility — build record retained 365 days minimum | cross-ref selfdef MS037 | F05662 | non-negotiable | false | 10 |
| R11299 | Reproducibility — second build with same inputs produces same outputs (bit-for-bit) | architecture | F05663 | non-negotiable | false | 10 |
| R11300 | Reproducibility — recorded in docs/decisions.md as L6 Persist | cross-ref selfdef MS039 + M062 dump 99 | F05664 | non-negotiable | false | 10 |
| R11301 | Replay validator — verifies historical kernel-build chain integrity | cross-ref selfdef MS009 | F05665 | non-negotiable | false | 10 |
| R11302 | Replay validator — detects build-input forgery | cross-ref selfdef MS003 + MS009 | F05666 | non-negotiable | false | 10 |
| R11303 | Replay validator — emits OCSF Detection Finding 2004 on chain break | cross-ref selfdef MS026 | F05667 | non-negotiable | false | 10 |
| R11304 | Replay validator — runs daily as systemd timer | cross-ref selfdef MS009 | F05665 | non-negotiable | false | 10 |
| R11305 | Replay validator — failures halt new kernel builds | architecture | F05665 | non-negotiable | false | 10 |
| R11306 | Checkpoint — pipeline checkpointed per major step | cross-ref M063 | F05668 | non-negotiable | false | 10 |
| R11307 | Checkpoint — fetch step checkpoint | M063 IaC pipeline | F05669 | non-negotiable | false | 10 |
| R11308 | Checkpoint — config step checkpoint | M063 | F05669 | non-negotiable | false | 10 |
| R11309 | Checkpoint — compile step checkpoint | M063 | F05669 | non-negotiable | false | 10 |
| R11310 | Checkpoint — install step checkpoint | M063 | F05669 | non-negotiable | false | 10 |
| R11311 | Checkpoint — `sovereign kernel-build --resume <id>` flag | architecture + M063 | F05670 | non-negotiable | false | 10 |
| R11312 | Checkpoint — checkpoint file at /var/lib/sovereign-os/kernel-build-checkpoint.json | architecture | F05671 | non-negotiable | false | 10 |
| R11313 | Checkpoint — checkpoint signed via MS003 | cross-ref selfdef MS003 | F05672 | non-negotiable | false | 10 |
| R11314 | Checkpoint — checkpoint TTL 7 days (orphan checkpoints purged) | architecture | F05671 | non-negotiable | false | 10 |
| R11315 | Checkpoint — partial failure does not require full re-fetch (M063 IaC quality bar) | M063 dump 393 | F05668 | non-negotiable | false | 10 |
| R11316 | Observability — every build step emits M049 13-field trace | cross-ref M049 | F05673 | non-negotiable | false | 10 |
| R11317 | Observability — every build step emits OCSF System Activity class 1001 | cross-ref selfdef MS026 | F05674 | non-negotiable | false | 10 |
| R11318 | Observability — D-09 hardware pressure dashboard shows build progress + ETA | cross-ref M060 | F05675 | non-negotiable | false | 10 |
| R11319 | Observability — D-00 main dashboard shows current kernel build phase | cross-ref M060 | F05676 | non-negotiable | false | 10 |
| R11320 | Observability — D-08 rollback points surfaces kernel install snapshots | cross-ref M060 | F05683 | non-negotiable | false | 10 |
| R11321 | Typed mirror — sovereign-kernel-build-mirror under MS007 8/8 SATURATED | cross-ref selfdef MS007 | F05677 | non-negotiable | false | 10 |
| R11322 | Typed mirror — KernelBuildRecord struct {version, kcflags, kcppflags, config_hash, output_hashes, signature, ts} | cross-ref selfdef MS007 | F05678 | non-negotiable | false | 10 |
| R11323 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 | F05679 | non-negotiable | false | 10 |
| R11324 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 | F05680 | non-negotiable | false | 10 |
| R11325 | Typed mirror — re-exported via sovereign-os cargo workspace | cross-ref selfdef MS007 | F05677 | non-negotiable | false | 10 |
| R11326 | Typed mirror — no_std friendly | architecture | F05677 | non-negotiable | false | 10 |
| R11327 | Typed mirror — serde + bincode derives present | architecture | F05677 | non-negotiable | false | 10 |
| R11328 | Typed mirror — schema-breaking changes require schema_version bump | architecture + cross-ref selfdef MS007 | F05679 | non-negotiable | false | 10 |
| R11329 | High-risk — kernel build = L6 Persist (super-model manifest update) | cross-ref selfdef MS039 + M059 | F05681 | non-negotiable | false | 10 |
| R11330 | High-risk — requires MS041 triple-gate snapshot + test/eval + oracle-or-human | cross-ref selfdef MS041 | F05682 | non-negotiable | false | 10 |
| R11331 | High-risk — kernel install snapshot via ZFS pre-commit | cross-ref selfdef MS037 + M068 (pending) | F05683 | non-negotiable | false | 10 |
| R11332 | High-risk — snapshot retained 365 days minimum | cross-ref selfdef MS037 | F05683 | non-negotiable | false | 10 |
| R11333 | High-risk — rollback via ZFS rollback to pre-install snapshot | cross-ref selfdef MS037 | F05683 | non-negotiable | false | 10 |
| R11334 | High-risk — test/eval = boot-validation in QEMU (M062 PR 9 harness) | cross-ref M062 PR 9 | F05682 | non-negotiable | false | 10 |
| R11335 | High-risk — oracle-or-human = sovereign-os oracle OR operator approval | cross-ref selfdef MS041 | F05682 | non-negotiable | false | 10 |
| R11336 | CLI — `sovereign kernel build --version <ver>` invokes pipeline | architecture + cross-ref selfdef MS043 | F05684 | non-negotiable | false | 10 |
| R11337 | CLI — `sovereign kernel show` returns current kernel build record | architecture | F05685 | non-negotiable | false | 10 |
| R11338 | CLI — `sovereign kernel history` returns prior builds | architecture | F05686 | non-negotiable | false | 10 |
| R11339 | CLI — `sovereign kernel verify <build-id>` verifies signature chain | cross-ref selfdef MS003 | F05687 | non-negotiable | false | 10 |
| R11340 | CLI — `sovereign kernel build --resume <ckpt>` resumes from checkpoint | architecture + M063 | F05670 | non-negotiable | false | 10 |
| R11341 | CLI — `sovereign kernel install <build-id>` installs build (high-risk gated) | architecture + MS041 | F05644 | non-negotiable | false | 10 |
| R11342 | CLI — `sovereign kernel rollback <prior-build-id>` rolls back to prior | cross-ref selfdef MS041 | F05683 | non-negotiable | false | 10 |
| R11343 | CLI — all kernel subcommands emit M049 trace | cross-ref M049 | F05673 | non-negotiable | false | 10 |
| R11344 | CLI — all kernel subcommands signed via MS003 | cross-ref selfdef MS003 | F05657 | non-negotiable | false | 10 |
| R11345 | Boundary — kernel includes eBPF support compiled in (Tetragon dependency) | architecture | F05690 | non-negotiable | false | 10 |
| R11346 | Boundary — Guardian Daemon (Tetragon eBPF loop) IMPLEMENTATION lives in selfdef MS044 (pending) | operator standing direction "Respect the projects" | F05688 | non-negotiable | false | 10 |
| R11347 | Boundary — M067 scope = kernel build only | architecture + operator standing direction | F05689 | non-negotiable | false | 10 |
| R11348 | Boundary — kernel build never mutates selfdef IPS state | operator standing direction | F05691 | non-negotiable | false | 10 |
| R11349 | Boundary — kernel build emits state mirror via MS007 selfdef-kernel-build-mirror crate | cross-ref selfdef MS007 | F05677 | non-negotiable | false | 10 |
| R11350 | Boundary — kernel build operator surface in M067 CLI; selfdef MS043 cross-refs for IPS-side reading | cross-ref selfdef MS043 | F05684 | non-negotiable | false | 10 |
| R11351 | Doctrinal preservation — "-march=znver5" verbatim across M067 doc | dump 504 + 670 | F05692 | non-negotiable | false | 10 |
| R11352 | Doctrinal preservation — "tmpfs RAM mount" verbatim | dump 663 + 593 | F05693 | non-negotiable | false | 10 |
| R11353 | Doctrinal preservation — KCFLAGS="-march=znver5 -O3" verbatim | dump 670 | F05639 | non-negotiable | false | 10 |
| R11354 | Doctrinal preservation — KCPPFLAGS="-march=znver5 -O3" verbatim | dump 670 | F05640 | non-negotiable | false | 10 |
| R11355 | Doctrinal preservation — bindeb-pkg target verbatim | dump 670 | F05641 | non-negotiable | false | 10 |
| R11356 | Doctrinal preservation — output filename pattern linux-image-6.12.*-znver5_*.deb verbatim | dump 672-674 | F05642 | non-negotiable | false | 10 |
| R11357 | Doctrinal preservation — output filename pattern linux-headers-6.12.*-znver5_*.deb verbatim | dump 672-674 | F05643 | non-negotiable | false | 10 |
| R11358 | Doctrinal preservation — operator words "no hacks, no shortcuts, no compromises" verbatim | dump 600 | F05694 | non-negotiable | false | 10 |
| R11359 | Doctrinal preservation — verbatim quotes never paraphrased | operator standing direction | F05694 | non-negotiable | false | 10 |
| R11360 | Doctrinal preservation — info-hub indexes kernel-build pipeline as second-brain entry | operator standing direction "second-brain" | F05677 | non-negotiable | false | 10 |
| R11361 | Composition — kernel build composes with M058 hardware-aware scheduler (Pulse manifestation) | cross-ref M058 | F05675 | non-negotiable | false | 10 |
| R11362 | Composition — kernel build composes with M063 SFIF Infrastructure phase | cross-ref M063 | F05668 | non-negotiable | false | 10 |
| R11363 | Composition — kernel build composes with M064 Debian-as-Ark customization | cross-ref M064 | F05636 | non-negotiable | false | 10 |
| R11364 | Composition — kernel build composes with M065 Stage Gates (SG5 + post-Stage-2 builds) | cross-ref M065 | F05682 | non-negotiable | false | 10 |
| R11365 | Composition — kernel build composes with M066 Trinity (The Pulse manifestation) | cross-ref M066 | F05646 | non-negotiable | false | 10 |
| R11366 | Composition — kernel build composes forward with M068 ZFS Storage Architecture (pending) | cross-ref M068 (pending) | F05683 | non-negotiable | false | 10 |
| R11367 | Composition — kernel build composes forward with M073 1-bit ternary logic (pending) | cross-ref M073 (pending) | F05646 | non-negotiable | false | 10 |
| R11368 | Composition — kernel build composes forward with M074 AVX-512 VNNI fusion (pending) | cross-ref M074 (pending) | F05654 | non-negotiable | false | 10 |
| R11369 | Composition — kernel build composes forward with selfdef MS044 Guardian Daemon (pending; uses kernel eBPF) | cross-ref selfdef MS044 (pending) | F05690 | non-negotiable | false | 10 |
| R11370 | Performance — kernel build runtime `<` 30min on Ryzen 9 9900X with tmpfs (target) | architecture | F05638 | non-negotiable | false | 10 |
| R11371 | Performance — `sovereign kernel show` runtime `<` 50ms p95 | architecture | F05685 | non-negotiable | false | 10 |
| R11372 | Performance — `sovereign kernel verify` runtime `<` 2s p95 | architecture | F05687 | non-negotiable | false | 10 |
| R11373 | Performance — kernel install runtime `<` 60s p95 (excluding gates) | architecture | F05644 | non-negotiable | false | 10 |
| R11374 | Performance — typed-mirror publication latency `<` 100ms p95 | cross-ref selfdef MS007 | F05677 | non-negotiable | false | 10 |
| R11375 | Telemetry — kernel build duration histograms emitted via M049 | cross-ref M049 | F05673 | non-negotiable | false | 10 |
| R11376 | Telemetry — kernel build success rate emitted via M049 | cross-ref M049 | F05673 | non-negotiable | false | 10 |
| R11377 | Telemetry — kernel build failure root-cause distribution emitted via M049 | cross-ref M049 + M055 | F05673 | non-negotiable | false | 10 |
| R11378 | Telemetry — current kernel version + commit emitted via M049 | cross-ref M049 + M059 | F05685 | non-negotiable | false | 10 |
| R11379 | Telemetry — kernel rollback count emitted via M049 (high-priority alert) | cross-ref M049 | F05683 | non-negotiable | false | 10 |
| R11380 | Operational — kernel build CLI runs in dedicated systemd-nspawn (M062 PR 9 harness) | cross-ref M062 PR 9 | F05626 | non-negotiable | false | 10 |
| R11381 | Operational — kernel build CLI honors SIGTERM (writes resumable checkpoint) | architecture + M063 | F05670 | non-negotiable | false | 10 |
| R11382 | Operational — kernel build CLI emits readiness probe at /run/sovereign-kernel-build/ready | architecture | F05684 | non-negotiable | false | 10 |
| R11383 | Operational — kernel build CLI exit codes follow sysexits.h | architecture | F05684 | non-negotiable | false | 10 |
| R11384 | Closing — M067 covers dump 498-510 (CFLAGS/CXXFLAGS + GGML env-vars) verbatim | dump 498-510 | F05646 | non-negotiable | false | 10 |
| R11385 | Closing — M067 covers dump 651-676 (Phase II kernel compilation) verbatim | dump 651-676 | F05624 | non-negotiable | false | 10 |
| R11386 | Closing — sovereign-os catalog at 67/67 milestones | architecture | F05695 | non-negotiable | false | 10 |
| R11387 | Closing — combined ecosystem 110 milestones | architecture | F05695 | non-negotiable | false | 10 |
| R11388 | Closing — combined R-rows ~21710 | architecture | F05695 | non-negotiable | false | 10 |
| R11389 | Closing — every R-row carries 10 hard non-negotiable sub-requirements | operator standing direction | F05611 | non-negotiable | false | 10 |
| R11390 | Closing — M067 covers kernel build dump scope verbatim; M068 ZFS Storage Architecture next | dump 498-676 + operator standing direction | F05695 | non-negotiable | false | 10 |

## Sub-requirements accounting

Every R-row carries 10 hard non-negotiable sub-requirements. Total = 170 R × 10 = **1,700 sub-requirements** for M067.

## Cross-references

- **M044** — substrate (kernel build is Debian 13 customization)
- **M048** — modules map (Base OS module)
- **M049** — observability + trace pipeline
- **M055** — failure modes (kernel build failure taxonomy)
- **M058** — hardware-aware scheduler (Pulse manifestation)
- **M059** — peace machine close (super-model manifest update on each build)
- **M060** — cockpit + dashboards (D-09 hardware pressure shows build progress)
- **M062** — Macro-Arc 10-PR scaffold (PR 4 substrate decision informs kernel build choice)
- **M063** — SFIF discipline (kernel build is Infrastructure phase)
- **M064** — Debian-as-Ark (kernel customization per working hypothesis)
- **M065** — Five Stage Gates (Stage 2+ kernel-build work)
- **M066** — Trinity Framework Genesis (The Pulse physical manifestation)
- **M068** — ZFS Storage Architecture (kernel install ZFS snapshot; pending)
- **M073** — 1-bit ternary logic (kernel enables AVX-512 for ternary; pending)
- **M074** — AVX-512 VNNI fusion (kernel enables VNNI compile flags; pending)
- **selfdef MS003** — selfdef-signing (signs every build record + checkpoint)
- **selfdef MS007** — typed-mirror crate scheme (sovereign-kernel-build-mirror)
- **selfdef MS009** — replay validator (verifies build chain)
- **selfdef MS026** — observability + OCSF event emission
- **selfdef MS037** — filesystem boundary (ZFS snapshot pre-install)
- **selfdef MS039** — authority levels (kernel install is L6 Persist)
- **selfdef MS041** — commit authority (kernel install requires triple-gate)
- **selfdef MS043** — IPS operator surface (CLI integration)
- **selfdef MS044** — Guardian Daemon (pending; kernel ships eBPF support for it)

## Schema

```
schema_version: "1.0.0"
milestone_id: M067
parent: sovereign-os
epics: 10
modules: 17
features: 85
requirements: 170
sub_requirements_per_requirement: 10
total_sub_requirements: 1700
source_dump_lines:
  - 498-510 (CFLAGS / CXXFLAGS / GGML env-vars)
  - 651-676 (Phase II: Zen 5 Kernel Compilation Engine)
kernel_version: 6.12+ LTS vanilla upstream
compiler: gcc-14 + g++-14
build_flags:
  KCFLAGS: "-march=znver5 -O3"
  KCPPFLAGS: "-march=znver5 -O3"
  CFLAGS: "-march=znver5 -mavx512f -mavx512dq -mavx512bw -mavx512vl -mavx512bf16 -mavx512fp16"
  CXXFLAGS: "-march=znver5 -mavx512f -mavx512dq -mavx512bw -mavx512vl -mavx512bf16 -mavx512fp16"
  GGML_AVX512: "1"
  GGML_AVX512_VBMI: "1"
  GGML_AVX512_VNNI: "1"
build_target: bindeb-pkg
output:
  - linux-image-6.12.*-znver5_*.deb
  - linux-headers-6.12.*-znver5_*.deb
build_location: tmpfs RAM mount (eliminates NVMe write cycles)
typed_mirror_crate: sovereign-kernel-build-mirror
catalog_status:
  sovereign_os: 67/67 milestones
  selfdef: 43/43 milestones
  combined: 110 milestones
```
