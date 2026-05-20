# M081 — Whitelabel Architecture — Debian surface audit + declarative rebrand mechanism

**Parent**: sovereign-os runtime — image-build + brand-identity discipline
**Source**: `~/infohub/raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md`
- **PR 7 — Whitelabel Audit SDD** (lines 174–199) — `docs/sdd/006-debian-surface-audit.md` exhaustive inventory
- **PR 8 — Whitelabel Mechanism SDD** (lines 202–227) — `docs/sdd/007-whitelabel-mechanism.md` + `schemas/whitelabel.schema.yaml`
- **Stage Gate 4** (lines 222–224) — operator reviews audit + mechanism together; brand name optional defer
- **PR 7 LOC estimate**: ~950 / **PR 8 LOC estimate**: ~900
**Operator standing direction** (verbatim, 2026-05-19): *"the two ultimate solutions and their perfectioning and high UX/Developer Experience"* / *"over 20 dashboards and a main one and everything can be turned on and off"* / *"DO NOT MINIMIZE WHAT I SAY, SAID OR ASKED FOR"*
**Project boundary**: sovereign-os ONLY — IPS (selfdef) is brand-neutral (operator-facing surface only mentions "selfdef IPS"); sovereign-os is the whitelabel-capable runtime + image-build identity layer

## Doctrinal anchors

> "Survey/audit only. Identifies every place 'Debian' surfaces in a default Debian 13 system. No rebranding mechanism yet." (macro-arc dump 178)
> "Each surface categorized: must-rebrand, should-rebrand, may-leave, must-not-touch (legal/license obligations — Debian trademark, GPL attribution, etc.)." (macro-arc dump 191)
> "Mechanism shape: declarative whitelabel-profile YAML referenced by main profiles" (macro-arc dump 208)
> "Per-surface strategy: template-substitution vs file-overlay vs package-replacement vs build-time-flag." (macro-arc dump 210)
> "Evolvability: how a whitelabel can be swapped without re-building the entire image (where possible)." (macro-arc dump 212)
> "Legal compliance binding: enforce the 'must-not-touch' list from PR 7 at validation time." (macro-arc dump 213)

## Projection statement

Sovereign-OS is built on Debian 13 (substrate decision per M064). Every default Debian system surfaces the word "Debian" in dozens of places — `/etc/os-release`, DPKG vendor strings, GRUB theme, GDM splash, kernel `/proc/version`, man-page references. The Whitelabel Architecture is the **declarative, per-profile, evolvable** mechanism that transforms a Debian-branded image into a sovereign-branded image (or any operator-chosen brand), while **respecting Debian's trademark + DFSG legal obligations** through a `must-not-touch` enforcement list. The audit (PR 7) is the structural inventory — every surface enumerated, categorized, legal-anchored. The mechanism (PR 8) is the rendering engine — declarative YAML schema, per-surface strategy (template-substitution, file-overlay, package-replacement, build-time-flag), and pre/during/post-build lifecycle staging. This milestone catalogues BOTH because they form one logical contract (Stage Gate 4 reviews them together).

## Epics (E0778-E0787)

| epic | name | source |
|---|---|---|
| E0778 | Debian surface audit — exhaustive inventory of every "Debian" reference in default install | macro-arc 180–189 |
| E0779 | Surface categorization taxonomy — must-rebrand / should-rebrand / may-leave / must-not-touch | macro-arc 191 |
| E0780 | Legal-obligation section — Debian trademark + DFSG + GPL attribution requirements | macro-arc 192 |
| E0781 | Whitelabel profile schema — declarative YAML referenced by main profiles | macro-arc 208 |
| E0782 | Per-surface rendering strategies — template-substitution / file-overlay / package-replacement / build-time-flag | macro-arc 210 |
| E0783 | Lifecycle staging — pre-build patches / install-time substitutions / first-boot scripts | macro-arc 211 |
| E0784 | Evolvability — swap whitelabel without re-building full image where possible | macro-arc 212 |
| E0785 | Legal-compliance validator — enforce must-not-touch list at validation time | macro-arc 213 |
| E0786 | Default whitelabel placeholder — no brand committed; operator decides later | macro-arc 217 |
| E0787 | Stage Gate 4 — operator reviews audit + mechanism together; brand-name commit optional | macro-arc 222–224 |

## Modules (M01343-M01368)

| module | name | source |
|---|---|---|
| M01343 | sovereign-whitelabel-audit-inventory (filesystem surfaces enumerator) | macro-arc 181 |
| M01344 | sovereign-whitelabel-audit-package-mgr (DPKG vendor / APT sources / dpkg-vendor / lsb_release) | macro-arc 182 |
| M01345 | sovereign-whitelabel-audit-boot (GRUB theme + Plymouth + kernel boot logo + systemd boot banner) | macro-arc 183 |
| M01346 | sovereign-whitelabel-audit-installer (debian-installer / Calamares / preseed banner) | macro-arc 184 |
| M01347 | sovereign-whitelabel-audit-desktop (GDM/SDDM/LightDM + default wallpaper + GNOME/KDE about) | macro-arc 185 |
| M01348 | sovereign-whitelabel-audit-kernel (/proc/version + uname-a + kernel package naming) | macro-arc 186 |
| M01349 | sovereign-whitelabel-audit-docs (man pages + /usr/share/doc/ + default README) | macro-arc 187 |
| M01350 | sovereign-whitelabel-audit-network (hostname pattern + NTP/DNS pool + APT mirror) | macro-arc 188 |
| M01351 | sovereign-whitelabel-audit-telemetry (popcon / apport / phone-home defaults) | macro-arc 189 |
| M01352 | sovereign-whitelabel-audit-categorizer (assigns each surface to one of 4 categories) | macro-arc 191 |
| M01353 | sovereign-whitelabel-audit-legal-section (Debian trademark + DFSG + GPL attribution) | macro-arc 192 |
| M01354 | sovereign-whitelabel-schema (`schemas/whitelabel.schema.yaml` formal schema) | macro-arc 216 |
| M01355 | sovereign-whitelabel-profile-loader (loads whitelabel YAML referenced by main profile) | macro-arc 208 |
| M01356 | sovereign-whitelabel-rendering-engine (consumes whitelabel + targets surfaces) | macro-arc 209 |
| M01357 | sovereign-whitelabel-strategy-router (per-surface strategy picker) | macro-arc 210 |
| M01358 | sovereign-whitelabel-template-substitutor (Jinja2-like template engine for text-file surfaces) | macro-arc 210 |
| M01359 | sovereign-whitelabel-file-overlayer (drop-in file overlay onto chroot) | macro-arc 210 |
| M01360 | sovereign-whitelabel-package-replacer (alt-package substitution at apt install time) | macro-arc 210 |
| M01361 | sovereign-whitelabel-build-time-flag-injector (build-script env-var passthrough) | macro-arc 210 |
| M01362 | sovereign-whitelabel-lifecycle-stager (pre / during / post-install staging) | macro-arc 211 |
| M01363 | sovereign-whitelabel-evolvability-engine (live-swap subset for evolvable surfaces) | macro-arc 212 |
| M01364 | sovereign-whitelabel-legal-validator (enforces must-not-touch at validate-time) | macro-arc 213 |
| M01365 | sovereign-whitelabel-default-profile (`whitelabel/default.yaml` placeholder, brand TBD) | macro-arc 217 |
| M01366 | sovereign-whitelabel-index (`whitelabel/INDEX.md` enumerates available whitelabels) | macro-arc 218 |
| M01367 | sovereign-whitelabel-cli (`sovereign whitelabel audit | apply | swap | validate`) | derived from M060 cockpit |
| M01368 | sovereign-whitelabel-cockpit-binding (M060 dashboard panel surfaces active whitelabel + audit verdict) | cross-ref M060 |

