#!/usr/bin/env python3
"""add-smart-display.py — one-shot transformer: adds the tier field to every
GROUPS item + the "Advanced display" toggle to the app-shell settings pane.

Run ONCE to apply the Smart Display feature. After this, the app-shell
snippet is the canonical source (sync-app-shell.py distributes it).

Usage:
  python3 scripts/webapp/add-smart-display.py          # dry-run (print diff)
  python3 scripts/webapp/add-smart-display.py --apply  # write the file
"""
from __future__ import annotations
import re, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SNIPPET = REPO_ROOT / "webapp" / "_shared" / "app-shell-snippet.html"

# ── Tier assignments ──────────────────────────────────────────────────────
# 'core' = always shown (Smart Display default). 'adv' = only when
# "Advanced display" is toggled ON in ⚙ Settings.
CORE_DIRS = frozenset({
    # Learn
    'course',
    # Trinity & Orchestration
    'trinity', 'brain', 'router',
    'd-01-active-sessions', 'd-03-model-health',
    # Models & Compute
    'd-21-lm-orchestration', 'd-22-lm-status-operability', 'code-console',
    # Hardware & Operations
    'd-09-hardware-pressure', 'd-04-costs', 'd-08-rollback-points',
    'd-02-profile-choices', 'global-history', 'build-configurator',
    # Security & selfdef
    'd-25-selfdef-management', 'd-06-pending-approvals',
    'd-20-peace-machine-health',
    # Governance & Meta
    'master-dashboard', 'personalization',
})

