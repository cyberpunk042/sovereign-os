//! `sovereign-router-7axis` — M042 7-axis routing brain.
//!
//! Per M042 + dump 12219-12225 (NadirClaw "many prompts do not deserve
//! the expensive model"), this crate maps an incoming task (described
//! by 7 axes) to the cheapest viable model in the M075 SRP topology
//! (Conductor / Logic / Oracle).
//!
//! The seven axes per R07039-R07045 + F03527-F03533:
//!
//! | axis              | values                                  |
//! |-------------------|-----------------------------------------|
//! | complexity        | simple / complex                        |
//! | privacy           | private / public                        |
//! | safety            | safe / risky                            |
//! | domain            | coding / research / gui                 |
//! | locality          | local / cloud                           |
//! | latency           | fast / careful                          |
//! | quality           | cheap / oracle                          |
//!
//! Routing strategy (NadirClaw doctrine):
//! - private + risky → local Oracle (Blackwell, no cloud egress)
//! - simple + cheap + fast → Conductor (CPU ternary, lowest cost)
//! - complex + careful + oracle → Oracle (Blackwell PRO 6000)
//! - all in-between → Logic Engine (RTX 4090 NVFP4)
//!
//! Standing rule: We do not minimize anything. We catalogue the 7-axis
//! decision per the published NadirClaw doctrine; we do not invent.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Verbatim NadirClaw doctrine surface per dump 12219.
pub const DOCTRINE_NOT_EVERY_PROMPT: &str = "many prompts do not deserve the expensive model";

/// Axis 1 (R07039) — task complexity.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Complexity {
    /// Single-step, low-context tool invocation.
    Simple,
    /// Multi-step, high-context reasoning.
    Complex,
}

/// Axis 2 (R07040) — privacy envelope.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Privacy {
    /// Private — must stay on-device, no cloud egress.
    Private,
    /// Public — cloud egress is acceptable.
    Public,
}

/// Axis 3 (R07041) — safety class.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Safety {
    /// Safe — deterministic, well-bounded.
    Safe,
    /// Risky — exploratory, may need sandbox + oracle review.
    Risky,
}

/// Axis 4 (R07042) — domain class.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Domain {
    /// Coding task (refactor / generate / debug).
    Coding,
    /// Research task (synthesise across sources).
    Research,
    /// GUI / visual / multimodal task.
    Gui,
}

/// Axis 5 (R07043) — locality preference.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Locality {
    /// Local only.
    Local,
    /// Cloud allowed.
    Cloud,
}

/// Axis 6 (R07044) — latency target.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Latency {
    /// Latency-first (favour throughput).
    Fast,
    /// Correctness-first (favour quality).
    Careful,
}

/// Axis 7 (R07045) — quality target.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Quality {
    /// Cheapest viable model.
    Cheap,
    /// Oracle-grade (highest quality, highest cost).
    Oracle,
}

/// Composite 7-axis task descriptor.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TaskAxes {
    /// Complexity.
    pub complexity: Complexity,
    /// Privacy.
    pub privacy: Privacy,
    /// Safety.
    pub safety: Safety,
    /// Domain.
    pub domain: Domain,
    /// Locality.
    pub locality: Locality,
    /// Latency.
    pub latency: Latency,
    /// Quality.
    pub quality: Quality,
}

/// M075 SRP role assignment target.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SrpRole {
    /// Conductor — CPU ternary (M073). Lowest cost.
    Conductor,
    /// Logic Engine — RTX 4090 NVFP4. Mid cost.
    Logic,
    /// Oracle Core — Blackwell PRO 6000. Highest cost.
    Oracle,
    /// Cloud — refused when privacy=Private.
    Cloud,
}

/// Output of the router.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RouteDecision {
    /// Assigned SRP role.
    pub role: SrpRole,
    /// Single-line reason text.
    pub reason: String,
    /// Doctrine source ("R07039..R07045 + NadirClaw").
    pub provenance: String,
}

/// Routing errors.
#[derive(Debug, Error)]
pub enum RouterError {
    /// Privacy=Private + Locality=Cloud is a contradiction.
    #[error("contradiction: privacy=Private with locality=Cloud — refused")]
    PrivacyLocalityContradiction,
}