## Features (F06716-F06835)

| feature | name | source |
|---|---|---|
| F06716 | `/etc/issue` surface enumerated as must-rebrand | macro-arc 181 |
| F06717 | `/etc/issue.net` surface enumerated as must-rebrand | macro-arc 181 |
| F06718 | `/etc/os-release` surface enumerated as must-rebrand | macro-arc 181 |
| F06719 | `/etc/lsb-release` surface enumerated as must-rebrand | macro-arc 181 |
| F06720 | `/etc/debian_version` surface enumerated as may-leave (operator decides per legal) | macro-arc 181 + legal |
| F06721 | `/etc/motd` surface enumerated as must-rebrand | macro-arc 181 |
| F06722 | `/usr/lib/os-release` surface enumerated as must-rebrand | macro-arc 181 |
| F06723 | DPKG vendor string surface enumerated as should-rebrand | macro-arc 182 |
| F06724 | APT sources header surface enumerated as should-rebrand | macro-arc 182 |
| F06725 | `dpkg-vendor` output surface enumerated as should-rebrand | macro-arc 182 |
| F06726 | `lsb_release` output surface enumerated as should-rebrand | macro-arc 182 |
| F06727 | GRUB theme directory surface enumerated as should-rebrand | macro-arc 183 |
| F06728 | GRUB menu entry titles surface enumerated as should-rebrand | macro-arc 183 |
| F06729 | Plymouth boot splash surface enumerated as should-rebrand | macro-arc 183 |
| F06730 | Kernel boot logo surface enumerated as should-rebrand | macro-arc 183 |
| F06731 | systemd boot banner surface enumerated as should-rebrand | macro-arc 183 |
| F06732 | debian-installer branding surface enumerated as should-rebrand (if substrate uses d-i) | macro-arc 184 |
| F06733 | Calamares branding surface enumerated as should-rebrand (if substrate uses Calamares) | macro-arc 184 |
| F06734 | preseed banner text surface enumerated as may-leave | macro-arc 184 |
| F06735 | GDM theming surface enumerated as should-rebrand | macro-arc 185 |
| F06736 | SDDM theming surface enumerated as should-rebrand | macro-arc 185 |
| F06737 | LightDM theming surface enumerated as should-rebrand | macro-arc 185 |
| F06738 | Default wallpaper surface enumerated as must-rebrand | macro-arc 185 |
| F06739 | GNOME "About System" dialog surface enumerated as should-rebrand | macro-arc 185 |
| F06740 | KDE "About System" dialog surface enumerated as should-rebrand | macro-arc 185 |
| F06741 | `/proc/version` string surface enumerated as may-leave (compile-time, GPL attribution friction) | macro-arc 186 + legal |
| F06742 | `uname -a` fields surface enumerated as may-leave | macro-arc 186 |
| F06743 | Kernel package naming surface enumerated as should-rebrand | macro-arc 186 |
| F06744 | Man pages referencing Debian surface enumerated as may-leave (preserve attribution) | macro-arc 187 + legal |
| F06745 | `/usr/share/doc/` surface enumerated as must-not-touch (license obligations) | macro-arc 187 + 192 |
| F06746 | Default README files surface enumerated as should-rebrand | macro-arc 187 |
| F06747 | Default hostname pattern surface enumerated as must-rebrand (sovereign-NN) | macro-arc 188 |
| F06748 | NTP pool surface enumerated as should-rebrand (operator-chosen NTP) | macro-arc 188 |
| F06749 | DNS pool surface enumerated as should-rebrand (operator-chosen resolver) | macro-arc 188 |
| F06750 | Default APT mirror surface enumerated as should-rebrand (operator-chosen mirror) | macro-arc 188 |
| F06751 | popcon (popularity-contest) surface enumerated as must-rebrand-or-disable | macro-arc 189 |
| F06752 | apport surface enumerated as must-rebrand-or-disable | macro-arc 189 |
| F06753 | Phone-home defaults enumerated as must-disable | macro-arc 189 |
| F06754 | Surface category — **must-rebrand** — non-functional surface visible to operator; brand-replacement REQUIRED | macro-arc 191 |
| F06755 | Surface category — **should-rebrand** — operator-visible but minor; brand-replacement RECOMMENDED | macro-arc 191 |
| F06756 | Surface category — **may-leave** — leaving Debian acceptable; trademark gray zone | macro-arc 191 |
| F06757 | Surface category — **must-not-touch** — legal obligation prevents modification (license/attribution/trademark) | macro-arc 191 |
| F06758 | Legal section — Debian Trademark Policy citation (debian.org/trademark) | macro-arc 192 + legal |
| F06759 | Legal section — DFSG attribution requirements citation | macro-arc 192 + legal |
| F06760 | Legal section — GPL §2 binary distribution attribution citation | macro-arc 192 + legal |
| F06761 | Legal section — Debian Free Software Guidelines whitelabel-derivative obligations | macro-arc 192 + legal |
| F06762 | Legal section — citation-grade format (URL + retrieved date + section anchor) | macro-arc 192 |
| F06763 | Audit deliverable — `docs/sdd/006-debian-surface-audit.md` (~900 LOC target) | macro-arc 196 |
| F06764 | Audit deliverable — markdown table per surface category with rendering strategy column | macro-arc 191 + 210 |
| F06765 | Audit deliverable — cross-reference column to mechanism strategy (F06778–F06781) | macro-arc 210 |
| F06766 | Mechanism shape — declarative whitelabel-profile YAML | macro-arc 208 |
| F06767 | Mechanism shape — referenced by main profiles via `profile.whitelabel: <whitelabel-name>` | macro-arc 208 |
| F06768 | Mechanism shape — rendering engine consumes whitelabel + targets surfaces from audit | macro-arc 209 |
| F06769 | Per-surface strategy — **template-substitution** — Jinja2-like text substitution for `*.conf` text surfaces | macro-arc 210 |
| F06770 | Per-surface strategy — **file-overlay** — drop-in file replacement (binary safe — logos, wallpapers, fonts) | macro-arc 210 |
| F06771 | Per-surface strategy — **package-replacement** — substitute alt-branded package at apt install time | macro-arc 210 |
| F06772 | Per-surface strategy — **build-time-flag** — env-var passthrough to upstream build scripts | macro-arc 210 |
| F06773 | Per-surface strategy — justification REQUIRED per surface (mechanism doc explains why one strategy over another) | macro-arc 210 |
| F06774 | Lifecycle — **pre-build patches** — applied to source tree before live-build runs | macro-arc 211 |
| F06775 | Lifecycle — **install-time substitutions** — applied during chroot package installation | macro-arc 211 |
| F06776 | Lifecycle — **first-boot scripts** — applied via /etc/rc.firstboot.d or systemd first-boot unit | macro-arc 211 |
| F06777 | Lifecycle — per-stage manifest documents which surfaces are touched at which stage | macro-arc 211 |
| F06778 | Evolvability — first-boot whitelabels can be swapped post-install via `sovereign whitelabel swap <name>` | macro-arc 212 + M01367 |
| F06779 | Evolvability — pre-build whitelabels REQUIRE full image rebuild (documented constraint) | macro-arc 212 |
| F06780 | Evolvability — install-time whitelabels swappable on next package upgrade (degraded — banner shows mixed-state) | macro-arc 212 |
| F06781 | Evolvability — operator sees current-vs-target whitelabel diff in M060 cockpit panel | F06778 + cross-ref M060 |
| F06782 | Legal-compliance binding — must-not-touch list from PR 7 enforced at validation | macro-arc 213 |
| F06783 | Legal-compliance binding — validation rejects whitelabel YAML that touches must-not-touch surface | macro-arc 213 |
| F06784 | Legal-compliance binding — validation emits diagnostic with cited legal section | macro-arc 192 + 213 |
| F06785 | Legal-compliance binding — operator override REQUIRES legal-team sign-off (manifest with `legal_review_kid`) | macro-arc 213 + arch |
| F06786 | Schema deliverable — `schemas/whitelabel.schema.yaml` (~200 LOC) | macro-arc 216 |
| F06787 | Schema fields — `name`, `version`, `surfaces` map, `strategy_overrides`, `legal_review_kid` (optional) | macro-arc 208 + 216 |
| F06788 | Schema validation — `surfaces` map keys MUST match the audit inventory (no surface unknown to PR 7) | macro-arc 208 + 213 |
| F06789 | Schema validation — every surface assignment carries a strategy + lifecycle stage | macro-arc 210 + 211 |
| F06790 | Schema validation — must-not-touch surfaces auto-rejected even if listed in YAML | macro-arc 213 |
| F06791 | Default whitelabel deliverable — `whitelabel/default.yaml` placeholder | macro-arc 217 |
| F06792 | Default whitelabel — brand name field is EXPLICIT `<<TBD-OPERATOR-DECISION>>` | macro-arc 217 |
| F06793 | Default whitelabel — palette field is EXPLICIT `<<TBD-OPERATOR-DECISION>>` | macro-arc 217 |
| F06794 | Default whitelabel — logo field is EXPLICIT `<<TBD-OPERATOR-DECISION>>` | macro-arc 217 |
| F06795 | Default whitelabel — passes schema validation despite placeholder fields (placeholders are valid) | macro-arc 217 |
| F06796 | INDEX deliverable — `whitelabel/INDEX.md` enumerates available whitelabel profiles | macro-arc 218 |
| F06797 | INDEX deliverable — row per whitelabel with name, version, last-audit-date, legal-review status | macro-arc 218 + 192 |
| F06798 | Mechanism deliverable — `docs/sdd/007-whitelabel-mechanism.md` (~600 LOC) | macro-arc 220 |
| F06799 | Mechanism document — section 1: declarative shape + rendering pipeline diagram | macro-arc 208–209 |
| F06800 | Mechanism document — section 2: per-surface strategies (4 strategies, justification per surface) | macro-arc 210 |
| F06801 | Mechanism document — section 3: lifecycle stages + manifest format | macro-arc 211 |
| F06802 | Mechanism document — section 4: evolvability rules + degraded-state UX | macro-arc 212 + F06781 |
| F06803 | Mechanism document — section 5: legal-compliance enforcement + override path | macro-arc 213 + F06785 |
| F06804 | Stage Gate 4 — operator reviews PR 7 + PR 8 together (not independently) | macro-arc 222 |
| F06805 | Stage Gate 4 — operator confirms legal posture before brand commit | macro-arc 223 |
| F06806 | Stage Gate 4 — operator optionally supplies brand identity (name, palette, logo) | macro-arc 224 |
| F06807 | Stage Gate 4 — operator may defer brand commit to later PR (placeholder ok) | macro-arc 224 |
| F06808 | Stage Gate 4 — gate output recorded in `docs/decisions/sg4-whitelabel-review-<YYYY-MM-DD>.md` | macro-arc 323+ + arch |
| F06809 | CLI — `sovereign whitelabel audit` — re-runs audit, shows surface diff vs last run | M01367 |
| F06810 | CLI — `sovereign whitelabel apply <name>` — applies whitelabel at current lifecycle stage | M01367 |
| F06811 | CLI — `sovereign whitelabel swap <new-name>` — swaps active whitelabel for evolvable surfaces | M01367 + F06778 |
| F06812 | CLI — `sovereign whitelabel validate <yaml>` — runs schema + legal validation, exits non-zero on issues | M01367 + F06782 |
| F06813 | CLI — `sovereign whitelabel diff <a> <b>` — surface-level diff between two whitelabels | M01367 + UX |
| F06814 | CLI — `sovereign whitelabel show` — displays active whitelabel with brand, palette, lifecycle stage | M01367 + UX |
| F06815 | CLI — `--json` flag returns structured output (cross-ref MS043 R10131 convention) | M01367 + cross-ref selfdef MS043 |
| F06816 | CLI — startup p95 ≤ 50 ms (cross-ref MS043 R10137 convention) | M01367 + cross-ref selfdef MS043 |
| F06817 | Cockpit binding — M060 dashboard panel surfaces active whitelabel name | M01368 + cross-ref M060 |
| F06818 | Cockpit binding — palette swatch row (4 colors visible) | M01368 + UX |
| F06819 | Cockpit binding — logo preview thumbnail | M01368 + UX |
| F06820 | Cockpit binding — surface coverage row (audited vs rendered count) | M01368 + UX |
| F06821 | Cockpit binding — legal review row (Yes/No/Expired with timestamp) | M01368 + F06797 |
| F06822 | Cockpit binding — last audit date row (warns if > 90 days) | M01368 + ops |
| F06823 | Cockpit binding — last validate verdict row (Pass/Fail with diagnostic link) | M01368 + F06812 |
| F06824 | Cockpit binding — last swap timestamp row | M01368 + F06811 |
| F06825 | Cockpit binding — mixed-state banner if install-time + first-boot surfaces drift | M01368 + F06780 |
| F06826 | Cockpit binding — read-only — no whitelabel mutation from cockpit | M01368 + safety |
| F06827 | Cockpit binding — operator confirms whitelabel swap from cockpit via signed action gate | M01368 + cross-ref selfdef MS003 |
| F06828 | Test contract — schema validation tests via PR 9 TDD harness (L1) | macro-arc 230–235 |
| F06829 | Test contract — must-not-touch enforcement tested under L2 (mocked filesystem) | macro-arc 232 + F06782 |
| F06830 | Test contract — apply mechanism tested under L3 (chroot acceptance) | macro-arc 233 + F06810 |
| F06831 | Test contract — swap mechanism tested under L3 (chroot + service restart) | macro-arc 233 + F06811 |
| F06832 | Test contract — full image boot test (L4 QEMU smoke) verifies surface coverage | macro-arc 234 + F06820 |
| F06833 | Test contract — hardware-conformance test (L5) verifies wallpaper + GRUB on actual hw | macro-arc 235 |
| F06834 | Test contract — flake policy: 3 consecutive failures → block release; 1 failure → retry once | macro-arc 240+ |
| F06835 | Test contract — every audit row has at least one assertion in PR 9 harness | F06763 + macro-arc 230 |

