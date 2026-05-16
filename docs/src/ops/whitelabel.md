# Whitelabel authoring (operator handbook)

Each whitelabel is a YAML file at `whitelabel/<id>.yaml`, schema-validated against `schemas/whitelabel.schema.yaml`. Operator-authored.

## Minimum viable whitelabel

```yaml
schema_version: "1.0.0"

identity:
  id: my-brand
  name: "My Brand Whitelabel"
  version: "0.1.0"
  status: draft
  maintainer: your-name
  description: |
    At least 30 characters of description.

compliance_target: dfsg-only   # or trademark-cleared | internal-only

branding:
  os_id: my-brand
  os_name: "My Brand"
  os_pretty_name: "My Brand v1.0"
  os_version: "1.0"
  os_codename: "alpha"
  vendor: "your-name"
  home_url: "https://example.com"
  bug_report_url: "https://example.com/issues"
  support_url: "https://example.com/docs"
  motd: |
    Your motto here.

surfaces:
  /etc/os-release:
    strategy: template-substitution
    template: templates/os-release.tmpl
    when: pre-build

  # ... add more surface declarations per SDD-007 strategy taxonomy
```

## Template + overlay bodies

Live under `whitelabel/<id>/templates/` (for `template-substitution` strategy) and `whitelabel/<id>/overlays/` (for `file-overlay` strategy).

Template syntax: `${var}` references from `branding:` block. Unknown vars are left as-is.

## Strategy taxonomy

See [whitelabel mechanism page](../whitelabel/mechanism.md) for the 7-strategy reference.

## Legal-floor enforcement

Render engine refuses to write to:

- `/etc/debian_version`
- `/usr/share/doc/*/copyright`
- `/usr/share/man/*`
- `*/debian-logo*`
- `*/debian-swirl*`

A whitelabel that declares a `surfaces:` entry matching any of these patterns fails with exit code 4 (legal-floor violation).

## Compliance posture

Must match the profile's `whitelabel.legal_compliance`. Mismatch fails with exit code 3.

## Validation

```sh
# Schema check
python3 -c "
import yaml, jsonschema
schema = yaml.safe_load(open('schemas/whitelabel.schema.yaml'))
wl = yaml.safe_load(open('whitelabel/my-brand.yaml'))
jsonschema.Draft202012Validator(schema).validate(wl)
print('PASS')
"

# Render dry-run (validates legal floor + compliance match)
python3 scripts/whitelabel/render.py \
  --profile profiles/sain-01.yaml \
  --whitelabel whitelabel/my-brand.yaml \
  --out /tmp/wl-test \
  --substrate mkosi
```

## On-running-system apply

```sh
sovereign-osctl whitelabel apply my-brand
```

Renders to `/tmp/sovereign-os-whitelabel-my-brand/`. Non-rebuild strategies copy to live system; build-time-flag strategies require image rebuild.
