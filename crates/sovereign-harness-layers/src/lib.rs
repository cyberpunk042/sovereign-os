//! `sovereign-harness-layers` — M082: the 5-layer TDD test pyramid.
//!
//! sovereign-os is an image-build project; its harness validates the bootable
//! artifact **without requiring the hardware** for all but the top layer. The
//! pyramid (E0788) is:
//!
//! | # | layer | virtualization | runs… |
//! |---|-------|----------------|-------|
//! | 1 | schema/lint | none (pure CI) | every PR (required gate) |
//! | 2 | unit (mocked fs/apt/dpkg) | none (pure CI) | every PR |
//! | 3 | stage-acceptance | chroot + systemd-nspawn | merge to main OR label |
//! | 4 | integration | QEMU system + qemu-user | merge to main OR label |
//! | 5 | hardware-conformance | real SAIN-01 hardware | operator-local ONLY (never CI) |
//!
//! This crate fixes that taxonomy + the CI gating (which layers run on which
//! event), the per-layer virtualization stack (E0789), the test-directory
//! classification used for discovery (E0791), and the flake-retry policy
//! (F06852). It is the decision substrate the CI-workflow generator and the
//! test runner consume; it runs no tests itself.
//!
//! Gating values are verbatim from M082 F06836-F06898. The only inferred datum
//! is L2's trigger: the dump explicitly gates the *virtualized* layers (L3/L4)
//! to merge/label and L5 to operator-local, and states L1 runs every PR; L2 is
//! pure-CI (mocked, no virtualization) exactly like L1, so it runs on every PR
//! by the same rationale. That inference is documented at [`TestLayer::trigger`].
//!
//! # This models the M082 *target*, not (yet) the current workflow
//!
//! The gating here is the M082 design target. The current
//! `.github/workflows/test.yml` has NOT yet implemented it: it runs L1 + L2 +
//! L3 (nspawn) on **every PR and every push to main** (no merge/label gate),
//! has **no L4 (qemu) job at all**, and of course no L5. So a consumer asking
//! "what runs on a PR right now" should read the workflow, not this crate;
//! this crate describes where the harness is *going* (merge/label gating + a
//! qemu L4), which the workflow is expected to grow into as M082 completes.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// L5's wall-clock runtime budget on operator hardware, seconds (F06887).
pub const L5_RUNTIME_BUDGET_SECS: u32 = 3600;

/// One layer of the 5-layer pyramid (E0788).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum TestLayer {
    /// L1 — schema + lint, pure CI, no virtualization.
    SchemaLint,
    /// L2 — unit tests with mocked filesystem / apt / dpkg.
    Unit,
    /// L3 — stage-acceptance via chroot + systemd-nspawn.
    StageAcceptance,
    /// L4 — integration via QEMU system + qemu-user.
    Integration,
    /// L5 — hardware-conformance on a real SAIN-01 node.
    HardwareConformance,
}

/// A virtualization mechanism in the stack (E0789).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Virtualization {
    /// No virtualization — pure CI.
    None,
    /// `chroot`.
    Chroot,
    /// `systemd-nspawn`.
    SystemdNspawn,
    /// QEMU full-system emulation.
    QemuSystem,
    /// `qemu-user` (cross-arch).
    QemuUser,
    /// Real hardware.
    Hardware,
}

/// When a layer runs in the CI/operator workflow.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum CiTrigger {
    /// Every pull request — a required gate (F06893).
    EveryPr,
    /// Merge to main, OR a label-triggered PR (F06866/F06878/F06894/F06895).
    MergeOrLabel,
    /// Operator-local only; NEVER runs in CI (F06896).
    OperatorLocalOnly,
}

/// A CI/workflow event the runner is reacting to.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum CiEvent {
    /// A pull request opened/updated (no special label).
    PullRequest,
    /// A PR carrying the virtualization opt-in label.
    LabeledPullRequest,
    /// A merge to `main`.
    MergeToMain,
    /// The operator running the suite locally on real hardware.
    OperatorLocal,
}

impl TestLayer {
    /// All five layers, base to apex.
    pub const ALL: [TestLayer; 5] = [
        TestLayer::SchemaLint,
        TestLayer::Unit,
        TestLayer::StageAcceptance,
        TestLayer::Integration,
        TestLayer::HardwareConformance,
    ];

