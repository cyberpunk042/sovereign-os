# shellcheck shell=bash
# scripts/osctl.d/env.sh — sovereign-osctl `env` verb module (F-2026-025).
# Sourced by the main sovereign-osctl dispatcher; do not run directly.
#
# environment / runtime-config inspection.
# Extracted verbatim from the sovereign-osctl monolith — behavior is
# byte-identical (same shell, same globals: __REPO_ROOT / PYTHON3 /
# log_* / common.sh helpers are all resident before dispatch sources this).

cmd_env() {
  local sub="${1:-list}"
  shift || true

  case "${sub}" in
    list)
      local filter=""
      while [ $# -gt 0 ]; do
        case "$1" in
          --filter) filter="${2:-}"; shift 2 ;;
          -*) log_error "unknown env list flag: $1"; return 2 ;;
          *) shift ;;
        esac
      done

      # Scan + dedupe + present
      ENV_FILTER="${filter}" REPO_ROOT="${__REPO_ROOT}" ${PYTHON3} - <<'PY'
import os, re, pathlib, collections

repo = pathlib.Path(os.environ["REPO_ROOT"])
flt  = os.environ.get("ENV_FILTER", "")
flt_re = re.compile(flt) if flt else None

# Two patterns:
#   defaults  — `: "${VAR:=value}"` or `: ${VAR:=value}`
#   reads     — bare `${VAR}` or `$VAR` references
DEFAULT_RE = re.compile(r':\s*"?\$\{(SOVEREIGN_OS_[A-Z0-9_]+):=([^}]*)\}"?')
READ_RE    = re.compile(r'\bSOVEREIGN_OS_[A-Z0-9_]+\b')

defaults = {}     # var → (default-value, file)
consumers = collections.defaultdict(set)   # var → set(file)

for path in repo.glob("scripts/**/*"):
    if not path.is_file(): continue
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        continue
    rel = str(path.relative_to(repo))
    for m in DEFAULT_RE.finditer(text):
        var, default = m.group(1), m.group(2)
        if var not in defaults:
            defaults[var] = (default, rel)
    for var in READ_RE.findall(text):
        consumers[var].add(rel)

all_vars = sorted(set(defaults) | set(consumers))
if flt_re:
    all_vars = [v for v in all_vars if flt_re.search(v)]

# Header
print(f"{'NAME':<46} {'DEFAULT':<32} CONSUMERS")
for var in all_vars:
    default, _ = defaults.get(var, ("(no default; set by operator)", ""))
    default_short = default[:30] + ".." if len(default) > 32 else default
    consumer_count = len(consumers.get(var, ()))
    print(f"{var:<46} {default_short:<32} {consumer_count}")

print()
print(f"  total: {len(all_vars)} env var(s)")
if flt_re:
    print(f"  filter: /{flt}/")
print(f"  for details: sovereign-osctl env show <NAME>")
PY
      ;;

    show)
      local name="${1:-}"
      if [ -z "${name}" ]; then
        log_error "usage: sovereign-osctl env show <NAME>"
        return 2
      fi
      ENV_NAME="${name}" REPO_ROOT="${__REPO_ROOT}" CURRENT="${!name:-(unset)}" ${PYTHON3} - <<'PY'
import os, re, pathlib, sys

repo = pathlib.Path(os.environ["REPO_ROOT"])
name = os.environ["ENV_NAME"]
current = os.environ["CURRENT"]

if not name.startswith("SOVEREIGN_OS_"):
    print(f"warn: '{name}' does not start with SOVEREIGN_OS_ — env-var discovery limited", file=sys.stderr)

DEFAULT_RE = re.compile(rf':\s*"?\$\{{{re.escape(name)}:=([^}}]*)\}}"?')
READ_RE = re.compile(rf'\b{re.escape(name)}\b')

default_value = None
default_file = None
consumers = []
for path in repo.glob("scripts/**/*"):
    if not path.is_file(): continue
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        continue
    rel = str(path.relative_to(repo))
    m = DEFAULT_RE.search(text)
    if m and default_value is None:
        default_value = m.group(1)
        default_file = rel
    if READ_RE.search(text):
        consumers.append(rel)

print(f"  name:           {name}")
print(f"  default:        {default_value if default_value else '(no default; set by operator)'}")
if default_file:
    print(f"  default-from:   {default_file}")
print(f"  currently set:  {current}")
print(f"  consumed by:    {len(consumers)} file(s)")
for c in sorted(set(consumers))[:20]:
    print(f"                  - {c}")
if len(set(consumers)) > 20:
    print(f"                  ... and {len(set(consumers)) - 20} more")
if not default_value and not consumers:
    print(f"  WARNING: env var '{name}' not found anywhere in scripts/")
    sys.exit(1)
PY
      ;;

    *)
      log_error "unknown env subcommand: ${sub}"
      log_error "  available: list [--filter <regex>] | show <NAME>"
      return 2
      ;;
  esac
}