## Requirements (R13431-R13670)

| req | name | source |
|---|---|---|
| R13431 | Audit deliverable — `docs/sdd/006-debian-surface-audit.md` exists in repo | macro-arc 196 |
| R13432 | Audit deliverable — total LOC ≈ 950 ± 10% | macro-arc 199 |
| R13433 | Audit enumerates `/etc/issue` with category + strategy + lifecycle stage | F06716 + macro-arc 181 |
| R13434 | Audit enumerates `/etc/issue.net` | F06717 |
| R13435 | Audit enumerates `/etc/os-release` | F06718 |
| R13436 | Audit enumerates `/etc/lsb-release` | F06719 |
| R13437 | Audit enumerates `/etc/debian_version` | F06720 |
| R13438 | Audit enumerates `/etc/motd` | F06721 |
| R13439 | Audit enumerates `/usr/lib/os-release` | F06722 |
| R13440 | Audit enumerates DPKG vendor string | F06723 |
| R13441 | Audit enumerates APT sources header | F06724 |
| R13442 | Audit enumerates `dpkg-vendor` output | F06725 |
| R13443 | Audit enumerates `lsb_release` output | F06726 |
| R13444 | Audit enumerates GRUB theme directory | F06727 |
| R13445 | Audit enumerates GRUB menu entry titles | F06728 |
| R13446 | Audit enumerates Plymouth boot splash | F06729 |
| R13447 | Audit enumerates kernel boot logo | F06730 |
| R13448 | Audit enumerates systemd boot banner | F06731 |
| R13449 | Audit enumerates debian-installer branding (conditional on d-i substrate) | F06732 + M064 |
| R13450 | Audit enumerates Calamares branding (conditional on Calamares substrate) | F06733 + M064 |
| R13451 | Audit enumerates preseed banner text | F06734 |
| R13452 | Audit enumerates GDM theming | F06735 |
| R13453 | Audit enumerates SDDM theming | F06736 |
| R13454 | Audit enumerates LightDM theming | F06737 |
| R13455 | Audit enumerates default wallpaper | F06738 |
| R13456 | Audit enumerates GNOME "About System" dialog | F06739 |
| R13457 | Audit enumerates KDE "About System" dialog | F06740 |
| R13458 | Audit enumerates `/proc/version` string | F06741 |
| R13459 | Audit enumerates `uname -a` fields | F06742 |
| R13460 | Audit enumerates kernel package naming convention | F06743 |
| R13461 | Audit enumerates Debian-referencing man pages | F06744 |
| R13462 | Audit enumerates `/usr/share/doc/` (must-not-touch) | F06745 |
| R13463 | Audit enumerates default README files | F06746 |
| R13464 | Audit enumerates default hostname pattern | F06747 |
| R13465 | Audit enumerates NTP pool defaults | F06748 |
| R13466 | Audit enumerates DNS pool defaults | F06749 |
| R13467 | Audit enumerates default APT mirror | F06750 |
| R13468 | Audit enumerates popcon (popularity-contest) | F06751 |
| R13469 | Audit enumerates apport | F06752 |
| R13470 | Audit enumerates phone-home defaults (none-allowed posture) | F06753 |
| R13471 | Every surface MUST be tagged exactly one of {must-rebrand, should-rebrand, may-leave, must-not-touch} | F06754–F06757 + macro-arc 191 |
| R13472 | must-rebrand category — surfaces are operator-visible non-functional Debian references | F06754 |
| R13473 | should-rebrand category — surfaces are minor but visible Debian references | F06755 |
| R13474 | may-leave category — Debian reference acceptable per legal review | F06756 |
| R13475 | must-not-touch category — legal obligation prevents modification | F06757 + macro-arc 191 |
| R13476 | Legal section MUST cite Debian Trademark Policy with URL + retrieved date | F06758 + macro-arc 192 |
| R13477 | Legal section MUST cite DFSG attribution requirements with section anchor | F06759 + macro-arc 192 |
| R13478 | Legal section MUST cite GPL §2 binary distribution attribution | F06760 + macro-arc 192 |
| R13479 | Legal section MUST be "citation-grade" — every claim sourced to canonical URL | macro-arc 192 |
| R13480 | Legal section authored or reviewed by operator (no AI fabrication of legal claims) | macro-arc 192 + operator agency |
| R13481 | Audit table row format — `Surface | Category | Strategy | Lifecycle stage | Notes` | F06764 |
| R13482 | Audit cross-references audit row to mechanism strategy section in `docs/sdd/007-` | F06765 |
| R13483 | Audit re-run differential — `sovereign whitelabel audit` shows surface diff since last run | F06809 + macro-arc 196 |
| R13484 | Audit re-run differential — new Debian surfaces (post-upgrade) trigger MEDIUM-severity dashboard banner | F06809 + ops |
| R13485 | Audit re-run cadence — RECOMMENDED quarterly + after every major Debian release upgrade | macro-arc 192 + ops |
| R13486 | Audit re-run scriptable — `--json` returns structured surface-by-surface verdict | F06815 |
| R13487 | Audit completeness gate — PR 7 SDD merge requires ALL surface categories listed (no TBD entries) | macro-arc 196 + arch |
| R13488 | Mechanism deliverable — `docs/sdd/007-whitelabel-mechanism.md` exists | macro-arc 220 |
| R13489 | Mechanism deliverable — total LOC ≈ 600 ± 10% | macro-arc 220 |
| R13490 | Mechanism deliverable — `schemas/whitelabel.schema.yaml` exists, ~200 LOC | macro-arc 216 + 220 |
| R13491 | Mechanism deliverable — `whitelabel/default.yaml` exists (placeholder, schema-valid) | F06791 + macro-arc 217 |
| R13492 | Mechanism deliverable — `whitelabel/INDEX.md` exists with row per profile | F06796 + macro-arc 218 |
| R13493 | Whitelabel YAML — `name` field non-empty, lowercase-kebab-case | F06787 + arch |
| R13494 | Whitelabel YAML — `version` field semver-pattern (`X.Y.Z`) | F06787 + arch |
| R13495 | Whitelabel YAML — `surfaces` map keys are subset of audited surfaces | F06788 + macro-arc 208 |
| R13496 | Whitelabel YAML — each surface entry has `strategy: <one of 4>` | F06789 + macro-arc 210 |
| R13497 | Whitelabel YAML — each surface entry has `stage: <pre-build | install-time | first-boot>` | F06789 + macro-arc 211 |
| R13498 | Whitelabel YAML — must-not-touch surface entries REJECTED at validation | F06790 + macro-arc 213 |
| R13499 | Whitelabel YAML — optional `legal_review_kid` field (signer id of legal-team override) | F06787 + F06785 |
| R13500 | Whitelabel YAML — schema_version field tracks schema evolution | F06786 + arch |
| R13501 | Rendering — template-substitution strategy uses Jinja2-like syntax (`{{ var }}`) for variables | F06769 + macro-arc 210 |
| R13502 | Rendering — template-substitution variables: `brand_name, palette[0..3], hostname_prefix, ntp_pool, dns_pool, apt_mirror` | F06769 + F06747–F06750 + arch |
| R13503 | Rendering — file-overlay strategy uses bit-for-bit replacement (no merge) | F06770 + macro-arc 210 |
| R13504 | Rendering — file-overlay supports binary surfaces (logos, wallpapers, fonts) | F06770 + macro-arc 210 |
| R13505 | Rendering — file-overlay preserves source file mode + ownership + xattrs | F06770 + arch |
| R13506 | Rendering — package-replacement strategy adds replacement source to APT sources at higher priority | F06771 + macro-arc 210 |
| R13507 | Rendering — package-replacement preserves package version constraints (no downgrade silently) | F06771 + arch |
| R13508 | Rendering — build-time-flag strategy passes brand env vars to upstream build scripts | F06772 + macro-arc 210 |
| R13509 | Rendering — build-time-flag MUST document each flag in the mechanism SDD | F06772 + F06800 |
| R13510 | Per-surface strategy choice MUST be justified in mechanism SDD §2 | F06773 + macro-arc 210 |
| R13511 | Lifecycle — pre-build surfaces patched in source tree before live-build | F06774 + macro-arc 211 |
| R13512 | Lifecycle — install-time surfaces patched during chroot package install | F06775 + macro-arc 211 |
| R13513 | Lifecycle — first-boot surfaces patched on first boot via systemd `firstboot.target` | F06776 + arch |
| R13514 | Lifecycle — per-stage manifest at `whitelabel/<name>/lifecycle-manifest.yaml` lists surfaces by stage | F06777 + arch |
| R13515 | Lifecycle — applying a whitelabel at the wrong stage REJECTED at validate-time | F06777 + F06812 |
| R13516 | Evolvability — `sovereign whitelabel swap <name>` swaps active whitelabel for first-boot surfaces | F06778 + F06811 |
| R13517 | Evolvability — swap operates only on first-boot + (subset of) install-time surfaces | F06778 + F06780 |
| R13518 | Evolvability — pre-build surfaces FAIL swap with diagnostic "rebuild required" | F06779 + macro-arc 212 |
| R13519 | Evolvability — install-time surfaces swappable on next package upgrade only | F06780 + macro-arc 212 |
| R13520 | Evolvability — mixed-state banner shown when swap is partial (M060 cockpit binding) | F06825 + M01368 |
| R13521 | Legal-compliance — validation rejects any YAML that touches must-not-touch surfaces | F06782 + F06790 + macro-arc 213 |
| R13522 | Legal-compliance — rejection includes the cited legal section from the audit | F06784 + macro-arc 213 |
| R13523 | Legal-compliance — operator override REQUIRES `legal_review_kid` field + matching signed manifest | F06785 + arch |
| R13524 | Legal-compliance — overridden whitelabels carry must-not-touch surface in YAML with `override: true` | F06785 + arch |
| R13525 | Legal-compliance — every override use logged to OCSF Audit 1003 with legal-review signer kid | F06785 + cross-ref selfdef MS026 |
| R13526 | Legal-compliance — override expiry: 365 days (legal-review valid for 1 year by default) | F06785 + arch |
| R13527 | Stage Gate 4 — operator reviews PR 7 + PR 8 together; reviewers may NOT merge PR 8 without PR 7 | F06804 + macro-arc 222 |
| R13528 | Stage Gate 4 — gate verdict recorded in `docs/decisions/sg4-whitelabel-review-<YYYY-MM-DD>.md` | F06808 + macro-arc 323+ |
| R13529 | Stage Gate 4 — gate may defer brand commit; placeholder values pass validation | F06807 + F06792–F06795 |
| R13530 | Stage Gate 4 — operator-supplied brand identity recorded in `whitelabel/<brand-name>.yaml` (separate from default) | F06806 + arch |
| R13531 | Stage Gate 4 — legal posture confirmed checkpoint MUST be explicit in gate record | F06805 + arch |
| R13532 | CLI — `sovereign whitelabel audit` exits 0 on success | F06809 + UX |
| R13533 | CLI — `sovereign whitelabel audit --json` returns surface-by-surface verdict | F06809 + F06815 |
| R13534 | CLI — `sovereign whitelabel apply <name>` validates schema + legal before applying | F06810 + F06782 |
| R13535 | CLI — `sovereign whitelabel apply` is a privileged operation gated by sovereign-os RBAC | F06810 + arch |
| R13536 | CLI — `sovereign whitelabel swap <name>` blocks if must-rebuild surfaces would change | F06811 + F06779 |
| R13537 | CLI — `sovereign whitelabel swap` emits OCSF Audit 1003 with swap manifest hash | F06811 + cross-ref selfdef MS026 |
| R13538 | CLI — `sovereign whitelabel validate <yaml>` runs schema + legal + lifecycle checks | F06812 + arch |
| R13539 | CLI — `sovereign whitelabel validate` exits 0 only when ALL checks pass | F06812 + UX |
| R13540 | CLI — `sovereign whitelabel diff <a> <b>` surfaces unified diff per surface key | F06813 + UX |
| R13541 | CLI — `sovereign whitelabel show` displays active whitelabel summary (brand, palette, lifecycle, audit-status) | F06814 + UX |
| R13542 | CLI — startup p95 ≤ 50 ms | F06816 + cross-ref selfdef MS043 R10137 |
| R13543 | CLI — `--json` flag returns structured output | F06815 + cross-ref selfdef MS043 R10131 |
| R13544 | Cockpit binding — M060 panel `Whitelabel` row visible on main dashboard | F06817 + M060 |
| R13545 | Cockpit binding — row displays active whitelabel name | F06817 + UX |
| R13546 | Cockpit binding — palette swatch row shows 4 brand colors as accessible swatches | F06818 + UX |
| R13547 | Cockpit binding — logo preview thumbnail (64×64 px) | F06819 + UX |
| R13548 | Cockpit binding — coverage row: "audited 38, rendered 38 / 38 surfaces" | F06820 + UX |
| R13549 | Cockpit binding — legal review row: status + signer + expiry timestamp | F06821 + F06797 |
| R13550 | Cockpit binding — last-audit-date row with warn-on-stale (>90 days yellow) | F06822 + ops |
| R13551 | Cockpit binding — last-validate-verdict row: Pass / Fail (clickable for diagnostic) | F06823 + UX |
| R13552 | Cockpit binding — last-swap-timestamp row | F06824 + UX |
| R13553 | Cockpit binding — mixed-state banner for partial swap state | F06825 + R13520 |
| R13554 | Cockpit binding — panel is READ-ONLY (no mutate buttons on the panel itself) | F06826 + safety |
| R13555 | Cockpit binding — swap action surfaced via separate confirmation gate (signed action) | F06827 + cross-ref selfdef MS003 |
| R13556 | Cockpit binding — panel updates within 1000 ms of state change (live freshness) | UX + cross-ref selfdef MS043 |
| R13557 | Cockpit binding — WCAG 2.1 AA contrast 4.5:1 (cross-ref selfdef MS043 R10175) | UX + cross-ref selfdef MS043 |
| R13558 | Cockpit binding — palette swatch has explicit hex value caption (color-blind friendly) | UX + accessibility |
| R13559 | Cockpit binding — read-only consumption via MS007 typed-mirror crate (`sovereign-cockpit-whitelabel-mirror`) | M01368 + cross-ref selfdef MS007 |
| R13560 | Test contract L1 — schema validation tests in PR 9 TDD harness | F06828 + macro-arc 230 |
| R13561 | Test contract L2 — must-not-touch enforcement tested with mocked filesystem | F06829 + macro-arc 232 |
| R13562 | Test contract L3 — chroot acceptance test for apply mechanism (4 strategies × 3 lifecycle stages) | F06830 + macro-arc 233 |
| R13563 | Test contract L3 — chroot + service-restart test for swap mechanism | F06831 + macro-arc 233 |
| R13564 | Test contract L4 — full image boot in QEMU verifies all rendered surfaces | F06832 + macro-arc 234 |
| R13565 | Test contract L5 — hardware-conformance — verifies wallpaper, GRUB, Plymouth on actual hardware | F06833 + macro-arc 235 |
| R13566 | Test contract — every audited surface MUST have at least one assertion in PR 9 harness | F06835 + F06763 |
| R13567 | Test contract — flake policy: 3 consecutive failures block release | F06834 + macro-arc 240+ |
| R13568 | Test contract — flake policy: 1 failure retries once with bisect-on-retry-fail | F06834 + macro-arc 240+ |
| R13569 | Test contract — assertions cite the audit row id (R13433–R13470) for traceability | F06835 + arch |
| R13570 | Cross-repo — selfdef-friction-audit-mirror does NOT depend on whitelabel (IPS is brand-neutral) | project boundary |
| R13571 | Cross-repo — sovereign-os fleet hostname pattern integrates with selfdef MS003 signer-kid convention | F06747 + cross-ref selfdef MS003 |
| R13572 | Cross-repo — sovereign-os ASCII MOTD MUST NOT impersonate the IPS daemon banner (IPS owns its own) | F06721 + project boundary |
| R13573 | Cross-repo — typed mirror crate name: exactly `sovereign-cockpit-whitelabel-mirror` | R13559 |
| R13574 | Cross-repo — selfdef MS043 TUI may show sovereign-os whitelabel name (informational only) | cross-ref selfdef MS043 + project boundary |
| R13575 | Survivability — whitelabel render failure does NOT block boot (fail-open with default brand) | arch + UX |
| R13576 | Survivability — whitelabel render failure emits OCSF Detection 2006 (medium severity) | arch + cross-ref selfdef MS026 |
| R13577 | Survivability — surface left at Debian default fires `whitelabel.surface_unrendered` event | F06820 + cross-ref selfdef MS026 |
| R13578 | Survivability — operator visible diagnostic in M060 cockpit "Unrendered: <N>" row | F06820 + UX |
| R13579 | Survivability — operator can re-apply whitelabel via `sovereign whitelabel apply --force` | F06810 + UX |
| R13580 | Performance — `sovereign whitelabel apply` p95 ≤ 30 seconds for first-boot lifecycle | arch + ops |
| R13581 | Performance — `sovereign whitelabel apply` p95 ≤ 5 seconds for swap-eligible first-boot surfaces | F06811 + ops |
| R13582 | Performance — `sovereign whitelabel validate` p95 ≤ 500 ms | F06812 + ops |
| R13583 | Performance — `sovereign whitelabel audit` p95 ≤ 5 seconds (filesystem-walk dominated) | F06809 + ops |
| R13584 | Performance — `sovereign whitelabel show` p95 ≤ 50 ms (cached state read) | F06814 + ops |
| R13585 | Performance — performance-regression budget: 10% drift over 30-day window triggers MS027 alert | ops + cross-ref selfdef MS027 |
| R13586 | Profile integration — main profile YAML field `profile.whitelabel: <name>` references a whitelabel | F06767 + macro-arc 208 |
| R13587 | Profile integration — missing whitelabel reference falls back to `whitelabel/default.yaml` (placeholder) | F06791 + arch |
| R13588 | Profile integration — main profile validate-time check verifies whitelabel reference exists | F06767 + F06812 |
| R13589 | Profile integration — main profile + whitelabel form one logical unit for SDD review | macro-arc 222 |
| R13590 | Profile integration — switching main profile may change whitelabel (operator confirms swap) | F06827 + arch |
| R13591 | Documentation — `docs/sdd/006-debian-surface-audit.md` lints clean (markdown-lint, prose-lint) | arch + ops |
| R13592 | Documentation — `docs/sdd/007-whitelabel-mechanism.md` lints clean | arch + ops |
| R13593 | Documentation — every SDD section anchored via H2/H3 headings for direct linking | arch |
| R13594 | Documentation — code blocks marked with language for syntax highlighting | arch |
| R13595 | Documentation — every Debian surface entry has a citation URL where the surface is defined | arch + macro-arc 192 |
| R13596 | Documentation — both SDDs reference the LICENSE file for Debian Trademark + DFSG | arch + macro-arc 192 |
| R13597 | Documentation — both SDDs reference `whitelabel/INDEX.md` for current set | arch + F06796 |
| R13598 | Documentation — second-brain (info-hub) gets `wiki/whitelabel/<surface>.md` page per audited surface | F06820 + arch |
| R13599 | Documentation — second-brain has `wiki/runbooks/whitelabel-swap-failure.md` | arch + ops |
| R13600 | Documentation — second-brain has `wiki/runbooks/whitelabel-legal-review.md` | arch + F06785 |
| R13601 | Threat-model — adversary supplying malicious whitelabel rejected at schema validate | arch + F06790 |
| R13602 | Threat-model — adversary forging legal-review override detected by signature failure | arch + F06785 + cross-ref selfdef MS003 |
| R13603 | Threat-model — must-not-touch surface modification detected by validator + audit re-run diff | arch + F06782 + F06809 |
| R13604 | Threat-model — silent brand-name change post-deploy detected by M060 cockpit panel | arch + F06817 |
| R13605 | Threat-model — phishing-style brand impersonation (using legitimate Debian visual cues) → mechanism SHALL warn | arch + F06800 |
| R13606 | Audit-cycle integration — whitelabel mechanism participates in MS009 audit-cycle review | cross-ref selfdef MS009 |
| R13607 | Audit-cycle integration — must-not-touch enforcement reviewed at audit-cycle cadence | cross-ref selfdef MS009 + F06782 |
| R13608 | Audit-cycle integration — legal-review expiry monitored at audit-cycle cadence | cross-ref selfdef MS009 + R13526 |
| R13609 | Audit-cycle integration — surface coverage drift (audited vs rendered) reviewed at audit-cycle cadence | cross-ref selfdef MS009 + F06820 |
| R13610 | Audit-cycle integration — every audit-cycle iteration may revise audit/mechanism SDDs | cross-ref selfdef MS009 + arch |
| R13611 | INDEX integration — every M060 dashboard has whitelabel coverage row | F06820 + cross-ref M060 |
| R13612 | INDEX integration — every operator profile has a referenced whitelabel | F06767 + arch |
| R13613 | INDEX integration — `whitelabel/INDEX.md` row form: `name | version | audit-date | legal | active? | mechanism-coverage` | F06797 + arch |
| R13614 | INDEX integration — INDEX.md auto-regenerated on `sovereign whitelabel apply` | F06796 + ops |
| R13615 | INDEX integration — INDEX.md changes committed via signed commit (operator audit trail) | arch + cross-ref selfdef MS041 |
| R13616 | UX — every operator-visible whitelabel surface MUST be operator-readable (no encoded blobs) | UX |
| R13617 | UX — palette colors selected for WCAG 2.1 AA contrast (validator checks pair ratios) | UX + accessibility + R13557 |
| R13618 | UX — palette colors include 1 success / 1 warning / 1 error / 1 neutral semantic (operator extension) | UX + arch |
| R13619 | UX — wallpaper resolution ≥ 1920×1080 (validator checks dimensions) | UX + F06738 |
| R13620 | UX — logo SVG-preferred; PNG ≥ 256×256 fallback | UX + F06819 |
| R13621 | UX — brand-name field ≤ 32 chars, ASCII letters/numbers/space/hyphen | UX + arch |
| R13622 | UX — diagnostic strings on failure include operator-actionable next step | UX + F06784 |
| R13623 | UX — TUI / web mirror surfaces reflect active whitelabel (selfdef MS043 informational only) | R13574 + cross-ref selfdef MS043 |
| R13624 | UX — M060 cockpit panel sortable by name / audit-date / legal-status | UX + F06796 + F06822 |
| R13625 | UX — operator can preview a whitelabel before apply (`sovereign whitelabel preview <name>`) | UX + F06810 |
| R13626 | UX — preview mode shows a side-by-side surface diff vs current active | UX + F06813 |
| R13627 | UX — preview mode does NOT modify any system state | UX + safety |
| R13628 | UX — preview mode emits OCSF Audit 1003 (operator inspection logged) | UX + cross-ref selfdef MS026 |
| R13629 | UX — `sovereign whitelabel show --details` includes per-surface rendering verdict | UX + F06814 |
| R13630 | UX — confirmation modal on swap shows pre/during/post-swap impact summary | UX + F06811 |
| R13631 | Schema evolution — whitelabel schema version bump REQUIRES migration script | arch + F06800 |
| R13632 | Schema evolution — migration script tested under PR 9 TDD harness (L1) | arch + F06828 |
| R13633 | Schema evolution — operator notified of pending migrations via M060 cockpit banner | arch + UX |
| R13634 | Schema evolution — old-version YAMLs loaded read-only until migrated | arch |
| R13635 | Schema evolution — every schema version retains backward-compatible read for ≥ 2 major bumps | arch |
| R13636 | Substrate dependency — whitelabel surfaces conditional on M064 substrate decision (Debian vs alternate base) | F06732 + F06733 + M064 |
| R13637 | Substrate dependency — substrate-switch invalidates pre-build whitelabel surfaces (rebuild required) | F06779 + M064 |
| R13638 | Substrate dependency — substrate-switch decision rule recorded in `docs/decisions/Q-016-substrate-base.md` | M064 |
| R13639 | Substrate dependency — alternate-base substrates require fresh audit (PR 7 re-run on new base) | F06809 + M064 |
| R13640 | Substrate dependency — whitelabel/INDEX.md row includes substrate-target field | F06796 + M064 |
| R13641 | Atomicity — multi-surface apply uses ZFS clone + atomic rename (cross-ref M068) | arch + cross-ref M068 |
| R13642 | Atomicity — apply failure auto-rollback via ZFS snapshot (cross-ref M071 atomic state) | arch + cross-ref M071 |
| R13643 | Atomicity — operator sees rollback verdict in M060 cockpit | arch + F06817 |
| R13644 | Atomicity — apply emits one OCSF Audit 1003 START + one OCSF Audit 1003 END (paired events) | arch + cross-ref selfdef MS026 |
| R13645 | Atomicity — partial-apply state is NEVER persisted (all-or-nothing semantics) | arch + cross-ref M071 |
| R13646 | Atomicity — operator can dry-run apply via `sovereign whitelabel apply --dry-run` | UX + F06810 |
| R13647 | Atomicity — dry-run emits the surface-by-surface plan as JSON | UX + F06815 |
| R13648 | Operator agency — brand name NEVER auto-suggested by AI (operator-only input) | macro-arc 224 + operator agency |
| R13649 | Operator agency — palette colors NEVER auto-generated (operator-only) | macro-arc 224 + operator agency |
| R13650 | Operator agency — logo NEVER AI-generated; operator-supplied asset | macro-arc 224 + operator agency |
| R13651 | Operator agency — placeholder values explicitly flagged `<<TBD-OPERATOR-DECISION>>` (visible) | F06792–F06794 |
| R13652 | Operator agency — Stage Gate 4 record explicitly states operator-supplied vs deferred | F06806 + F06807 |
| R13653 | Operator agency — operator may rescind brand commit via new Stage Gate 4 record | macro-arc 222 + operator agency |
| R13654 | Operator agency — operator may delegate brand commit to a named operator delegate via signed manifest | arch + cross-ref selfdef MS040 |
| R13655 | Operator agency — delegated brand commit logged to OCSF Audit 1003 with delegator + delegate kids | arch + cross-ref selfdef MS026 |
| R13656 | Operator agency — brand commit revocation is reversible (operator can restore prior commit) | arch + cross-ref selfdef MS041 |
| R13657 | Self-defending — whitelabel system MUST NOT be a covert channel for branding-as-policy escalation | security |
| R13658 | Self-defending — whitelabel YAML CANNOT modify systemd unit ordering | security + arch |
| R13659 | Self-defending — whitelabel YAML CANNOT modify IPS daemon behavior | project boundary + R13570 |
| R13660 | Self-defending — whitelabel YAML CANNOT modify package manager security settings | security + F06723–F06725 |
| R13661 | Self-defending — whitelabel CANNOT silently grant or revoke selfdef capability tokens | cross-ref selfdef MS035 + project boundary |
| R13662 | Documentation — every Sub-requirement decomposed in `docs/sdd/SDD-whitelabel-subreqs.md` | arch + operator standing |
| R13663 | Documentation — sub-requirements ≥ 10 per R-row per operator standing direction | operator standing 2026-05-19 |
| R13664 | Documentation — sub-requirements link to L1-L5 test fixtures by ID | arch + F06828–F06834 |
| R13665 | Cross-cutting — whitelabel is part of every release-readiness checkpoint | arch + cross-ref M072 |
| R13666 | Cross-cutting — whitelabel verdict surfaces in M072 master-bootstrap checklist | cross-ref M072 |
| R13667 | Cross-cutting — whitelabel coverage reported in M060 main dashboard top-row summary | F06817 + M060 |
| R13668 | Cross-cutting — whitelabel changes recorded in MS027 observability stream (read-only) | cross-ref selfdef MS027 |
| R13669 | Cross-cutting — whitelabel apply triggers MS009 audit-cycle replay-validator | cross-ref selfdef MS009 |
| R13670 | Cross-cutting — whitelabel data NEVER leaves the local node by default (no telemetry phone-home) | F06753 + arch |

