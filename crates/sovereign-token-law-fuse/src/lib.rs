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

use sovereign_json_schema_grammar::Schema;
use sovereign_regex_constrain::{RegexConstraint, RegexDenyConstraint};
use sovereign_token_grammar_mask::TokenGrammarMask;
use sovereign_token_law_deny::DenyConstraint;
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

    /// The vocabulary size the laws were compiled against.
    pub fn vocab_size(&self) -> usize {
        self.vocab_size
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
    /// The vocabulary (token id → string) to mask over.
    pub vocab: Vec<String>,
}

impl FuseRequest {
    /// Compile this request's layers against its `vocab` and fuse at `generated`.
    pub fn fuse(&self) -> Result<FusedMask, FuseError> {
        let denylist: Vec<&str> = self.denylist.iter().map(String::as_str).collect();
        let regex_denylist: Vec<&str> = self.regex_denylist.iter().map(String::as_str).collect();
        let policy_planes: Vec<&[u64]> = self.policy_planes.iter().map(Vec::as_slice).collect();
        let layers = FuseLayers {
            schema: self.schema.as_ref(),
            regex: self.regex.as_deref(),
            denylist: &denylist,
            regex_denylist: &regex_denylist,
            policy_planes: &policy_planes,
        };
        let compiled = CompiledFuse::compile(&layers, self.vocab.clone())?;
        Ok(compiled.fused_mask(&self.generated))
    }

    /// The active layer names, in fuse order — for surfacing "which laws fired".
    pub fn layers_active(&self) -> Vec<&'static str> {
        let mut v = Vec::new();
        if self.schema.is_some() {
            v.push("grammar");
        }
        if self.regex.is_some() {
            v.push("regex");
        }
        if !self.denylist.is_empty() {
            v.push("denylist");
        }
        if !self.regex_denylist.is_empty() {
            v.push("regex_denylist");
        }
        if !self.policy_planes.is_empty() {
            v.push("policy");
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
}
