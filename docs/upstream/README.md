# Upstream issue drafts

Bugs found in third-party projects while running them here, written up as ready-to-file
issue text. Kept in-repo so the reproduction and measurements survive the session that
found them, and so the same bug is not re-discovered later.

**These are drafts, not filed issues.** Filing goes through the operator's own account:

```sh
gh auth login                                            # interactive, once
gh issue create --repo <upstream> --title "<title line>" \
                --body-file docs/upstream/<file>.md      # strip the Title: line first
```

| draft | upstream | status |
|---|---|---|
| [colibri-omp-cuda-gate.md](colibri-omp-cuda-gate.md) | [JustVugg/colibri](https://github.com/JustVugg/colibri) | **filed 2026-07-28 → [#669](https://github.com/JustVugg/colibri/issues/669)** |
| [anything-llm-open-computer-linux.md](anything-llm-open-computer-linux.md) | [Mintplex-Labs/anything-llm](https://github.com/Mintplex-Labs/anything-llm) | draft — not filed |

## anything-llm-open-computer-linux

Five defects that together make `open-computer` unusable on Debian/Ubuntu through its
documented path. Found while provisioning the SDD-706 sandbox on ai-workstation
(2026-07-30/31), all with host-side workarounds now carried in
[`scripts/iac/modules/60-open-computer.sh`](../../scripts/iac/modules/60-open-computer.sh).

What made this expensive to diagnose is worth noting for anyone who hits it: the VM
**looks healthy the entire time**. It boots to a full XFCE desktop, `sshd` logs
`Server listening on 0.0.0.0 port 22`, and the forwarded host ports accept TCP — because
QEMU's slirp accepts the connection itself before discovering the guest never got a DHCP
lease. Four hypotheses (corrupt image, mismatched pflash pair, a skipped `build` step,
then `build` being mandatory) were all wrong; the guest's own persistent journal settled
it in one line, comparing the image-build boot to ours:

```
2026-07-08 (upstream): virtio_net virtio0 enp0s1: renamed from eth0  -> DHCP, ssh OK
2026-07-30 (here):     virtio_net virtio0 enp0s2: renamed from eth0  -> nothing raised
```

The image pins `enp0s1` in `/etc/network/interfaces`, `enpXsY` encodes the PCI slot, and
`vm.ts` never pins one — so the image only works on the QEMU topology it was built
against.

## colibri-omp-cuda-gate

Colibri skips its OpenMP hot-thread tuning whenever `COLI_CUDA` is set
(`colibri.c:6282`), on the assumption that a CUDA build runs its expert matmuls on the
GPU. That assumption holds only when the expert bank fits VRAM. Measured here on
GLM-5.2 (383.7 GB int4) against 130.8 GB of VRAM: only **7,094 of 19,456 experts** are
resident, and `PROF=1` shows **routed CPU 10.793s of a 30.7s decode** — running untuned,
because `COLI_CUDA=1` was set.

The draft is deliberately honest about its weak point: applying the tuning by hand did
**not** produce a clear win in this configuration (the apparent 1.17× was disk-wait
variance, and `expert-matmul` itself got slightly worse). So it is reported as a **wrong
gating condition** — the premise is measurably false above VRAM size — rather than as a
proven regression. Full context:
[`docs/evaluations/chromofold-fold-measurement-glm52-2026-07-27.md`](../evaluations/chromofold-fold-measurement-glm52-2026-07-27.md).
