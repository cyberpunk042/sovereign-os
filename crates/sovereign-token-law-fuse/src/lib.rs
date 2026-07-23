//! # sovereign-token-law-fuse — the checkpoint-free token-law fusion primitive
//!
//! SDD-500…506 built the M00117 five-plane engine plane-by-plane and folded it
//! into `sovereign-llm`'s `complete_with_token_law` — but the only way to reach
//! it is to *run the transformer*. This crate factors out the one part that
//! needs **no model at all**: the per-step **fusion** — compose the active
//! named laws at a given generated prefix into ONE vocab allow-mask.
//!
//! The fused mask is the deterministic-cortex **decision** ("which next tokens
//! does every active law permit?"). It is a pure function of the layer sources
//! (a JSON schema, a regex, a denylist, …) and the **vocabulary strings** — it
//! never touches embeddings, attention, or logits. So the mask is *exact
//! regardless of which checkpoint is loaded, or whether any is*: a trained model,
//! the untrained in-repo fixture, and "no model, just the tokenizer" all produce
//! the identical mask. That is what makes an operator surface honest — you can
//! inspect and drive the law engine without a trained model behind it.
//!
//! `sovereign-llm` consumes [`CompiledFuse::fused_mask`] once per decode step
//! (so generation and inspection share ONE definition of the mask); the M00155
//! operator surface — `POST /v1/data-plane/token-law/fuse` (F00797) and the
//! `--token-law-mask-layers` osctl verb (F00795) — drives it directly over a
//! caller-supplied vocab.
#![forbid(unsafe_code)]

use std::collections::BTreeSet;

use sovereign_json_schema_grammar::Schema;
use sovereign_regex_constrain::{RegexConstraint, RegexDenyConstraint};
use sovereign_token_grammar_mask::{IncrementalGrammarMask, TokenGrammarMask};
use sovereign_token_law_deny::{AcState, DenyConstraint};
use sovereign_token_law_entropy::EntropyConstraint;
use sovereign_token_law_mask::TokenLawPlanes;

/// A compile error for one of the regex-shaped layers (`regex` / `regex_denylist`).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FuseError(pub String);

impl std::fmt::Display for FuseError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "token-law fuse: {}", self.0)
    }
}

impl std::error::Error for FuseError {}

/// Which named mask layers are **active** (F00793/F00794/F00795 — the
/// operator-configurable `token_law_engine_mask_layers` / `--token-law-mask-layers`
/// / `SOVEREIGN_TOKEN_LAW_MASK_LAYERS` selection). A deselected layer is skipped
/// even when its source is supplied, so an operator can dial the engine down to
/// (say) `safety` only without changing the request. Unset ⇒ all layers active.
///
/// The canonical layer names are the engine's real planes — `grammar` (the
/// JSON-schema→grammar plane), `regex`, `denylist`, `regex_denylist`, `policy`.
/// The milestone's conceptual names are accepted as aliases: `schema`→`grammar`,
/// `tool`→`regex`, and `safety`→`denylist`+`regex_denylist`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MaskLayerSet {
    /// The JSON-schema→grammar plane (aliases: `schema`).
    pub grammar: bool,
    /// The positive-regex plane (aliases: `tool`).
    pub regex: bool,
    /// The literal-denylist plane (part of `safety`).
    pub denylist: bool,
    /// The negated-regex plane (part of `safety`).
    pub regex_denylist: bool,
    /// The static policy-bitset planes.
    pub policy: bool,
    /// The heuristic entropy (text→token secret-shape) plane (SDD-513).
    pub entropy: bool,
}

impl Default for MaskLayerSet {
    fn default() -> Self {
        Self::all()
    }
}

impl MaskLayerSet {
    /// Every layer active (the default when nothing is configured).
    pub const fn all() -> Self {
        Self {
            grammar: true,
            regex: true,
            denylist: true,
            regex_denylist: true,
            policy: true,
            entropy: true,
        }
    }

    /// No layer active.
    pub const fn none() -> Self {
        Self {
            grammar: false,
            regex: false,
            denylist: false,
            regex_denylist: false,
            policy: false,
            entropy: false,
        }
    }

    fn enable(&mut self, token: &str) -> Result<(), FuseError> {
        match token.trim().to_ascii_lowercase().as_str() {
            "grammar" | "schema" => self.grammar = true,
            "regex" | "tool" => self.regex = true,
            "denylist" => self.denylist = true,
            "regex_denylist" | "regex-denylist" => self.regex_denylist = true,
            "safety" => {
                self.denylist = true;
                self.regex_denylist = true;
            }
            "policy" => self.policy = true,
            // A DISTINCT name, not folded into `safety`: `safety` stays exactly
            // denylist+regex_denylist so an existing `safety`-only selection is
            // unchanged; entropy is opt-in on its own (SDD-513).
            "entropy" => self.entropy = true,
            other => {
                return Err(FuseError(format!(
                    "unknown mask layer {other:?}; valid: grammar, schema, tool, \
                     regex, denylist, regex_denylist, safety, policy, entropy"
                )));
            }
        }
        Ok(())
    }

    /// Parse a comma-separated selection (real names or milestone aliases). An
    /// empty/whitespace string ⇒ [`all`](Self::all) (unset means "everything on").
    pub fn from_csv(csv: &str) -> Result<Self, FuseError> {
        Self::from_names(csv.split(','))
    }

