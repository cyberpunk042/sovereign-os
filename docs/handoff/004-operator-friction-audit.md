# Operator Friction Audit (Round 133 — 2026-05-16)

> Honest critical review prompted by the operator's question:
> "could the User go through everything, and make every decisions he
> wants and keeps going without friction from the build to the
> installation to the system and environment setup and all the pre
> and post and durings."
>
> Short answer: **no**. The codebase is comprehensive. The operator
> JOURNEY has measurable friction at 10+ points. This document
> inventories them honestly and proposes the smallest fix for each.

## Severity scale

- **CRIT** — could cause data loss / system breakage / security regression
- **HIGH** — blocks an operator from completing the journey without external help
- **MED** — slows the operator down or forces undocumented decisions
- **LOW** — UX paper cut; operator can route around

## The 13 friction points

### F-01 — CRIT — Disk dump has NO safety gate  ✅ **CLOSED (Round 134)**

`sovereign-osctl install image [--plan] <img> --to <device>` shipped
with 6 gates (image exists + non-empty + regular file · target is
block device · target is whole disk not partition · target is NOT
running root or its parent · `SOVEREIGN_OS_CONFIRM_DESTROY=YES` ·
typed-device-path interactive confirm). 13-assertion L3.
install-runbook §2.1 updated to recommend the gated path.

**Where**: `docs/src/install-runbook.md` § 2.1 — operator runs
`sudo dd if=build/sain-01/output/sain-01 of=/dev/nvme0n1 bs=4M
status=progress conv=fsync` directly.

**Why it bites**: One typo on `of=` and the operator has nuked the
wrong disk. No confirmation, no device fingerprint check, no preview
of what's about to be destroyed.

**Fix**: `sovereign-osctl install image <path> --to <device>` verb that
- shows the device fingerprint (model · serial · capacity · is-system-disk?)
- refuses if the target is the currently-mounted root
- gates with `SOVEREIGN_OS_CONFIRM_DESTROY=YES` like the decommission verbs
- delegates to `dd` only after both gates pass

### F-02 — HIGH — No interactive `sovereign-osctl init` wizard  ✅ **CLOSED (Round 136)**

`sovereign-osctl init [--non-interactive]` shipped. Walks operator
through 5 decisions (profile · substrate · secure-boot · encrypt ·
whitelabel) with recommendations + per-decision rationale, writes
`.sovereign-os/init-state.yaml`, prints exact next-command block
(preflight → orchestrate.sh run --dry-run → install image --plan).
Honors SOVEREIGN_OS_NONINTERACTIVE for CI/fleet bootstrap. Idempotent
(re-running overwrites). 27-assertion L3.

**Where**: Fresh-machine operator clones the repo, reads README, has
to read 26 SDDs to understand the choice space (profile · substrate ·
secure-boot posture · disk encryption · whitelabel · etc.).

**Why it bites**: Operator has to manually compose 5+ decisions before
they can `make build`. Each decision links to an SDD that links to
others. Cognitive friction at the worst possible moment (first
impression).

**Fix**: `sovereign-osctl init` interactive wizard that walks the
operator through the 5 mandatory decisions in order, surfaces the
recommendation per decision, writes the chosen values to
`.sovereign-os/init-state.yaml`, and prints the EXACT next command.

### F-03 — HIGH — No `sovereign-osctl env list` env-var reference  ✅ **CLOSED (Round 137)**

`sovereign-osctl env list [--filter <regex>]` + `env show <NAME>` shipped.
Scans `scripts/` for every `SOVEREIGN_OS_*` reference, dedupes,
discovers defaults (matches `: "${VAR:=value}"` pattern) + consumer
files, presents tabular index. Filter narrows. `show` drills into
one var (default · default-from-file · currently-set value · consumer
list, capped at 20). 19-assertion L3; 80+ env vars discovered out
of the box.

**Where**: 30+ `SOVEREIGN_OS_*` env vars scattered across scripts.
Operator hunting for "what env var changes X" greps the codebase.

**Why it bites**: Operator can't discover knobs they don't already
know about. Documentation lag — env vars get added without a central
update.

**Fix**: `sovereign-osctl env list` verb that scans all
`SOVEREIGN_OS_*` defaults in the codebase and surfaces them with
description (parsed from the `: "${VAR:=default}" # comment` pattern)
+ where they're consumed. Optional `--filter <regex>` for narrowing.

