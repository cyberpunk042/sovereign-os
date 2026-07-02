//! `sovereign-precision-profile` — a declarative, opt-in/opt-out precision plan.
//!
//! Precision is a *choice*, and the operator's doctrine is that every such
//! choice is flexible: an option to opt into or out of, expressed as a profile,
//! never hardcoded. This crate is that profile. A [`PrecisionProfile`] declares,
//! for a decoder stack:
//!
//! - a **default** [`Precision`] used for any layer not otherwise assigned —
//!   [`Precision::F32`] by default, i.e. *opt out of all quantization* until you
//!   opt in;
//! - **per-layer** overrides (`layer index → precision`) — opt a specific layer
//!   into ternary / NVFP4 / INT8-VNNI;
//! - **high-precision projections** by name (e.g. `lm_head`) that stay dense even
//!   inside a quantized layer;
//! - **AVX-512 tier flags** ([`Tiers`]) — which instruction tiers from the
//!   operator's note (T1 quant/dot, T2 bitwise/attention, T3 structure/KV) the
//!   runtime is allowed to exploit.
//!
//! Presets ([`PrecisionProfile::f32`], [`uniform`](PrecisionProfile::uniform),
//! [`mixed`](PrecisionProfile::mixed), [`all_ternary`](PrecisionProfile::all_ternary),
//! [`int8_hot`](PrecisionProfile::int8_hot)) are starting points, not walls —
//! every field is public and serde-round-trips, so a profile can be authored,
//! stored, diffed, and evolved.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_linear::Precision;
use std::collections::BTreeMap;

/// Schema version of the precision-profile surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Per-tier AVX-512 exploitation opt-in flags (the operator's T1/T2/T3 note).
/// Advisory: they record which instruction tiers the runtime may use; a
/// consumer that lacks a tier simply falls back to a portable path.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Tiers {
    /// T1 — quantization & dot product (VPDPBUSD INT8 / VDPBF16PS BF16).
    pub t1_quant_dot: bool,
    /// T2 — bitwise logic & attention masking (VPTERNLOG / VP2INTERSECT).
    pub t2_bitwise_attn: bool,
    /// T3 — structuring, pruning & KV-cache (VPERMB / VPSHLDV / VPCOMPRESS/EXPAND).
    pub t3_structure_kv: bool,
}

impl Tiers {
    /// All tiers off — the portable, opt-out baseline.
    pub const NONE: Tiers = Tiers {
        t1_quant_dot: false,
        t2_bitwise_attn: false,
        t3_structure_kv: false,
    };
    /// All tiers on — exploit every AVX-512 instruction tier available.
    pub const ALL: Tiers = Tiers {
        t1_quant_dot: true,
        t2_bitwise_attn: true,
        t3_structure_kv: true,
    };

    /// Whether any tier is opted in.
    pub fn any(&self) -> bool {
        self.t1_quant_dot || self.t2_bitwise_attn || self.t3_structure_kv
    }
}

impl Default for Tiers {
    fn default() -> Self {
        Tiers::NONE
    }
}

/// A declarative precision plan for a decoder stack.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PrecisionProfile {
    /// Human-readable name (a preset name, or an operator-authored label).
    pub name: String,
    /// Precision for any layer without an explicit per-layer override.
    pub default: Precision,
    /// Per-layer-index precision overrides (opt-in).
    pub layers: BTreeMap<usize, Precision>,
    /// Projection names kept dense (f32) even inside a quantized layer.
    pub high_precision: Vec<String>,
    /// Which AVX-512 instruction tiers the runtime may exploit.
    pub tiers: Tiers,
}

impl PrecisionProfile {
    /// The safe default: **every** layer f32, all tiers off — a full opt-out of
    /// quantization and AVX-512 exploitation. Opt in from here.
    pub fn f32() -> Self {
        Self {
            name: "f32".into(),
            default: Precision::F32,
            layers: BTreeMap::new(),
            high_precision: Vec::new(),
            tiers: Tiers::NONE,
        }
    }

    /// Every layer at one precision (all tiers on when it's a quantized one).
    pub fn uniform(precision: Precision) -> Self {
        let tiers = if precision == Precision::F32 {
            Tiers::NONE
        } else {
            Tiers::ALL
        };
        Self {
            name: format!("uniform-{}", precision_slug(precision)),
            default: precision,
            layers: BTreeMap::new(),
            high_precision: Vec::new(),
            tiers,
        }
    }

    /// Every layer ternary (1.58-bit) — the multiplication-free BitLinear path.
    pub fn all_ternary() -> Self {
        Self {
            name: "all-ternary".into(),
            ..Self::uniform(Precision::Ternary)
        }
    }

    /// The INT8-VNNI hot path everywhere (T1 emphasis).
    pub fn int8_hot() -> Self {
        Self {
            name: "int8-hot".into(),
            ..Self::uniform(Precision::Int8)
        }
    }

    /// A mixed stack that demonstrates every precision in one residual stream:
    /// layer 0 → f32, 1 → ternary, 2 → NVFP4, and 3+ → INT8-VNNI (the default).
    /// The classic "one model, four precisions" demonstration, all tiers on.
    pub fn mixed() -> Self {
        let mut layers = BTreeMap::new();
        layers.insert(0, Precision::F32);
        layers.insert(1, Precision::Ternary);
        layers.insert(2, Precision::Nvfp4);
        Self {
            name: "mixed".into(),
            default: Precision::Int8,
            layers,
            high_precision: Vec::new(),
            tiers: Tiers::ALL,
        }
    }

