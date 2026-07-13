//! `sovereign-whitelabel` CLI — the runnable end of M081.
//!
//! The library fixes the whitelabel taxonomy — how each Debian surface must be
//! treated during a rebrand ([`RebrandCategory`]), how it is rendered with the
//! brand ([`RenderStrategy`]), and when the rebrand is applied
//! ([`LifecycleStage`]) — plus the load-bearing safety rule (`must-not-touch`
//! is never modifiable). But nothing *ran* it, so "is this proposed rebrand
//! plan legal?" was unanswerable at the command line. This binary is that
//! runnable end: the E0785 legal-compliance validator, expressed over the
//! crate's own types.
//!
//! Modes:
//!   * default (no args) — print the whitelabel model as a human-readable
//!     reference: the 4 rebrand categories (each with `may-modify` /
//!     `is-required`), the 4 render strategies, and the 3 lifecycle stages.
//!   * `--check FILE` — load a rebrand plan (a surface object or a JSON array of
//!     them) and validate each surface against the M081 contract: a
//!     `must-not-touch` surface is never modified and never carries a render
//!     strategy (E0785); a `must-rebrand` surface must actually be modified.
//!     Reports OK / the violation(s) and exits non-zero if any surface fails.
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use serde::Deserialize;
use sovereign_whitelabel::{LifecycleStage, RebrandCategory, RenderStrategy};

/// The stable kebab-case label for a category — identical to how
/// [`RebrandCategory`] serializes to JSON (kept honest by the
/// `labels_match_serde` test).
fn category_label(category: RebrandCategory) -> &'static str {
    match category {
        RebrandCategory::MustRebrand => "must-rebrand",
        RebrandCategory::ShouldRebrand => "should-rebrand",
        RebrandCategory::MayLeave => "may-leave",
        RebrandCategory::MustNotTouch => "must-not-touch",
    }
}

/// A one-line description of how a category obliges a rebrand pass to treat a
/// surface.
fn category_description(category: RebrandCategory) -> &'static str {
    match category {
        RebrandCategory::MustRebrand => "operator-visible brand surfaces — a rebrand is required",
        RebrandCategory::ShouldRebrand => "recommended, not blocking",
        RebrandCategory::MayLeave => "optional; may be left as-is",
        RebrandCategory::MustNotTouch => {
            "licenses, third-party code, protocol identifiers — never modified"
        }
    }
}

/// The stable kebab-case label for a render strategy — identical to how
/// [`RenderStrategy`] serializes to JSON.
fn strategy_label(strategy: RenderStrategy) -> &'static str {
    match strategy {
        RenderStrategy::TemplateSubstitution => "template-substitution",
        RenderStrategy::FileOverlay => "file-overlay",
        RenderStrategy::PackageReplacement => "package-replacement",
        RenderStrategy::BuildTimeFlag => "build-time-flag",
    }
}

/// A one-line description of what a render strategy does.
fn strategy_description(strategy: RenderStrategy) -> &'static str {
    match strategy {
        RenderStrategy::TemplateSubstitution => "substitute brand tokens in a template",
        RenderStrategy::FileOverlay => "overlay a replacement file",
        RenderStrategy::PackageReplacement => "replace a whole package",
        RenderStrategy::BuildTimeFlag => "flip a build-time flag",
    }
}

/// The stable kebab-case label for a lifecycle stage — identical to how
/// [`LifecycleStage`] serializes to JSON.
fn stage_label(stage: LifecycleStage) -> &'static str {
    match stage {
        LifecycleStage::PreBuild => "pre-build",
        LifecycleStage::InstallTime => "install-time",
        LifecycleStage::FirstBoot => "first-boot",
    }
}

/// A one-line description of when a lifecycle stage applies the rebrand.
fn stage_description(stage: LifecycleStage) -> &'static str {
    match stage {
        LifecycleStage::PreBuild => "pre-build patches",
        LifecycleStage::InstallTime => "install-time substitutions",
        LifecycleStage::FirstBoot => "first-boot scripts",
    }
}