## Sub-requirements accounting

Per operator standing direction *"every of those requirements is in reality already quite specific and with at least 10 hard non-negotiable requirements each"*: each R-row above decomposes into ≥10 sub-requirements under SDD discipline. The sub-requirements live in:
- `docs/sdd/006-debian-surface-audit.md` (audit-side R-rows R13431–R13487)
- `docs/sdd/007-whitelabel-mechanism.md` (mechanism-side R-rows R13488–R13560)
- `docs/sdd/SDD-whitelabel-subreqs.md` (≥10 sub-requirements per R-row binding)
- `wiki/whitelabel/<surface>.md` (per-surface sub-requirement bindings)
- `wiki/runbooks/whitelabel-{swap-failure,legal-review}.md` (operator runbooks)

This milestone catalogues the **top-level R-rows** that anchor the sub-requirement decomposition. Per operator direction, no R-row is invented — every row is sourced from macro-arc dump §PR 7 / §PR 8 verbatim, cross-referenced to prior sovereign-os milestones (M060 cockpit, M064 substrate, M068 ZFS, M071 atomic state, M072 bootstrap checklist), or to selfdef cross-repo bindings (MS003 signing, MS007 mirrors, MS009 audit-cycle, MS026 OCSF, MS027 observability, MS035 capability tokens, MS040 authority profile, MS041 commit authority, MS043 IPS operator surface).