    /// Parse a selection from an iterator of layer names (real or alias). Empty ⇒
    /// [`all`](Self::all).
    pub fn from_names<I, S>(names: I) -> Result<Self, FuseError>
    where
        I: IntoIterator<Item = S>,
        S: AsRef<str>,
    {
        let mut set = Self::none();
        let mut any = false;
        for name in names {
            let tok = name.as_ref().trim();
            if tok.is_empty() {
                continue;
            }
            any = true;
            set.enable(tok)?;
        }
        Ok(if any { set } else { Self::all() })
    }

    /// Resolve the effective selection from the `SOVEREIGN_TOKEN_LAW_MASK_LAYERS`
    /// env var, falling back to [`all`](Self::all) when unset/empty. The impure
    /// boundary (a daemon route, a CLI) calls this; the pure `fuse` core takes an
    /// already-resolved selection.
    pub fn from_env_or_all() -> Self {
        match std::env::var("SOVEREIGN_TOKEN_LAW_MASK_LAYERS") {
            Ok(v) => Self::from_csv(&v).unwrap_or_else(|_| Self::all()),
            Err(_) => Self::all(),
        }
    }

    /// The active layers' canonical names, in fuse order.
    pub fn names(&self) -> Vec<&'static str> {
        let mut v = Vec::new();
        if self.grammar {
            v.push("grammar");
        }
        if self.regex {
            v.push("regex");
        }
        if self.denylist {
            v.push("denylist");
        }
        if self.regex_denylist {
            v.push("regex_denylist");
        }
        if self.policy {
            v.push("policy");
        }
        if self.entropy {
            v.push("entropy");
        }
        v
    }
}

/// The named laws to fuse, borrowed. Mirrors `sovereign-llm`'s `TokenLawSpec`
/// so the decode loop can hand its spec straight through — but this type carries
/// no lifetime tie to a model, only to the caller's sources.
#[derive(Default)]
pub struct FuseLayers<'a> {
    /// Grammar plane — a JSON-schema the output must remain a valid prefix of.
    pub schema: Option<&'a Schema>,
    /// Positive-regex plane — the output must stay a prefix of a match.
    pub regex: Option<&'a str>,
    /// Negative literal-denylist plane — the output must never contain any.
    pub denylist: &'a [&'a str],
    /// Negative-regex plane — the output must never *match* any of these.
    pub regex_denylist: &'a [&'a str],
    /// Static policy planes — pre-packed allow-bitsets AND-ed in verbatim.
    pub policy_planes: &'a [&'a [u64]],
    /// Heuristic entropy plane (SDD-513) — ban tokens that keep the trailing
    /// window at/above a Shannon-entropy threshold (a text→token secret-shape
    /// projection). `None` ⇒ the plane is off.
    pub entropy: Option<EntropyConstraint>,
}

impl<'a> FuseLayers<'a> {
    /// A copy with every **deselected** layer cleared (F00793/4/5) — a skipped
    /// layer contributes nothing to the fuse even when its source is supplied.
    /// No allocation: cleared slices become the empty slice, `schema`/`regex`
    /// become `None`.
    pub fn select(&self, sel: &MaskLayerSet) -> FuseLayers<'a> {
        const EMPTY_STR: &[&str] = &[];
        const EMPTY_PLANES: &[&[u64]] = &[];
        FuseLayers {
            schema: if sel.grammar { self.schema } else { None },
            regex: if sel.regex { self.regex } else { None },
            denylist: if sel.denylist {
                self.denylist
            } else {
                EMPTY_STR
            },
            regex_denylist: if sel.regex_denylist {
                self.regex_denylist
            } else {
                EMPTY_STR
            },
            policy_planes: if sel.policy {
                self.policy_planes
            } else {
                EMPTY_PLANES
            },
            entropy: if sel.entropy { self.entropy } else { None },
        }
    }
}

/// One active layer's contribution to the fused mask at the current prefix.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct LayerCoverage {
    /// Stable layer name (`grammar` / `regex` / `denylist` / `regex_denylist`).
    pub layer: &'static str,
    /// How many vocab tokens this layer alone permits at the current prefix.
    pub allowed: usize,
}

/// The fused decision at one prefix.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct FusedMask {
    /// The AND-composed allow-bitset — `⌈vocab/64⌉` words; bit `id` set = token
    /// `id` is permitted by *every* active law.
    pub mask: Vec<u64>,
    /// Popcount of `mask` — how many of the vocab survive all laws.
    pub allowed: usize,
    /// Per-active-dynamic-layer allowed counts, in fuse order.
    pub per_layer: Vec<LayerCoverage>,
    /// True when generation must stop here: a completed grammar (`eos`), a
    /// dynamic layer that permits nothing, or an empty intersection. The mask
    /// is still returned (it may be all-zero) so an inspector sees the state.
    pub stop: bool,
}