### F-04 — MED — No profile fork/scaffold helper  ✅ **CLOSED (Round 140)**

`sovereign-osctl profiles fork <base> <new>` shipped. Copies base
profile YAML, mutates `identity.{id, parent, status, description}` to
mark the fork relationship, preserves mixin composition + the
language-server header hint, validates schema immediately, registers
in `profiles/INDEX.md`. Refuses on existing target (exit 1) or
invalid id (exit 2 + pattern hint) or missing base. Prints NEXT-steps
block (edit / validate / compare / switch). 16-assertion L3.

**Where**: Operator wanting a custom profile copies `sain-01.yaml` →
`my-host.yaml`, edits manually. No validator runs until they
`scripts/validate-profiles.sh`. Hooks paths can drift silently.

**Why it bites**: Profile authoring is a yaml-editing exercise with
schema validation gated at lint time only. No "I know you want to
customize the GPU declaration; here's a fork-from-sain-01 template
with that pre-set" path.

**Fix**: `sovereign-osctl profiles fork <base-id> <new-id>` that
copies the base, updates identity.id + sets `parent: <base-id>` for
inheritance traceability, validates immediately, registers in
`profiles/INDEX.md`.

### F-05 — MED — No secure-boot key-generation helper  ✅ **CLOSED (Round 143)**

`sovereign-osctl secure-boot {gen-keys, status}` shipped.
`gen-keys --out <dir> [--cn <name>]` generates 4096-bit RSA / 10-year
PK + KEK + db triple via openssl; emits .key/.crt/.cer (and .esl/.auth
if efitools present); 0600 perms on private keys; writes README.md
with SDD-015 enrollment contract + backup discipline + efi-updatevar
+ sbsign recipes. HARD REFUSAL if --out is under repo root (operator-
supplied keys MUST NOT live in-repo per SDD-015). `status` surfaces
UEFI / SecureBoot / MOK state. 25-assertion L3.

**Where**: SDD-015 says operator-supplied keys (never in-repo). What
operator manually runs `openssl + sbsigntools` to produce PK/KEK/db?
Few. Most will skip secure_boot=signed because the key dance is
opaque.

**Why it bites**: A whole posture in SDD-015 effectively unused
because the onboarding friction is too high.

**Fix**: `sovereign-osctl secure-boot gen-keys --out <dir>` that
generates PK/KEK/db with sane defaults (4096-bit RSA, 10-year validity,
hostname-keyed CN), writes them outside the repo, prints the
enrollment command, and emits a clear "now back these up; sovereign-os
never sees them again" warning.

### F-06 — MED — Layer 4 QEMU validation requires KVM

**Where**: `tests/qemu/scaffold.sh` SKIPs gracefully without KVM.
Operator on a WSL or non-KVM host can't validate their build
end-to-end before deploying.

**Why it bites**: The reproducibility self-test gate exists but
"does this image actually BOOT?" is gated on hardware that not every
operator has.

**Fix (partial)**: Document a tinyemulator path (qemu-system-x86_64
without kvm; slow but works); add a "Layer 4 slow" gate that runs
without KVM and accepts a 5-minute boot probe. Not perfect, but
unblocks the validation axis.

### F-07 — MED — No "did my customization land" comprehensive check  ✅ **CLOSED (Round 142)**

`sovereign-osctl audit customization [--json]` shipped. Cross-cuts
5 axes: active-profile file matches env · /etc/os-release ID matches
whitelabel.branding.os_id · hardening drop-in landed (server or
workstation) · installed package count vs declared · hostname (info-
only). Per-check status (pass/warn/fail) with expected vs actual.
`--json` mode emits `{summary{pass,warn,fail}, profile, checks[]}`.
Exit 1 if any fail. 13-assertion L3.

**Where**: `sovereign-osctl audit drift` checks hardening drop-ins
(R111). What about profile-declared packages? Whitelabel surfaces
(/etc/os-release ID matches profile?)? Profile env var defaults?

**Why it bites**: Operator who customized the profile has to manually
spot-check each axis. Easy to miss "I changed packages.deny to remove
X but the running system still has X."

