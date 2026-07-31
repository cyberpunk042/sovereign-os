**Title:** open-computer is unusable on Debian/Ubuntu: non-executable build output, Alpine-only firmware paths, a NIC name the guest pins but the host never guarantees, and a LAN-exposed hostfwd

---

### Summary

Bringing `open-computer/` up on Ubuntu 26.04 (QEMU 10.2.1, Node 22, OVMF
2025.11) hit five separate defects. Each is small; together they make the
documented path (`open-computer create <name>` → `http://localhost:9800`)
impossible to complete on the two most common Linux distributions, and the
failures are unusually hard to read because the VM *looks* healthy throughout —
it boots to a full XFCE desktop with the AnythingLLM wallpaper while nothing is
reachable.

All five have host-side workarounds, given below. Reproduced twice from a clean
sparse clone.

---

### 1. `npm run build` writes `cli/dist/open-computer` without the execute bit

```bash
git clone --filter=blob:none --sparse https://github.com/Mintplex-Labs/anything-llm src
git -C src sparse-checkout set open-computer
cd src/open-computer/cli && npm install && npm run build
```

Both steps succeed with no warnings, and the artefact appears:

```
$ ls -l dist/open-computer
-rw-rw-r-- 1 user user 156876 dist/open-computer     # not executable

$ ls -l ../open-computer
lrwxrwxrwx ../open-computer -> cli/dist/open-computer

$ ../open-computer --help
bash: ../open-computer: Permission denied
```

`cli/package.json` declares `"bin": {"open-computer": "./dist/open-computer"}`,
and npm sets the execute bit on `bin` targets during install — which masks this
in the `npm i -g` path. It surfaces for anyone building from the repo and
invoking the tree-local wrapper, which the layout (top-level symlink +
`open-computer.cmd`) invites.

It is also self-blocking: `open-computer-install`-style flows that gate on
`[ -x .../open-computer ]` conclude the build never happened, re-clone and
rebuild, land 0664 again, and never converge — with no error anywhere, because
the build genuinely succeeded.

**Fix:** `chmodSync(outFile, 0o755)` after writing the bundle in
`cli/build.mjs`. esbuild does not set a mode for generated executables.

---

### 2. EFI firmware paths assume the upstream/Alpine layout

`cli/src/config.ts`, on Linux with no `QEMU_DIST`:

```
resolveEfiCode() -> /usr/share/qemu/edk2-x86_64-code.fd
resolveEfiVars() -> /usr/share/qemu/edk2-i386-vars.fd
```

Debian and Ubuntu ship the same firmware under different names in a different
directory (package `ovmf`):

```
/usr/share/OVMF/OVMF_CODE_4M.fd      (CODE, read-only pflash)
/usr/share/OVMF/OVMF_VARS_4M.fd      (VARS, writable variable store)
```

so the VM never starts:

```
qemu-system-x86_64: -drive if=pflash,...,file=/usr/share/qemu/edk2-x86_64-code.fd:
  Could not open '/usr/share/qemu/edk2-x86_64-code.fd': No such file or directory
Failed to start QEMU.
```

`OPEN_COMPUTER_QEMU_DIR` is a workable escape hatch (a shim directory of
symlinks named the way `config.ts` expects), but out of the box the sandbox is
unbootable on Debian/Ubuntu.

**Fix:** probe a candidate list rather than one hardcoded path — 
`/usr/share/qemu/edk2-x86_64-code.fd`, then `/usr/share/OVMF/OVMF_CODE_4M.fd`,
then `/usr/share/ovmf/OVMF.fd` — pairing the VARS lookup the same way. QEMU also
publishes firmware descriptors in `/usr/share/qemu/firmware/*.json` that encode
the correct per-distro paths, if a single source of truth is preferred.

---

### 3. `vm.ts` copies the CODE firmware into the VARS pflash on non-Windows

`cli/src/vm.ts:119`:

```js
fs.copyFileSync(PLATFORM === 'win32' ? resolveEfiVars() : efiCode, efi);
```

On Windows this correctly seeds the per-VM variable store from the VARS
template. On Linux/macOS it copies `efiCode` — the read-only CODE firmware —
into the writable vars slot.

That is precisely the failure `cli/src/config.test.ts` documents:

