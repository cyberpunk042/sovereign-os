# Profile authoring (operator handbook)

Every profile is a YAML file at `profiles/<id>.yaml`, schema-validated against `schemas/profile.schema.yaml`.

## Minimum viable profile

```yaml
schema_version: "1.0.0"

mixins:
  - role-workstation
  - whitelabel-default
  - observability-tier-1

identity:
  id: my-profile
  name: "My Custom Profile"
  version: "0.1.0"
  parent: null
  status: draft
  maintainer: your-name
  description: |
    At least 30 characters of human-readable description.

hardware:
  cpu:
    architecture: x86_64
    family: amd-zen5
    march: znver5
    features:
      required: [avx512f]
    cores:
      physical: 8
      threads: 16

  memory:
    minimum_gb: 16
    type: ddr5

  storage:
    layout: ext4
    devices:
      - role: rootfs
        type: nvme-pcie-5
        count: 1
        topology: single

  network:
    - role: lan
      speed_gbps: 2.5
      default_gateway: true

kernel:
  source: substrate-default
  version_minimum: "6.6"

packages:
  base:
    - openssh-server
    - sudo
    - tmux
  profile: []
  deny:
    - popularity-contest
    - apport

hooks:
  post_install_first_boot: []

lifecycle:
  evolution_policy: replaceable
```

## Validation

```sh
sovereign-osctl profiles validate
```

Both the raw profile and the mixin-resolved effective profile must pass schema-conformance.

## Mixins

Cross-cutting fragments. Composed via `mixins:` list. Each mixin lives in `profiles/mixins/<id>.yaml` and contributes to packages, hooks, observability, etc.

Authoring a mixin:

```yaml
schema_version: "1.0.0"
mixin:
  id: my-mixin
  description: |
    What this mixin contributes.

packages:
  base:
    - bash-completion
```

## Inheritance (parent)

Set `identity.parent: <base-profile-id>` to derive from another profile. The merger resolves: mixins → parent → child (last wins on scalar conflicts; mixin-vs-mixin conflicts FAIL).

## Conflict resolution rules

- Scalars: child > parent > mixins
- Lists: child appends to parent; `packages.deny` strips matching items
- Maps: deep-merge with child-wins-on-conflict
- Mixin-vs-mixin scalar conflict: **build fails** (no silent precedence)

See `tools/profile_merger.py` for the implementation.
