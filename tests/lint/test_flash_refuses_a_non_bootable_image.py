"""dd writes anything faithfully — check what it is BEFORE the write.

2026-07-27. `sovereign-osctl install image` wrote with dd and never inspected
the source. Three ways that ends badly, all of them an hour of the operator's
time and none of them explained at the point of failure:

  * a truncated or half-written image (interrupted build, full disk),
  * the 8.6G appliance .raw picked when the 1.2G installer .iso was meant,
  * any file at all, since the panel selects by name.

dd reports success in every case and the target simply does not boot.

`file -bs` costs milliseconds and names the artifact. Both real artifacts pass
(the ISO is "ISO 9660 ... (DOS/MBR boot sector)", the appliance is "DOS/MBR boot
sector; partition 1 ..."), and anything else is refused with an explicit
override for the deliberate case.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

ACCEPT = ("ISO 9660", "DOS/MBR boot sector", "GPT partition table")


def flash_block() -> str:
    t = OSCTL.read_text(encoding="utf-8")
    i = t.index("SANITY-CHECK THE IMAGE FIRST")
    return t[i:t.index("dd_ok=0", i)]


def test_the_check_runs_before_the_write():
    t = OSCTL.read_text(encoding="utf-8")
    assert t.index("SANITY-CHECK THE IMAGE FIRST") < t.index('dd if="${image}"'), (
        "the image must be inspected BEFORE dd starts; afterwards the target is "
        "already partially written"
    )


def test_it_accepts_both_real_artifact_shapes():
    block = flash_block()
    for kind in ACCEPT:
        assert kind in block, (
            f"{kind!r} is not accepted — the installer ISO and the appliance "
            ".raw must both be flashable"
        )


def test_it_offers_a_deliberate_override():
    block = flash_block()
    assert "SOVEREIGN_OS_FLASH_ANY_IMAGE" in block, (
        "a refusal with no way past it is a wall; the operator may have a "
        "legitimate image `file` does not recognise"
    )


def test_the_classification_behaves_on_real_inputs(tmp_path: Path):
    """Exercise the actual case statement, not a paraphrase of it."""
    decoy = tmp_path / "decoy.iso"
    decoy.write_text("not an image\n", encoding="utf-8")

    def verdict(path: Path) -> str:
        script = f'''
        _img_kind="$(file -bs "{path}" 2>/dev/null || echo unknown)"
        case "${{_img_kind}}" in
          *"ISO 9660"*|*"DOS/MBR boot sector"*|*"GPT partition table"*) echo ACCEPT ;;
          *) echo REFUSE ;;
        esac'''
        return subprocess.run(["bash", "-c", script],
                              capture_output=True, text=True).stdout.strip()

    assert verdict(decoy) == "REFUSE", "a text file was accepted as a bootable image"

    iso = REPO_ROOT / "build" / "sain-01" / "output" / "sain-01-installer.iso"
    if iso.exists():
        assert verdict(iso) == "ACCEPT", "the real installer ISO was refused"


def test_no_invented_helpers_in_the_block():
    """The first version called emit_flash_metric, which does not exist.

    It was `|| true`-guarded so it would not have broken anything — but a call
    to a function that is not defined reads as working instrumentation and is
    not (2026-07-27).
    """
    import re
    block = flash_block()
    # Helpers may be defined in sovereign-osctl OR in the common.sh it sources
    # (log_info/log_error live there). Searching only the one file reported a
    # false positive on a perfectly ordinary logger (2026-07-27).
    # Helpers live in sovereign-osctl OR any of the libs it sources —
    # log_info/log_error are in scripts/build/lib/logging.sh, not common.sh.
    # Guessing the file was wrong twice; scan the whole lib directory.
    sources = [OSCTL.read_text(encoding="utf-8")]
    for lib in sorted(REPO_ROOT.glob("scripts/**/lib/*.sh")):
        sources.append(lib.read_text(encoding="utf-8"))
    body = "\n".join(sources)
    for call in sorted(set(re.findall(r"\b(emit_\w+|log_\w+)\s", block))):
        assert re.search(rf"^{call}\s*\(\)", body, re.M), (
            f"{call} is called in the flash guard but defined nowhere — it "
            "reads as working instrumentation and is not"
        )
