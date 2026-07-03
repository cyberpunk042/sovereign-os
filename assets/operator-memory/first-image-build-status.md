---
name: first-image-build-status
description: "First sain-01 image built+verified 2026-06-10; what's proven, what remains (DKMS module signing under SB, consolidation pass)"
metadata: 
  node_type: memory
  type: project
  originSessionId: ec0b95b5-4599-4a88-a259-5c7079c80ec0
---

2026-06-10: the FIRST sovereign-os image ever built went green end-to-end
(all 9 orchestrate.sh steps): custom znver5 kernel (6.12.0, no avx512_fp16 —
Zen 5 lacks it), nvidia+zfs DKMS built in-image, UKI `EFI/Linux/debian-6.12.0.efi`
+ systemd-boot signed by the operator MOK (/etc/sovereign-os/keys/), verified
by step 08's loop-mount sbverify. ~12 build-loop bugs fixed that session, all
documented in-code with "first real build 2026-06-10" comments.

Open items after the green run:
- **DKMS modules are signed by the image's ephemeral /var/lib/dkms key, NOT
  the operator MOK.** Shimless direct-boot chain → mokutil enrollment is NOT
  available → under enforcing Secure Boot nvidia/zfs modules will be REJECTED.
  First hardware boots should run SB disabled; fix = dkms framework.conf
  pointing at operator key (sovereignty decision) or enroll dkms pub in db.auth.
- Consolidation pass promised: forge old-revision deb cleanup (accumulates
  per rebuild), qemu smoke needs console=ttyS0 + proper OVMF pflash pair
  (current warn is a false negative), profile placeholder header removal,
  reset-to-green clean-slate rebuild proof.
- Host machine IS the SAIN-01 hardware on plain Debian 13 (ProArt X870E,
  9900X, PRO 6000 Max-Q 300W [[sain-01-gpu-config]], 4090 @ 320W cap, BIOS
  2202, IOMMU groups 14/16 clean). selfdef checkout was 5 commits behind.
- Operator's 16GB USB key = /dev/sda (14.4G DataTraveler) → root SizeMinBytes
  lowered 16G→8G so the image fits install media.
