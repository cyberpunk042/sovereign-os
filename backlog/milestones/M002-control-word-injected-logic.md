# M002 — 32/64-bit injected logic / control word per branch

> Parent: `backlog/milestones/INDEX.md` row M002 (dump 118–212).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 118–212.
> All entries below are extracted from the dump line range. No invention.

## Epics (E0011–E0019)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0011 | Control word bitfield layout — mode/event/intensity/cooldown/neighborhood/paramA/paramB | 136–143 |
| E0012 | Branchless masked-op execution per lane | 146–154 |
| E0013 | 64-entry boolean LUT inside one u64 via `(rule_word >> 6-bit-condition) & 1` | 161–177 |
| E0014 | Per-branch micro-rule table as inline memory | 168–177 |
| E0015 | Layout — state / memory / rule / random per ZMM | 182–199 |
| E0016 | Variable per-lane shifts cost-vs-AND/XOR/OR tradeoff | 199 |
| E0017 | 32-bit rule word — 5-bit condition, 32-entry table | 204 |
| E0018 | 64-bit rule word — 6-bit condition, 64-entry table | 205 |
| E0019 | 128-bit rule word — two u64 limbs | 206 |

## Modules (M00012–M00028)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00012 | u64 lane fields — state_lo / state_hi / control / scratch | 124–129 | E0015 |
| M00013 | 64-bit control word bit layout — bits 0..3 mode / 4..7 event / 8..15 intensity / 16..23 cooldown / 24..31 neighborhood / 32..47 paramA / 48..63 paramB | 136–143 | E0011 |
| M00014 | Branchless decision — `mask = (mode == 3)` | 146–154 | E0012 |
| M00015 | Masked AVX-512 ops per lane | 152 | E0012 |
| M00016 | 6-bit condition = neighbor + stress + damage + random bits | 158–162 | E0013 |
| M00017 | 64-entry boolean rule LUT via right-shift+AND | 165–170 | E0013 |
| M00018 | Per-lane DNA — rule embedded inside state | 173–177 | E0014 |
| M00019 | Strong layout — zmm0 state / zmm1 memory / zmm2 rule / zmm3 random/feed | 182–188 | E0015 |
| M00020 | Round update — extract / decision / apply / update memory / advance RNG | 189–197 | E0015 |
| M00021 | Variable per-lane shifts cost — more expensive than AND/XOR/OR | 199 | E0016 |
| M00022 | 5-bit condition → 32-entry table inside u32 | 204 | E0017 |
| M00023 | 6-bit condition → 64-entry table inside u64 | 205 | E0018 |
| M00024 | 128-bit rule across two u64 limbs | 206 | E0019 |
| M00025 | Compose 64-bit control word from 8 bitfields without overflow | 136–143 | E0011 |
| M00026 | Decompose 64-bit control word into 8 typed fields | 136–143 | E0011 |
| M00027 | Bit-packing helper library (Rust + C++) for control words | 136–143 | E0011 |
| M00028 | Bit-extract helper library (Rust + C++) for control words | 136–143 | E0011 |

