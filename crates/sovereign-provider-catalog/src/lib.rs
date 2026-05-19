//! `sovereign-provider-catalog` — declared inference providers.
//!
//! Each `ProviderEntry` declares (id, locality, requires_api_key,
//! allowed_bundles, endpoint, status). The router picks from the
//! subset that is Online + the active BundleName is in allowed_bundles.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_profile_bundles::BundleName;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 6 canonical provider ids.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ProviderId {
    /// Local Ollama runtime.
    LocalOllama,
    /// Local vLLM runtime.
    LocalVllm,
    /// Cloud Anthropic.
    CloudAnthropic,
    /// Cloud OpenAI.
    CloudOpenai,
    /// Cloud Google.
    CloudGoogle,
    /// Mock provider (tests / canary).
    Mock,
}

/// Locality.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Locality {
    /// On-host.
    Local,
    /// External network.
    Cloud,
    /// In-process / synthetic.
    Synthetic,
}

/// Status.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Status {
    /// Reachable.
    Online,
    /// Configured but currently unreachable.
    Offline,
    /// Operator disabled.
    Disabled,
}

/// One provider record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProviderEntry {
    /// Id.
    pub id: ProviderId,
    /// Operator-readable label.
    pub label: String,
    /// Endpoint URL or socket path.
    pub endpoint: String,
    /// Locality.
    pub locality: Locality,
    /// Requires API key.
    pub requires_api_key: bool,
    /// Bundles this provider is offered in.
    pub allowed_bundles: Vec<BundleName>,
    /// Current status.
    pub status: Status,
}

/// Catalog envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProviderCatalog {
    /// Schema version.
    pub schema_version: String,
    /// 6 entries (canonical).
    pub entries: Vec<ProviderEntry>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ProviderError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Count != 6.
    #[error("provider count {0} != 6 canonical")]
    CountInvalid(usize),
    /// Missing canonical id.
    #[error("missing provider: {0:?}")]
    Missing(ProviderId),
    /// Endpoint empty.
    #[error("provider {0:?} endpoint empty")]
    EmptyEndpoint(ProviderId),
    /// allowed_bundles empty.
    #[error("provider {0:?} has no allowed_bundles")]
    NoBundles(ProviderId),
    /// Cloud requires api key.
    #[error("provider {0:?} is cloud but requires_api_key is false")]
    CloudWithoutKey(ProviderId),
}

const REQUIRED: [ProviderId; 6] = [
    ProviderId::LocalOllama, ProviderId::LocalVllm,
    ProviderId::CloudAnthropic, ProviderId::CloudOpenai, ProviderId::CloudGoogle,
    ProviderId::Mock,
];