/// The active laws compiled once against a fixed vocabulary. Reuse across every
/// step of a generation (or every request against the same vocab): the sources
/// are parsed once, and [`fused_mask`](CompiledFuse::fused_mask) is the only
/// per-prefix work.
pub struct CompiledFuse {
    vocab: Vec<String>,
    vocab_size: usize,
    grammar: Option<TokenGrammarMask>,
    regex: Option<RegexConstraint>,
    deny: Option<DenyConstraint>,
    regex_deny: Vec<RegexDenyConstraint>,
    entropy: Option<EntropyConstraint>,
    planes: TokenLawPlanes,
}

impl CompiledFuse {
    /// Compile the active laws in `layers` against `vocab` (token id → string).
    /// Parses each regex-shaped source (errors on an invalid pattern); the
    /// grammar/denylist/policy layers cannot fail.
    pub fn compile(layers: &FuseLayers<'_>, vocab: Vec<String>) -> Result<Self, FuseError> {
        let vocab_size = vocab.len();
        let grammar = layers.schema.map(|s| {
            let g = sovereign_json_schema_grammar::compile(s);
            TokenGrammarMask::new(g, vocab.clone())
        });
        let regex = match layers.regex {
            Some(p) => Some(RegexConstraint::new(p).map_err(|e| FuseError(e.to_string()))?),
            None => None,
        };
        let deny = if layers.denylist.is_empty() {
            None
        } else {
            Some(DenyConstraint::new(layers.denylist.iter().copied()))
        };
        let regex_deny: Vec<RegexDenyConstraint> = layers
            .regex_denylist
            .iter()
            .map(|p| RegexDenyConstraint::new(p).map_err(|e| FuseError(e.to_string())))
            .collect::<Result<_, _>>()?;
        let mut planes = TokenLawPlanes::new(vocab_size);
        for p in layers.policy_planes {
            planes = planes.with_plane(p.to_vec());
        }
        Ok(Self {
            vocab,
            vocab_size,
            grammar,
            regex,
            deny,
            regex_deny,
            entropy: layers.entropy,
            planes,
        })
    }

    /// The fused allow-mask for the token *after* `generated`. Collects every
    /// active dynamic layer's allow-list at this prefix and AND-composes them
    /// with the static policy planes through the real `token_law_combine`
    /// kernel (via [`TokenLawPlanes::combine_with_dynamics`]) — bit-for-bit the
    /// same mask `sovereign-llm`'s decode loop applies to the logits, so
    /// inspection and generation never diverge.
    pub fn fused_mask(&self, generated: &str) -> FusedMask {
        let vocab_refs: Vec<&str> = self.vocab.iter().map(String::as_str).collect();
        let mut dynamics: Vec<Vec<usize>> = Vec::new();
        let mut per_layer: Vec<LayerCoverage> = Vec::new();
        let mut stop = false;

        if let Some(g) = &self.grammar {
            let m = g.mask(generated);
            if m.eos {
                stop = true;
            }
            let ids = m.allowed_ids();
            if ids.is_empty() {
                stop = true;
            }
            per_layer.push(LayerCoverage {
                layer: "grammar",
                allowed: ids.len(),
            });
            dynamics.push(ids);
        }
        if let Some(rc) = &self.regex {
            let ids = rc.allowed_token_ids(generated, &vocab_refs);
            if ids.is_empty() {
                stop = true;
            }
            per_layer.push(LayerCoverage {
                layer: "regex",
                allowed: ids.len(),
            });
            dynamics.push(ids);
        }
        if let Some(deny) = &self.deny {
            let ids = deny.safe_token_ids(generated, &vocab_refs);
            if ids.is_empty() {
                stop = true;
            }
            per_layer.push(LayerCoverage {
                layer: "denylist",
                allowed: ids.len(),
            });
            dynamics.push(ids);
        }
        for rd in &self.regex_deny {
            let ids = rd.safe_token_ids(generated, &vocab_refs);
            if ids.is_empty() {
                stop = true;
            }
            per_layer.push(LayerCoverage {
                layer: "regex_denylist",
                allowed: ids.len(),
            });
            dynamics.push(ids);
        }
        if let Some(entropy) = &self.entropy {
            let ids = entropy.safe_token_ids(generated, &vocab_refs);
            if ids.is_empty() {
                stop = true;
            }
            per_layer.push(LayerCoverage {
                layer: "entropy",
                allowed: ids.len(),
            });
            dynamics.push(ids);
        }

        self.compose(dynamics, per_layer, stop)
    }

    /// AND-compose the per-plane allow-lists with the static policy planes into the
    /// final `FusedMask`. Shared by [`fused_mask`](Self::fused_mask) and
    /// [`FuseSession`] so the stateless and incremental paths are bit-for-bit
    /// identical (the incremental parity invariant, SDD-514).
    fn compose(
        &self,
        dynamics: Vec<Vec<usize>>,
        per_layer: Vec<LayerCoverage>,
        mut stop: bool,
    ) -> FusedMask {
        let refs: Vec<&[usize]> = dynamics.iter().map(Vec::as_slice).collect();
        let mask = self.planes.combine_with_dynamics(&refs);
        // Count only REAL vocab bits: the identity mask (no planes) sets the
        // padding bits past `vocab_size` too, and those are not tokens. The mask
        // itself is returned verbatim — bit-for-bit what the decoder applies.
        let allowed = (0..self.vocab_size)
            .filter(|&id| mask[id / 64] & (1u64 << (id % 64)) != 0)
            .count();
        if allowed == 0 {
            stop = true;
        }
        FusedMask {
            mask,
            allowed,
            per_layer,
            stop,
        }
    }