**Fix**: Extend `audit drift` (or new `audit customization`) to also
diff:
- installed packages vs `profile.packages.{base,role,deny}`
- /etc/os-release ID vs `whitelabel.branding.os_id`
- /etc/hostname vs hostname declared in cloud-init
- active sovereign-osctl version vs profile.lifecycle.expected-osctl

### F-08 — HIGH — No first-time-on-machine onboarding path  ✅ **CLOSED (Round 138)**

`scripts/onboard.sh` shipped. 3-stage wrapper: (1) `setup.sh`
dev-environment validation, (2) `sovereign-osctl init` decision
wizard (R136), (3) `orchestrate.sh preflight` against the chosen
profile. Then prints the EXACT next-command block (run --dry-run →
real run → safety-gated install image). USEFUL OPERATOR VERBS
section enumerates env list / doctor / alerts / audit drift /
recover with one-line each. NONINTERACTIVE env honored for CI;
SOVEREIGN_OS_ONBOARD_SKIP_PREFLIGHT to fast-path re-runs. Idempotent.
17-assertion L3.

**Where**: README is generic. install-runbook is sain-01-specific.
Operator on a fresh laptop sees: "here's a build pipeline" but no
"here's what you decide first."

**Why it bites**: Repo discovery is friction. Operators bounce.

**Fix**: `scripts/onboard.sh` (NEW; parallels `scripts/setup.sh` for
dev-env) — runs `sovereign-osctl init` wizard + `make build` for the
chosen profile + tells operator what to do next.

### F-09 — MED — Hook authoring requires manual YAML editing  ✅ **CLOSED (Round 141)**

`sovereign-osctl hooks {list, add, remove}` shipped. `add` validates
stage (5-enum) + script exists + script executable + id pattern; refuses
duplicate id in same stage. `remove` is its inverse. Both preserve the
yaml-language-server header on the profile file. Round-trip (add then
remove) leaves the profile byte-equivalent for the relevant section
and schema-validates clean. 21-assertion L3.