/// Compute the SRP route for a 7-axis task descriptor.
pub fn route(axes: &TaskAxes) -> Result<RouteDecision, RouterError> {
    // First refuse contradictions: Private + Cloud cannot coexist (privacy wins).
    if axes.privacy == Privacy::Private && axes.locality == Locality::Cloud {
        return Err(RouterError::PrivacyLocalityContradiction);
    }

    let role = decide_role(axes);
    Ok(RouteDecision {
        role,
        reason: explain(axes, role),
        provenance: "R07039..R07045 + NadirClaw".into(),
    })
}

fn decide_role(a: &TaskAxes) -> SrpRole {
    // 1. private + risky → keep local Oracle (no cloud egress, highest local quality).
    if a.privacy == Privacy::Private && a.safety == Safety::Risky {
        return SrpRole::Oracle;
    }
    // 2. quality=Oracle always lands on Oracle Core unless privacy permits cloud.
    if a.quality == Quality::Oracle {
        return if a.locality == Locality::Cloud && a.privacy == Privacy::Public {
            SrpRole::Cloud
        } else {
            SrpRole::Oracle
        };
    }
    // 3. GUI domain → Logic Engine (4090 with VFIO browser/CUDA paths).
    // Must precede the simple+cheap+fast Conductor path: GUI inherently
    // needs the 4090 substrate even for "simple" requests.
    if a.domain == Domain::Gui {
        return SrpRole::Logic;
    }
    // 4. simple + cheap + fast → Conductor.
    if a.complexity == Complexity::Simple
        && a.quality == Quality::Cheap
        && a.latency == Latency::Fast
    {
        return SrpRole::Conductor;
    }
    // 5. complex + careful → Logic Engine for NVFP4 long-context.
    if a.complexity == Complexity::Complex && a.latency == Latency::Careful {
        return SrpRole::Logic;
    }
    // 6. Default fallback: cheapest viable per NadirClaw — Conductor.
    SrpRole::Conductor
}

