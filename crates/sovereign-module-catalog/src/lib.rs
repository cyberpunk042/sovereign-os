//! `sovereign-module-catalog` — M048 sovereign-os 10-module base catalog.
//!
//! Per M048 + E0459-E0467 + M00800-M00815 + dump 14402-14812:
//!
//! | # | Module                  | Module-ID  | Source (R8002..)      |
//! |---|-------------------------|------------|-----------------------|
//! | 1 | Base OS                 | M00800     | E0459 dump 14446      |
//! | 2 | Compute Fabric          | M00801     | E0460 dump 14494      |
//! | 3 | Container/Sandbox Fabric| M00804     | E0461 dump 14538      |
//! | 4 | Gateway (Anthropic-first)| M00806    | E0462 dump 14584      |
//! | 5 | Memory OS               | M00807     | E0463 dump 14616      |
//! | 6 | Workflow Compiler       | M00808     | E0463 dump 14648      |
//! | 7 | Eval/Value Plane        | M00809     | E0464 dump 14682      |
//! | 8 | Continuity Manager      | M00810     | E0464 dump 14706      |
//! | 9 | Observability           | M00811     | E0465 dump 14728      |
//! | 10| LoRA Foundry            | M00812     | E0465 dump 14748      |
//!
//! Plus 3 supplementary surfaces (M00813-M00815):
//! - Configuration Surfaces 3-level (User / Power user / System)
//! - Continuity Stack 6-layer (Hardware / OS / Agent / Memory / Model / Human)
//! - KEY LINE module
//!
//! KEY LINE preserved verbatim per E0467 dump 14810:
//!
//! > "Every module is a controlled continuation of user intent across hardware, software, memory, and time"
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// KEY LINE verbatim per E0467 dump 14810.
pub const KEY_LINE: &str = "Every module is a controlled continuation of user intent across hardware, software, memory, and time";

/// The 10 canonical sovereign-os modules per M00800-M00812.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum CoreModule {
    /// Module 1: Base OS (M00800).
    BaseOs,
    /// Module 2: Compute Fabric (M00801).
    ComputeFabric,
    /// Module 3: Container/Sandbox Fabric (M00804).
    SandboxFabric,
    /// Module 4: Gateway (M00806).
    Gateway,
    /// Module 5: Memory OS (M00807).
    MemoryOs,
    /// Module 6: Workflow Compiler (M00808).
    WorkflowCompiler,
    /// Module 7: Eval/Value Plane (M00809).
    EvalValue,
    /// Module 8: Continuity Manager (M00810).
    ContinuityManager,
    /// Module 9: Observability (M00811).
    Observability,
    /// Module 10: LoRA Foundry (M00812).
    LoraFoundry,
}

impl CoreModule {
    /// Canonical 1..10 position.
    pub fn position(self) -> u8 {
        match self {
            CoreModule::BaseOs => 1,
            CoreModule::ComputeFabric => 2,
            CoreModule::SandboxFabric => 3,
            CoreModule::Gateway => 4,
            CoreModule::MemoryOs => 5,
            CoreModule::WorkflowCompiler => 6,
            CoreModule::EvalValue => 7,
            CoreModule::ContinuityManager => 8,
            CoreModule::Observability => 9,
            CoreModule::LoraFoundry => 10,
        }
    }
    /// Module ID per M00800-M00812.
    pub fn module_id(self) -> &'static str {
        match self {
            CoreModule::BaseOs => "M00800",
            CoreModule::ComputeFabric => "M00801",
            CoreModule::SandboxFabric => "M00804",
            CoreModule::Gateway => "M00806",
            CoreModule::MemoryOs => "M00807",
            CoreModule::WorkflowCompiler => "M00808",
            CoreModule::EvalValue => "M00809",
            CoreModule::ContinuityManager => "M00810",
            CoreModule::Observability => "M00811",
            CoreModule::LoraFoundry => "M00812",
        }
    }
}

/// Module health state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ModuleState {
    /// Healthy + serving.
    Healthy,
    /// Degraded but reachable.
    Degraded,
    /// Offline / unreachable.
    Offline,
    /// Quarantined per MS042 mismatch.
    Quarantined,
}

