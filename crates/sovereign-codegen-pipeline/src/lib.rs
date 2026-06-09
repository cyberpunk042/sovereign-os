//! `sovereign-codegen-pipeline` — E0216: the Generated Code Path.
//!
//! Generated code earns trust; it is never trusted on arrival. Every piece runs
//! a seven-step pipeline before it can commit, and over its lifetime it climbs a
//! five-rung promotion ladder from ad-hoc snippet to trusted runtime primitive —
//! one rung at a time, never skipping. This crate fixes both sequences and the
//! no-skip promotion rule.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// The 7 steps a piece of generated code passes before commit (E0216).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum CodegenStep {
    /// 1. Propose the code.
    Propose,
    /// 2. Validate its capability requirements.
    ValidateCaps,
    /// 3. Run it in the appropriate execution tier.
    RunInTier,
    /// 4. Capture its I/O.
    CaptureIo,
    /// 5. Validate the output schema.
    ValidateSchema,
    /// 6. Attach the trace.
    AttachTrace,
    /// 7. Commit or reject.
    CommitOrReject,
}

impl CodegenStep {
    /// All 7 steps, in order.
    pub const ALL: [CodegenStep; 7] = [
        CodegenStep::Propose,
        CodegenStep::ValidateCaps,
        CodegenStep::RunInTier,
        CodegenStep::CaptureIo,
        CodegenStep::ValidateSchema,
        CodegenStep::AttachTrace,
        CodegenStep::CommitOrReject,
    ];

    /// 1-based position.
    #[must_use]
    pub fn position(self) -> u8 {
        (Self::ALL.iter().position(|s| *s == self).unwrap() + 1) as u8
    }

    /// The next step, or `None` after commit-or-reject.
    #[must_use]
    pub fn next(self) -> Option<CodegenStep> {
        let i = Self::ALL.iter().position(|s| *s == self).unwrap();
        Self::ALL.get(i + 1).copied()
    }
}

/// The 5-rung promotion ladder a tool climbs over its lifetime (E0216),
/// ascending trust.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PromotionRung {
    /// Ad-hoc snippet.
    AdHoc,
    /// A sandboxed script.
    SandboxedScript,
    /// A tested tool.
    TestedTool,
    /// A WASM plugin.
    WasmPlugin,
    /// A trusted runtime primitive.
    TrustedPrimitive,
}

impl PromotionRung {
    /// All 5 rungs, lowest trust first.
    pub const ALL: [PromotionRung; 5] = [
        PromotionRung::AdHoc,
        PromotionRung::SandboxedScript,
        PromotionRung::TestedTool,
        PromotionRung::WasmPlugin,
        PromotionRung::TrustedPrimitive,
    ];

    /// Trust rank (AdHoc=0 … TrustedPrimitive=4).
    #[must_use]
    pub fn rank(self) -> u8 {
        Self::ALL.iter().position(|r| *r == self).unwrap() as u8
    }

    /// The next rung up, or `None` at the top.
    #[must_use]
    pub fn next(self) -> Option<PromotionRung> {
        Self::ALL.get(self.rank() as usize + 1).copied()
    }

    /// Whether `self → to` is a legal promotion: exactly one rung up (no
    /// skipping — a snippet can't jump straight to a trusted primitive).
    #[must_use]
    pub fn can_promote_to(self, to: PromotionRung) -> bool {
        self.next() == Some(to)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn seven_steps_ordered_and_chained() {
        assert_eq!(CodegenStep::ALL.len(), 7);
        assert_eq!(CodegenStep::Propose.position(), 1);
        assert_eq!(CodegenStep::CommitOrReject.position(), 7);
        assert_eq!(CodegenStep::Propose.next(), Some(CodegenStep::ValidateCaps));
        assert_eq!(CodegenStep::CommitOrReject.next(), None);
    }

    #[test]
    fn caps_validated_before_running() {
        // validate-caps must come before run-in-tier (don't run un-vetted caps).
        assert!(CodegenStep::ValidateCaps.position() < CodegenStep::RunInTier.position());
        // schema validated before the trace is attached and committed.
        assert!(CodegenStep::ValidateSchema.position() < CodegenStep::CommitOrReject.position());
    }

    #[test]
    fn promotion_is_one_rung_at_a_time() {
        assert!(PromotionRung::AdHoc.can_promote_to(PromotionRung::SandboxedScript));
        assert!(PromotionRung::WasmPlugin.can_promote_to(PromotionRung::TrustedPrimitive));
        // no skipping: ad-hoc can't jump to trusted primitive.
        assert!(!PromotionRung::AdHoc.can_promote_to(PromotionRung::TrustedPrimitive));
        assert!(!PromotionRung::AdHoc.can_promote_to(PromotionRung::TestedTool));
        // no demotion through this method.
        assert!(!PromotionRung::TestedTool.can_promote_to(PromotionRung::SandboxedScript));
    }

    #[test]
    fn top_rung_cannot_promote_further() {
        assert_eq!(PromotionRung::TrustedPrimitive.next(), None);
        assert!(PromotionRung::TrustedPrimitive.rank() > PromotionRung::AdHoc.rank());
    }

    #[test]
    fn serde_kebab() {
        assert_eq!(
            serde_json::to_string(&CodegenStep::CommitOrReject).unwrap(),
            "\"commit-or-reject\""
        );
        assert_eq!(
            serde_json::to_string(&PromotionRung::TrustedPrimitive).unwrap(),
            "\"trusted-primitive\""
        );
    }
}
