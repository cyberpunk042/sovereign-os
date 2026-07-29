# Standing directive — a build artifact must NAME its distro, and the panels must SAY it

**Status**: ACTIVE (operator directive, 2026-07-29, logged during the work)
**Audience**: every session touching `scripts/build/lib/distro.sh`, any substrate
builder, steps 07/09, `scripts/operator/{flash,emulate}-api.py`, or
`webapp/{flash,emulate}/index.html`
**Extends**: [2026-07-28-ubuntu-26-04-as-a-second-distro.md](2026-07-28-ubuntu-26-04-as-a-second-distro.md).
That directive made distro a first-class axis; this one makes the axis visible
in the artifacts it produces.

## Verbatim operator statement (sacrosanct — do not paraphrase)

> "lets make sure we wont confuse wihch is which at the Emulator or Flash to
> Device panel select, like if its ubuntu or debian iso,m they should not
> collide"

## What was actually wrong

Artifact naming was ad-hoc per substrate, and **two of the four collided
silently**:

| substrate | emitted | |
|---|---|---|
| `installer-cdd` (debian) | `sain-01-installer.iso` | |
| `ubuntu-autoinstall` | `sain-01-ubuntu-installer.iso` | |
| `live-build` (**either** distro) | `sain-01-installer.iso` | **overwrote the Debian d-i ISO** |
| `mkosi` (**either** distro) | `sain-01.raw` | **Ubuntu appliance overwrote Debian's** |

The two installer ISOs avoided collision only because the Ubuntu builder
happened to insert `-ubuntu-`. That was a coincidence, not a rule. For
`live-build` and `mkosi` the second build silently replaced the first, and
afterwards **nothing on disk said which distro the file was**.

It had already produced a wrong report: step 07 matched a bare `*.iso` and
announced "the .iso is UNCHANGED" while naming the OTHER distro's image. Step 09
would have gone further and "verified" an artifact the build never produced.

A third bug lived in the same line: `installer-cdd/build.sh` hardcoded
`sain-01-installer.iso`, ignoring the profile — building `test-02` wrote into
sain-01's name. That is the same bug class the builder's own comment records as
fixed for the output DIRECTORY on 2026-07-26, still live in the FILENAME.

## The rule

**The distro is always in the artifact name.** One definition,
`distro_artifact_basename()` in `scripts/build/lib/distro.sh`:

    image      ->  <profile>-<distro>          e.g. sain-01-ubuntu.raw
    installer  ->  <profile>-<distro>-installer    sain-01-debian-installer.iso

Ubuntu's existing name already satisfied it; only Debian's changed. The inverse,
`artifact_distro_of()`, parses a name back to its distro and treats the legacy
`<profile>-installer.iso` / `<profile>.raw` (no distro segment) as **debian** —
unambiguous, because the Ubuntu substrates did not exist when those were built.
Calling a real artifact unidentifiable helps nobody.

## Naming is necessary but NOT sufficient

A name stops the overwrite. It does not stop a mis-click, and flashing the wrong
distro to an internal disk is not recoverable. Both installer ISOs end in
`-installer.iso`, so the flash panel rendered an identical row for each:

    🖴 INSTALLER · sain-01/<name> · <size>

…distinguishable only by reading the filename closely — and the panel
**default-selects the newest installer**, which after a Ubuntu build is Ubuntu
even if the operator had just built Debian.

So the APIs report `distro` + `distro_label`, and the panels render it:

    🖴 INSTALLER · Debian 13    · sain-01/sain-01-debian-installer.iso · 1.3 GiB
    🖴 INSTALLER · Ubuntu 26.04 · sain-01/sain-01-ubuntu-installer.iso · 6.2 GiB

The flash panel repeats the distro beside the armed selection and warns
explicitly when artifacts for more than one distro are present — precisely the
condition under which a mis-pick is possible.

## Discovery must be scoped too

No build step may glob a bare `*.iso` over the shared `output/` directory. Steps
07 and 09 derive their pattern from `distro_artifact_basename()`, accepting the
legacy name alongside it.

## Never delete the operator's artifact

A rebuild leaves the legacy-named ISO beside the new one — two rows, same
distro, same profile, different vintage. Step 07 **warns and prints the exact
`rm`**; it does not remove anything. Silently deleting a 1.3 GB artifact the
operator may still want is not a fix for a naming bug.

## Enforced by

`tests/lint/test_artifacts_never_collide_across_distros.py` (18 tests, proven to
bite — reinstating the old rule fails 7 of them, including the collision test
itself). It checks the property directly: no two (distro, artifact) pairs may
produce the same basename; every name round-trips back to its distro; both APIs
report it; both panels render it; neither step globs bare `*.iso`.

## Cross-references

- Rule + inverse: `scripts/build/lib/distro.sh`
- Builders: `scripts/build/installer-cdd/build.sh`,
  `scripts/build/adapters/mkosi-emit.sh`, `scripts/build/07-image-build.sh`
- Discovery: `scripts/build/07-image-build.sh`, `scripts/build/09-image-verify.sh`
- Panels: `scripts/operator/{flash,emulate}-api.py`,
  `webapp/{flash,emulate}/index.html`
