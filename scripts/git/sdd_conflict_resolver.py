#!/usr/bin/env python3
"""
scripts/git/sdd_conflict_resolver.py — auto-resolve parallel-session SDD-number
collisions, verify, and warn on doubt (SDD-980).

WHY THIS EXISTS
---------------
Three (or more) sessions work sovereign-os in parallel, each on its own branch
merging to `main`. SDD-100 gives each session a disjoint number band (recover
100–199, header-sidemenu 200–299, science-tools 300–399, cockpit-wasm 800–899,
compute-plane 900–949, phase-1 audit 950–999) so their SDD numbers never
collide. `.gitattributes merge=union` keeps both sides' appended registry rows.

But a session can still slip and take a number OUTSIDE its band (it happened
twice: a dup SDD-969, then a dup SDD-974). Two differently-slugged files with the
same number do NOT git-conflict — they simply coexist — so the mistake surfaces
only when `tests/lint/test_sdd_numbers_unique.py` goes red AFTER the merge. That
is exactly the class of conflict whose resolution logic is deterministic and
known, so it should be automatic.

THE DETERMINISTIC RULE
----------------------
Every banded SDD declares its band in its body: `> Number band: **950–999 …`.
That declared range is the file's AUTHORSHIP signal — which session wrote it —
independent of the (possibly-wrong) number it currently carries. On a duplicate
number N shared by two files:

  * the file whose DECLARED band contains N  → the rightful owner (keeps N);
  * the file whose declared band does NOT    → the intruder (renumber it into
    the next free slot of ITS OWN band).

`docs/sdd/SESSIONS.md` is the authoritative session registry (id → band); a file's
declared band must match a registered session band (enforced by
`tests/lint/test_session_registry.py`), so the signal can't quietly rot.

AGGRESSIVENESS (operator-chosen 2026-07-13): "Auto-apply, verify, warn on doubt."
When the rule is unambiguous, renumber the intruder in place (rename the file,
rewrite every `SDD-<n>`/`E11.M<n>` reference across docs, regenerate the mdbook
catalog, recompute the context.md counts) and VERIFY by re-running the
uniqueness / band-contiguity / counts lints. If verification fails, or the case
is ambiguous (no band declared, both in-band, both out-of-band, band full), it
REVERTS its own changes and warns with the exact manual remediation — it never
leaves a half-applied, unverified state.

Every auto-resolution (and every warn) is appended to `docs/sdd/RESOLUTION-LOG.md`
— the cross-session ledger: what was resolved, by which rule, and the residual
follow-ups (e.g. the intruding session should pull main; consider branch
protection). That log doubles as the seed of the session-to-session / session-to
-operator message board (SDD-980 "sessions talk to each other" frame).

MODES
-----
  --check    detect + report only; exit 1 if any UNRESOLVED collision remains,
             0 if clean. No writes. (CI / curiosity.)
  --dry-run  show exactly what --apply WOULD do; no writes.
  --apply    (default) resolve unambiguous collisions, verify, log; revert +
             warn on doubt. Leaves changes UNSTAGED for the user to review and
             commit — a hook must never auto-commit.

Silent + fast on the happy path (no duplicate numbers → exit 0, no output, no
log write) so it is safe to fire from post-merge / post-rewrite on every pull.

Stdlib only (re, subprocess, pathlib, datetime, argparse).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# --- repo geography ---------------------------------------------------------
REPO = Path(__file__).resolve().parents[2]
SDD_DIR = REPO / "docs" / "sdd"
INDEX = SDD_DIR / "INDEX.md"
SESSIONS = SDD_DIR / "SESSIONS.md"
RESOLUTION_LOG = SDD_DIR / "RESOLUTION-LOG.md"
MANDATE = REPO / "docs" / "standing-directives" / "2026-05-17-operator-mandate.md"
CONTEXT = REPO / "context.md"
GEN_CATALOG = REPO / "scripts" / "docs" / "gen-sdd-catalog.py"

_FILE_RE = re.compile(r"^(\d+)-(.+)\.md$")
_BAND_RE = re.compile(r"Number band:\s*\*\*(\d+)\s*[–-]\s*(\d+)")
# SESSIONS.md registry row: | id | lo–hi | E11… | branch | purpose | status |
_SESSION_ROW_RE = re.compile(r"^\|\s*([a-z0-9-]+)\s*\|\s*(\d+)\s*[–-]\s*(\d+)\s*\|", re.M)


# --- ansi (only when speaking) ---------------------------------------------
def _c(code: str) -> str:
    return f"\033[{code}m" if sys.stderr.isatty() else ""


RED, YLW, GRN, RST = _c("1;31"), _c("33"), _c("32"), _c("0")


class Doubt(Exception):
    """Raised when a collision cannot be resolved deterministically."""


# --- band contiguity key (mirrors test_mandate_section_1_subsections.py) ----
def _band_key(n: int) -> int:
    """The sub-band a number keys into for the contiguity lint: 9xx is split
    into compute-plane 900-949 and phase-1 audit 950-999."""
    return 950 if n >= 950 else (n // 100)


# --- reading the tree -------------------------------------------------------
def _sdd_files() -> list[tuple[int, Path]]:
    out = []
    for p in SDD_DIR.glob("*.md"):
        m = _FILE_RE.match(p.name)
        if m:
            out.append((int(m.group(1)), p))
    return out


def _declared_band(path: Path) -> tuple[int, int] | None:
    m = _BAND_RE.search(path.read_text(encoding="utf-8"))
    return (int(m.group(1)), int(m.group(2))) if m else None


def duplicate_numbers() -> list[int]:
    nums = [n for n, _ in _sdd_files()]
    return sorted(n for n, c in Counter(nums).items() if c > 1)


# --- the resolution plan ----------------------------------------------------
class Move:
    def __init__(self, path: Path, old: int, new: int, band: tuple[int, int]):
        self.path, self.old, self.new, self.band = path, old, new, band

    def __repr__(self) -> str:
        return f"SDD-{self.old} → SDD-{self.new} ({self.path.name}, own band {self.band[0]}-{self.band[1]})"


def _plan_for(number: int) -> Move:
    """Decide which of the files sharing `number` is the intruder and where it
    moves. Raises Doubt when the deterministic rule does not apply cleanly."""
    contenders = [(n, p) for n, p in _sdd_files() if n == number]
    bands: dict[Path, tuple[int, int] | None] = {p: _declared_band(p) for _, p in contenders}

    undeclared = [p.name for p, b in bands.items() if b is None]
    if undeclared:
        raise Doubt(
            f"SDD-{number}: {', '.join(undeclared)} declare no `Number band:` — "
            f"cannot tell which session owns it. Add the band line, or renumber by hand."
        )

    owners = [p for p, (lo, hi) in bands.items() if lo <= number <= hi]
    intruders = [p for p, (lo, hi) in bands.items() if not (lo <= number <= hi)]

    if len(owners) != 1 or not intruders:
        who = "; ".join(f"{p.name} declares {b[0]}-{b[1]}" for p, b in bands.items())
        raise Doubt(
            f"SDD-{number}: no single in-band owner ({len(owners)} owner(s), "
            f"{len(intruders)} intruder(s)). {who}. Ambiguous — resolve by hand."
        )
    if len(intruders) != 1:
        raise Doubt(
            f"SDD-{number}: {len(intruders)} intruders at once — resolve by hand."
        )

    intruder = intruders[0]
    lo, hi = bands[intruder]  # its OWN band
    used = {n for n, _ in _sdd_files() if lo <= n <= hi}
    new = (max(used) + 1) if used else lo
    if new > hi:
        raise Doubt(
            f"SDD-{number}: intruder {intruder.name}'s own band {lo}-{hi} is full "
            f"(next slot {new} > {hi}). Extend the band or renumber by hand."
        )
    return Move(intruder, number, new, (lo, hi))


# --- applying a move --------------------------------------------------------
def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True, text=True,
    )


def _session_bands() -> dict[str, tuple[int, int]]:
    """session-id → (lo, hi) from the SESSIONS.md registry."""
    if not SESSIONS.is_file():
        return {}
    return {m.group(1): (int(m.group(2)), int(m.group(3)))
            for m in _SESSION_ROW_RE.finditer(SESSIONS.read_text(encoding="utf-8"))}


def _row_band(last_cell: str, bands: dict[str, tuple[int, int]]) -> tuple[int, int] | None:
    """Which session-band does a registry row's self-declaring last cell name?
    INDEX rows end `… (cockpit-wasm session)`; mandate rows end `… branch
    claude/…cockpit-wasm…`. Match any registered session-id appearing in the cell."""
    hit = None
    for sid, band in bands.items():
        if sid in last_cell:
            # longest id wins (avoid a short id matching inside a longer one)
            if hit is None or len(sid) > len(hit[0]):
                hit = (sid, band)
    return hit[1] if hit else None


def _fix_registry_row(path: Path, row_re: re.Pattern, old: int, new: int,
                      own_band: tuple[int, int], bands: dict[str, tuple[int, int]],
                      token_sub) -> bool:
    """Surgically renumber THE intruder's single row in a number-keyed registry.
    The intruder row = the one matching `old` whose self-declaring last cell names
    the SAME band as the intruder file (`own_band`). Rewrites only that one line.
    Returns True if a row was rewritten, False if none/ambiguous (→ verify catches)."""
    if not path.is_file():
        return False
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    candidates = [i for i, ln in enumerate(lines) if row_re.match(ln)]
    # among rows carrying `old`, pick the one whose last cell's band == own_band
    target = None
    for i in candidates:
        cells = lines[i].rstrip("\n").split("|")
        last_cell = cells[-2] if len(cells) >= 2 else lines[i]
        if _row_band(last_cell, bands) == own_band:
            if target is not None:
                return False  # two rows claim the intruder band — ambiguous
            target = i
    if target is None:
        return False
    lines[target] = token_sub(lines[target], old, new)
    path.write_text("".join(lines), encoding="utf-8")
    return True


def _apply_move(mv: Move) -> dict[str, bool]:
    """Rename the intruder file, fix its own internal refs, and surgically
    renumber its INDEX + mandate rows (band-identified). Returns what was done."""
    bands = _session_bands()
    old, new = mv.old, mv.new
    slug = _FILE_RE.match(mv.path.name).group(2)
    new_path = mv.path.with_name(f"{new}-{slug}.md")

    # 1) rename the file with a plain rename (NOT `git mv`): we deliberately
    # leave every change UNSTAGED so the operator reviews `git status` and
    # commits — and so a verify-failure revert (`git checkout -- .` restores the
    # tracked original from HEAD; `git clean` drops the untracked new name) fully
    # undoes us without touching the index. git's diff still detects the rename.
    mv.path.rename(new_path)

    # 2) fix the intruder file's OWN internal self-references (single file)
    body = new_path.read_text(encoding="utf-8")
    body = re.sub(rf"\bSDD-{old}\b", f"SDD-{new}", body)
    body = re.sub(rf"\bE11\.M{old}\b", f"E11.M{new}", body)
    new_path.write_text(body, encoding="utf-8")

    # 3) surgically renumber the intruder's INDEX row (leading `| old |` + SDD-old)
    def _index_sub(line: str, o: int, n: int) -> str:
        line = re.sub(rf"^\|\s*{o}\s*\|", f"| {n} |", line)
        return re.sub(rf"\bSDD-{o}\b", f"SDD-{n}", line)

    idx_ok = _fix_registry_row(
        INDEX, re.compile(rf"^\|\s*{old}\s*\|"), old, new, mv.band, bands, _index_sub)

    # 4) surgically renumber the intruder's mandate row (`| E11.Mold |` + SDD-old)
    def _mandate_sub(line: str, o: int, n: int) -> str:
        line = re.sub(rf"^\|\s*E11\.M{o}\s*\|", f"| E11.M{n} |", line)
        line = re.sub(rf"\bE11\.M{o}\b", f"E11.M{n}", line)
        return re.sub(rf"\bSDD-{o}\b", f"SDD-{n}", line)

    man_ok = _fix_registry_row(
        MANDATE, re.compile(rf"^\|\s*E11\.M{old}\s*\|"), old, new, mv.band, bands, _mandate_sub)

    return {"file": True, "index_row": idx_ok, "mandate_row": man_ok}


def _regenerate() -> None:
    """Regenerate derived surfaces so they reflect the renumber."""
    if GEN_CATALOG.is_file():
        subprocess.run([sys.executable, str(GEN_CATALOG)], cwd=str(REPO),
                       capture_output=True, text=True)
    _recompute_context_counts()


def _recompute_context_counts() -> None:
    """Recompute context.md's `sdd files` count from the tree (the one count a
    renumber can leave stale is the total, which is unchanged by a rename — but
    a fresh merge that ADDED the intruder does change it, so recompute all)."""
    if not CONTEXT.is_file():
        return
    files = sum(1 for p in SDD_DIR.glob("*.md") if _FILE_RE.match(p.name))
    txt = CONTEXT.read_text(encoding="utf-8")
    txt = re.sub(r"(\|\s*sdd files\s*\|\s*)\d+(\s*\|)", rf"\g<1>{files}\g<2>", txt)
    CONTEXT.write_text(txt, encoding="utf-8")


# --- verification -----------------------------------------------------------
# Precise node-ids: the checks a renumber must keep green — number uniqueness,
# E11 band contiguity, and the context.md counts. We target the single
# contiguity function (not the whole mandate-subsections file, whose other
# assertions cover §1g/§1h content unrelated to a renumber).
LINTS = (
    "tests/lint/test_sdd_numbers_unique.py",
    "tests/lint/test_mandate_section_1_subsections.py::test_e11_modules_sequential",
    "tests/lint/test_context_md_counts.py",
)


def _verify() -> tuple[bool, str]:
    """Re-run the uniqueness / contiguity / counts lints. Falls back to an
    internal recompute if pytest is unavailable."""
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *LINTS],
        cwd=str(REPO), capture_output=True, text=True,
    )
    if r.returncode == 0:
        return True, "pytest lints green"
    if "No module named pytest" in (r.stderr + r.stdout):
        # internal fallback: uniqueness + contiguity from the tree
        nums = [n for n, _ in _sdd_files()]
        dups = [n for n, c in Counter(nums).items() if c > 1]
        blocks: dict[int, list[int]] = defaultdict(list)
        for n in nums:
            blocks[_band_key(n)].append(n)
        gaps = {
            b: sorted(set(range(min(v), max(v) + 1)) - set(v))
            for b, v in blocks.items()
            if set(range(min(v), max(v) + 1)) - set(v)
        }
        ok = not dups and not gaps
        return ok, f"internal check (pytest absent): dups={dups} gaps={gaps}"
    return False, (r.stdout + r.stderr).strip()[-2000:]


# --- resolution log (the cross-session ledger / message-board seed) ---------
def _log(entry: str) -> None:
    if not RESOLUTION_LOG.is_file():
        RESOLUTION_LOG.write_text(_LOG_HEADER, encoding="utf-8")
    with RESOLUTION_LOG.open("a", encoding="utf-8") as fh:
        fh.write(entry)


_LOG_HEADER = """# SDD conflict-resolution log (SDD-980)