impl ProviderCatalog {
    /// Canonical catalog.
    pub fn canonical() -> Self {
        use BundleName::*;
        let entries = vec![
            ProviderEntry {
                id: ProviderId::LocalOllama,
                label: "Local Ollama".into(),
                endpoint: "http://127.0.0.1:11434".into(),
                locality: Locality::Local,
                requires_api_key: false,
                allowed_bundles: vec![Private, Careful, Fast, Sovereign],
                status: Status::Offline,
            },
            ProviderEntry {
                id: ProviderId::LocalVllm,
                label: "Local vLLM".into(),
                endpoint: "http://127.0.0.1:8000".into(),
                locality: Locality::Local,
                requires_api_key: false,
                allowed_bundles: vec![Private, Careful, Fast, Sovereign],
                status: Status::Offline,
            },
            ProviderEntry {
                id: ProviderId::CloudAnthropic,
                label: "Cloud Anthropic".into(),
                endpoint: "https://api.anthropic.com".into(),
                locality: Locality::Cloud,
                requires_api_key: true,
                allowed_bundles: vec![Careful, Fast, Sovereign],
                status: Status::Offline,
            },
            ProviderEntry {
                id: ProviderId::CloudOpenai,
                label: "Cloud OpenAI".into(),
                endpoint: "https://api.openai.com".into(),
                locality: Locality::Cloud,
                requires_api_key: true,
                allowed_bundles: vec![Careful, Fast, Sovereign],
                status: Status::Offline,
            },
            ProviderEntry {
                id: ProviderId::CloudGoogle,
                label: "Cloud Google".into(),
                endpoint: "https://generativelanguage.googleapis.com".into(),
                locality: Locality::Cloud,
                requires_api_key: true,
                allowed_bundles: vec![Careful, Fast, Sovereign],
                status: Status::Offline,
            },
            ProviderEntry {
                id: ProviderId::Mock,
                label: "Mock".into(),
                endpoint: "mock://".into(),
                locality: Locality::Synthetic,
                requires_api_key: false,
                allowed_bundles: vec![Private, Careful, Fast, Sovereign],
                status: Status::Online,
            },
        ];
        Self {
            schema_version: SCHEMA_VERSION.into(),
            entries,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ProviderError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ProviderError::SchemaMismatch);
        }
        if self.entries.len() != 6 {
            return Err(ProviderError::CountInvalid(self.entries.len()));
        }
        for r in REQUIRED {
            if !self.entries.iter().any(|e| e.id == r) {
                return Err(ProviderError::Missing(r));
            }
        }
        for e in &self.entries {
            if e.endpoint.is_empty() { return Err(ProviderError::EmptyEndpoint(e.id)); }
            if e.allowed_bundles.is_empty() { return Err(ProviderError::NoBundles(e.id)); }
            if e.locality == Locality::Cloud && !e.requires_api_key {
                return Err(ProviderError::CloudWithoutKey(e.id));
            }
        }
        Ok(())
    }

    /// Lookup.
    pub fn get(&self, id: ProviderId) -> Option<&ProviderEntry> {
        self.entries.iter().find(|e| e.id == id)
    }

    /// Set status by id.
    pub fn set_status(&mut self, id: ProviderId, status: Status) -> bool {
        for e in self.entries.iter_mut() {
            if e.id == id { e.status = status; return true; }
        }
        false
    }

    /// Providers eligible in (bundle) right now (Online + bundle-permitted).
    pub fn eligible(&self, bundle: BundleName) -> Vec<&ProviderEntry> {
        self.entries.iter()
            .filter(|e| e.status == Status::Online && e.allowed_bundles.contains(&bundle))
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_validates() {
        ProviderCatalog::canonical().validate().unwrap();
    }

    #[test]
    fn six_providers_present() {
        let c = ProviderCatalog::canonical();
        for id in REQUIRED {
            assert!(c.get(id).is_some(), "missing {id:?}");
        }
    }

    #[test]
    fn cloud_providers_require_api_key() {
        let c = ProviderCatalog::canonical();
        for id in [ProviderId::CloudAnthropic, ProviderId::CloudOpenai, ProviderId::CloudGoogle] {
            assert!(c.get(id).unwrap().requires_api_key, "{id:?} should require api key");
        }
    }

    #[test]
    fn local_providers_dont_require_api_key() {
        let c = ProviderCatalog::canonical();
        for id in [ProviderId::LocalOllama, ProviderId::LocalVllm] {
            assert!(!c.get(id).unwrap().requires_api_key);
        }
    }

    #[test]
    fn private_bundle_excludes_cloud_providers() {
        let c = ProviderCatalog::canonical();
        for id in [ProviderId::CloudAnthropic, ProviderId::CloudOpenai, ProviderId::CloudGoogle] {
            assert!(!c.get(id).unwrap().allowed_bundles.contains(&BundleName::Private));
        }
    }

    #[test]
    fn set_status_updates() {
        let mut c = ProviderCatalog::canonical();
        assert_eq!(c.get(ProviderId::LocalOllama).unwrap().status, Status::Offline);
        assert!(c.set_status(ProviderId::LocalOllama, Status::Online));
        assert_eq!(c.get(ProviderId::LocalOllama).unwrap().status, Status::Online);
    }

    #[test]
    fn eligible_returns_only_online_and_bundle_permitted() {
        let mut c = ProviderCatalog::canonical();
        // Initially only Mock is Online.
        let v = c.eligible(BundleName::Sovereign);
        assert_eq!(v.len(), 1);
        assert_eq!(v[0].id, ProviderId::Mock);
        // Bring Anthropic online.
        c.set_status(ProviderId::CloudAnthropic, Status::Online);
        let v = c.eligible(BundleName::Sovereign);
        assert_eq!(v.len(), 2);
        // Bundle Private excludes cloud.
        let v = c.eligible(BundleName::Private);
        assert_eq!(v.len(), 1);
        assert_eq!(v[0].id, ProviderId::Mock);
    }

    #[test]
    fn cloud_without_key_invalid() {
        let mut c = ProviderCatalog::canonical();
        for e in c.entries.iter_mut() {
            if e.id == ProviderId::CloudAnthropic { e.requires_api_key = false; }
        }
        assert!(matches!(c.validate().unwrap_err(), ProviderError::CloudWithoutKey(ProviderId::CloudAnthropic)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = ProviderCatalog::canonical();
        c.schema_version = "9.9.9".into();
        assert!(matches!(c.validate().unwrap_err(), ProviderError::SchemaMismatch));
    }

    #[test]
    fn count_invalid_caught() {
        let mut c = ProviderCatalog::canonical();
        c.entries.pop();
        assert!(matches!(c.validate().unwrap_err(), ProviderError::CountInvalid(5)));
    }

    #[test]
    fn provider_serde_kebab() {
        assert_eq!(serde_json::to_string(&ProviderId::LocalOllama).unwrap(), "\"local-ollama\"");
        assert_eq!(serde_json::to_string(&ProviderId::CloudAnthropic).unwrap(), "\"cloud-anthropic\"");
        assert_eq!(serde_json::to_string(&ProviderId::Mock).unwrap(), "\"mock\"");
    }

    #[test]
    fn catalog_serde_roundtrip() {
        let c = ProviderCatalog::canonical();
        let j = serde_json::to_string(&c).unwrap();
        let back: ProviderCatalog = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