## Cross-references

- **Source dump**: `~/infohub/raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md` §PR 7 lines 174–199 + §PR 8 lines 202–227
- **Companion**: M062 Macro-Arc 10-PR Foundation Scaffold (this milestone is PR 7 + PR 8 of the 10-PR arc)
- **Substrate dependency**: M064 "Debian as Ark" + Q-016 distro-base reconsideration
- **Stage Gate**: M065 Five Stage Gates SG1-SG5 (SG4 = whitelabel-review checkpoint)
- **Cockpit dependency**: M060 Cockpit + 20+ dashboards + UX surface
- **Atomicity dependency**: M068 ZFS storage architecture + M071 Atomic State Transition Protocol
- **Bootstrap dependency**: M072 Master Bootstrap Verification Checklist (whitelabel row 1:1)
- **Cross-repo bindings (selfdef)**: MS003 signing, MS007 typed-mirror, MS009 audit-cycle, MS026 OCSF, MS027 observability, MS035 capability tokens, MS040 authority profile, MS041 commit authority, MS043 IPS operator surface
- **Project boundary**: sovereign-os ONLY; selfdef IPS is brand-neutral (R13570, R13572, R13659)

## Schema

```yaml
# schemas/whitelabel.schema.yaml (sketch — formal schema is the deliverable)
schema_version: "1.0.0"
name: string  # lowercase-kebab-case, ≤ 32 chars
version: string  # semver X.Y.Z
substrate: enum { debian-13, ... }  # M064 binding
surfaces:
  <surface-key>:
    strategy: enum { template-substitution, file-overlay, package-replacement, build-time-flag }
    stage: enum { pre-build, install-time, first-boot }
    value: string | path | package-spec | env-name
legal_review_kid: string  # optional; required if any must-not-touch surface present
legal_review_expiry_ms: u64  # required when legal_review_kid present
```

— End of M081.
