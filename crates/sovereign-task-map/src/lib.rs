//! `sovereign-task-map` — E0551: Map (lifecycle step 4).
//!
//! "MAP prevents blind action." Before planning, the runtime builds a
//! domain-specific map of the territory. There are four domains, each gathering
//! a different set of components; this crate fixes those four maps and the
//! components each requires.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// The four map domains (E0551).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum MapDomain {
    /// Code tasks.
    Code,
    /// Research tasks.
    Research,
    /// GUI tasks.
    Gui,
    /// OS / admin tasks.
    OsAdmin,
}

impl MapDomain {
    /// All four domains.
    pub const ALL: [MapDomain; 4] = [
        MapDomain::Code,
        MapDomain::Research,
        MapDomain::Gui,
        MapDomain::OsAdmin,
    ];

    /// The components this domain's map gathers (E0551, verbatim).
    #[must_use]
    pub fn components(self) -> &'static [&'static str] {
        match self {
            MapDomain::Code => &[
                "repo structure",
                "language/framework",
                "test commands",
                "dependency graph",
                "recent failures",
                "relevant files",
                "project policy",
            ],
            MapDomain::Research => &[
                "source landscape",
                "claim types",
                "freshness requirements",
                "citation needs",
            ],
            MapDomain::Gui => &[
                "screen elements",
                "state machine",
                "allowed actions",
                "risk zones",
            ],
            MapDomain::OsAdmin => &[
                "service state",
                "logs",
                "hardware pressure",
                "rollback points",
                "permissions",
            ],
        }
    }
}

/// A built map: a domain plus the gathered component values.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TaskMap {
    /// Which domain.
    pub domain: MapDomain,
    /// Component name → gathered value/summary.
    pub gathered: Vec<(String, String)>,
}

impl TaskMap {
    /// A new, empty map for a domain.
    #[must_use]
    pub fn new(domain: MapDomain) -> Self {
        Self {
            domain,
            gathered: Vec::new(),
        }
    }

    /// Record a component's gathered value.
    pub fn gather(&mut self, component: impl Into<String>, value: impl Into<String>) {
        self.gathered.push((component.into(), value.into()));
    }

    /// The components the domain requires but the map hasn't gathered yet —
    /// the blind spots that would make planning "blind action".
    #[must_use]
    pub fn missing_components(&self) -> Vec<&'static str> {
        self.domain
            .components()
            .iter()
            .copied()
            .filter(|c| !self.gathered.iter().any(|(name, _)| name == c))
            .collect()
    }

    /// Whether every required component for the domain has been gathered.
    #[must_use]
    pub fn is_complete(&self) -> bool {
        self.missing_components().is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn four_domains_with_catalogued_component_counts() {
        assert_eq!(MapDomain::ALL.len(), 4);
        assert_eq!(MapDomain::Code.components().len(), 7);
        assert_eq!(MapDomain::Research.components().len(), 4);
        assert_eq!(MapDomain::Gui.components().len(), 4);
        assert_eq!(MapDomain::OsAdmin.components().len(), 5);
    }

    #[test]
    fn os_admin_map_includes_rollback_points() {
        // OS/admin tasks must know their rollback points before acting.
        assert!(MapDomain::OsAdmin.components().contains(&"rollback points"));
        assert!(MapDomain::OsAdmin.components().contains(&"hardware pressure"));
    }

    #[test]
    fn missing_components_are_the_blind_spots() {
        let mut m = TaskMap::new(MapDomain::Code);
        assert_eq!(m.missing_components().len(), 7);
        assert!(!m.is_complete());
        for c in MapDomain::Code.components() {
            m.gather(*c, "…");
        }
        assert!(m.missing_components().is_empty());
        assert!(m.is_complete());
    }

    #[test]
    fn partial_map_reports_only_the_gaps() {
        let mut m = TaskMap::new(MapDomain::Research);
        m.gather("source landscape", "arxiv + blogs");
        m.gather("claim types", "empirical");
        let missing = m.missing_components();
        assert_eq!(missing.len(), 2);
        assert!(missing.contains(&"freshness requirements"));
        assert!(missing.contains(&"citation needs"));
    }

    #[test]
    fn domain_serializes_kebab() {
        assert_eq!(serde_json::to_string(&MapDomain::OsAdmin).unwrap(), "\"os-admin\"");
    }
}