    /// Open a stateful [`FuseSession`] over this compiled fuse — the **incremental**
    /// per-step decision (SDD-514). Where [`fused_mask`](Self::fused_mask) re-walks
    /// every plane from the start of the whole prefix each call (O(n²) over a
    /// decode), a session carries each plane's committed automaton state and
    /// advances it by only the newly-committed token, so per-step cost is the token
    /// not the prefix. `session.mask()` is bit-for-bit `fused_mask(prefix)`.
    pub fn session(&self) -> FuseSession<'_> {
        FuseSession {
            grammar: self
                .grammar
                .as_ref()
                .map(|g| IncrementalGrammarMask::new(g.grammar().clone(), self.vocab.clone())),
            regex_live: self.regex.as_ref().map(|rc| Some(rc.start_state())),
            deny_state: self.deny.as_ref().map(|d| d.start_state()),
            regex_deny_states: self.regex_deny.iter().map(|rd| rd.start_state()).collect(),
            entropy_tail: String::new(),
            fuse: self,
        }
    }

    /// The vocabulary size the laws were compiled against.
    pub fn vocab_size(&self) -> usize {
        self.vocab_size
    }
}

/// A **stateful, incremental** view over a [`CompiledFuse`] (SDD-514). It carries
/// each plane's committed automaton state and advances it by only the
/// newly-committed token each decode step, so a decode loop pays the token, not
/// the whole prefix (removing the O(n²) re-walk of [`CompiledFuse::fused_mask`]).
///
/// [`mask`](Self::mask) at any point is **bit-for-bit** what `fused_mask` would
/// return for the same committed prefix (proven by the parity test) — so a caller
/// can swap the stateless `fused_mask(text)` per step for
/// `session.advance_token(id)` with no behavioral change.
///
/// Valid only for a **char-concatenative** tokenizer (each token's surface string
/// is appended verbatim — byte-level BPE qualifies), the same precondition
/// `IncrementalGrammarMask` documents.
pub struct FuseSession<'f> {
    fuse: &'f CompiledFuse,
    /// Committed grammar chart (present iff the grammar plane is active).
    grammar: Option<IncrementalGrammarMask>,
    /// Committed positive-regex live set: `Some(None)` = plane active but the
    /// prefix went off-pattern (sticky dead — nothing viable); `Some(Some(set))` =
    /// live; `None` = no regex plane.
    regex_live: Option<Option<BTreeSet<usize>>>,
    /// Committed denylist Aho-Corasick node (present iff the deny plane is active).
    deny_state: Option<AcState>,
    /// One committed unanchored live set per negated-regex pattern.
    regex_deny_states: Vec<BTreeSet<usize>>,
    /// The trailing window of committed text the entropy plane scores. Truncated
    /// to the entropy plane's `window` after each advance — entropy only ever reads
    /// the last `window` chars, so this keeps its per-step cost O(window·vocab),
    /// not O(prefix·vocab) (the whole point of the session).
    entropy_tail: String,
}