    /// Layer number, 1..=5.
    #[must_use]
    pub const fn number(self) -> u8 {
        match self {
            TestLayer::SchemaLint => 1,
            TestLayer::Unit => 2,
            TestLayer::StageAcceptance => 3,
            TestLayer::Integration => 4,
            TestLayer::HardwareConformance => 5,
        }
    }

    /// The virtualization mechanisms this layer needs (E0789).
    #[must_use]
    pub fn virtualization(self) -> &'static [Virtualization] {
        match self {
            TestLayer::SchemaLint | TestLayer::Unit => &[Virtualization::None],
            TestLayer::StageAcceptance => &[Virtualization::Chroot, Virtualization::SystemdNspawn],
            TestLayer::Integration => &[Virtualization::QemuSystem, Virtualization::QemuUser],
            TestLayer::HardwareConformance => &[Virtualization::Hardware],
        }
    }

    /// When this layer runs.
    ///
    /// L1 is the explicit every-PR required gate (F06893); L2 is inferred to
    /// also run every PR because it is pure-CI / hardware-free exactly like L1
    /// (the dump gates only the virtualized L3/L4 to merge/label and L5 to
    /// operator-local). L3/L4 run on merge-or-label (F06866/F06878). L5 is
    /// operator-local only and NEVER runs in CI (F06896).
    #[must_use]
    pub const fn trigger(self) -> CiTrigger {
        match self {
            TestLayer::SchemaLint | TestLayer::Unit => CiTrigger::EveryPr,
            TestLayer::StageAcceptance | TestLayer::Integration => CiTrigger::MergeOrLabel,
            TestLayer::HardwareConformance => CiTrigger::OperatorLocalOnly,
        }
    }

    /// Whether this layer ever runs in CI (L5 never does — F06896).
    #[must_use]
    pub const fn runs_in_ci(self) -> bool {
        !matches!(self.trigger(), CiTrigger::OperatorLocalOnly)
    }

    /// Retries allowed on a transient flake. Only L2 (mocked) gets one retry
    /// (F06852); every other layer is retry-0 (a failure is a failure).
    #[must_use]
    pub const fn flake_retries(self) -> u8 {
        match self {
            TestLayer::Unit => 1,
            _ => 0,
        }
    }

    /// Classify a test directory name (e.g. `schema`, `lint`, `unit`, `chroot`,
    /// `nspawn`, `qemu`, `hardware`) to its layer. `schema` and `lint` both map
    /// to L1; `chroot` and `nspawn` both map to L3. Unknown ⇒ `None`.
    #[must_use]
    pub fn classify_dir(dir: &str) -> Option<TestLayer> {
        match dir.trim().trim_matches('/').to_ascii_lowercase().as_str() {
            "schema" | "lint" => Some(TestLayer::SchemaLint),
            "unit" => Some(TestLayer::Unit),
            "chroot" | "nspawn" => Some(TestLayer::StageAcceptance),
            "qemu" => Some(TestLayer::Integration),
            "hardware" => Some(TestLayer::HardwareConformance),
            _ => None,
        }
    }
}

/// Whether a layer runs for a given CI/workflow event.
#[must_use]
pub fn layer_runs_on(layer: TestLayer, event: CiEvent) -> bool {
    match event {
        // A plain PR runs only the every-PR layers.
        CiEvent::PullRequest => layer.trigger() == CiTrigger::EveryPr,
        // A labeled PR additionally opts into the merge-or-label (virtualized)
        // layers; still no hardware.
        CiEvent::LabeledPullRequest | CiEvent::MergeToMain => {
            matches!(
                layer.trigger(),
                CiTrigger::EveryPr | CiTrigger::MergeOrLabel
            )
        }
        // The operator running locally on real hardware runs the full pyramid.
        CiEvent::OperatorLocal => true,
    }
}

