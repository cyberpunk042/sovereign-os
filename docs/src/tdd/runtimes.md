# chroot · nspawn · QEMU runtimes

Virtualization stack per test layer.

## chroot — filesystem-level assertions

```sh
chroot $ROOT dpkg -l <package>          # package presence
[ -f $ROOT/etc/os-release ]              # file presence
grep -q 'ID=sovereign' $ROOT/etc/os-release   # content
```

Used in Layer 3 for: pre-install package set + whitelabel surface verification.

## systemd-nspawn — service-startup assertions

```sh
systemd-nspawn -D $ROOT systemctl is-active tetragon
systemd-nspawn -D $ROOT zpool status tank
```

Used in Layer 3 for: inter-service ordering invariants (Tetragon before podman; ZFS before tank/* mounts); Tetragon TracingPolicy load + test syscall.

## QEMU — full boot

```sh
qemu-system-x86_64 -m 8G -enable-kvm \
  -drive file=image.img,format=raw,if=virtio \
  -snapshot \
  -nographic -no-reboot
```

Used in Layer 4 for: full boot through firmware → kernel → initramfs → systemd → login. Inside-VM smoke runs once guest-agent ships.

## qemu-user (deferred)

Out of scope for sain-01 + old-workstation (both x86_64). Relevant only if a future profile targets non-amd64.

## CI runner requirements

- Layer 1/2: stock `ubuntu-latest`
- Layer 3 chroot: works on any runner
- Layer 3 nspawn: needs `systemd-container` + `unshare` (operator may need cap-add)
- Layer 4 QEMU: KVM-enabled runner preferred; falls back to TCG emulation (slower)
- Layer 5: bare-metal SAIN-01 only; never CI