> Append-only cross-session ledger. Each entry records a parallel-session SDD
> collision the auto-resolver handled (or could not), the deterministic rule it
> applied, and the residual follow-ups. `.gitattributes merge=union` keeps every
> session's entries across merges — so it also serves as the seed of the
> session-to-session / session-to-operator message board (see SDD-980).
>
> Format per entry: a `## <UTC timestamp> — <from-session> → <to>` header, then
> WHAT / RULE / ACTION / VERIFY / FURTHER-NEEDS lines.

"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _current_session() -> str:
    r = _git("rev-parse", "--abbrev-ref", "HEAD")
    return r.stdout.strip() if r.returncode == 0 else "unknown-branch"


# --- top-level orchestration ------------------------------------------------
def run(mode: str) -> int:
    dups = duplicate_numbers()
    if not dups:
        return 0  # happy path: silent, fast

    session = _current_session()
    resolved: list[Move] = []
    doubts: list[str] = []
    plans: list[Move] = []

    for n in dups:
        try:
            plans.append(_plan_for(n))
        except Doubt as d:
            doubts.append(str(d))

    if mode == "check":
        for mv in plans:
            print(f"resolvable: {mv}")
        for d in doubts:
            print(f"{YLW}unresolved:{RST} {d}", file=sys.stderr)
        return 1 if (doubts or plans) else 0

    if mode == "dry-run":
        for mv in plans:
            band_used = sorted(x for x, _ in _sdd_files() if mv.band[0] <= x <= mv.band[1])
            print(f"WOULD renumber {mv}  (band currently uses {band_used})")
        for d in doubts:
            print(f"{YLW}WOULD warn:{RST} {d}", file=sys.stderr)
        return 0

    # --- apply -------------------------------------------------------------
    for mv in plans:
        slug = _FILE_RE.match(mv.path.name).group(2)
        did = _apply_move(mv)
        _regenerate()
        ok, detail = _verify()
        if ok:
            resolved.append(mv)
            rows = "INDEX row " + ("✓" if did["index_row"] else "— (none/ambiguous, left)")
            rows += ", mandate row " + ("✓" if did["mandate_row"] else "— (none/ambiguous, left)")
            _log(
                f"## {_now()} — {session} → {_band_label(mv.band)}\n"
                f"- WHAT: two SDD files shared number {mv.old}; `{mv.new}-{slug}.md` was the "
                f"intruder (its declared band {mv.band[0]}-{mv.band[1]} does not contain {mv.old}).\n"
                f"- RULE: declared-band ownership (SDD-980) — the out-of-band file yields; the "
                f"in-band owner keeps {mv.old}.\n"
                f"- ACTION: renamed SDD-{mv.old} → SDD-{mv.new} (+ internal refs); {rows}; "
                f"regenerated the mdbook catalog + context.md counts.\n"
                f"- VERIFY: {detail}.\n"
                f"- FURTHER-NEEDS: changes are UNSTAGED — review `git status` then commit. "
                f"Any prose mention of SDD-{mv.old} outside the registries (e.g. CHANGELOG) is "
                f"left untouched — grep `SDD-{mv.old}` and repoint by hand if it referred to this "
                f"doc. The session that took SDD-{mv.old} out of band should pull main and confirm "
                f"its local band. Branch protection ('require branches up to date before merging') "
                f"would prevent recurrence.\n\n"
            )
        else:
            # verification failed — revert this move's writes, warn.
            _revert()
            doubts.append(
                f"SDD-{mv.old}: auto-renumber to SDD-{mv.new} did not verify and was "
                f"reverted. Lint output:\n{detail}"
            )

    _report(session, resolved, doubts)
    return 0 if not doubts else 1