impl FuseSession<'_> {
    /// The fused allow-mask for the token *after* the committed prefix — identical
    /// to [`CompiledFuse::fused_mask`] at that prefix, gathered from the carried
    /// incremental state instead of re-walking. Mirrors `fused_mask`'s plane order
    /// and stop conditions exactly.
    pub fn mask(&mut self) -> FusedMask {
        let vocab_refs: Vec<&str> = self.fuse.vocab.iter().map(String::as_str).collect();
        let mut dynamics: Vec<Vec<usize>> = Vec::new();
        let mut per_layer: Vec<LayerCoverage> = Vec::new();
        let mut stop = false;

        if let Some(g) = &mut self.grammar {
            let m = g.mask();
            if m.eos {
                stop = true;
            }
            let ids = m.allowed_ids();
            if ids.is_empty() {
                stop = true;
            }
            per_layer.push(LayerCoverage {
                layer: "grammar",
                allowed: ids.len(),
            });
            dynamics.push(ids);
        }
        if let (Some(live), Some(rc)) = (&self.regex_live, &self.fuse.regex) {
            let ids = match live {
                Some(base) => rc.allowed_token_ids_from(base, &vocab_refs),
                None => Vec::new(), // off-pattern → nothing viable
            };
            if ids.is_empty() {
                stop = true;
            }
            per_layer.push(LayerCoverage {
                layer: "regex",
                allowed: ids.len(),
            });
            dynamics.push(ids);
        }
        if let (Some(state), Some(deny)) = (self.deny_state, &self.fuse.deny) {
            let ids = deny.safe_token_ids_from(state, &vocab_refs);
            if ids.is_empty() {
                stop = true;
            }
            per_layer.push(LayerCoverage {
                layer: "denylist",
                allowed: ids.len(),
            });
            dynamics.push(ids);
        }
        for (rd, base) in self.fuse.regex_deny.iter().zip(&self.regex_deny_states) {
            let ids = rd.safe_token_ids_from(base, &vocab_refs);
            if ids.is_empty() {
                stop = true;
            }
            per_layer.push(LayerCoverage {
                layer: "regex_denylist",
                allowed: ids.len(),
            });
            dynamics.push(ids);
        }
        if let Some(entropy) = &self.fuse.entropy {
            let ids = entropy.safe_token_ids(&self.entropy_tail, &vocab_refs);
            if ids.is_empty() {
                stop = true;
            }
            per_layer.push(LayerCoverage {
                layer: "entropy",
                allowed: ids.len(),
            });
            dynamics.push(ids);
        }

        self.fuse.compose(dynamics, per_layer, stop)
    }

    /// Commit token `id` (append its surface string to every plane's state) and
    /// return the mask for the NEXT token. The delta is `vocab[id]` — the same
    /// string `fused_mask` would have re-scanned.
    pub fn advance_token(&mut self, id: usize) -> FusedMask {
        let delta = self.fuse.vocab.get(id).cloned().unwrap_or_default();
        self.advance_str(&delta)
    }

    /// Commit an arbitrary text `delta` (append it to every plane's committed
    /// state) and return the mask for the next token. Prefer
    /// [`advance_token`](Self::advance_token) in a decode loop.
    pub fn advance_str(&mut self, delta: &str) -> FusedMask {
        if let Some(g) = &mut self.grammar {
            g.advance(delta);
        }
        if let (Some(live), Some(rc)) = (&mut self.regex_live, &self.fuse.regex) {
            *live = match live.as_ref() {
                Some(base) => rc.advance_state(base, delta), // None once off-pattern (sticky)
                None => None,
            };
        }
        if let (Some(state), Some(deny)) = (self.deny_state, &self.fuse.deny) {
            self.deny_state = Some(deny.advance_state(state, delta));
        }
        for (rd, base) in self
            .fuse
            .regex_deny
            .iter()
            .zip(self.regex_deny_states.iter_mut())
        {
            *base = rd.advance_state(base, delta);
        }
        if let Some(entropy) = &self.fuse.entropy {
            self.entropy_tail.push_str(delta);
            // Keep only the trailing `window` chars: `safe_token_ids` reads no more
            // than that (its `trailing_window`), and `tail + tok`'s trailing window
            // equals `full + tok`'s whenever `tail` holds the last `window` chars —
            // so this is O(window)-bounded WITHOUT changing the result (parity).
            let w = entropy.window();
            let n = self.entropy_tail.chars().count();
            if n > w {
                self.entropy_tail = self.entropy_tail.chars().skip(n - w).collect();
            }
        }
        self.mask()
    }
}

/// The wire shape of the entropy plane (SDD-513). Present (even `{}`) ⇒ the plane
/// is ON with the given knobs, each defaulting to the `sovereign-secret-scan`
/// value the post-hoc scanner uses; absent ⇒ the plane is off.
#[derive(Debug, Clone, Copy, Default, serde::Deserialize)]
pub struct EntropyRequest {
    /// Ban cutoff in bits/char (default: the secret-scan `ENTROPY_THRESHOLD_BITS`).
    #[serde(default)]
    pub threshold_bits: Option<f64>,
    /// Trailing-window character count scored (default: secret-scan window).
    #[serde(default)]
    pub window: Option<usize>,
    /// Shortest window judged (default: secret-scan min length).
    #[serde(default)]
    pub min_len: Option<usize>,
}

impl EntropyRequest {
    /// Resolve this wire request into a compiled [`EntropyConstraint`], each unset
    /// knob defaulting to the `sovereign-secret-scan` value the post-hoc scanner
    /// uses. Public so a serving consumer (gatewayd's `ServingTokenLaw`) reuses the
    /// SAME defaulting the fuse route does.
    pub fn to_constraint(self) -> EntropyConstraint {
        let d = EntropyConstraint::default();
        EntropyConstraint::new(
            self.threshold_bits.unwrap_or_else(|| d.threshold_bits()),
            self.window.unwrap_or_else(|| d.window()),
            self.min_len.unwrap_or_else(|| d.min_len()),
        )
    }
}

/// An owned, deserializable fusion request — the wire shape a data-plane HTTP
/// route (F00797) or a CLI verb deserializes, then [`fuse`](FuseRequest::fuse)s.
/// Every layer field defaults to empty, so a request may carry any subset.
#[derive(Debug, Clone, Default, serde::Deserialize)]
pub struct FuseRequest {
    /// Grammar plane (JSON-schema).
    #[serde(default)]
    pub schema: Option<Schema>,
    /// Positive-regex plane.
    #[serde(default)]
    pub regex: Option<String>,
    /// Literal-denylist plane.
    #[serde(default)]
    pub denylist: Vec<String>,
    /// Negated-regex plane.
    #[serde(default)]
    pub regex_denylist: Vec<String>,
    /// Static policy allow-bitsets.
    #[serde(default)]
    pub policy_planes: Vec<Vec<u64>>,
    /// The committed generation so far (empty = fuse at the start).
    #[serde(default)]
    pub generated: String,
    /// Which mask layers to keep active (F00795) — real names or milestone
    /// aliases (`grammar`/`schema`, `regex`/`tool`, `denylist`, `regex_denylist`,
    /// `safety`, `policy`). Absent/empty ⇒ all layers active.
    #[serde(default)]
    pub mask_layers: Option<Vec<String>>,
    /// Heuristic entropy plane (SDD-513) — present ⇒ on. Absent ⇒ off.
    #[serde(default)]
    pub entropy: Option<EntropyRequest>,
    /// The vocabulary (token id → string) to mask over.
    pub vocab: Vec<String>,
}

