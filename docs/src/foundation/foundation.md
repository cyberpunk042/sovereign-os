# Foundation tier (PRs 4–8)

Research + spec layer; decisions land here.

- **PR 4** — SDD-003 substrate survey → Stage Gate 2 (Q-001 + Q-016)
- **PR 5** — SDD-004 profile schema + formal JSON Schema → Gate 3 (Q-002)
- **PR 6** — Initial profile stubs (sain-01 + old-workstation) + 3 mixins + SDD-005
- **PR 7** — SDD-006 Debian surface audit (~50 surfaces; legal floor)
- **PR 8** — SDD-007 whitelabel mechanism (7-strategy taxonomy) → Gate 4 (Q-004)

## Stage Gate 2 — substrate decision

**Primary recommendation**: `mkosi` on Debian 13 Trixie. See [SDD-003 § Recommendation](https://github.com/cyberpunk042/sovereign-os/blob/main/docs/sdd/003-substrate-survey.md#recommendation--direct-stack-no-unifying-abstraction-for-sain-01).

## Stage Gate 3 — schema lock

Hybrid: single-parent inheritance + cross-cutting mixins. Substantively closed via `tools/profile_merger.py` + 18 passing tests. See [SDD-004 § Inheritance model](https://github.com/cyberpunk042/sovereign-os/blob/main/docs/sdd/004-profile-schema.md#inheritance-model-q-002-resolution).

## Stage Gate 4 — whitelabel mechanism + legal scope

7-strategy taxonomy. Legal-floor enforcement in `scripts/whitelabel/render.py` (5 fnmatch patterns).

| Strategy | When | Used for |
|---|---|---|
| `template-substitution` | pre-build | os-release, issue, lsb-release, motd |
| `file-overlay` | pre-build | Plymouth theme, GRUB theme, wallpapers |
| `package-replacement` | pre-build | desktop-base, Plymouth alternative |
| `build-time-flag` | pre-build | kernel KBUILD_BUILD_USER, CONFIG_LOCALVERSION |
| `install-time-substitution` | during-install | hostname preseed, installer banners |
| `first-boot-script` | post-install | dynamic motd, install-fingerprint |
| `must-not-touch` | validation | /etc/debian_version, /usr/share/doc/*/copyright, manpages, trademark assets |