def _band_label(band: tuple[int, int]) -> str:
    return f"session-band-{band[0]}-{band[1]}"


def _revert() -> None:
    """Undo uncommitted worktree changes this tool made (renames + rewrites).
    Only touches tracked files — restores them to HEAD/index; removes the new
    untracked renamed file if the mv fell back to a plain rename."""
    _git("checkout", "--", ".")
    _git("clean", "-fd", "docs/sdd")


def _report(session: str, resolved: list[Move], doubts: list[str]) -> None:
    if resolved:
        lines = [f"{GRN}✓ sovereign-os · SDD auto-resolver ({session}):{RST} "
                 f"resolved {len(resolved)} collision(s):"]
        for mv in resolved:
            lines.append(f"    {mv}")
        lines.append(f"  Changes are UNSTAGED — review `git status` and commit. "
                     f"Details in {RESOLUTION_LOG.relative_to(REPO)}.")
        print("\n".join(lines), file=sys.stderr)
    if doubts:
        lines = ["", f"{RED}⚠  sovereign-os · SDD auto-resolver ({session}): "
                     f"{len(doubts)} collision(s) it could NOT resolve — manual fix needed:{RST}"]
        for d in doubts:
            lines.append(f"{YLW}    • {d}{RST}")
        lines.append(f"{YLW}  The deterministic rule (SDD-980): the file whose declared band does "
                     f"not contain the number is the intruder; renumber it into the next free slot "
                     f"of its own band, then re-run the uniqueness/contiguity/counts lints.{RST}")
        print("\n".join(lines), file=sys.stderr)
        _log(
            f"## {_now()} — {session} → operator (UNRESOLVED)\n"
            + "".join(f"- WARN: {d}\n" for d in doubts)
            + "- FURTHER-NEEDS: operator or the owning session must renumber by hand "
              "per SDD-980, then re-run `python3 scripts/git/sdd_conflict_resolver.py --check`.\n\n"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_const", dest="mode", const="check",
                   help="detect + report only; exit 1 if unresolved collisions remain")
    g.add_argument("--dry-run", action="store_const", dest="mode", const="dry-run",
                   help="show what --apply would do; no writes")
    g.add_argument("--apply", action="store_const", dest="mode", const="apply",
                   help="resolve, verify, log; revert + warn on doubt (default)")
    ap.set_defaults(mode="apply")
    args = ap.parse_args()
    return run(args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