impl FuseRequest {
    /// The effective layer selection: the request's `mask_layers` if given
    /// (empty list ⇒ all), else all. Env/flag defaults are resolved by the
    /// caller (the daemon route / CLI) before the request reaches here.
    pub fn selection(&self) -> Result<MaskLayerSet, FuseError> {
        match &self.mask_layers {
            Some(names) => MaskLayerSet::from_names(names),
            None => Ok(MaskLayerSet::all()),
        }
    }

    /// Compile this request's **selected** layers against its `vocab` and fuse
    /// at `generated`.
    pub fn fuse(&self) -> Result<FusedMask, FuseError> {
        let sel = self.selection()?;
        let denylist: Vec<&str> = self.denylist.iter().map(String::as_str).collect();
        let regex_denylist: Vec<&str> = self.regex_denylist.iter().map(String::as_str).collect();
        let policy_planes: Vec<&[u64]> = self.policy_planes.iter().map(Vec::as_slice).collect();
        let layers = FuseLayers {
            schema: self.schema.as_ref(),
            regex: self.regex.as_deref(),
            denylist: &denylist,
            regex_denylist: &regex_denylist,
            policy_planes: &policy_planes,
            entropy: self.entropy.map(EntropyRequest::to_constraint),
        }
        .select(&sel);
        let compiled = CompiledFuse::compile(&layers, self.vocab.clone())?;
        Ok(compiled.fused_mask(&self.generated))
    }

    /// The active layer names, in fuse order — a layer fires only when its
    /// source is present AND the selection keeps it. For surfacing "which laws
    /// fired" (and the `sovereign_data_plane_token_law_mask_layers` metric).
    pub fn layers_active(&self) -> Vec<&'static str> {
        let sel = self.selection().unwrap_or_else(|_| MaskLayerSet::all());
        let mut v = Vec::new();
        if self.schema.is_some() && sel.grammar {
            v.push("grammar");
        }
        if self.regex.is_some() && sel.regex {
            v.push("regex");
        }
        if !self.denylist.is_empty() && sel.denylist {
            v.push("denylist");
        }
        if !self.regex_denylist.is_empty() && sel.regex_denylist {
            v.push("regex_denylist");
        }
        if !self.policy_planes.is_empty() && sel.policy {
            v.push("policy");
        }
        if self.entropy.is_some() && sel.entropy {
            v.push("entropy");
        }
        v
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn vocab(toks: &[&str]) -> Vec<String> {
        toks.iter().map(|s| s.to_string()).collect()
    }

    fn set_bits(mask: &[u64]) -> Vec<usize> {
        let mut ids = Vec::new();
        for (w, word) in mask.iter().enumerate() {
            for b in 0..64 {
                if word & (1u64 << b) != 0 {
                    ids.push(w * 64 + b);
                }
            }
        }
        ids
    }

    #[test]
    fn entropy_plane_fuses_through_the_request_and_bans_a_secret_extender() {
        // SDD-513: a FuseRequest carrying `entropy` (defaults) at a hot 20-char
        // prefix must drop the token that keeps the trailing window high-entropy
        // and keep a low-entropy run, with "entropy" in layers_active.
        let prefix = "aB3xK9zQ7mP2wL5nR8tV"; // 20 high-entropy chars
        let req = FuseRequest {
            entropy: Some(EntropyRequest::default()),
            generated: prefix.to_string(),
            vocab: vocab(&["Y4", "aaaaaaaaaaaaaaaaaaaaaa"]),
            ..Default::default()
        };
        assert_eq!(req.layers_active(), vec!["entropy"]);
        let fused = req.fuse().unwrap();
        let allowed = set_bits(&fused.mask);
        assert!(
            !allowed.contains(&0),
            "the entropy-extending token must be masked out"
        );
        assert!(
            allowed.contains(&1),
            "a low-entropy run must survive the entropy plane"
        );
    }

    #[test]
    fn entropy_layer_can_be_deselected() {
        // With `mask_layers` excluding entropy, the plane is skipped even though
        // the source is present → the hot extender is allowed again.
        let req = FuseRequest {
            entropy: Some(EntropyRequest::default()),
            generated: "aB3xK9zQ7mP2wL5nR8tV".to_string(),
            mask_layers: Some(vec!["grammar".to_string()]),
            vocab: vocab(&["Y4", "aaaaaaaaaaaaaaaaaaaaaa"]),
            ..Default::default()
        };
        assert!(
            req.layers_active().is_empty(),
            "entropy deselected + no grammar source"
        );
        let allowed = set_bits(&req.fuse().unwrap().mask);
        assert!(
            allowed.contains(&0) && allowed.contains(&1),
            "no plane active → all allowed"
        );
    }