## Features (F00086–F00170)

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F00086 | Toggle u64 lane-fields layout (state_lo/state_hi/control/scratch) | 124–129 | M00012 | mode | true |
| F00087 | Profile knob — `lane_fields_layout = standard \| custom` | 124–129 | M00012 | profile | true |
| F00088 | Env var `SOVEREIGN_CTRL_LANE_FIELDS_LAYOUT` | 124–129 | M00012 | env_var | true |
| F00089 | CLI `--lane-fields <layout>` | 124–129 | M00012 | cli_verb | true |
| F00090 | Dashboard surface — lane-fields layout visualization | 124–129 | M00012 | dashboard | true |
| F00091 | Toggle 64-bit control word standard bit layout | 136–143 | M00013 | mode | true |
| F00092 | Profile knob — `control_word_layout_version` | 136–143 | M00013 | profile | true |
| F00093 | Env var `SOVEREIGN_CTRL_WORD_LAYOUT_VERSION` | 136–143 | M00013 | env_var | true |
| F00094 | CLI `--control-word-layout <version>` | 136–143 | M00013 | cli_verb | true |
| F00095 | Dashboard surface — control-word bit-layout inspector | 136–143 | M00013 | dashboard | true |
| F00096 | API `GET /v1/control-word/layout` — return current layout schema | 136–143 | M00013 | api_endpoint | true |
| F00097 | Metric `sovereign_os_control_word_layout_version` | 136–143 | M00013 | observability_metric | true |
| F00098 | Test — control-word bitfields encode/decode round-trip | 136–143 | M00027 | test | true |
| F00099 | Test — control-word overflow detection on each field | 136–143 | M00027 | test | true |
| F00100 | Lifecycle hook — pre-decode control word | 136–143 | M00028 | lifecycle_hook | true |
| F00101 | Lifecycle hook — post-encode control word | 136–143 | M00027 | lifecycle_hook | true |
| F00102 | Personalization — operator-defined control-word layout YAML | 136–143 | M00013 | configuration | true |
| F00103 | Personalization — operator-defined control-word field aliases | 136–143 | M00013 | configuration | true |
| F00104 | Toggle branchless masked-op execution mode | 146–154 | M00014 | mode | true |
| F00105 | Profile knob — `masked_op_mode = branchless \| branchy` | 146–154 | M00014 | profile | true |
| F00106 | Env var `SOVEREIGN_CTRL_MASKED_OP_MODE` | 146–154 | M00014 | env_var | true |
| F00107 | CLI `--masked-op-mode <mode>` | 146–154 | M00014 | cli_verb | true |
| F00108 | Dashboard surface — masked-op execution per-lane heatmap | 146–154 | M00015 | dashboard | true |
| F00109 | Metric `sovereign_os_masked_op_per_lane_diversity_pct` | 146–154 | M00015 | observability_metric | true |
| F00110 | Test — branchless mode produces identical output to branchy on uniform input | 146–154 | M00014 | test | true |
| F00111 | Test — branchless mode advantages preserved under heterogeneous lane inputs | 146–154 | M00015 | test | true |
| F00112 | Lifecycle hook — pre-masked-op CPU AVX-512 feature check | 146–154 | M00015 | lifecycle_hook | true |
| F00113 | Composite — branchless + lane-fields-aware control-word evolver | 146–154 | composite: [M00014, M00012] | capability | true |
| F00114 | Toggle 6-bit-condition LUT mode | 161–177 | M00017 | mode | true |
| F00115 | Profile knob — `lut_condition_width = 5 \| 6 \| 7` | 161–177 | M00017 | profile | true |
| F00116 | Env var `SOVEREIGN_CTRL_LUT_CONDITION_WIDTH` | 161–177 | M00017 | env_var | true |
| F00117 | CLI `--lut-condition-width <bits>` | 161–177 | M00017 | cli_verb | true |
| F00118 | Dashboard surface — 64-entry LUT inspector per branch | 161–177 | M00017 | dashboard | true |
| F00119 | API `POST /v1/control-word/lut/lookup` — return decision bit for condition | 161–177 | M00017 | api_endpoint | true |
| F00120 | Metric `sovereign_os_lut_hit_rate_per_condition` | 161–177 | M00017 | observability_metric | true |
| F00121 | Test — `(rule_word >> condition) & 1` correctness across condition 0..63 | 161–177 | M00017 | test | true |
| F00122 | Test — LUT round-trip encode/decode | 161–177 | M00017 | test | true |
| F00123 | Composite — per-branch DNA evolver using inline LUT + control word | 168–177 | composite: [M00017, M00018, M00013] | capability | true |
| F00124 | Toggle per-lane-DNA mode | 173–177 | M00018 | mode | true |
| F00125 | Profile knob — `per_lane_dna_enabled` | 173–177 | M00018 | profile | true |
| F00126 | Env var `SOVEREIGN_CTRL_PER_LANE_DNA_ENABLED` | 173–177 | M00018 | env_var | true |
| F00127 | CLI `--per-lane-dna` | 173–177 | M00018 | cli_verb | true |
| F00128 | Dashboard surface — per-lane DNA visualizer | 173–177 | M00018 | dashboard | true |
| F00129 | Metric `sovereign_os_per_lane_dna_diversity_index` | 173–177 | M00018 | observability_metric | true |
| F00130 | Test — per-lane DNA mode produces unique evolution per lane | 173–177 | M00018 | test | true |
| F00131 | Lifecycle hook — pre-DNA-update emit current DNA fingerprint | 173–177 | M00018 | lifecycle_hook | true |
| F00132 | Lifecycle hook — post-DNA-update log delta | 173–177 | M00018 | lifecycle_hook | true |
| F00133 | Toggle strong ZMM layout (state/memory/rule/random) | 182–188 | M00019 | mode | true |
| F00134 | Profile knob — `zmm_layout = strong \| operator_custom` | 182–188 | M00019 | profile | true |
| F00135 | Env var `SOVEREIGN_CTRL_ZMM_LAYOUT` | 182–188 | M00019 | env_var | true |
| F00136 | CLI `--zmm-layout <layout>` | 182–188 | M00019 | cli_verb | true |
| F00137 | Dashboard surface — ZMM layout assignment table | 182–188 | M00019 | dashboard | true |
| F00138 | Metric `sovereign_os_zmm_layout_register_assignment` (info gauge) | 182–188 | M00019 | observability_metric | true |
| F00139 | Test — strong layout register assignment matches profile | 182–188 | M00019 | test | true |
| F00140 | Toggle 5-step round-update mode | 189–197 | M00020 | mode | true |
| F00141 | Profile knob — `round_update_strict = true \| false` | 189–197 | M00020 | profile | true |
| F00142 | Env var `SOVEREIGN_CTRL_ROUND_UPDATE_STRICT` | 189–197 | M00020 | env_var | true |
| F00143 | CLI `--round-update <strict\|relaxed>` | 189–197 | M00020 | cli_verb | true |
| F00144 | Dashboard surface — round-update step timeline | 189–197 | M00020 | dashboard | true |
| F00145 | Metric `sovereign_os_round_update_steps_per_sec` | 189–197 | M00020 | observability_metric | true |
| F00146 | Test — round-update produces deterministic state across 1000 iterations | 189–197 | M00020 | test | true |
| F00147 | Lifecycle hook — pre-round emit branch snapshot | 189–197 | M00020 | lifecycle_hook | true |
| F00148 | Lifecycle hook — post-round emit state transition | 189–197 | M00020 | lifecycle_hook | true |
| F00149 | Toggle variable-shift mode (more expensive but per-lane flexibility) | 199 | M00021 | mode | true |
| F00150 | Profile knob — `variable_shift_enabled` | 199 | M00021 | profile | true |
| F00151 | Env var `SOVEREIGN_CTRL_VARIABLE_SHIFT_ENABLED` | 199 | M00021 | env_var | true |
| F00152 | CLI `--variable-shift` | 199 | M00021 | cli_verb | true |
| F00153 | Dashboard surface — shift-cost comparison (variable vs AND/XOR) | 199 | M00021 | dashboard | true |
| F00154 | Metric `sovereign_os_variable_shift_cost_ratio` | 199 | M00021 | observability_metric | true |
| F00155 | Test — variable shift correctness when replacing branchy code | 199 | M00021 | test | true |
| F00156 | Toggle 32-bit rule mode (5-bit condition) | 204 | M00022 | mode | true |
| F00157 | Toggle 64-bit rule mode (6-bit condition) | 205 | M00023 | mode | true |
| F00158 | Toggle 128-bit rule mode (two u64 limbs) | 206 | M00024 | mode | true |
| F00159 | Profile knob — `rule_word_width = 32 \| 64 \| 128` | 204–206 | M00022 | profile | true |
| F00160 | Env var `SOVEREIGN_CTRL_RULE_WORD_WIDTH` | 204–206 | M00022 | env_var | true |
| F00161 | CLI `--rule-word-width <bits>` | 204–206 | M00022 | cli_verb | true |
| F00162 | Dashboard surface — rule-word width comparison | 204–206 | M00022 | dashboard | true |
| F00163 | Metric `sovereign_os_rule_word_width_in_use` | 204–206 | M00022 | observability_metric | true |
| F00164 | Test — 32/64/128-bit rule modes equivalence on common conditions | 204–206 | M00022 | test | true |
| F00165 | Composite — control-word + LUT + per-lane DNA + variable shift composite kernel | 173–199 | composite: [M00013, M00017, M00018, M00021] | capability | true |
| F00166 | Composite — bit-packing helper library composes with all rule-word widths | 204–206 | composite: [M00027, M00028] | capability | true |
| F00167 | Personalization — operator-defined bit-field semantic naming | 136–143 | M00013 | configuration | true |
| F00168 | Personalization — operator-defined LUT named-rules registry | 161–177 | M00017 | configuration | true |
| F00169 | Personalization — operator-defined per-branch evolution recipe | 168–177 | M00018 | configuration | true |
| F00170 | Personalization — operator-defined layout-experiment harness | 182–188 | M00019 | configuration | true |