fn explain(a: &TaskAxes, role: SrpRole) -> String {
    match role {
        SrpRole::Conductor => format!(
            "Conductor (CPU ternary): {:?}+{:?}+{:?} → cheapest viable per NadirClaw",
            a.complexity, a.quality, a.latency
        ),
        SrpRole::Logic => format!(
            "Logic Engine (4090 NVFP4): {:?} domain or complex+careful",
            a.domain
        ),
        SrpRole::Oracle => {
            if a.privacy == Privacy::Private && a.safety == Safety::Risky {
                "Oracle Core (Blackwell): private+risky stays local".into()
            } else {
                "Oracle Core (Blackwell): quality=Oracle local-pinned".into()
            }
        }
        SrpRole::Cloud => "Cloud: quality=Oracle + privacy=Public + locality=Cloud".into(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn t() -> TaskAxes {
        TaskAxes {
            complexity: Complexity::Simple,
            privacy: Privacy::Private,
            safety: Safety::Safe,
            domain: Domain::Coding,
            locality: Locality::Local,
            latency: Latency::Fast,
            quality: Quality::Cheap,
        }
    }

    #[test]
    fn doctrine_verbatim_present() {
        assert_eq!(
            DOCTRINE_NOT_EVERY_PROMPT,
            "many prompts do not deserve the expensive model"
        );
    }

    #[test]
    fn private_cloud_contradiction_refused() {
        let mut a = t();
        a.privacy = Privacy::Private;
        a.locality = Locality::Cloud;
        assert!(matches!(
            route(&a).unwrap_err(),
            RouterError::PrivacyLocalityContradiction
        ));
    }

    #[test]
    fn private_risky_lands_on_oracle_local() {
        let mut a = t();
        a.privacy = Privacy::Private;
        a.safety = Safety::Risky;
        let d = route(&a).unwrap();
        assert_eq!(d.role, SrpRole::Oracle);
        assert!(d.reason.contains("private+risky"));
    }

    #[test]
    fn simple_cheap_fast_lands_on_conductor() {
        let a = t(); // simple + cheap + fast
        let d = route(&a).unwrap();
        assert_eq!(d.role, SrpRole::Conductor);
    }

    #[test]
    fn quality_oracle_lands_on_oracle_when_private_or_local() {
        let mut a = t();
        a.quality = Quality::Oracle;
        a.privacy = Privacy::Private;
        a.locality = Locality::Local;
        assert_eq!(route(&a).unwrap().role, SrpRole::Oracle);

        let mut b = t();
        b.quality = Quality::Oracle;
        b.privacy = Privacy::Public;
        b.locality = Locality::Local;
        assert_eq!(route(&b).unwrap().role, SrpRole::Oracle);
    }

    #[test]
    fn quality_oracle_public_cloud_routes_to_cloud() {
        let mut a = t();
        a.quality = Quality::Oracle;
        a.privacy = Privacy::Public;
        a.locality = Locality::Cloud;
        assert_eq!(route(&a).unwrap().role, SrpRole::Cloud);
    }

    #[test]
    fn gui_lands_on_logic() {
        let mut a = t();
        a.domain = Domain::Gui;
        a.quality = Quality::Cheap; // ensure not preempted by Oracle path
        assert_eq!(route(&a).unwrap().role, SrpRole::Logic);
    }

    #[test]
    fn complex_careful_lands_on_logic() {
        let mut a = t();
        a.complexity = Complexity::Complex;
        a.latency = Latency::Careful;
        a.quality = Quality::Cheap;
        assert_eq!(route(&a).unwrap().role, SrpRole::Logic);
    }

    #[test]
    fn private_risky_overrides_oracle_quality() {
        // Private+Risky path runs FIRST in decide_role, so even with quality=Oracle
        // we still land on local Oracle.
        let mut a = t();
        a.privacy = Privacy::Private;
        a.safety = Safety::Risky;
        a.quality = Quality::Oracle;
        a.locality = Locality::Local;
        let d = route(&a).unwrap();
        assert_eq!(d.role, SrpRole::Oracle);
    }

    #[test]
    fn provenance_cites_r_rows_and_doctrine() {
        let a = t();
        let d = route(&a).unwrap();
        assert!(d.provenance.contains("R07039"));
        assert!(d.provenance.contains("R07045"));
        assert!(d.provenance.contains("NadirClaw"));
    }

    #[test]
    fn task_axes_serde_roundtrip() {
        let original = t();
        let j = serde_json::to_string(&original).unwrap();
        let back: TaskAxes = serde_json::from_str(&j).unwrap();
        assert_eq!(original, back);
    }

    #[test]
    fn srp_role_serde_kebab_case() {
        assert_eq!(
            serde_json::to_string(&SrpRole::Conductor).unwrap(),
            "\"conductor\""
        );
        assert_eq!(serde_json::to_string(&SrpRole::Logic).unwrap(), "\"logic\"");
        assert_eq!(
            serde_json::to_string(&SrpRole::Oracle).unwrap(),
            "\"oracle\""
        );
        assert_eq!(serde_json::to_string(&SrpRole::Cloud).unwrap(), "\"cloud\"");
    }

    #[test]
    fn all_axes_have_two_or_three_values() {
        // Complexity: 2, Privacy: 2, Safety: 2, Domain: 3, Locality: 2, Latency: 2, Quality: 2
        // Total combinations: 2*2*2*3*2*2*2 = 192 — exercise a few to confirm no panics.
        for &c in &[Complexity::Simple, Complexity::Complex] {
            for &p in &[Privacy::Private, Privacy::Public] {
                for &s in &[Safety::Safe, Safety::Risky] {
                    for &dom in &[Domain::Coding, Domain::Research, Domain::Gui] {
                        for &l in &[Locality::Local, Locality::Cloud] {
                            // Skip the contradiction combo
                            if p == Privacy::Private && l == Locality::Cloud {
                                continue;
                            }
                            for &lat in &[Latency::Fast, Latency::Careful] {
                                for &q in &[Quality::Cheap, Quality::Oracle] {
                                    let a = TaskAxes {
                                        complexity: c,
                                        privacy: p,
                                        safety: s,
                                        domain: dom,
                                        locality: l,
                                        latency: lat,
                                        quality: q,
                                    };
                                    let _ = route(&a).unwrap();
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