    /// Opt layer `index` into `precision` (fluent).
    pub fn with_layer(mut self, index: usize, precision: Precision) -> Self {
        self.layers.insert(index, precision);
        self
    }

    /// Keep projection `name` dense (f32) even in a quantized layer (fluent).
    pub fn with_high_precision(mut self, name: impl Into<String>) -> Self {
        self.high_precision.push(name.into());
        self
    }

    /// Set the AVX-512 tier flags (fluent).
    pub fn with_tiers(mut self, tiers: Tiers) -> Self {
        self.tiers = tiers;
        self
    }

    /// The precision layer `index` resolves to: its override if present, else
    /// the profile default.
    pub fn resolve(&self, index: usize) -> Precision {
        self.layers.get(&index).copied().unwrap_or(self.default)
    }

    /// The resolved precision for the first `count` layers, in order.
    pub fn plan(&self, count: usize) -> Vec<Precision> {
        (0..count).map(|i| self.resolve(i)).collect()
    }

    /// Whether projection `name` is pinned to high precision.
    pub fn is_high_precision(&self, name: &str) -> bool {
        self.high_precision.iter().any(|n| n == name)
    }

    /// The high-precision projection names as `&str` (for
    /// `MhaDecoderBlock::from_weights_selective`).
    pub fn high_precision_refs(&self) -> Vec<&str> {
        self.high_precision.iter().map(String::as_str).collect()
    }

    /// Whether this profile does any quantization at all (any non-f32 layer).
    /// A pure opt-out profile returns `false`.
    pub fn quantizes(&self) -> bool {
        self.default != Precision::F32 || self.layers.values().any(|&p| p != Precision::F32)
    }
}

impl Default for PrecisionProfile {
    fn default() -> Self {
        Self::f32()
    }
}

/// A short slug for a precision, for profile names.
fn precision_slug(p: Precision) -> &'static str {
    match p {
        Precision::F32 => "f32",
        Precision::Ternary => "ternary",
        Precision::Nvfp4 => "nvfp4",
        Precision::Int8 => "int8",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn f32_default_is_a_full_opt_out() {
        let p = PrecisionProfile::f32();
        assert_eq!(p.plan(4), vec![Precision::F32; 4]);
        assert!(!p.quantizes());
        assert!(!p.tiers.any());
    }

    #[test]
    fn default_trait_is_the_opt_out() {
        assert_eq!(PrecisionProfile::default(), PrecisionProfile::f32());
    }

    #[test]
    fn mixed_preset_spans_four_precisions_in_order() {
        let p = PrecisionProfile::mixed();
        assert_eq!(
            p.plan(4),
            vec![
                Precision::F32,
                Precision::Ternary,
                Precision::Nvfp4,
                Precision::Int8, // the default fills layer 3+
            ]
        );
        // an unassigned later layer keeps resolving to the default.
        assert_eq!(p.resolve(7), Precision::Int8);
        assert!(p.quantizes());
        assert_eq!(p.tiers, Tiers::ALL);
    }

    #[test]
    fn uniform_presets_pick_one_precision_everywhere() {
        assert_eq!(
            PrecisionProfile::all_ternary().plan(3),
            vec![Precision::Ternary; 3]
        );
        assert_eq!(
            PrecisionProfile::int8_hot().plan(3),
            vec![Precision::Int8; 3]
        );
        // a uniform f32 profile leaves the tiers off (nothing to exploit).
        assert!(!PrecisionProfile::uniform(Precision::F32).tiers.any());
        // a quantized uniform profile turns the tiers on.
        assert!(PrecisionProfile::uniform(Precision::Nvfp4).tiers.any());
    }

    #[test]
    fn opt_in_out_is_fluent_and_layer_overrides_win() {
        // start from a full opt-out, opt just layer 2 into INT8.
        let p = PrecisionProfile::f32().with_layer(2, Precision::Int8);
        assert_eq!(
            p.plan(4),
            vec![
                Precision::F32,
                Precision::F32,
                Precision::Int8,
                Precision::F32
            ]
        );
        assert!(p.quantizes());
        // opting a layer back to f32 is also just an override.
        let q = PrecisionProfile::all_ternary().with_layer(1, Precision::F32);
        assert_eq!(q.resolve(0), Precision::Ternary);
        assert_eq!(q.resolve(1), Precision::F32);
    }

    #[test]
    fn high_precision_projections_are_tracked() {
        let p = PrecisionProfile::mixed()
            .with_high_precision("lm_head")
            .with_high_precision("embed.out");
        assert!(p.is_high_precision("lm_head"));
        assert!(!p.is_high_precision("layer3.gate"));
        assert_eq!(p.high_precision_refs(), vec!["lm_head", "embed.out"]);
    }

    #[test]
    fn tiers_opt_in_out() {
        let p = PrecisionProfile::f32().with_tiers(Tiers {
            t1_quant_dot: true,
            ..Tiers::NONE
        });
        assert!(p.tiers.t1_quant_dot);
        assert!(!p.tiers.t2_bitwise_attn);
        assert!(p.tiers.any());
    }

    #[test]
    fn serde_round_trip_preserves_the_plan() {
        let p = PrecisionProfile::mixed()
            .with_high_precision("lm_head")
            .with_layer(5, Precision::Ternary);
        let j = serde_json::to_string(&p).unwrap();
        let back: PrecisionProfile = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
        assert_eq!(back.plan(6), p.plan(6));
    }
}