/// The human-readable reference: the whole M081 whitelabel model.
fn reference_text() -> String {
    let mut s = String::from(
        "M081 whitelabel model — the surface rebrand taxonomy, the render\n\
         strategies, and the lifecycle stages.\n\n\
         REBRAND CATEGORIES — how a surface must be treated:\n",
    );
    for category in RebrandCategory::ALL {
        s.push_str(&format!(
            "  {:<15} may-modify={:<5} is-required={:<5} {}\n",
            category_label(category),
            category.may_modify(),
            category.is_required(),
            category_description(category),
        ));
    }
    s.push_str("\nRENDER STRATEGIES — how a surface is rendered with the brand:\n");
    for strategy in RenderStrategy::ALL {
        s.push_str(&format!(
            "  {:<22} {}\n",
            strategy_label(strategy),
            strategy_description(strategy),
        ));
    }
    s.push_str("\nLIFECYCLE STAGES — when the rebrand is applied, in apply order:\n");
    for (i, stage) in LifecycleStage::ALL.into_iter().enumerate() {
        s.push_str(&format!(
            "  {}. {:<13} {}\n",
            i + 1,
            stage_label(stage),
            stage_description(stage),
        ));
    }
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-whitelabel — the M081 whitelabel model + legal-compliance validator\n\n\
     Every Debian surface is categorized (must-rebrand / should-rebrand /\n\
     may-leave / must-not-touch), rendered by a strategy, and applied at a\n\
     lifecycle stage. The load-bearing safety rule: must-not-touch surfaces\n\
     (licenses, third-party code, protocol identifiers) are never modified.\n\n\
     USAGE:\n\
     \x20   sovereign-whitelabel                 print the whitelabel model (reference)\n\
     \x20   sovereign-whitelabel --check FILE     validate a rebrand plan from JSON\n\
     \x20   sovereign-whitelabel --help           print this help and exit\n\n\
     --check FILE loads a rebrand plan — a single surface object or a JSON array\n\
     of them, each { \"surface\": name, \"category\": <category>, \"modified\": bool,\n\
     optional \"strategy\": <strategy>, optional \"stage\": <stage> } — and enforces\n\
     the E0785 contract: a must-not-touch surface is never modified and never\n\
     carries a render strategy, and a must-rebrand surface must be modified.\n\
     Exits non-zero if any surface violates the contract.\n"
        .to_string()
}

/// One surface as declared in a rebrand plan. Operates on the crate's own enums
/// via serde: `category`, `strategy`, and `stage` all deserialize from the
/// crate's kebab-case JSON.
#[derive(Debug, Deserialize)]
struct PlanSurface {
    /// The surface name (e.g. `"boot"`, `"package-mgr"`, `"gpl-notice"`).
    surface: String,
    /// How this surface must be treated (the crate taxonomy).
    category: RebrandCategory,
    /// Whether the plan modifies this surface (defaults to `false`).
    #[serde(default)]
    modified: bool,
    /// The render strategy the plan assigns to this surface, if any.
    #[serde(default)]
    strategy: Option<RenderStrategy>,
    /// The lifecycle stage the plan applies this surface at, if any.
    #[serde(default)]
    stage: Option<LifecycleStage>,
}

/// A specific way a plan surface violates the M081 contract.
#[derive(Debug, PartialEq, Eq)]
enum Violation {
    /// Modifies a surface whose category forbids modification (must-not-touch).
    ModifiesProtected,
    /// Assigns a render strategy to a surface that must not be touched.
    StrategyOnProtected,
    /// A must-rebrand surface the plan leaves unmodified.
    RequiredNotApplied,
}

impl std::fmt::Display for Violation {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let msg = match self {
            Violation::ModifiesProtected => "modifies a must-not-touch surface (E0785 safety rule)",
            Violation::StrategyOnProtected => {
                "assigns a render strategy to a must-not-touch surface"
            }
            Violation::RequiredNotApplied => "must-rebrand surface left unmodified",
        };
        f.write_str(msg)
    }
}

/// Check one surface against the M081 contract, using the crate's own
/// [`RebrandCategory::may_modify`] / [`RebrandCategory::is_required`] rules.
fn violations(surface: &PlanSurface) -> Vec<Violation> {
    let mut out = Vec::new();
    if !surface.category.may_modify() {
        if surface.modified {
            out.push(Violation::ModifiesProtected);
        }
        if surface.strategy.is_some() {
            out.push(Violation::StrategyOnProtected);
        }
    }
    if surface.category.is_required() && !surface.modified {
        out.push(Violation::RequiredNotApplied);
    }
    out
}

/// The outcome of checking one surface.
struct SurfaceOutcome {
    /// The surface's `surface` name.
    surface: String,
    /// The surface's declared category.
    category: RebrandCategory,
    /// The surface's declared lifecycle stage, if any.
    stage: Option<LifecycleStage>,
    /// The contract violations found (empty means compliant).
    violations: Vec<Violation>,
}

/// Accept either a single surface object or a JSON array of them.
fn parse_plan(json: &str) -> Result<Vec<PlanSurface>, serde_json::Error> {
    match serde_json::from_str::<Vec<PlanSurface>>(json) {
        Ok(v) => Ok(v),
        // Not an array — try a single surface object, surfacing that error.
        Err(_) => serde_json::from_str::<PlanSurface>(json).map(|s| vec![s]),
    }
}

/// Parse a rebrand plan from JSON and check every surface.
fn check_plan(json: &str) -> Result<Vec<SurfaceOutcome>, serde_json::Error> {
    let plan = parse_plan(json)?;
    Ok(plan
        .into_iter()
        .map(|s| SurfaceOutcome {
            violations: violations(&s),
            surface: s.surface,
            category: s.category,
            stage: s.stage,
        })
        .collect())
}