    #[test]
    fn session_is_bit_for_bit_identical_to_stateless_across_all_planes() {
        // SDD-514: the incremental session must reproduce fused_mask EXACTLY at
        // every prefix, with all five dynamic planes + a policy plane active.
        let v = vocab(&["ye", "s", "no", "a", "x", "q"]);
        let policy: Vec<u64> = vec![0xFFFF]; // allow the low ids
        let layers = FuseLayers {
            schema: Some(&Schema::Enum(vec!["yes".into(), "no".into()])),
            regex: Some("[a-z]+"),
            denylist: &["xx"],
            regex_denylist: &["[0-9][0-9]"],
            policy_planes: &[&policy],
            entropy: Some(EntropyConstraint::default()),
        };
        let fuse = CompiledFuse::compile(&layers, v.clone()).unwrap();

        // Walk a token sequence; at every step session.mask() must equal
        // fused_mask(running_text) — full FusedMask equality (mask/allowed/
        // per_layer/stop).
        let seq = ["ye", "s", "a", "q", "no"];
        let mut session = fuse.session();
        let mut running = String::new();
        assert_eq!(
            session.mask(),
            fuse.fused_mask(&running),
            "parity at the empty prefix"
        );
        for tok in seq {
            running.push_str(tok);
            let id = v.iter().position(|t| t == tok).unwrap();
            let from_session = session.advance_token(id);
            let from_stateless = fuse.fused_mask(&running);
            assert_eq!(
                from_session, from_stateless,
                "session diverged from stateless after committing {tok:?} (prefix {running:?})"
            );
        }
    }

    #[test]
    fn session_matches_stateless_off_pattern_and_at_eos() {
        // A positive regex that the prefix walks OFF (regex_live → None) and a
        // grammar Enum that reaches a complete match (eos) — the two trickiest
        // states — must still match the stateless fuse bit-for-bit.
        let v = vocab(&["9", "no", "z"]);
        let layers = FuseLayers {
            schema: Some(&Schema::Enum(vec!["no".into()])),
            regex: Some("[a-z]+"),
            denylist: &[],
            regex_denylist: &[],
            policy_planes: &[],
            entropy: None,
        };
        let fuse = CompiledFuse::compile(&layers, v.clone()).unwrap();
        let mut session = fuse.session();
        let mut running = String::new();
        for tok in ["9", "no", "z"] {
            running.push_str(tok);
            let id = v.iter().position(|t| t == tok).unwrap();
            assert_eq!(
                session.advance_token(id),
                fuse.fused_mask(&running),
                "off-pattern/eos parity failed at {running:?}"
            );
        }
    }

    #[test]
    fn empty_layers_permit_everything() {
        let layers = FuseLayers::default();
        let f = CompiledFuse::compile(&layers, vocab(&["a", "b", "c"])).unwrap();
        let out = f.fused_mask("");
        // No dynamic planes, no policy planes → identity → every real token
        // allowed (the mask sets padding bits past the vocab too, so `allowed`
        // is the vocab-bounded count, not a raw popcount).
        assert_eq!(out.allowed, 3);
        assert!(
            [0usize, 1, 2]
                .iter()
                .all(|&id| out.mask[id / 64] & (1u64 << (id % 64)) != 0)
        );
        assert!(out.per_layer.is_empty());
        assert!(!out.stop);
    }

    #[test]
    fn positive_regex_layer_restricts_to_digits() {
        // vocab: 0="5", 1="x", 2="7"; regex [0-9]+ permits only the digit tokens.
        let dl: [&str; 0] = [];
        let rdl: [&str; 0] = [];
        let pp: [&[u64]; 0] = [];
        let layers = FuseLayers {
            schema: None,
            regex: Some("[0-9]+"),
            denylist: &dl,
            regex_denylist: &rdl,
            policy_planes: &pp,
            entropy: None,
        };
        let f = CompiledFuse::compile(&layers, vocab(&["5", "x", "7"])).unwrap();
        let out = f.fused_mask("");
        assert_eq!(set_bits(&out.mask), vec![0, 2]);
        assert_eq!(
            out.per_layer,
            vec![LayerCoverage {
                layer: "regex",
                allowed: 2
            }]
        );
        assert!(!out.stop);
    }

    #[test]
    fn positive_and_negated_regex_compose() {
        // [a-z]+ ∧ ¬[xyz]: from {a,x,q,z} only a and q survive.
        let dl: [&str; 0] = [];
        let pp: [&[u64]; 0] = [];
        let rdl = ["[xyz]"];
        let layers = FuseLayers {
            schema: None,
            regex: Some("[a-z]+"),
            denylist: &dl,
            regex_denylist: &rdl,
            policy_planes: &pp,
            entropy: None,
        };
        let f = CompiledFuse::compile(&layers, vocab(&["a", "x", "q", "z"])).unwrap();
        let out = f.fused_mask("");
        assert_eq!(set_bits(&out.mask), vec![0, 2]);
        // Two active dynamic layers recorded in fuse order.
        assert_eq!(out.per_layer.len(), 2);
        assert_eq!(out.per_layer[0].layer, "regex");
        assert_eq!(out.per_layer[1].layer, "regex_denylist");
    }

