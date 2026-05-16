#!/usr/bin/env python3
"""
scripts/whitelabel/render.py — sovereign-os whitelabel render engine.

Implements SDD-007's Layer 1 — substrate-agnostic file-tree changeset
generation from a whitelabel YAML + profile YAML. Output is then
consumed by Layer 2 substrate adapters (mkosi.skeleton/ etc.).

7-strategy taxonomy per SDD-007:
  1. template-substitution
  2. file-overlay
  3. package-replacement
  4. build-time-flag
  5. install-time-substitution
  6. first-boot-script
  7. must-not-touch (validation only)

Legal-floor enforcement: refuses to write to any path matching the
must-not-touch list per SDD-006 § Legal floor.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import pathlib
import re
import shutil
import string
import sys
from dataclasses import dataclass, field

try:
    import yaml
except ImportError:
    sys.stderr.write("error: python3-yaml not installed; apt-get install python3-yaml\n")
    sys.exit(2)


# Legal-floor paths that MUST NOT be touched — from SDD-006 § Legal floor.
LEGAL_FLOOR_PATTERNS = [
    "/etc/debian_version",
    "/usr/share/doc/*/copyright",
    "/usr/share/man/*",
    "*/debian-logo*",
    "*/debian-swirl*",
]


@dataclass
class Changeset:
    """Substrate-agnostic file-tree changeset."""

    pre_build_files: dict[str, str] = field(default_factory=dict)  # path → content
    pre_build_overlays: dict[str, str] = field(default_factory=dict)  # dest path → source overlay dir
    package_actions: list[dict] = field(default_factory=list)  # diverts, alternatives, etc.
    build_time_env: dict[str, str] = field(default_factory=dict)  # env var → value
    install_time: list[dict] = field(default_factory=list)
    first_boot_scripts: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"  pre-build files:       {len(self.pre_build_files)}\n"
            f"  pre-build overlays:    {len(self.pre_build_overlays)}\n"
            f"  package actions:       {len(self.package_actions)}\n"
            f"  build-time env vars:   {len(self.build_time_env)}\n"
            f"  install-time entries:  {len(self.install_time)}\n"
            f"  first-boot scripts:    {len(self.first_boot_scripts)}\n"
        )


def violates_legal_floor(path: str) -> bool:
    """Check whether a target path violates the SDD-006 legal floor."""
    for pattern in LEGAL_FLOOR_PATTERNS:
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def render_template_substitution(branding: dict, content: str) -> str:
    """${var} expansion in content using branding dict."""
    # safe_substitute returns the source unchanged on missing keys
    tmpl = string.Template(content)
    return tmpl.safe_substitute(branding)


def load_yaml(path: pathlib.Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f)


def build_changeset(profile: dict, whitelabel: dict, wl_dir: pathlib.Path) -> Changeset:
    """Translate whitelabel YAML into a substrate-agnostic changeset."""
    cs = Changeset()
    branding = whitelabel.get("branding") or {}

    # Validate compliance_target vs profile.whitelabel.legal_compliance
    profile_compliance = (profile.get("whitelabel") or {}).get("legal_compliance")
    wl_compliance = whitelabel.get("compliance_target")
    if wl_compliance and profile_compliance and wl_compliance != profile_compliance:
        sys.stderr.write(
            f"error: compliance mismatch — profile says '{profile_compliance}', "
            f"whitelabel says '{wl_compliance}'\n"
        )
        sys.exit(3)

    surfaces = whitelabel.get("surfaces") or {}
    for surface_path, decl in surfaces.items():
        strategy = decl.get("strategy")
        when = decl.get("when")

        # Legal-floor guard — applies regardless of strategy
        if violates_legal_floor(surface_path):
            sys.stderr.write(
                f"error: whitelabel '{whitelabel['identity']['id']}' "
                f"tries to override legal-floor path: {surface_path}\n"
            )
            sys.exit(4)

        if strategy == "template-substitution":
            if "template" in decl:
                tmpl_path = wl_dir / decl["template"]
                if not tmpl_path.exists():
                    sys.stderr.write(
                        f"warn: template not found: {tmpl_path} (Stage 2+ ships content)\n"
                    )
                    continue
                content = tmpl_path.read_text()
            elif "content" in decl:
                content = decl["content"]
            else:
                sys.stderr.write(f"warn: surface {surface_path} has no template/content\n")
                continue

            rendered = render_template_substitution(branding, content)

            # line-replace operation: read existing file, replace matching line
            op = decl.get("operation")
            if op == "line-replace":
                pattern = decl.get("pattern", "")
                replacement = render_template_substitution(branding, decl.get("replacement", ""))
                # Store as a pending edit; substrate adapter applies later
                cs.package_actions.append({
                    "type": "line-replace",
                    "path": surface_path,
                    "pattern": pattern,
                    "replacement": replacement,
                })
            else:
                cs.pre_build_files[surface_path] = rendered

        elif strategy == "file-overlay":
            overlay = decl.get("overlay")
            if not overlay:
                continue
            cs.pre_build_overlays[surface_path] = str(wl_dir / overlay)

        elif strategy == "package-replacement":
            cs.package_actions.append({
                "type": "package-replacement",
                "package": decl.get("package"),
                "alternative": decl.get("alternative"),
                "points_to": decl.get("points_to"),
                "diverts": decl.get("diverts") or [],
            })

        elif strategy == "build-time-flag":
            flags = decl.get("flags") or {}
            for k, v in flags.items():
                cs.build_time_env[k] = render_template_substitution(branding, str(v))

        elif strategy == "install-time-substitution":
            cs.install_time.append({
                "key": decl.get("key"),
                "value": render_template_substitution(branding, str(decl.get("value", ""))),
                "target": decl.get("target"),
                "template": decl.get("template"),
                "operation": decl.get("operation"),
            })

        elif strategy == "first-boot-script":
            script = decl.get("script")
            if script:
                cs.first_boot_scripts.append(script)

        elif strategy == "must-not-touch":
            # SDD-007 strategy 7: explicit "this whitelabel declines to
            # override this surface". Declarative opt-out — different from
            # the legal-floor LIST (hard refuse for anyone). Useful when a
            # whitelabel inherits from a parent that DOES override the
            # surface, and the child wants to revert to the upstream.
            #
            # No changeset emission. Operator-readable side effect: emit
            # a tracking entry so 'sovereign-osctl whitelabel show' can
            # surface "explicitly NOT touched" surfaces alongside the
            # touched ones.
            cs.package_actions.append({
                "type": "must-not-touch",
                "path": surface_path,
                "reason": decl.get("reason", "explicit no-op declaration"),
            })

        else:
            sys.stderr.write(f"warn: unknown strategy '{strategy}' on {surface_path}\n")

    return cs


def emit_for_mkosi(cs: Changeset, out_dir: pathlib.Path) -> None:
    """Apply changeset into the mkosi.skeleton/ + mkosi.extra/ trees."""
    skeleton = out_dir / "mkosi.skeleton"
    extra = out_dir / "mkosi.extra"
    skeleton.mkdir(parents=True, exist_ok=True)
    extra.mkdir(parents=True, exist_ok=True)

    # pre_build_files → mkosi.skeleton (overlaid before chroot is sealed)
    for surface_path, content in cs.pre_build_files.items():
        # Surface path is absolute (/etc/...); strip leading slash for overlay-relative
        rel = surface_path.lstrip("/")
        target = skeleton / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        print(f"  + skeleton: {surface_path}")

    # pre_build_overlays → mkosi.extra (overlaid late)
    for surface_path, src_dir in cs.pre_build_overlays.items():
        src = pathlib.Path(src_dir)
        if not src.exists():
            print(f"  ! overlay source missing: {src} (Stage 2+ ships content)")
            continue
        rel = surface_path.lstrip("/")
        target = extra / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(src, target)
        print(f"  + overlay: {surface_path} ← {src}")

    # build_time_env → write to mkosi.conf.d snippet
    if cs.build_time_env:
        env_conf = out_dir / "mkosi.conf.d" / "10-whitelabel-build-env.conf"
        env_conf.parent.mkdir(parents=True, exist_ok=True)
        lines = ["[Build]", "Environment="]
        for k, v in cs.build_time_env.items():
            lines.append(f"    {k}={v}")
        env_conf.write_text("\n".join(lines) + "\n")
        print(f"  + build-env: {env_conf}")

    # install_time + first_boot_scripts → captured in a manifest for
    # the install/first-boot hooks to read (Stage 2+ wires these in)
    manifest = out_dir / "whitelabel-manifest.json"
    manifest.write_text(json.dumps({
        "install_time": cs.install_time,
        "first_boot_scripts": cs.first_boot_scripts,
        "package_actions": cs.package_actions,
    }, indent=2))
    print(f"  + manifest: {manifest}")


def emit_for_live_build(cs: Changeset, out_dir: pathlib.Path) -> None:
    """Apply changeset into the live-build config/includes.chroot/ tree.

    live-build merges everything under config/includes.chroot/ into the
    rootfs late in the build, after the package install pass. This is
    the substrate-parallel of mkosi.skeleton/ + mkosi.extra/.

    Surface mapping:
      pre_build_files     → config/includes.chroot/<path>
      pre_build_overlays  → config/includes.chroot/<path>/  (recursive copy)
      build_time_env      → config/auto/config.d/10-whitelabel-env.conf (lb_config snippet)
      install/first_boot  → whitelabel-manifest.json (substrate-agnostic; hooks read it)
    """
    chroot = out_dir / "config" / "includes.chroot"
    chroot.mkdir(parents=True, exist_ok=True)

    for surface_path, content in cs.pre_build_files.items():
        rel = surface_path.lstrip("/")
        target = chroot / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        print(f"  + chroot: {surface_path}")

    for surface_path, src_dir in cs.pre_build_overlays.items():
        src = pathlib.Path(src_dir)
        if not src.exists():
            print(f"  ! overlay source missing: {src} (Stage 2+ ships content)")
            continue
        rel = surface_path.lstrip("/")
        target = chroot / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(src, target)
        print(f"  + overlay: {surface_path} ← {src}")

    if cs.build_time_env:
        env_conf = out_dir / "config" / "auto" / "config.d" / "10-whitelabel-env.conf"
        env_conf.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# whitelabel build-time env (lb_config picks up via shell-source)"]
        for k, v in cs.build_time_env.items():
            lines.append(f'export {k}="{v}"')
        env_conf.write_text("\n".join(lines) + "\n")
        print(f"  + build-env: {env_conf}")

    manifest = out_dir / "whitelabel-manifest.json"
    manifest.write_text(json.dumps({
        "install_time": cs.install_time,
        "first_boot_scripts": cs.first_boot_scripts,
        "package_actions": cs.package_actions,
    }, indent=2))
    print(f"  + manifest: {manifest}")


def main() -> int:
    parser = argparse.ArgumentParser(description="sovereign-os whitelabel render engine")
    parser.add_argument("--profile", required=True, help="profile YAML path")
    parser.add_argument("--whitelabel", required=True, help="whitelabel YAML path")
    parser.add_argument("--out", required=True, help="substrate output dir")
    parser.add_argument(
        "--substrate",
        choices=["mkosi", "live-build", "rpm-ostree", "nixos"],
        default="mkosi",
        help="substrate adapter target",
    )
    args = parser.parse_args()

    profile = load_yaml(pathlib.Path(args.profile))
    whitelabel = load_yaml(pathlib.Path(args.whitelabel))
    wl_dir = pathlib.Path(args.whitelabel).parent

    cs = build_changeset(profile, whitelabel, wl_dir)
    print(cs.summary())

    out_dir = pathlib.Path(args.out)

    if args.substrate == "mkosi":
        emit_for_mkosi(cs, out_dir)
    elif args.substrate == "live-build":
        emit_for_live_build(cs, out_dir)
    else:
        sys.stderr.write(
            f"error: substrate '{args.substrate}' adapter not yet implemented; "
            f"mkosi + live-build are the foundation-phase substrates\n"
        )
        return 5

    print("render complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