/// `--check FILE`: read the file, validate the rebrand plan, print a report,
/// and return a process exit code (non-zero on read/parse error or any
/// violation).
fn run_check(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("error: cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let outcomes = match check_plan(&json) {
        Ok(o) => o,
        Err(e) => {
            eprintln!("error: {path} is not a rebrand plan (surface object or array): {e}");
            return ExitCode::FAILURE;
        }
    };
    if outcomes.is_empty() {
        println!("(no surfaces in {path})");
        return ExitCode::SUCCESS;
    }

    let mut all_ok = true;
    for o in &outcomes {
        let cat = category_label(o.category);
        let stage = o.stage.map_or("-", stage_label);
        if o.violations.is_empty() {
            println!("OK   {} [{cat}] stage={stage} — compliant", o.surface);
        } else {
            all_ok = false;
            for v in &o.violations {
                println!("FAIL {} [{cat}] — {v}", o.surface);
            }
        }
    }

    if all_ok {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();

    if args.iter().any(|a| a == "--help" || a == "-h") {
        print!("{}", help_text());
        return ExitCode::SUCCESS;
    }

    if let Some(i) = args.iter().position(|a| a == "--check") {
        let Some(path) = args.get(i + 1) else {
            eprintln!("error: --check requires a FILE argument\n");
            eprint!("{}", help_text());
            return ExitCode::FAILURE;
        };
        return run_check(path);
    }

    if let Some(unknown) = args.iter().find(|a| a.starts_with('-')) {
        eprintln!("error: unknown argument '{unknown}'\n");
        eprint!("{}", help_text());
        return ExitCode::FAILURE;
    }

    print!("{}", reference_text());
    ExitCode::SUCCESS
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reference_lists_the_whole_model() {
        let t = reference_text();
        for c in RebrandCategory::ALL {
            assert!(
                t.contains(category_label(c)),
                "reference missing {c:?}:\n{t}"
            );
            assert!(
                t.contains(category_description(c)),
                "reference missing description for {c:?}:\n{t}"
            );
        }
        for s in RenderStrategy::ALL {
            assert!(
                t.contains(strategy_label(s)),
                "reference missing {s:?}:\n{t}"
            );
        }
        for st in LifecycleStage::ALL {
            assert!(
                t.contains(stage_label(st)),
                "reference missing {st:?}:\n{t}"
            );
        }
    }

    #[test]
    fn labels_match_serde() {
        // The CLI's kebab labels must not drift from the enums' JSON form.
        for c in RebrandCategory::ALL {
            assert_eq!(
                serde_json::to_string(&c).unwrap(),
                format!("\"{}\"", category_label(c))
            );
        }
        for s in RenderStrategy::ALL {
            assert_eq!(
                serde_json::to_string(&s).unwrap(),
                format!("\"{}\"", strategy_label(s))
            );
        }
        for st in LifecycleStage::ALL {
            assert_eq!(
                serde_json::to_string(&st).unwrap(),
                format!("\"{}\"", stage_label(st))
            );
        }
    }

    #[test]
    fn check_accepts_compliant_plan() {
        // must-rebrand surface actually modified; must-not-touch left alone.
        let json = r#"[
            {"surface":"boot","category":"must-rebrand","modified":true,"strategy":"file-overlay","stage":"pre-build"},
            {"surface":"gpl-notice","category":"must-not-touch","modified":false}
        ]"#;
        let outcomes = check_plan(json).unwrap();
        assert_eq!(outcomes.len(), 2);
        assert!(outcomes.iter().all(|o| o.violations.is_empty()));
        assert_eq!(outcomes[0].stage, Some(LifecycleStage::PreBuild));
    }

    #[test]
    fn check_flags_modified_must_not_touch() {
        // The load-bearing safety rule: never modify a must-not-touch surface.
        let json = r#"{"surface":"gpl-notice","category":"must-not-touch","modified":true}"#;
        let outcomes = check_plan(json).unwrap();
        assert_eq!(outcomes.len(), 1);
        assert_eq!(outcomes[0].violations, vec![Violation::ModifiesProtected]);
    }

    #[test]
    fn check_flags_strategy_on_protected() {
        let json = r#"{"surface":"gpl-notice","category":"must-not-touch","strategy":"template-substitution"}"#;
        let outcomes = check_plan(json).unwrap();
        assert_eq!(outcomes[0].violations, vec![Violation::StrategyOnProtected]);
    }

    #[test]
    fn check_flags_required_not_applied() {
        let json = r#"{"surface":"os-release","category":"must-rebrand","modified":false}"#;
        let outcomes = check_plan(json).unwrap();
        assert_eq!(outcomes[0].violations, vec![Violation::RequiredNotApplied]);
    }

    #[test]
    fn check_parses_single_object_and_array() {
        let one = check_plan(r#"{"surface":"docs","category":"may-leave"}"#).unwrap();
        assert_eq!(one.len(), 1);
        assert!(one[0].violations.is_empty());

        let many = check_plan(r#"[{"surface":"docs","category":"may-leave"}]"#).unwrap();
        assert_eq!(many.len(), 1);
    }

    #[test]
    fn check_reports_invalid_json_as_error() {
        assert!(check_plan("not json").is_err());
        // An unknown category value is also a parse error (the crate's enum).
        assert!(check_plan(r#"{"surface":"x","category":"burn-it-down"}"#).is_err());
    }
}