/// The ordered set of layers that run for an event.
#[must_use]
pub fn layers_for_event(event: CiEvent) -> Vec<TestLayer> {
    TestLayer::ALL
        .into_iter()
        .filter(|l| layer_runs_on(*l, event))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn five_layers_numbered_base_to_apex() {
        assert_eq!(TestLayer::ALL.len(), 5);
        for (i, l) in TestLayer::ALL.into_iter().enumerate() {
            assert_eq!(l.number(), (i + 1) as u8);
        }
    }

    #[test]
    fn only_l5_is_excluded_from_ci() {
        for l in TestLayer::ALL {
            assert_eq!(l.runs_in_ci(), l != TestLayer::HardwareConformance, "{l:?}");
        }
    }

    #[test]
    fn pure_ci_layers_have_no_virtualization() {
        assert_eq!(
            TestLayer::SchemaLint.virtualization(),
            &[Virtualization::None]
        );
        assert_eq!(TestLayer::Unit.virtualization(), &[Virtualization::None]);
        assert_eq!(
            TestLayer::StageAcceptance.virtualization(),
            &[Virtualization::Chroot, Virtualization::SystemdNspawn]
        );
        assert_eq!(
            TestLayer::Integration.virtualization(),
            &[Virtualization::QemuSystem, Virtualization::QemuUser]
        );
        assert_eq!(
            TestLayer::HardwareConformance.virtualization(),
            &[Virtualization::Hardware]
        );
    }

    #[test]
    fn only_unit_layer_retries_flakes() {
        assert_eq!(TestLayer::Unit.flake_retries(), 1);
        for l in TestLayer::ALL.into_iter().filter(|l| *l != TestLayer::Unit) {
            assert_eq!(l.flake_retries(), 0, "{l:?}");
        }
    }

    #[test]
    fn pr_runs_only_pure_ci_layers() {
        assert_eq!(
            layers_for_event(CiEvent::PullRequest),
            vec![TestLayer::SchemaLint, TestLayer::Unit]
        );
    }

    #[test]
    fn merge_and_label_run_through_l4_but_never_hardware() {
        let merge = layers_for_event(CiEvent::MergeToMain);
        let label = layers_for_event(CiEvent::LabeledPullRequest);
        assert_eq!(merge, label, "merge and labeled-PR run the same set");
        assert_eq!(
            merge,
            vec![
                TestLayer::SchemaLint,
                TestLayer::Unit,
                TestLayer::StageAcceptance,
                TestLayer::Integration
            ]
        );
        assert!(
            !merge.contains(&TestLayer::HardwareConformance),
            "hardware never in CI"
        );
    }

    #[test]
    fn operator_local_runs_the_full_pyramid() {
        assert_eq!(
            layers_for_event(CiEvent::OperatorLocal),
            TestLayer::ALL.to_vec()
        );
    }

    #[test]
    fn classify_dir_maps_the_test_tree() {
        assert_eq!(
            TestLayer::classify_dir("schema"),
            Some(TestLayer::SchemaLint)
        );
        assert_eq!(TestLayer::classify_dir("lint"), Some(TestLayer::SchemaLint));
        assert_eq!(TestLayer::classify_dir("unit"), Some(TestLayer::Unit));
        assert_eq!(
            TestLayer::classify_dir("chroot"),
            Some(TestLayer::StageAcceptance)
        );
        assert_eq!(
            TestLayer::classify_dir("nspawn"),
            Some(TestLayer::StageAcceptance)
        );
        assert_eq!(
            TestLayer::classify_dir("qemu"),
            Some(TestLayer::Integration)
        );
        assert_eq!(
            TestLayer::classify_dir("/hardware/"),
            Some(TestLayer::HardwareConformance)
        );
        assert_eq!(TestLayer::classify_dir("docs"), None);
    }

    #[test]
    fn l5_budget_constant() {
        assert_eq!(L5_RUNTIME_BUDGET_SECS, 3600);
    }

    #[test]
    fn serde_kebab() {
        assert_eq!(
            serde_json::to_string(&TestLayer::SchemaLint).unwrap(),
            "\"schema-lint\""
        );
        assert_eq!(
            serde_json::to_string(&CiTrigger::EveryPr).unwrap(),
            "\"every-pr\""
        );
        assert_eq!(
            serde_json::to_string(&Virtualization::SystemdNspawn).unwrap(),
            "\"systemd-nspawn\""
        );
    }
}