## Requirements (R00171–R00340)

| R ID | Phrase | Dump line | Parent F | Class | Opt-in | Sub-req min |
|---|---|---|---|---|---|---|
| R00171 | u64 lane field `state_lo` covers bits 0..15 | 124–129 | F00086 | non-negotiable | true | 10 |
| R00172 | u64 lane field `state_hi` covers bits 16..31 | 124–129 | F00086 | non-negotiable | true | 10 |
| R00173 | u64 lane field `control` covers bits 32..47 | 124–129 | F00086 | non-negotiable | true | 10 |
| R00174 | u64 lane field `scratch` covers bits 48..63 | 124–129 | F00086 | non-negotiable | true | 10 |
| R00175 | Lane fields layout = standard is the daemon default | 124–129 | F00087 | non-negotiable | true | 10 |
| R00176 | Lane fields layout = custom accepts operator YAML mapping | 124–129 | F00087 | non-negotiable | true | 10 |
| R00177 | Env var `SOVEREIGN_CTRL_LANE_FIELDS_LAYOUT` accepts `standard` \| `custom_<name>` | 124–129 | F00088 | non-negotiable | true | 10 |
| R00178 | CLI `--lane-fields` overrides profile when present | 124–129 | F00089 | non-negotiable | true | 10 |
| R00179 | Dashboard lane-fields layout visualization refreshes via SSE | 124–129 | F00090 | non-negotiable | true | 10 |
| R00180 | Control word standard bit layout = mode 0..3 / event 4..7 / intensity 8..15 / cooldown 16..23 / neighborhood 24..31 / paramA 32..47 / paramB 48..63 | 136–143 | F00091 | non-negotiable | false | 10 |
| R00181 | Control word layout version is semver `x.y.z` | 136–143 | F00092 | non-negotiable | true | 10 |
| R00182 | Control word layout version bump on any bit-field add or rename | 136–143 | F00092 | non-negotiable | false | 10 |
| R00183 | Env var `SOVEREIGN_CTRL_WORD_LAYOUT_VERSION` accepts semver version string | 136–143 | F00093 | non-negotiable | true | 10 |
| R00184 | CLI `--control-word-layout <version>` accepts semver version string | 136–143 | F00094 | non-negotiable | true | 10 |
| R00185 | Dashboard bit-layout inspector renders each field with label and color | 136–143 | F00095 | non-negotiable | true | 10 |
| R00186 | API `GET /v1/control-word/layout` returns JSON schema | 136–143 | F00096 | non-negotiable | true | 10 |
| R00187 | Metric `sovereign_os_control_word_layout_version` is info gauge | 136–143 | F00097 | non-negotiable | false | 10 |
| R00188 | Test — encode then decode produces identical bit pattern | 136–143 | F00098 | non-negotiable | false | 10 |
| R00189 | Test — overflow on field `paramA` (bits 32..47) when value > 65535 raises error | 136–143 | F00099 | non-negotiable | false | 10 |
| R00190 | Lifecycle hook `pre-decode` runs before every control-word read | 136–143 | F00100 | non-negotiable | true | 10 |
| R00191 | Lifecycle hook `post-encode` runs after every control-word write | 136–143 | F00101 | non-negotiable | true | 10 |
| R00192 | Operator-defined layout YAML schema: `name` `version` `fields:[{name,bits_lo,bits_hi}]` | 136–143 | F00102 | non-negotiable | true | 10 |
| R00193 | Operator-defined field aliases YAML: `aliases:{<canonical>:<operator-name>}` | 136–143 | F00103 | non-negotiable | true | 10 |
| R00194 | Branchless masked-op mode uses k-mask register for per-lane decision | 146–154 | F00104 | non-negotiable | false | 10 |
| R00195 | Branchless mode = default; branchy mode opt-in via profile | 146–154 | F00105 | non-negotiable | true | 10 |
| R00196 | Env var `SOVEREIGN_CTRL_MASKED_OP_MODE` accepts `branchless` \| `branchy` | 146–154 | F00106 | non-negotiable | true | 10 |
| R00197 | CLI `--masked-op-mode <mode>` accepts same enum | 146–154 | F00107 | non-negotiable | true | 10 |
| R00198 | Dashboard masked-op heatmap shades lane diversity 0–100% | 146–154 | F00108 | non-negotiable | true | 10 |
| R00199 | Metric `sovereign_os_masked_op_per_lane_diversity_pct` is Prometheus gauge | 146–154 | F00109 | non-negotiable | false | 10 |
| R00200 | Test — branchless and branchy modes produce bit-identical output on uniform input | 146–154 | F00110 | non-negotiable | false | 10 |
| R00201 | Test — branchless mode demonstrates speedup ≥1.5x on heterogeneous lane inputs | 146–154 | F00111 | preferable | false | 10 |
| R00202 | Lifecycle hook `pre-masked-op` aborts kernel if AVX-512 k-mask registers unavailable | 146–154 | F00112 | non-negotiable | false | 10 |
| R00203 | Composite F00113 requires modules M00014 + M00012 | 146–154 | F00113 | non-negotiable | false | 10 |
| R00204 | 6-bit condition LUT default mode | 161–177 | F00114 | non-negotiable | true | 10 |
| R00205 | LUT condition width accepts 5 / 6 / 7 (not 4 — too few entries) | 161–177 | F00115 | non-negotiable | true | 10 |
| R00206 | Env var `SOVEREIGN_CTRL_LUT_CONDITION_WIDTH` accepts integer 5/6/7 | 161–177 | F00116 | non-negotiable | true | 10 |
| R00207 | CLI `--lut-condition-width` accepts integer 5/6/7 | 161–177 | F00117 | non-negotiable | true | 10 |
| R00208 | Dashboard LUT inspector shows 64-entry table per branch with hit-count | 161–177 | F00118 | non-negotiable | true | 10 |
| R00209 | API `/v1/control-word/lut/lookup` accepts `rule_word` + `condition` and returns decision bit | 161–177 | F00119 | non-negotiable | true | 10 |
| R00210 | Metric `sovereign_os_lut_hit_rate_per_condition` is Prometheus counter labeled by condition | 161–177 | F00120 | non-negotiable | false | 10 |
| R00211 | Test — `(rule_word >> condition) & 1` correct for all 64 condition values on 100 random rule words | 161–177 | F00121 | non-negotiable | false | 10 |
| R00212 | Test — LUT serialize/deserialize round-trip | 161–177 | F00122 | non-negotiable | false | 10 |
| R00213 | Composite F00123 requires modules M00017 + M00018 + M00013 | 168–177 | F00123 | non-negotiable | false | 10 |
| R00214 | Per-lane DNA mode opt-in via profile; off by default | 173–177 | F00124 | non-negotiable | true | 10 |
| R00215 | Profile knob `per_lane_dna_enabled` accepts boolean | 173–177 | F00125 | non-negotiable | true | 10 |
| R00216 | Env var `SOVEREIGN_CTRL_PER_LANE_DNA_ENABLED` accepts `0`/`1`/`true`/`false` | 173–177 | F00126 | non-negotiable | true | 10 |
| R00217 | CLI `--per-lane-dna` opt-in toggle | 173–177 | F00127 | non-negotiable | true | 10 |
| R00218 | Dashboard per-lane DNA visualizer renders 8 lanes × 64-bit DNA bitmap | 173–177 | F00128 | non-negotiable | true | 10 |
| R00219 | Metric `sovereign_os_per_lane_dna_diversity_index` is Prometheus gauge | 173–177 | F00129 | non-negotiable | false | 10 |
| R00220 | Test — per-lane DNA mode produces ≥8 distinct evolution paths in 1000 rounds | 173–177 | F00130 | preferable | false | 10 |
| R00221 | Lifecycle hook `pre-DNA-update` emits OTel span with current fingerprint | 173–177 | F00131 | non-negotiable | false | 10 |
| R00222 | Lifecycle hook `post-DNA-update` emits OTel span with bit-flip delta | 173–177 | F00132 | non-negotiable | false | 10 |
| R00223 | Strong ZMM layout assigns zmm0 = state | 182–188 | F00133 | non-negotiable | true | 10 |
| R00224 | Strong ZMM layout assigns zmm1 = memory | 182–188 | F00133 | non-negotiable | true | 10 |
| R00225 | Strong ZMM layout assigns zmm2 = rule | 182–188 | F00133 | non-negotiable | true | 10 |
| R00226 | Strong ZMM layout assigns zmm3 = random/feed | 182–188 | F00133 | non-negotiable | true | 10 |
| R00227 | Operator-custom ZMM layout YAML accepts register-name-to-purpose mapping | 182–188 | F00134 | non-negotiable | true | 10 |
| R00228 | Env var `SOVEREIGN_CTRL_ZMM_LAYOUT` accepts `strong` \| `<custom_name>` | 182–188 | F00135 | non-negotiable | true | 10 |
| R00229 | CLI `--zmm-layout` accepts same enum | 182–188 | F00136 | non-negotiable | true | 10 |
| R00230 | Dashboard ZMM-layout table shows 4 register assignments | 182–188 | F00137 | non-negotiable | true | 10 |
| R00231 | Metric `sovereign_os_zmm_layout_register_assignment` is info gauge with register/purpose labels | 182–188 | F00138 | non-negotiable | false | 10 |
| R00232 | Test — strong layout assignment matches profile YAML | 182–188 | F00139 | non-negotiable | false | 10 |
| R00233 | 5-step round update — features = extract / decision = (rule >> features) & 1 / state = apply / memory = update / random = advance | 189–197 | F00140 | non-negotiable | false | 10 |
| R00234 | Strict mode aborts kernel on step failure | 189–197 | F00141 | non-negotiable | true | 10 |
| R00235 | Relaxed mode logs step failure and continues | 189–197 | F00141 | non-negotiable | true | 10 |
| R00236 | Env var `SOVEREIGN_CTRL_ROUND_UPDATE_STRICT` accepts boolean | 189–197 | F00142 | non-negotiable | true | 10 |
| R00237 | CLI `--round-update` accepts `strict` \| `relaxed` | 189–197 | F00143 | non-negotiable | true | 10 |
| R00238 | Dashboard round-update timeline shows step-by-step latency | 189–197 | F00144 | non-negotiable | true | 10 |
| R00239 | Metric `sovereign_os_round_update_steps_per_sec` is Prometheus counter | 189–197 | F00145 | non-negotiable | false | 10 |
| R00240 | Test — deterministic state across 1000 iterations with seeded RNG | 189–197 | F00146 | non-negotiable | false | 10 |
| R00241 | Lifecycle hook `pre-round` emits branch snapshot | 189–197 | F00147 | non-negotiable | true | 10 |
| R00242 | Lifecycle hook `post-round` emits state transition | 189–197 | F00148 | non-negotiable | true | 10 |
| R00243 | Variable-shift mode opt-in (more expensive than AND/XOR/OR) | 199 | F00149 | non-negotiable | true | 10 |
| R00244 | Profile knob `variable_shift_enabled` accepts boolean | 199 | F00150 | non-negotiable | true | 10 |
| R00245 | Env var `SOVEREIGN_CTRL_VARIABLE_SHIFT_ENABLED` | 199 | F00151 | non-negotiable | true | 10 |
| R00246 | CLI `--variable-shift` opt-in toggle | 199 | F00152 | non-negotiable | true | 10 |
| R00247 | Dashboard shift-cost comparison shows variable-shift vs AND/XOR cycles | 199 | F00153 | non-negotiable | true | 10 |
| R00248 | Metric `sovereign_os_variable_shift_cost_ratio` is Prometheus gauge | 199 | F00154 | non-negotiable | false | 10 |
| R00249 | Test — variable shift produces correct output when replacing branchy code | 199 | F00155 | non-negotiable | false | 10 |
| R00250 | 32-bit rule mode uses 5-bit condition → 32-entry boolean table | 204 | F00156 | non-negotiable | true | 10 |
| R00251 | 64-bit rule mode uses 6-bit condition → 64-entry boolean table | 205 | F00157 | non-negotiable | true | 10 |
| R00252 | 128-bit rule mode uses two u64 limbs (lo + hi) | 206 | F00158 | non-negotiable | true | 10 |
| R00253 | Profile knob `rule_word_width` accepts 32 / 64 / 128 | 204–206 | F00159 | non-negotiable | true | 10 |
| R00254 | Env var `SOVEREIGN_CTRL_RULE_WORD_WIDTH` accepts 32 / 64 / 128 | 204–206 | F00160 | non-negotiable | true | 10 |
| R00255 | CLI `--rule-word-width` accepts 32 / 64 / 128 | 204–206 | F00161 | non-negotiable | true | 10 |
| R00256 | Dashboard rule-word width comparison shows entries/expressiveness trade-off | 204–206 | F00162 | non-negotiable | true | 10 |
| R00257 | Metric `sovereign_os_rule_word_width_in_use` is info gauge | 204–206 | F00163 | non-negotiable | false | 10 |
| R00258 | Test — 32-bit and 64-bit modes produce identical decisions for first 32 conditions | 204–206 | F00164 | non-negotiable | false | 10 |
| R00259 | Composite F00165 requires modules M00013 + M00017 + M00018 + M00021 | 173–199 | F00165 | non-negotiable | false | 10 |
| R00260 | Composite F00166 requires modules M00027 + M00028 | 204–206 | F00166 | non-negotiable | false | 10 |
| R00261 | Bit-packing helper library compiles with `forbid(unsafe_code)` in Rust crate | 136–143 | M00027 | non-negotiable | false | 10 |
| R00262 | Bit-extract helper library compiles with `forbid(unsafe_code)` in Rust crate | 136–143 | M00028 | non-negotiable | false | 10 |
| R00263 | Bit-packing API: `pack_u64(&[u16; 8]) -> u64` | 136–143 | M00027 | non-negotiable | true | 10 |
| R00264 | Bit-extract API: `unpack_u64(u64) -> [u16; 8]` | 136–143 | M00028 | non-negotiable | true | 10 |
| R00265 | Operator-defined bit-field semantic naming via YAML | 136–143 | F00167 | non-negotiable | true | 10 |
| R00266 | Operator-defined LUT named-rules registry — JSON or TOML | 161–177 | F00168 | non-negotiable | true | 10 |
| R00267 | Operator-defined per-branch evolution recipe — YAML | 168–177 | F00169 | non-negotiable | true | 10 |
| R00268 | Operator-defined layout-experiment harness — YAML | 182–188 | F00170 | non-negotiable | true | 10 |
| R00269 | Control word bit layout schema is operator-stable; backward-compatible adds only | 136–143 | M00013 | non-negotiable | false | 10 |
| R00270 | Control word bit layout schema rejects renames without major-version bump | 136–143 | M00013 | non-negotiable | false | 10 |
| R00271 | Per-branch control word survives ZFS snapshot/restore | 136–143 | M00013 | non-negotiable | false | 10 |
| R00272 | Per-branch control word survives CRIU checkpoint/restore | 136–143 | M00013 | non-negotiable | false | 10 |
| R00273 | Per-branch control word serializes to OTel attribute on every model_call span | 136–143 | M00013 | non-negotiable | false | 10 |
| R00274 | Per-branch control word redacted from cloud-provider outbound when profile is private | 136–143 | M00013 | non-negotiable | true | 10 |
| R00275 | Per-branch control word never logged as plaintext outside replay log | 136–143 | M00013 | non-negotiable | false | 10 |
| R00276 | Per-branch control word content-addressed via blake3 hash in replay log | 136–143 | M00013 | non-negotiable | false | 10 |
| R00277 | LUT entry update is atomic (no torn write) | 161–177 | M00017 | non-negotiable | false | 10 |
| R00278 | LUT entry update emits OTel span | 161–177 | M00017 | non-negotiable | false | 10 |
| R00279 | LUT entry signed by operator key when `--require-signed-luts` set | 161–177 | M00017 | non-negotiable | true | 10 |
| R00280 | Per-lane DNA fingerprint = blake3(control_word + rule_word + state) | 173–177 | M00018 | non-negotiable | true | 10 |
| R00281 | Per-lane DNA fingerprint emitted on every round | 173–177 | M00018 | non-negotiable | false | 10 |
| R00282 | Per-lane DNA quarantine triggered on fingerprint drift beyond threshold | 173–177 | M00018 | non-negotiable | true | 10 |
| R00283 | Per-lane DNA replay supports forward-stepping a single lane | 173–177 | M00018 | non-negotiable | true | 10 |
| R00284 | Per-lane DNA replay supports backward-stepping a single lane | 173–177 | M00018 | non-negotiable | true | 10 |
| R00285 | Strong ZMM layout register assignment immutable during kernel execution | 182–188 | M00019 | non-negotiable | false | 10 |
| R00286 | Strong ZMM layout register assignment hot-swappable between kernels | 182–188 | M00019 | non-negotiable | true | 10 |
| R00287 | Strong ZMM layout register assignment audit log on every swap | 182–188 | M00019 | non-negotiable | false | 10 |
| R00288 | Strong ZMM layout register assignment verified pre-kernel via CPUID + register-name match | 182–188 | M00019 | non-negotiable | false | 10 |
| R00289 | Round update step `extract` reads from zmm0/zmm1/zmm3 | 189–197 | M00020 | non-negotiable | true | 10 |
| R00290 | Round update step `decision` reads zmm2 (rule) and applies `(rule >> features) & 1` | 189–197 | M00020 | non-negotiable | true | 10 |
| R00291 | Round update step `apply state` writes back to zmm0 | 189–197 | M00020 | non-negotiable | true | 10 |
| R00292 | Round update step `update memory` writes to zmm1 | 189–197 | M00020 | non-negotiable | true | 10 |
| R00293 | Round update step `advance RNG` writes to zmm3 | 189–197 | M00020 | non-negotiable | true | 10 |
| R00294 | Round update step boundaries observable via OTel spans | 189–197 | M00020 | non-negotiable | false | 10 |
| R00295 | Round update step idempotent retry on transient failure | 189–197 | M00020 | non-negotiable | false | 10 |
| R00296 | Variable shift uses VPSLLVD/VPSLLVQ instructions | 199 | M00021 | non-negotiable | false | 10 |
| R00297 | Variable shift cycle cost measured via CPUID rdtsc benchmark | 199 | M00021 | non-negotiable | false | 10 |
| R00298 | Variable shift cycle cost compared against AND/XOR baseline | 199 | M00021 | non-negotiable | false | 10 |
| R00299 | Variable shift cycle cost emitted as Prometheus metric | 199 | M00021 | non-negotiable | false | 10 |
| R00300 | 32-bit rule word stored as `u32` | 204 | M00022 | non-negotiable | false | 10 |
| R00301 | 32-bit rule word indexed by 5-bit condition (0..31) | 204 | M00022 | non-negotiable | false | 10 |
| R00302 | 64-bit rule word stored as `u64` | 205 | M00023 | non-negotiable | false | 10 |
| R00303 | 64-bit rule word indexed by 6-bit condition (0..63) | 205 | M00023 | non-negotiable | false | 10 |
| R00304 | 128-bit rule word stored as `(u64, u64)` lo + hi limb pair | 206 | M00024 | non-negotiable | false | 10 |
| R00305 | 128-bit rule word indexed by 7-bit condition (0..127) | 206 | M00024 | non-negotiable | false | 10 |
| R00306 | 128-bit rule word limb-selection by condition bit 6 | 206 | M00024 | non-negotiable | false | 10 |
| R00307 | 128-bit rule word entry-selection within limb by condition bits 0..5 | 206 | M00024 | non-negotiable | false | 10 |
| R00308 | Compose 64-bit control word from 8 bitfields without overflow detection | 136–143 | M00025 | non-negotiable | false | 10 |
| R00309 | Decompose 64-bit control word into 8 typed fields | 136–143 | M00026 | non-negotiable | false | 10 |
| R00310 | Bit-packing helper library publishes to `crates.io` (Rust) or vendor lock (C++) | 136–143 | M00027 | preferable | true | 10 |
| R00311 | Bit-packing helper library unit tests cover every field width | 136–143 | M00027 | non-negotiable | false | 10 |
| R00312 | Bit-packing helper library compatible with `no_std` Rust target | 136–143 | M00027 | non-negotiable | false | 10 |
| R00313 | Bit-packing helper library benchmarks vs hand-rolled packing | 136–143 | M00027 | preferable | false | 10 |
| R00314 | Bit-extract helper library round-trip property tests via proptest/quickcheck | 136–143 | M00028 | non-negotiable | false | 10 |
| R00315 | Bit-extract helper library API supports both compile-time-known and runtime-known field locations | 136–143 | M00028 | non-negotiable | true | 10 |
| R00316 | Bit-extract helper library supports zero-allocation extraction | 136–143 | M00028 | non-negotiable | false | 10 |
| R00317 | Bit-extract helper library handles unaligned reads | 136–143 | M00028 | non-negotiable | false | 10 |
| R00318 | Control-word bitfield arithmetic saturates on overflow when `--saturate` set | 136–143 | M00013 | non-negotiable | true | 10 |
| R00319 | Control-word bitfield arithmetic wraps on overflow by default | 136–143 | M00013 | non-negotiable | true | 10 |
| R00320 | Control-word bitfield arithmetic aborts on overflow when `--abort-on-overflow` set | 136–143 | M00013 | non-negotiable | true | 10 |
| R00321 | LUT 64-entry table represented as `u64` (one bit per entry) | 161–177 | M00017 | non-negotiable | false | 10 |
| R00322 | LUT 64-entry table loadable from operator-supplied 16-hex-digit string | 161–177 | M00017 | non-negotiable | true | 10 |
| R00323 | LUT 64-entry table renders as 8x8 grid in dashboard | 161–177 | F00118 | non-negotiable | true | 10 |
| R00324 | LUT 64-entry table renders truth-table-style in dashboard alternative view | 161–177 | F00118 | non-negotiable | true | 10 |
| R00325 | LUT 64-entry table exportable to JSON | 161–177 | M00017 | non-negotiable | true | 10 |
| R00326 | LUT 64-entry table importable from JSON | 161–177 | M00017 | non-negotiable | true | 10 |
| R00327 | Per-lane DNA mode increases memory cost by 1× ZMM register per lane | 173–177 | M00018 | non-negotiable | false | 10 |
| R00328 | Per-lane DNA mode register pressure tracked separately from baseline | 173–177 | M00018 | non-negotiable | false | 10 |
| R00329 | Per-lane DNA replay supports rewind across multiple lanes simultaneously | 173–177 | M00018 | non-negotiable | true | 10 |
| R00330 | Round-update strict mode aborts kernel on step failure | 189–197 | M00020 | non-negotiable | false | 10 |
| R00331 | Round-update strict mode emits OTel error span with step-id label | 189–197 | M00020 | non-negotiable | false | 10 |
| R00332 | Round-update relaxed mode logs step failure to journald | 189–197 | M00020 | non-negotiable | false | 10 |
| R00333 | Round-update relaxed mode continues to next step on failure | 189–197 | M00020 | non-negotiable | false | 10 |
| R00334 | Variable-shift mode disabled by default on profiles `private` and `production` | 199 | M00021 | non-negotiable | true | 10 |
| R00335 | Variable-shift mode auto-enabled on profile `experimental` | 199 | M00021 | non-negotiable | true | 10 |
| R00336 | Variable-shift mode performance regression alert at >2x baseline cost | 199 | M00021 | non-negotiable | true | 10 |
| R00337 | 32/64/128-bit rule modes selectable per kernel invocation | 204–206 | M00022 | non-negotiable | true | 10 |
| R00338 | 32/64/128-bit rule modes audit-logged in replay log | 204–206 | M00022 | non-negotiable | false | 10 |
| R00339 | 32/64/128-bit rule modes signed by operator when `--require-signed-rules` set | 204–206 | M00022 | non-negotiable | true | 10 |
| R00340 | 32/64/128-bit rule modes immutable during kernel execution | 204–206 | M00022 | non-negotiable | false | 10 |

— End of M002 milestone file.