/// One module-entry in the manifest.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ModuleEntry {
    /// Module discriminator.
    pub module: CoreModule,
    /// Canonical M-id (must equal CoreModule::module_id()).
    pub module_id: String,
    /// Current state.
    pub state: ModuleState,
    /// ISO-8601 UTC last-heartbeat.
    pub last_heartbeat_at: String,
    /// Free-form status text.
    pub notes: String,
}

/// 6-layer continuity stack per E0467 + M00814.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ContinuityLayer {
    /// Hardware layer (Blackwell / 3090 / AVX / ZFS).
    Hardware,
    /// OS layer (Debian 13 / Ubuntu 24 / systemd / kernel).
    Os,
    /// Agent layer (Podman + sandbox isolation).
    Agent,
    /// Memory layer (M028 8-type Memory OS).
    Memory,
    /// Model layer (warm pools + KV cache).
    Model,
    /// Human layer (operator gates + approval surface).
    Human,
}

impl ContinuityLayer {
    /// 1..6 layer position.
    pub fn position(self) -> u8 {
        match self {
            ContinuityLayer::Hardware => 1,
            ContinuityLayer::Os => 2,
            ContinuityLayer::Agent => 3,
            ContinuityLayer::Memory => 4,
            ContinuityLayer::Model => 5,
            ContinuityLayer::Human => 6,
        }
    }
}

/// 3-level configuration surface per E0466 + M00813.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ConfigLevel {
    /// User level — simple profiles + prompts (R10173).
    User,
    /// Power-user level — toggles + budgets + allowed providers + sandbox levels (R10174).
    PowerUser,
    /// System level — policy + hardware profile + routing weights + eval thresholds (R10175).
    System,
}

/// Top-level manifest.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ModuleManifest {
    /// Wire-stable schema version.
    pub schema_version: String,
    /// KEY LINE doctrine string — MUST equal [`KEY_LINE`].
    pub key_line: String,
    /// 10 module entries (MUST be exactly 10).
    pub modules: Vec<ModuleEntry>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ModuleError {
    /// Schema drift.
    #[error("schema version mismatch: expected {expected}, got {actual}")]
    SchemaMismatch {
        /// Expected.
        expected: String,
        /// Observed.
        actual: String,
    },
    /// KEY LINE tampered.
    #[error("KEY LINE tampered: expected verbatim \"{expected}\", got \"{actual}\"")]
    KeyLineTampered {
        /// Expected.
        expected: String,
        /// Observed.
        actual: String,
    },
    /// Module count != 10.
    #[error("module count {0} != 10 canonical core modules")]
    ModuleCountInvalid(usize),
    /// One core module missing.
    #[error("required core module missing: {0:?}")]
    ModuleMissing(CoreModule),
    /// Duplicate core module.
    #[error("duplicate core module: {0:?}")]
    DuplicateModule(CoreModule),
    /// Entry's module_id field doesn't match its CoreModule's canonical id.
    #[error("module_id mismatch: entry {module:?} declared id {declared} != canonical {canonical}")]
    ModuleIdMismatch {
        /// Module.
        module: CoreModule,
        /// Declared id.
        declared: String,
        /// Canonical id.
        canonical: String,
    },
}

impl ModuleManifest {
    /// Construct a canonical empty manifest with all 10 modules Offline + heartbeat-0.
    pub fn empty_canonical() -> Self {
        let now = "1970-01-01T00:00:00Z";
        let modules = [
            CoreModule::BaseOs,
            CoreModule::ComputeFabric,
            CoreModule::SandboxFabric,
            CoreModule::Gateway,
            CoreModule::MemoryOs,
            CoreModule::WorkflowCompiler,
            CoreModule::EvalValue,
            CoreModule::ContinuityManager,
            CoreModule::Observability,
            CoreModule::LoraFoundry,
        ]
        .into_iter()
        .map(|m| ModuleEntry {
            module: m,
            module_id: m.module_id().into(),
            state: ModuleState::Offline,
            last_heartbeat_at: now.into(),
            notes: String::new(),
        })
        .collect();
        Self {
            schema_version: SCHEMA_VERSION.into(),
            key_line: KEY_LINE.into(),
            modules,
        }
    }

