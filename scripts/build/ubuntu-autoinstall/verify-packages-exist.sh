#!/bin/sh
# Fail the BUILD if the autoinstall names a package Ubuntu does not ship.
#
# WHY THIS EXISTS. Subiquity resolves `packages:` against the archive. A name it
# cannot find aborts the install — AFTER partitioning and unpacking, which is
# the worst possible moment to learn about a typo.
#
# The Debian side already learned this twice: `verify-iso-has-packages.sh` exists
# because "Unable to install zstd" cost an hour, and `xdg-utils` — needed by
# EVERY frontend's dashboards deploy — was in no package list at all, so the
# whole cockpit deploy died on a clean install (2026-07-28).
#
# So check it where it is cheap: against the real archive index, in seconds,
# before a 6 GB remaster. This is the Ubuntu counterpart of
# installer-cdd/verify-iso-has-packages.sh.
#
# Needs network (it reads the archive Packages indices). SKIPS cleanly when
# offline rather than failing a build that is otherwise fine — an unverifiable
# list is not the same as a wrong one.
#
# Usage: verify-packages-exist.sh <user-data> [suite]
set -eu

UD="${1:?usage: verify-packages-exist.sh <user-data> [suite]}"
SUITE="${2:-${SOVEREIGN_OS_SUITE:-resolute}}"
MIRROR="${SOVEREIGN_OS_UBUNTU_MIRROR:-http://archive.ubuntu.com/ubuntu}"

[ -r "${UD}" ] || { echo "verify-packages: cannot read ${UD}" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || {
  echo "verify-packages: python3 unavailable — skipping" >&2; exit 0; }

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

got=0
for comp in main restricted universe multiverse; do
  if curl -sf --max-time 120 -o "${WORK}/${comp}.gz" \
       "${MIRROR}/dists/${SUITE}/${comp}/binary-amd64/Packages.gz" 2>/dev/null; then
    got=$((got + 1))
  fi
done
if [ "${got}" -eq 0 ]; then
  echo "verify-packages: could not fetch any ${SUITE} package index (offline?) — skipping" >&2
  exit 0
fi

python3 - "${UD}" "${WORK}" "${SUITE}" <<'PY'
import glob, gzip, sys, zlib, yaml

ud, work, suite = sys.argv[1], sys.argv[2], sys.argv[3]

# A FETCH FAILURE IS NOT A VERDICT ABOUT THE ARCHIVE.
#
# 2026-07-29: a partially-downloaded restricted/Packages.gz made gzip raise
# EOFError("Compressed file ended before the end-of-stream marker was
# reached"). EOFError is NOT an OSError, so it escaped the handler below,
# crashed this script, and build.sh reported
#     "the autoinstall names package(s) Ubuntu 26.04 does not have"
# about nvidia-driver-570-open, which Ubuntu absolutely does have. The
# diagnosis pointed at the package list instead of at the download.
#
# The subtler half: even when a truncated file reads PARTIALLY, the names it
# did yield can push the total past the sanity threshold while the component
# holding the wanted package is the one that got cut. A partial index must
# therefore invalidate the whole run, not merely shrink it.
have = set()
unreadable = []
for f in glob.glob(f"{work}/*.gz"):
    try:
        with gzip.open(f, "rt", errors="replace") as fh:
            for line in fh:
                if line.startswith("Package: "):
                    have.add(line[9:].strip())
    except (OSError, EOFError, zlib.error) as e:
        # gzip.BadGzipFile subclasses OSError; EOFError and zlib.error do not.
        unreadable.append(f"{f}: {type(e).__name__}: {e}")

if unreadable:
    print("verify-packages: could not read an index COMPLETELY:", file=sys.stderr)
    for u in unreadable:
        print(f"    {u}", file=sys.stderr)
    print("verify-packages: a partial index cannot prove a package is absent — "
          "skipping verification rather than blaming the package list",
          file=sys.stderr)
    raise SystemExit(0)

if len(have) < 1000:
    print(f"verify-packages: index looks truncated ({len(have)} names) — skipping",
          file=sys.stderr)
    raise SystemExit(0)

want = (yaml.safe_load(open(ud))["autoinstall"] or {}).get("packages") or []
missing = [p for p in want if p not in have]

print(f"verify-packages: {len(want)} requested, "
      f"{len(want) - len(missing)} present in {suite} ({len(have)} indexed)")
if missing:
    print("verify-packages: ‼ NOT IN THE UBUNTU ARCHIVE:", file=sys.stderr)
    for p in missing:
        print(f"    {p}", file=sys.stderr)
    print("  Subiquity aborts on an unknown package name — AFTER partitioning.",
          file=sys.stderr)
    print("  Fix the name (see scripts/build/lib/distro.sh for the Debian→Ubuntu map)",
          file=sys.stderr)
    print("  or drop it from autoinstall/user-data.", file=sys.stderr)
    raise SystemExit(1)
PY