> "The blank-display bug was caused by copying the OVMF CODE firmware into the
> writable vars pflash. These tests pin the correct VARS template per guest arch."

It only spared us because `efi-vars.fd` already existed from the base-image
tarball, so the `if (!fs.existsSync(efi))` guard skipped it. A fresh agent on a
clean host should hit it.

**Fix:** use `resolveEfiVars()` on every platform.

---

### 4. The base image pins a literal NIC name the host never guarantees

The costliest of the five, because everything looks healthy: the guest boots to
a full XFCE desktop, `sshd` logs `Server listening on 0.0.0.0 port 22`, and the
host-side forwarded ports accept connections. Nothing is reachable.

The base image's `/etc/network/interfaces`:

```
allow-hotplug enp0s1
iface enp0s1 inet dhcp
```

with ifupdown as its only network manager (no NetworkManager, netplan or
systemd-networkd). `enpXsY` encodes PCI **bus and slot**, so the interface name
depends entirely on where QEMU puts the NIC — and `cli/src/vm.ts` passes
`-device virtio-net-pci` with no `addr=`, leaving the slot to QEMU.

On the machine that built the image the NIC landed on slot 1. Here it lands on
slot 2, because QEMU auto-adds a default VGA at slot 1:

```
$ qemu-system-x86_64 -machine q35 -device virtio-net-pci,addr=0x1 ...
PCI: slot 1 function 0 not available for virtio-net-pci, in use by VGA
```

The guest's own persistent journal, image-build boot vs. ours:

```
2026-07-08 (upstream): virtio_net virtio0 enp0s1: renamed from eth0  -> ifup, DHCP lease, ssh OK
2026-07-30 (here):     virtio_net virtio0 enp0s2: renamed from eth0  -> nothing raised
```

With no stanza matching `enp0s2`, `networking.service` reports success having
configured nothing, the guest never leases `10.0.2.15`, and slirp forwards into
the void:

```
Connection established.
Local version string SSH-2.0-OpenSSH_10.2p1
Connection timed out during banner exchange
```

Note it **hangs** rather than being refused — slirp accepts the host-side TCP
before discovering nothing is behind it, so a plain `connect()` reports the
guest as reachable when it is not. Any health check using a bare TCP probe will
report a false positive here.

**Workaround** (A/B tested — control fails, this succeeds):

```
-vga none                                    # frees PCI slot 1
-device virtio-net-pci,netdev=net0,addr=0x1  # NIC lands there -> enp0s1
```

then `enp0s1 UP 10.0.2.15/24`, SSH answers, and
ssh/open-computer/memory-manager all report active.

**Fix:** either pin the NIC slot in `vm.ts` so the name the image expects is
guaranteed, or make the image name-agnostic (a systemd-networkd
`[Match] Name=en*` unit, or additional ifupdown stanzas). The second is more
robust — it survives any host whose PCI topology differs, including future QEMU
versions that shuffle default devices again.

---

### 5. `hostfwd` binds 0.0.0.0, exposing the sandbox to the whole LAN

`cli/src/vm.ts:122`:

```js
let netdev = `user,id=net0,hostfwd=tcp::${sshPort}-:22`;
// …
netdev += `,hostfwd=tcp::${appPort}-:8080`;
```

`hostfwd=tcp::PORT` with an empty host address binds **every** interface. On a
host with a LAN address the guest's SSH and desktop become reachable from every
machine on the network:

```
$ ss -ltn | grep -E ':9800|:2222'
LISTEN 0 1 0.0.0.0:2222 0.0.0.0:*
LISTEN 0 1 0.0.0.0:9800 0.0.0.0:*
```

The bind address is not parameterised anywhere in `cli/src`, so there is no way
to narrow it via configuration.

For a VM whose purpose is running autonomous agent activity, with SSH
forwarded, defaulting to LAN-wide exposure is surprising.

**Fix:** default to `hostfwd=tcp:127.0.0.1:${port}-:...` and expose the bind
address as an option/env var for operators who deliberately want wider reach.

---

### Environment

- Ubuntu 26.04 (kernel 7.0.0-28-generic), x86_64
- QEMU 10.2.1, OVMF 2025.11, Node v22.22.1, npm 9.2.0
- base image `06_08_2026/x64-base-image.tar` (sha256 verified)
- Reproduced twice from a clean sparse clone