    /// Validate canonical invariants.
    pub fn validate(&self) -> Result<(), ModuleError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ModuleError::SchemaMismatch {
                expected: SCHEMA_VERSION.into(),
                actual: self.schema_version.clone(),
            });
        }
        if self.key_line != KEY_LINE {
            return Err(ModuleError::KeyLineTampered {
                expected: KEY_LINE.into(),
                actual: self.key_line.clone(),
            });
        }
        if self.modules.len() != 10 {
            return Err(ModuleError::ModuleCountInvalid(self.modules.len()));
        }
        let required = [
            CoreModule::BaseOs,
            CoreModule::ComputeFabric,
            CoreModule::SandboxFabric,
            CoreModule::Gateway,
            CoreModule::MemoryOs,
            CoreModule::WorkflowCompiler,
            CoreModule::EvalValue,
            CoreModule::ContinuityManager,
            CoreModule::Observability,
            CoreModule::LoraFoundry,
        ];
        for m in required {
            if !self.modules.iter().any(|e| e.module == m) {
                return Err(ModuleError::ModuleMissing(m));
            }
        }
        use std::collections::HashSet;
        let mut seen: HashSet<CoreModule> = HashSet::new();
        for e in &self.modules {
            if !seen.insert(e.module) {
                return Err(ModuleError::DuplicateModule(e.module));
            }
            let canonical = e.module.module_id();
            if e.module_id != canonical {
                return Err(ModuleError::ModuleIdMismatch {
                    module: e.module,
                    declared: e.module_id.clone(),
                    canonical: canonical.into(),
                });
            }
        }
        Ok(())
    }

    /// Lookup by module.
    pub fn entry(&self, module: CoreModule) -> Option<&ModuleEntry> {
        self.modules.iter().find(|e| e.module == module)
    }

    /// Count of modules in each state.
    pub fn state_counts(&self) -> (u32, u32, u32, u32) {
        let mut h = 0;
        let mut d = 0;
        let mut o = 0;
        let mut q = 0;
        for e in &self.modules {
            match e.state {
                ModuleState::Healthy => h += 1,
                ModuleState::Degraded => d += 1,
                ModuleState::Offline => o += 1,
                ModuleState::Quarantined => q += 1,
            }
        }
        (h, d, o, q)
    }

    /// Mark a module's state.
    pub fn mark(
        &mut self,
        module: CoreModule,
        state: ModuleState,
        heartbeat_at: &str,
        notes: &str,
    ) {
        if let Some(e) = self.modules.iter_mut().find(|e| e.module == module) {
            e.state = state;
            e.last_heartbeat_at = heartbeat_at.into();
            e.notes = notes.into();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_canonical_validates() {
        ModuleManifest::empty_canonical().validate().unwrap();
    }

    #[test]
    fn ten_modules_present_in_canonical_order() {
        let m = ModuleManifest::empty_canonical();
        for (expected, n) in [
            (CoreModule::BaseOs, 1),
            (CoreModule::ComputeFabric, 2),
            (CoreModule::SandboxFabric, 3),
            (CoreModule::Gateway, 4),
            (CoreModule::MemoryOs, 5),
            (CoreModule::WorkflowCompiler, 6),
            (CoreModule::EvalValue, 7),
            (CoreModule::ContinuityManager, 8),
            (CoreModule::Observability, 9),
            (CoreModule::LoraFoundry, 10),
        ] {
            assert_eq!(m.modules[n - 1].module, expected, "position {n}");
            assert_eq!(expected.position(), n as u8);
        }
    }

    #[test]
    fn module_ids_match_m00800_to_m00812() {
        assert_eq!(CoreModule::BaseOs.module_id(), "M00800");
        assert_eq!(CoreModule::ComputeFabric.module_id(), "M00801");
        assert_eq!(CoreModule::SandboxFabric.module_id(), "M00804");
        assert_eq!(CoreModule::Gateway.module_id(), "M00806");
        assert_eq!(CoreModule::MemoryOs.module_id(), "M00807");
        assert_eq!(CoreModule::WorkflowCompiler.module_id(), "M00808");
        assert_eq!(CoreModule::EvalValue.module_id(), "M00809");
        assert_eq!(CoreModule::ContinuityManager.module_id(), "M00810");
        assert_eq!(CoreModule::Observability.module_id(), "M00811");
        assert_eq!(CoreModule::LoraFoundry.module_id(), "M00812");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = ModuleManifest::empty_canonical();
        m.schema_version = "9.9.9".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            ModuleError::SchemaMismatch { .. }
        ));
    }

    #[test]
    fn key_line_tamper_caught() {
        let mut m = ModuleManifest::empty_canonical();
        m.key_line = "Modules are containers".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            ModuleError::KeyLineTampered { .. }
        ));
    }

    #[test]
    fn module_count_invalid_caught() {
        let mut m = ModuleManifest::empty_canonical();
        m.modules.pop();
        assert!(matches!(
            m.validate().unwrap_err(),
            ModuleError::ModuleCountInvalid(9)
        ));
    }

    #[test]
    fn missing_module_caught_when_replaced() {
        let mut m = ModuleManifest::empty_canonical();
        m.modules[0] = ModuleEntry {
            module: CoreModule::ComputeFabric,
            module_id: "M00801".into(),
            state: ModuleState::Offline,
            last_heartbeat_at: "1970-01-01T00:00:00Z".into(),
            notes: String::new(),
        };
        let err = m.validate().unwrap_err();
        assert!(matches!(
            err,
            ModuleError::ModuleMissing(CoreModule::BaseOs)
                | ModuleError::DuplicateModule(CoreModule::ComputeFabric)
        ));
    }

    #[test]
    fn module_id_mismatch_caught() {
        let mut m = ModuleManifest::empty_canonical();
        m.modules[0].module_id = "M99999".into();
        let err = m.validate().unwrap_err();
        match err {
            ModuleError::ModuleIdMismatch {
                module,
                declared,
                canonical,
            } => {
                assert_eq!(module, CoreModule::BaseOs);
                assert_eq!(declared, "M99999");
                assert_eq!(canonical, "M00800");
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn mark_updates_state() {
        let mut m = ModuleManifest::empty_canonical();
        m.mark(
            CoreModule::Gateway,
            ModuleState::Healthy,
            "2026-05-19T03:00:00Z",
            "Anthropic-first online",
        );
        let e = m.entry(CoreModule::Gateway).unwrap();
        assert_eq!(e.state, ModuleState::Healthy);
        assert!(e.notes.contains("Anthropic-first"));
    }

    #[test]
    fn state_counts_track_lifecycle() {
        let mut m = ModuleManifest::empty_canonical();
        m.mark(CoreModule::Gateway, ModuleState::Healthy, "t", "");
        m.mark(CoreModule::MemoryOs, ModuleState::Healthy, "t", "");
        m.mark(CoreModule::Observability, ModuleState::Degraded, "t", "");
        m.mark(CoreModule::LoraFoundry, ModuleState::Quarantined, "t", "");
        let (h, d, o, q) = m.state_counts();
        assert_eq!((h, d, o, q), (2, 1, 6, 1));
    }

    // --- ContinuityLayer 6-layer + ConfigLevel 3-level ---

    #[test]
    fn six_continuity_layers_positioned() {
        let order = [
            (ContinuityLayer::Hardware, 1),
            (ContinuityLayer::Os, 2),
            (ContinuityLayer::Agent, 3),
            (ContinuityLayer::Memory, 4),
            (ContinuityLayer::Model, 5),
            (ContinuityLayer::Human, 6),
        ];
        for (l, p) in order {
            assert_eq!(l.position(), p);
        }
    }

    #[test]
    fn config_level_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&ConfigLevel::PowerUser).unwrap(),
            "\"power-user\""
        );
        assert_eq!(
            serde_json::to_string(&ConfigLevel::System).unwrap(),
            "\"system\""
        );
    }

    // --- Doctrine ---

    #[test]
    fn key_line_verbatim() {
        assert_eq!(
            KEY_LINE,
            "Every module is a controlled continuation of user intent across hardware, software, memory, and time"
        );
    }

    // --- Serde ---

    #[test]
    fn core_module_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&CoreModule::SandboxFabric).unwrap(),
            "\"sandbox-fabric\""
        );
        assert_eq!(
            serde_json::to_string(&CoreModule::LoraFoundry).unwrap(),
            "\"lora-foundry\""
        );
        assert_eq!(
            serde_json::to_string(&CoreModule::WorkflowCompiler).unwrap(),
            "\"workflow-compiler\""
        );
    }

    #[test]
    fn manifest_serde_roundtrip() {
        let mut m = ModuleManifest::empty_canonical();
        m.mark(
            CoreModule::Gateway,
            ModuleState::Healthy,
            "2026-05-19T03:00:00Z",
            "ok",
        );
        let j = serde_json::to_string(&m).unwrap();
        let back: ModuleManifest = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
