//! `sovereign-gateway` — M048 Module 4 Anthropic-first 6-surface + 7-responsibility gateway.
//!
//! Per M048 + E0462 + M00806 + dump 14584-14610.
//!
//! Doctrine verbatim:
//!
//! > "Instead of tools owning provider keys: client → Sovereign Gateway → local/cloud/model router"
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Doctrine verbatim per E0462 dump 14592.
pub const DOCTRINE_PROVIDER_INVERSION: &str =
    "Instead of tools owning provider keys: client → Sovereign Gateway → local/cloud/model router";

/// 6 gateway surfaces per E0462 dump 14586-14602.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum GatewaySurface {
    /// 1. Anthropic Messages-compatible API.
    AnthropicMessages,
    /// 2. OpenAI-compatible API shim.
    OpenAiShim,
    /// 3. MCP bridge.
    McpBridge,
    /// 4. Claude Code integration.
    ClaudeCode,
    /// 5. OpenCode + Cline compatibility.
    OpenCodeCline,
    /// 6. Cost + route ledger.
    CostRouteLedger,
}

impl GatewaySurface {
    /// Canonical 1..6.
    pub fn position(self) -> u8 {
        match self {
            GatewaySurface::AnthropicMessages => 1,
            GatewaySurface::OpenAiShim => 2,
            GatewaySurface::McpBridge => 3,
            GatewaySurface::ClaudeCode => 4,
            GatewaySurface::OpenCodeCline => 5,
            GatewaySurface::CostRouteLedger => 6,
        }
    }
}

/// 7 gateway responsibilities per E0462 dump 14604-14610.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum GatewayResponsibility {
    /// 1. Cost.
    Cost,
    /// 2. Privacy.
    Privacy,
    /// 3. Redaction.
    Redaction,
    /// 4. Routing.
    Routing,
    /// 5. Profiles.
    Profiles,
    /// 6. Approval.
    Approval,
    /// 7. Tracing.
    Tracing,
}

impl GatewayResponsibility {
    /// Canonical 1..7.
    pub fn position(self) -> u8 {
        match self {
            GatewayResponsibility::Cost => 1,
            GatewayResponsibility::Privacy => 2,
            GatewayResponsibility::Redaction => 3,
            GatewayResponsibility::Routing => 4,
            GatewayResponsibility::Profiles => 5,
            GatewayResponsibility::Approval => 6,
            GatewayResponsibility::Tracing => 7,
        }
    }
}

/// Surface enablement state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SurfaceState {
    /// Live + accepting requests.
    Live,
    /// Loaded but disabled by operator.
    Disabled,
    /// Loaded but failed health-check.
    Failed,
}

/// One surface record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SurfaceRecord {
    /// Surface kind.
    pub surface: GatewaySurface,
    /// State.
    pub state: SurfaceState,
    /// Bind path (e.g. "/v1/messages").
    pub bind_path: String,
}

/// Gateway manifest.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct GatewayManifest {
    /// Schema version.
    pub schema_version: String,
    /// Doctrine surface — MUST equal [`DOCTRINE_PROVIDER_INVERSION`].
    pub doctrine: String,
    /// 6 surfaces (exactly 6).
    pub surfaces: Vec<SurfaceRecord>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum GatewayError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Doctrine tampered.
    #[error("doctrine tampered")]
    DoctrineTampered,
    /// Surface count != 6.
    #[error("surface count {0} != 6 canonical surfaces")]
    SurfaceCountInvalid(usize),
    /// Required surface missing.
    #[error("required surface missing: {0:?}")]
    SurfaceMissing(GatewaySurface),
    /// Duplicate surface.
    #[error("duplicate surface: {0:?}")]
    DuplicateSurface(GatewaySurface),
}

impl GatewayManifest {
    /// Canonical empty manifest with all 6 surfaces Disabled.
    pub fn empty_canonical() -> Self {
        let surfaces = [
            (GatewaySurface::AnthropicMessages, "/v1/messages"),
            (GatewaySurface::OpenAiShim, "/v1/chat/completions"),
            (GatewaySurface::McpBridge, "/mcp"),
            (GatewaySurface::ClaudeCode, "/claude-code"),
            (GatewaySurface::OpenCodeCline, "/opencode-cline"),
            (GatewaySurface::CostRouteLedger, "/admin/ledger"),
        ].into_iter().map(|(s, p)| SurfaceRecord {
            surface: s,
            state: SurfaceState::Disabled,
            bind_path: p.into(),
        }).collect();
        Self {
            schema_version: SCHEMA_VERSION.into(),
            doctrine: DOCTRINE_PROVIDER_INVERSION.into(),
            surfaces,
        }
    }