**Where**: Operator wanting to add a post-install hook (e.g. "after
install, set up my dotfiles") edits the profile YAML manually.
Path-references can typo. No "register this hook" verb.

**Why it bites**: Operators familiar with the codebase do it fine;
new operators trip on the YAML schema.

**Fix**: `sovereign-osctl hooks add <stage> <script-path> [--mandatory]`
that updates the active profile YAML in-place + validates the path
exists + checks the script is executable.

### F-10 — LOW — Split log dirs between build-host and installed-system

**Where**: Build runs log to `~/.sovereign-os/log/build-<ts>.jsonl`.
Installed-system hooks log to `/var/log/sovereign-os/*.jsonl`.
`sovereign-osctl journal` falls through between them per R91 logic,
but operator who ran a build AND deployed sees logs in two places.

**Why it bites**: When debugging "why did X fail," operator may grep
the wrong dir.

**Fix**: `sovereign-osctl journal --all-dirs` flag that merges both
dirs into one chronological view.

### F-11 — MED — Decommission has no `--plan` preview  ✅ **CLOSED (Round 139)**

`sovereign-osctl decommission --plan` (alias `plan`) shipped. Shows
all 3 phases with the hook script · target identification · operation
description · live state check (zfs dataset/pool sizes when present) ·
invoke command. SOVEREIGN_OS_WIPE_DEVICES targets shown with
fingerprint when set; flagged as "NOT A BLOCK DEVICE" if invalid.
Writes nothing — no env-gate required because nothing is destroyed.
Parallels R134 `install image --plan` pattern.

**Where**: `sovereign-osctl decommission start` walks the operator
through 3 phases. Each requires explicit env var
(`SOVEREIGN_OS_CONFIRM_DESTROY=YES`). But there's no "show me
what THIS phase would do" preview.

**Why it bites**: Operator who fat-fingers the env var on the wrong
phase has just destroyed something. Even with the gate, no operator-
side rehearsal path.

**Fix**: `sovereign-osctl decommission --plan` shows the exact rm/zfs-
destroy/blkdiscard commands that WOULD execute (paths + sizes), does
not execute them, gives operator a chance to abort.

### F-12 — MED — No `profiles compare` verb  ✅ **CLOSED (Round 139)**

`sovereign-osctl profiles compare <a> <b>` shipped. Resolves both
profiles (mixin merge via `tools.profile_merger`) then emits unified
diff. Catches usage errors (1 arg → exit 2) and missing profiles
(→ exit 1 with clear error). Self-compare → exit 0 cleanly.

**Where**: 5 profiles. Operator wondering "what's different between
sain-01 and headless?" opens both YAMLs side-by-side manually.

**Why it bites**: Decision support is friction.

**Fix**: `sovereign-osctl profiles compare <a> <b>` that loads both
resolved profiles + emits a unified diff (yq-style) on the merged
output (so mixin contributions show as merged-in, not as inheritance
indirection).

### F-13 — CRIT — No documented recovery path for failed mid-pipeline  ✅ **CLOSED (Round 135)**

`scripts/build/orchestrate.sh recover` shipped (17-assertion L3). Reads
current state.yaml, identifies failed step + fail_reason, surfaces last
5 error/warn events from the JSONL log, presents 4 ranked next-action
options (a) fix+run, (b) rewind+run, (c) skip+run, (d) reset+run —
each with tradeoff rationale. Cross-references `sovereign-osctl
journal` for log inspection. install-runbook §5c documents the flow.

**Where**: If `orchestrate.sh run` fails at step 5 (substrate-prepare)
because mkosi.conf is broken, the operator runs `orchestrate.sh status`
and sees "5: failed". State persists. But the next operator action
isn't documented: do they `rewind 5`? Do they `skip 5`? Do they
fix the cause and re-run? Each has different consequences.

**Why it bites**: Operator stuck mid-build with no decision tree.

**Fix**: `sovereign-osctl recover` verb (or `orchestrate.sh recover`)
that reads the current state, inspects the failed step's log, and
SUGGESTS the operator next action: "step 5 failed with reason X;
fix the underlying issue THEN run `orchestrate.sh run` to retry, OR
`orchestrate.sh skip 5` if you want to bypass." Plus the install-
runbook needs an explicit "what to do when something fails" section.

## What's good (honest accounting both directions)

The codebase IS comprehensive. The operator who reads everything CAN
go end-to-end. The friction is in the DISCOVERY + DECISION-SUPPORT
layer, not in the underlying mechanisms.

Specifically working well:
- ✅ Build pipeline is resumable (state.yaml), drift-tolerant
  (inputs_hash), profile-aware (load_profile), and observable (JSONL +
  .prom emit on every step)
- ✅ Hardening IaC is real (5 server + 4 workstation drop-ins) with
  load-bearing invariants pinned in L1 lint
- ✅ Observability covers Layer A (journal) + B (metrics/alerts) + C
  (status/doctor) without ANY third-party dependency
- ✅ Reproducibility self-test gate (R84) proves byte-identical
  outputs under pinned inputs
- ✅ In-toto verifier triangle (manifest ↔ sums ↔ disk per R106)
- ✅ Decommission has 3 explicit confirmation gates
- ✅ All 7 SDD-007 whitelabel strategies implemented + test-pinned
- ✅ 17 real bugs caught + regression-gated by L1/L2/L3 tests
- ✅ Every SDD-stated invariant has a corresponding code guard
  (Learning 4 / R108)

The discipline is sound. What's missing is the operator-onboarding +
decision-support layer that wraps it.

## Severity rollup

- 2 CRIT (F-01 disk dump · F-13 mid-pipeline recovery)
- 3 HIGH (F-02 init wizard · F-03 env list · F-08 onboard.sh)
- 6 MED (F-04..F-07, F-09, F-11, F-12)
- 1 LOW (F-10 split log dirs)
- 1 MED (F-06 Layer 4 KVM — partial fix possible)

## Way forward

Operator can decide whether to close these in this session arc or
defer to a dedicated "operator-journey" phase. My recommendation:

  - Close F-01 + F-13 NEXT — both are CRIT and would cause real
    operator harm in their current state.
  - Defer the HIGH and MED ones to a dedicated arc if scope is right.
  - The wizards (F-02 / F-08) are not invention; they're operator
    productivity that the existing surface deserves.
  - The audit-customization extension (F-07) builds directly on R111
    drift work.

This document IS the deliverable: honest accounting of what the
operator hits when they actually USE sovereign-os, not the
codebase-internal view.
