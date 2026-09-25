# Cockpit model download service

Status: scoped grant installed by the operator; live download start verified.
Mocked transfer tests do not certify real artifact completion or model reliability.

## Live verification, 2026-09-24

All three candidate requests through `POST :8130/api/control/execute` returned
`ok: true`, `dry_run: false`, `exit_code: 0`. Qwen3.8-27B-Q4_K_M reached
`downloading`, with 23915836 / 18973870925 bytes reported; Q8_0 and
Qwen3-Coder-Next-Q6_K were queued. The Q4 unit reported `ActiveState=active`,
`SubState=running`. The live :8129 profile API exposes job progress and keeps
`ready=false`; the served HTML contains the Download / resume button.
No manual directory creation, API restart or workstation reboot was needed.
Download completion, resume behavior and model activation remain unverified.

## User workflow

Select a profile that needs models, then **Download / resume missing models**.
The button calls the existing `/api/control/execute` endpoint with the privileged
`model-download` control. The read-only LM API remains read-only. The control
starts a transient systemd service and returns without waiting for a large model
download. Transfers are serialized, leaving the cockpit execution rail available.

The worker creates the catalog model directory itself under `/mnt/vault/models`.
It accepts only catalog IDs with a real HF repository and explicit artifact
patterns, not arbitrary repository IDs, paths, tokens, shell commands or flags.
The worker reads credentials through `scripts/models/hf-auth.py`, including the
private `/etc/sovereign-os/model.env` file. Credentials are not passed in argv or
included in public job state. No recursive chown or chmod of the vault is used.

The worker pins the resolved HF revision, checks disk space with a 2 GiB margin,
downloads only selected files, and verifies weight SHA256 hashes before completion.
Partial transfers can be retried. A prior verification failure forces a fresh
download of the selected artifacts. Per-model systemd units prevent two workers
writing the same model simultaneously. The runtime limit is 24 hours per job.

The profile inspector displays queued/preflight/downloading/verifying/failed/
complete state and transferred bytes. The API no longer counts an empty directory
as resident. Legacy downloads without job manifests get presence checks, NOT
retroactive checksum certification. Model runtime fitness remains a separate test.
Download completion never implicitly activates a profile.

## Installation boundary

`config/sudoers.d/sovereign-os-cockpit` adds exactly:

    /usr/local/bin/sovereign-osctl models download *

The root-side helper validates the catalog ID and rejects extra CLI arguments.
The operator-sudoers installer already reads this canonical policy. An administrator
must review/install its update with `scripts/operator/operator-sudoers.sh` through
the normal authenticated installation procedure. Do not repurpose an existing
privileged maintenance/profile command to bypass that grant.

Deploy the changed CLI, helper, LM API, control primitive, catalog and cockpit asset
together. Restart the two API services after deployment so imported modules update;
no workstation reboot is required. The updated control primitive reports missing
sudo permission as HTTP 503 with `installation_required`, not a generic model error.

## Verification

`tests/test_model_download_job.py` covers catalog/path rejection, exact artifact
selection, incomplete files, failed checksums, token exclusion from state, symlink
refusal, detached command shape and missing-installation reporting. Related HF auth,
control registry, sudoers, action-execution and D21 contract tests run alongside it.

Still required after installation: real authenticated start from the cockpit,
progress rendering against an actual transfer, interruption/resume, final checksum
verification and a separate profile-activation check. No live reliability claim
until these pass.