    /// Validate canonical invariants.
    pub fn validate(&self) -> Result<(), GatewayError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(GatewayError::SchemaMismatch);
        }
        if self.doctrine != DOCTRINE_PROVIDER_INVERSION {
            return Err(GatewayError::DoctrineTampered);
        }
        if self.surfaces.len() != 6 {
            return Err(GatewayError::SurfaceCountInvalid(self.surfaces.len()));
        }
        let required = [
            GatewaySurface::AnthropicMessages, GatewaySurface::OpenAiShim,
            GatewaySurface::McpBridge, GatewaySurface::ClaudeCode,
            GatewaySurface::OpenCodeCline, GatewaySurface::CostRouteLedger,
        ];
        for s in required {
            if !self.surfaces.iter().any(|r| r.surface == s) {
                return Err(GatewayError::SurfaceMissing(s));
            }
        }
        use std::collections::HashSet;
        let mut seen: HashSet<GatewaySurface> = HashSet::new();
        for r in &self.surfaces {
            if !seen.insert(r.surface) {
                return Err(GatewayError::DuplicateSurface(r.surface));
            }
        }
        Ok(())
    }

    /// Count of live surfaces.
    pub fn live_count(&self) -> usize {
        self.surfaces.iter().filter(|r| r.state == SurfaceState::Live).count()
    }
}

/// All 7 responsibilities the gateway is required to own.
pub fn all_responsibilities() -> [GatewayResponsibility; 7] {
    [
        GatewayResponsibility::Cost, GatewayResponsibility::Privacy,
        GatewayResponsibility::Redaction, GatewayResponsibility::Routing,
        GatewayResponsibility::Profiles, GatewayResponsibility::Approval,
        GatewayResponsibility::Tracing,
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn six_surfaces_positioned_1_to_6() {
        for (s, p) in [
            (GatewaySurface::AnthropicMessages, 1), (GatewaySurface::OpenAiShim, 2),
            (GatewaySurface::McpBridge, 3), (GatewaySurface::ClaudeCode, 4),
            (GatewaySurface::OpenCodeCline, 5), (GatewaySurface::CostRouteLedger, 6),
        ] {
            assert_eq!(s.position(), p);
        }
    }

    #[test]
    fn seven_responsibilities_positioned_1_to_7() {
        for (r, p) in [
            (GatewayResponsibility::Cost, 1), (GatewayResponsibility::Privacy, 2),
            (GatewayResponsibility::Redaction, 3), (GatewayResponsibility::Routing, 4),
            (GatewayResponsibility::Profiles, 5), (GatewayResponsibility::Approval, 6),
            (GatewayResponsibility::Tracing, 7),
        ] {
            assert_eq!(r.position(), p);
        }
        assert_eq!(all_responsibilities().len(), 7);
    }

    #[test]
    fn empty_canonical_validates() {
        GatewayManifest::empty_canonical().validate().unwrap();
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = GatewayManifest::empty_canonical();
        m.schema_version = "9.9.9".into();
        assert!(matches!(m.validate().unwrap_err(), GatewayError::SchemaMismatch));
    }

    #[test]
    fn doctrine_tamper_caught() {
        let mut m = GatewayManifest::empty_canonical();
        m.doctrine = "Tools own provider keys".into();
        assert!(matches!(m.validate().unwrap_err(), GatewayError::DoctrineTampered));
    }

    #[test]
    fn surface_count_invalid_rejected() {
        let mut m = GatewayManifest::empty_canonical();
        m.surfaces.pop();
        assert!(matches!(m.validate().unwrap_err(), GatewayError::SurfaceCountInvalid(5)));
    }

    #[test]
    fn missing_surface_caught_when_replaced() {
        let mut m = GatewayManifest::empty_canonical();
        m.surfaces[0] = SurfaceRecord {
            surface: GatewaySurface::OpenAiShim,
            state: SurfaceState::Disabled,
            bind_path: "/dup".into(),
        };
        let err = m.validate().unwrap_err();
        assert!(matches!(err,
            GatewayError::SurfaceMissing(GatewaySurface::AnthropicMessages)
            | GatewayError::DuplicateSurface(GatewaySurface::OpenAiShim)
        ));
    }

    #[test]
    fn live_count_filters() {
        let mut m = GatewayManifest::empty_canonical();
        m.surfaces[0].state = SurfaceState::Live;
        m.surfaces[1].state = SurfaceState::Live;
        m.surfaces[2].state = SurfaceState::Failed;
        assert_eq!(m.live_count(), 2);
    }

    #[test]
    fn doctrine_verbatim() {
        assert_eq!(
            DOCTRINE_PROVIDER_INVERSION,
            "Instead of tools owning provider keys: client → Sovereign Gateway → local/cloud/model router"
        );
    }

    #[test]
    fn surface_serde_kebab() {
        assert_eq!(serde_json::to_string(&GatewaySurface::AnthropicMessages).unwrap(), "\"anthropic-messages\"");
        assert_eq!(serde_json::to_string(&GatewaySurface::McpBridge).unwrap(), "\"mcp-bridge\"");
        assert_eq!(serde_json::to_string(&GatewaySurface::CostRouteLedger).unwrap(), "\"cost-route-ledger\"");
        assert_eq!(serde_json::to_string(&GatewaySurface::OpenCodeCline).unwrap(), "\"open-code-cline\"");
    }

    #[test]
    fn responsibility_serde_kebab() {
        assert_eq!(serde_json::to_string(&GatewayResponsibility::Approval).unwrap(), "\"approval\"");
        assert_eq!(serde_json::to_string(&GatewayResponsibility::Redaction).unwrap(), "\"redaction\"");
    }

    #[test]
    fn manifest_serde_roundtrip() {
        let m = GatewayManifest::empty_canonical();
        let j = serde_json::to_string(&m).unwrap();
        let back: GatewayManifest = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