def _apply(content: str) -> tuple[str, list[str]]:
    """Return (new_content, list_of_changes)."""
    changes: list[str] = []

    # ── 1. Add tier field to each GROUPS item ─────────────────────────────
    gs = content.index("var GROUPS = [")
    ge = content.index("];", gs) + 2
    before, groups, after = content[:gs], content[gs:ge], content[ge:]

    tiered = 0
    for d in sorted(set(re.findall(r"dir:'([^']+)'", groups))):
        if f"dir:'{d}',tier:" in groups:
            continue  # already tiered (idempotent)
        tier = 'core' if d in CORE_DIRS else 'adv'
        old = f"dir:'{d}'"
        new = f"dir:'{d}',tier:'{tier}'"
        if old not in groups:
            print(f"  WARN: dir '{d}' not found in groups block", file=sys.stderr)
            continue
        groups = groups.replace(old, new, 1)
        tiered += 1

    content = before + groups + after
    changes.append(f"  [1] tier fields added to {tiered} GROUPS items "
                   f"({len(CORE_DIRS)} core, {tiered - len(CORE_DIRS)} advanced)")

    # ── 2. Replace buildSidemenu with tier-filtering version ─────────────
    old_build = (
        "  function buildSidemenu(dir){\n"
        "    var root='../';\n"
        "    var html=GROUPS.map(function(g){\n"
        "      var items=g.items.map(function(it){\n"
    )
    if "advOn()" in content:
        changes.append("  [2] buildSidemenu already has advOn() — skipped")
    else:
        assert old_build in content, "buildSidemenu head not found"
        new_build = (
            "  // ── Smart Display: advanced-mode toggle (localStorage-backed, OFF by\n"
            "     //    default = show only tier:'core' items; ON = show the full\n"
            "     //    catalog). Applies live — no reload. ──\n"
            "  var ADV_KEY='sovereign-os.advanced-display', ADV_SCHEMA=1;\n"
            "  function advOn(){ try{var p=JSON.parse(localStorage.getItem(ADV_KEY)); return !!(p&&p.schema===ADV_SCHEMA&&p.on);}catch(e){return false;} }\n"
            "  function advSet(on){\n"
            "    try{ localStorage.setItem(ADV_KEY, JSON.stringify({schema:ADV_SCHEMA, on:!!on})); }catch(e){}\n"
            "    try{ window.dispatchEvent(new CustomEvent('sovereign-os:adv-display',{detail:{on:!!on}})); }catch(e){}\n"
            "    var old=document.getElementById('so-sidemenu'); if(old) old.remove();\n"
            "    buildSidemenu(curDir());\n"
            "  }\n"
            "  function buildSidemenu(dir){\n"
            "    var root='../';\n"
            "    var _adv=advOn();\n"
            "    var html=GROUPS.map(function(g){\n"
            "      var items=g.items.filter(function(it){ return _adv||it.tier==='core'; }).map(function(it){\n"
        )
        content = content.replace(old_build, new_build, 1)

        # Close the filtered map + hide empty groups
        old_close = (
            "      }).join('');\n"
            "      return '<div class=\"so-grp\"><button class=\"so-grp-h\" type=\"button\"><span>'+esc(g.name)+'</span><span class=\"chev\">▾</span></button><div class=\"so-grp-items\">'+items+'</div></div>';\n"
        )
        new_close = (
            "      }).join('');\n"
            "      if(!items) return '';\n"
            "      return '<div class=\"so-grp\"><button class=\"so-grp-h\" type=\"button\"><span>'+esc(g.name)+'</span><span class=\"chev\">▾</span></button><div class=\"so-grp-items\">'+items+'</div></div>';\n"
        )
        # Only replace the first occurrence (inside buildSidemenu)
        content = content.replace(old_close, new_close, 1)
        changes.append("  [2] buildSidemenu now filters by tier (core-only when adv OFF)")

    # ── 3. Filter CMDK (⌘K palette) by tier ───────────────────────────────
    old_cmdk = (
        "    var CMDK=[]; GROUPS.forEach(function(g){ g.items.forEach(function(it){ "
        "CMDK.push({id:it.id,dir:it.dir,label:it.label,ico:it.ico,grp:g.name}); }); });"
    )
    cmdk_filtered = "if(_adv||it.tier==='core') CMDK.push" in content
    if cmdk_filtered:
        changes.append("  [3] CMDK already filtered — skipped")
    else:
        assert old_cmdk in content, "CMDK line not found"
        new_cmdk = (
            "    var _adv=advOn();\n"
            "    var CMDK=[]; GROUPS.forEach(function(g){ g.items.forEach(function(it){ "
            "if(_adv||it.tier==='core') CMDK.push({id:it.id,dir:it.dir,label:it.label,ico:it.ico,grp:g.name}); }); });"
        )
        content = content.replace(old_cmdk, new_cmdk, 1)
        changes.append("  [3] CMDK (⌘K palette) now filters by tier")

    # ── 4. Add "Advanced display" row to settings pane ────────────────────
    old_demo = (
        "          '<button class=\"so-set-switch\" id=\"so-demo-switch\" role=\"switch\" "
        "aria-checked=\"false\" aria-label=\"Toggle DEMO mode\"><span class=\"knob\"></span></button></div>'+"
    )
    if 'id="so-adv-switch"' in content:
        changes.append("  [4] adv-switch row already present — skipped")
    else:
        assert old_demo in content, "DEMO switch row not found"
        new_demo = (
            "          '<button class=\"so-set-switch\" id=\"so-demo-switch\" role=\"switch\" "
            "aria-checked=\"false\" aria-label=\"Toggle DEMO mode\"><span class=\"knob\"></span></button></div>'+\n"
            "        '<div class=\"so-set-row\"><div class=\"so-set-lbl\"><b>Advanced display</b>'+\n"
            "          '<span class=\"so-set-sub\">Show every panel in the sidemenu. "
            "Off = Smart Display (core panels only). On = full catalog. Applies live, no reload.</span></div>'+\n"
            "          '<button class=\"so-set-switch\" id=\"so-adv-switch\" role=\"switch\" "
            "aria-checked=\"false\" aria-label=\"Toggle advanced display\"><span class=\"knob\"></span></button></div>'+"
        )
        content = content.replace(old_demo, new_demo, 1)
        changes.append("  [4] 'Advanced display' row added to ⚙ Settings")

    # ── 5. Wire the switch + sync in setPaneOpen ──────────────────────────
    old_wire = (
        "    var setPane=document.getElementById('so-settings-pane'), "
        "setBtn=document.getElementById('so-settings-toggle'), "
        "demoSw=document.getElementById('so-demo-switch');"
    )
    if 'advSw' in content:
        changes.append("  [5] advSw already wired — skipped")
    else:
        assert old_wire in content, "setPane var line not found"
        new_wire = (
            "    var setPane=document.getElementById('so-settings-pane'), "
            "setBtn=document.getElementById('so-settings-toggle'), "
            "demoSw=document.getElementById('so-demo-switch'), "
            "advSw=document.getElementById('so-adv-switch');"
        )
        content = content.replace(old_wire, new_wire, 1)

        # Add syncAdvSwitch after syncDemoSwitch definition
        old_sync = (
            "    function syncDemoSwitch(){ var on=demoOn(); "
            "demoSw.setAttribute('aria-checked',on?'true':'false'); demoSw.classList.toggle('on',on); }"
        )
        new_sync = (
            "    function syncDemoSwitch(){ var on=demoOn(); "
            "demoSw.setAttribute('aria-checked',on?'true':'false'); demoSw.classList.toggle('on',on); }\n"
            "    function syncAdvSwitch(){ var on=advOn(); "
            "advSw.setAttribute('aria-checked',on?'true':'false'); advSw.classList.toggle('on',on); }"
        )
        content = content.replace(old_sync, new_sync, 1)

        # Add advSw click handler after demoSw click handler
        old_click = "    demoSw.addEventListener('click',function(){ demoSet(!demoOn()); });"
        new_click = (
            "    demoSw.addEventListener('click',function(){ demoSet(!demoOn()); });\n"
            "    advSw.addEventListener('click',function(){ advSet(!advOn()); syncAdvSwitch(); });"
        )
        content = content.replace(old_click, new_click, 1)

        # Add syncAdvSwitch() to setPaneOpen
        old_pane = "if(open){ syncDemoSwitch(); syncCourseSwitch(); }"
        new_pane = "if(open){ syncDemoSwitch(); syncAdvSwitch(); syncCourseSwitch(); }"
        content = content.replace(old_pane, new_pane, 1)

        # Add syncAdvSwitch() init call after syncDemoSwitch()
        # The standalone syncDemoSwitch() call (not inside setPaneOpen)
        old_init = "\n    syncDemoSwitch();\n"
        new_init = "\n    syncDemoSwitch();\n    syncAdvSwitch();\n"
        # Only replace the standalone one (not the one inside setPaneOpen)
        # The standalone one is followed by a comment about sticky close
        if old_init in content:
            content = content.replace(old_init, new_init, 1)

        changes.append("  [5] advSw wired (click handler + sync in setPaneOpen + init)")

    return content, changes


def main():
    apply = '--apply' in sys.argv
    content = SNIPPET.read_text(encoding='utf-8')
    new_content, changes = _apply(content)

    print("Smart Display transformer")
    print("=" * 50)
    for c in changes:
        print(c)
    print()

    if new_content == content:
        print("No changes needed (already applied).")
        return

    if not apply:
        # Show a unified diff
        import difflib
        diff = list(difflib.unified_diff(
            content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile='a/app-shell-snippet.html',
            tofile='b/app-shell-snippet.html',
            n=2,
        ))
        print(f"DRY-RUN: {len(diff)} diff lines. Pass --apply to write.\n")
        print(''.join(diff[:80]))
        if len(diff) > 80:
            print(f"  … {len(diff)-80} more lines …")
        return

    SNIPPET.write_text(new_content, encoding='utf-8')
    print(f"\n✓ Wrote {SNIPPET}")
    print("  Next: python3 scripts/webapp/sync-app-shell.py --apply")


if __name__ == '__main__':
    main()