    #[test]
    fn denylist_bans_the_completing_token_cross_boundary() {
        // Forbid "ab": after committed "a", the token "b" completes it → banned.
        let dl = ["ab"];
        let rdl: [&str; 0] = [];
        let pp: [&[u64]; 0] = [];
        let layers = FuseLayers {
            schema: None,
            regex: None,
            denylist: &dl,
            regex_denylist: &rdl,
            policy_planes: &pp,
            entropy: None,
        };
        let f = CompiledFuse::compile(&layers, vocab(&["b", "x", "c"])).unwrap();
        let out = f.fused_mask("a");
        // "b" completes "ab" → banned; "x","c" safe.
        assert_eq!(set_bits(&out.mask), vec![1, 2]);
        assert_eq!(
            out.per_layer,
            vec![LayerCoverage {
                layer: "denylist",
                allowed: 2
            }]
        );
    }

    #[test]
    fn policy_plane_ands_in_verbatim() {
        // Policy allows only tokens {0,2}; regex [a-z]+ allows {0,1,2}; AND = {0,2}.
        let dl: [&str; 0] = [];
        let rdl: [&str; 0] = [];
        // 3-token vocab → 1 word; bits 0 and 2 set = 0b101 = 5.
        let plane = [0b101u64];
        let planes: [&[u64]; 1] = [&plane];
        let layers = FuseLayers {
            schema: None,
            regex: Some("[a-z]+"),
            denylist: &dl,
            regex_denylist: &rdl,
            policy_planes: &planes,
            entropy: None,
        };
        let f = CompiledFuse::compile(&layers, vocab(&["a", "b", "c"])).unwrap();
        let out = f.fused_mask("");
        assert_eq!(set_bits(&out.mask), vec![0, 2]);
    }

    #[test]
    fn empty_intersection_signals_stop() {
        // regex demands a digit, but no vocab token is a digit → nothing survives.
        let dl: [&str; 0] = [];
        let rdl: [&str; 0] = [];
        let pp: [&[u64]; 0] = [];
        let layers = FuseLayers {
            schema: None,
            regex: Some("[0-9]+"),
            denylist: &dl,
            regex_denylist: &rdl,
            policy_planes: &pp,
            entropy: None,
        };
        let f = CompiledFuse::compile(&layers, vocab(&["a", "b"])).unwrap();
        let out = f.fused_mask("");
        assert_eq!(out.allowed, 0);
        assert!(out.stop);
    }

    #[test]
    fn invalid_regex_is_an_error() {
        let dl: [&str; 0] = [];
        let rdl: [&str; 0] = [];
        let pp: [&[u64]; 0] = [];
        let layers = FuseLayers {
            schema: None,
            regex: Some("[unterminated"),
            denylist: &dl,
            regex_denylist: &rdl,
            policy_planes: &pp,
            entropy: None,
        };
        assert!(CompiledFuse::compile(&layers, vocab(&["a"])).is_err());
    }

    #[test]
    fn fuse_request_round_trips_from_json() {
        let req: FuseRequest = serde_json::from_str(
            r#"{ "regex": "[a-z]+", "regex_denylist": ["[xyz]"], "vocab": ["a","x","q","z"] }"#,
        )
        .unwrap();
        assert_eq!(req.layers_active(), vec!["regex", "regex_denylist"]);
        let out = req.fuse().unwrap();
        assert_eq!(set_bits(&out.mask), vec![0, 2]);
    }

    #[test]
    fn mask_layer_set_parses_real_names_and_aliases() {
        // empty ⇒ all
        assert_eq!(MaskLayerSet::from_csv("").unwrap(), MaskLayerSet::all());
        assert_eq!(
            MaskLayerSet::from_csv("  , ,").unwrap(),
            MaskLayerSet::all()
        );
        // milestone default names map onto the real planes; `safety` ⇒ both denials
        let s = MaskLayerSet::from_csv("grammar,schema,tool,safety").unwrap();
        assert!(s.grammar && s.regex && s.denylist && s.regex_denylist);
        assert!(!s.policy);
        // real names, case-insensitive
        let r = MaskLayerSet::from_csv("REGEX, Policy").unwrap();
        assert_eq!(r.names(), vec!["regex", "policy"]);
        // unknown ⇒ error
        assert!(MaskLayerSet::from_csv("grammar,teleport").is_err());
    }

    #[test]
    fn selection_skips_a_deselected_layer_even_when_supplied() {
        // regex demands digits, denylist bans "5"; select ONLY safety → the regex
        // plane is dropped, so non-digits survive and only the denylist applies.
        let req: FuseRequest = serde_json::from_str(
            r#"{ "regex": "[0-9]+", "denylist": ["5"], "vocab": ["5","x","7"],
                 "mask_layers": ["safety"] }"#,
        )
        .unwrap();
        // only the denylist fires (regex/tool deselected)
        assert_eq!(req.layers_active(), vec!["denylist"]);
        let out = req.fuse().unwrap();
        // "5" banned by denylist; "x" and "7" survive (regex NOT applied)
        assert_eq!(set_bits(&out.mask), vec![1, 2]);
    }

    #[test]
    fn selecting_a_layer_that_is_absent_is_a_no_op() {
        // select grammar only, but the request has no schema → nothing fires,
        // everything is permitted.
        let req: FuseRequest = serde_json::from_str(
            r#"{ "regex": "[0-9]+", "vocab": ["5","x"], "mask_layers": ["grammar"] }"#,
        )
        .unwrap();
        assert!(req.layers_active().is_empty());
        let out = req.fuse().unwrap();
        assert_eq!(out.allowed, 2);
    }
}
