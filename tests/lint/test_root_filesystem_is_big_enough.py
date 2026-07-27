"""A root that fills up is an OS that cannot be logged into or repaired.

2026-07-27. The LVM recipe capped root at 15360 MB on a 1.8 TB disk:

    4096  8192 15360 ext4   lv_name{ root }
    4096 10000    -1 ext4   lv_name{ home }    <- took everything else

15 GB has to hold KDE Plasma, Firefox, the custom kernel AND its headers,
/opt/sovereign-os (the entire repo payload), /usr/local/lib/sovereign-os, the
apt cache — and later an NVIDIA driver and whatever
sovereign-inference-model-provision downloads. It fills, and then the machine
cannot log in, update, or be fixed, with 1.7 TB idle beside it.

expert_recipe fields are <min> <priority> <max> in MB.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PRESEED = (REPO_ROOT / "scripts" / "build" / "installer-cdd"
           / "profiles" / "default.preseed")

# Floor for a KDE workstation that also carries its own source tree and a GPU
# driver. Deliberately generous: the cost of over-sizing root on a 1.8 TB disk
# is nothing; the cost of under-sizing it is an unusable machine.
MIN_ROOT_MAX_MB = 40960


def recipe_entries() -> list[tuple[int, int, int, str]]:
    """(min, priority, max, lv_name) for each LV in the expert recipe."""
    text = PRESEED.read_text(encoding="utf-8")
    body = text[text.index("partman-auto/expert_recipe"):]
    body = body[:body.index("\nd-i ", 1)]
    out = []
    for m in re.finditer(r"^\s+(\d+) (\d+) (-?\d+) \w+\s+\\$(.*?)(?=^\s+\.|\Z)",
                         body, re.M | re.S):
        lv = re.search(r"lv_name\{\s*(\w+)", m.group(4))
        out.append((int(m.group(1)), int(m.group(2)), int(m.group(3)),
                    lv.group(1) if lv else ""))
    return out


def test_root_is_not_capped_absurdly_small():
    root = next((e for e in recipe_entries() if e[3] == "root"), None)
    assert root, f"no root LV found in the recipe: {recipe_entries()}"
    _min, _prio, _max, _ = root
    assert _max == -1 or _max >= MIN_ROOT_MAX_MB, (
        f"root is capped at {_max} MB. It must hold the desktop, the custom "
        "kernel + headers, the sovereign-os payload, an NVIDIA driver and the "
        f"apt cache; at least {MIN_ROOT_MAX_MB} MB (or -1) is required."
    )


def test_home_does_not_outrank_root_into_starvation():
    """home has max -1. If it also outranks root, root gets its minimum only."""
    entries = {e[3]: e for e in recipe_entries()}
    root, home = entries.get("root"), entries.get("home")
    if not (root and home):
        return
    if home[2] == -1:
        assert root[1] >= home[1], (
            f"home (priority {home[1]}, unlimited) outranks root "
            f"(priority {root[1]}) — root is squeezed toward its minimum while "
            "home takes the disk"
        )


def test_the_esp_is_large_enough_for_several_kernels():
    """A 100 MB ESP is the classic 'no space left' during a kernel upgrade."""
    esp = next((e for e in recipe_entries() if e[3] == ""), None)
    if esp:
        assert esp[0] >= 512, f"ESP minimum {esp[0]} MB is too small"
