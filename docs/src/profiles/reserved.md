# Reserved profile slots (Q-012)

Slots intentionally reserved without substantive bodies. Per the operator's "do not minimize, do not conflate" quality bar: authoring placeholder profile bodies suggests commitment without a stated need. INDEX reservation is the Q-012 acknowledgment.

| ID | Intent | When body lands |
|---|---|---|
| `minimal` | Server-class install; no DE; bare-essentials only | When concrete operator need surfaces |
| `developer` | Developer workstation with DE + full toolchain + debugging tooling | Same |
| `headless` | Headless install; no DE; remote-managed; useful for fleet member nodes | Same |

## How to author a new profile

1. Copy `profiles/sain-01.yaml` or `profiles/old-workstation.yaml`.
2. Update `identity.id` to match the new filename.
3. Adjust `hardware.*`, `kernel.*`, `packages.*`, `hooks.*` for the target.
4. Optionally compose mixins via `mixins:` list.
5. Run `sovereign-osctl profiles validate` — must PASS.
6. Add a row to `profiles/INDEX.md`.

## Custom profiles

Operator can add profiles freely. The schema (`schemas/profile.schema.yaml`) is the only constraint. Mixins (`profiles/mixins/`) reduce duplication across related profiles.
