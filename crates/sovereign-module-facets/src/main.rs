//! `sovereign-module-facets` CLI — the runnable end of E0477 / M00828.
//!
//! The library fixes the uniform module interface: every module MUST expose six
//! facets (state / events / policy hooks / profile knobs / rollback story /
//! learning signal), with a descriptor + completeness validator. But nothing
//! *ran* it, so "does this module honour the interface?" was unanswerable at the
//! command line. This binary is that runnable end.
//!
//! Modes:
//!   * default (no args) — print the 6 canonical facets (name + description) as a
//!     human-readable reference: the uniform module interface itself.
//!   * `--check FILE` — load a `ModuleDescriptor` (or a JSON array of them),
//!     `validate()` each, report OK / the `FacetError`, and whether the name is
//!     one of the 13 canonical modules; exit non-zero if any descriptor fails.
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use sovereign_module_facets::{FacetError, ModuleDescriptor, ModuleFacet};

/// The stable kebab-case label for a facet — identical to how [`ModuleFacet`]
/// serializes to JSON (kept honest by the `facet_label_matches_serde` test).
fn facet_label(facet: ModuleFacet) -> &'static str {
    match facet {
        ModuleFacet::State => "state",
        ModuleFacet::Events => "events",
        ModuleFacet::PolicyHooks => "policy-hooks",
        ModuleFacet::ProfileKnobs => "profile-knobs",
        ModuleFacet::Rollback => "rollback",
        ModuleFacet::LearningSignal => "learning-signal",
    }
}

/// A one-line human description of what each facet obliges a module to expose.
fn facet_description(facet: ModuleFacet) -> &'static str {
    match facet {
        ModuleFacet::State => "its observable state",
        ModuleFacet::Events => "the events it emits (the E0470 taxonomy)",
        ModuleFacet::PolicyHooks => "the policy hooks it honours (the E0473 questions)",
        ModuleFacet::ProfileKnobs => "the profile knobs that tune it",
        ModuleFacet::Rollback => "its rollback story (how its actions are reversed)",
        ModuleFacet::LearningSignal => {
            "the learning signal it feeds back (what adaptation it enables)"
        }
    }
}

/// The human-readable reference: the 6 facets every module must expose.
fn reference_text() -> String {
    let mut s = String::from(
        "The uniform module interface (E0477 / M00828): every module MUST expose these 6 facets.\n\n",
    );
    for (i, facet) in ModuleFacet::ALL.into_iter().enumerate() {
        s.push_str(&format!(
            "  {}. {:<16} {}\n",
            i + 1,
            facet_label(facet),
            facet_description(facet),
        ));
    }
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-module-facets — the uniform module interface (E0477 / M00828)\n\n\
     Every module MUST expose 6 facets: state, events, policy hooks, profile\n\
     knobs, a rollback story, and a learning signal.\n\n\
     USAGE:\n\
     \x20   sovereign-module-facets                 print the 6 canonical facets (reference)\n\
     \x20   sovereign-module-facets --check FILE     validate ModuleDescriptor(s) from JSON\n\
     \x20   sovereign-module-facets --help           print this help and exit\n\n\
     --check FILE loads a single ModuleDescriptor object or a JSON array of them,\n\
     runs validate() on each (all 6 facets present & non-empty), reports whether\n\
     the name is one of the 13 canonical modules, and exits non-zero if any fail.\n"
        .to_string()
}

/// The outcome of checking one descriptor.
struct CheckOutcome {
    /// The descriptor's `name`.
    name: String,
    /// Whether `name` is one of the 13 canonical modules.
    canonical: bool,
    /// The completeness-contract result.
    result: Result<(), FacetError>,
}

/// Accept either a single descriptor object or a JSON array of them.
fn parse_descriptors(json: &str) -> Result<Vec<ModuleDescriptor>, serde_json::Error> {
    match serde_json::from_str::<Vec<ModuleDescriptor>>(json) {
        Ok(v) => Ok(v),
        // Not an array — try a single descriptor object, surfacing that error.
        Err(_) => serde_json::from_str::<ModuleDescriptor>(json).map(|d| vec![d]),
    }
}

/// Parse one-or-many descriptors from JSON and validate each.
fn check_json(json: &str) -> Result<Vec<CheckOutcome>, serde_json::Error> {
    let descriptors = parse_descriptors(json)?;
    Ok(descriptors
        .into_iter()
        .map(|d| CheckOutcome {
            canonical: d.is_canonical(),
            result: d.validate(),
            name: d.name,
        })
        .collect())
}

/// `--check FILE`: read the file, validate the descriptor(s), print a report,
/// and return a process exit code (non-zero on read/parse error or any failure).
fn run_check(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("error: cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let outcomes = match check_json(&json) {
        Ok(o) => o,
        Err(e) => {
            eprintln!("error: {path} is not a ModuleDescriptor (or array of them): {e}");
            return ExitCode::FAILURE;
        }
    };
    if outcomes.is_empty() {
        println!("(no descriptors in {path})");
        return ExitCode::SUCCESS;
    }

    let mut all_ok = true;
    for o in &outcomes {
        let canon = if o.canonical {
            "canonical"
        } else {
            "non-canonical"
        };
        let name = &o.name;
        match &o.result {
            Ok(()) => println!("OK   {name} [{canon}] — all 6 facets declared"),
            Err(err) => {
                all_ok = false;
                println!("FAIL {name} [{canon}] — {err}");
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

    /// A descriptor for `name` declaring all six facets non-empty.
    fn complete(name: &str) -> ModuleDescriptor {
        let mut d = ModuleDescriptor::new(name);
        for f in ModuleFacet::ALL {
            d = d.with(f, format!("{f:?} of {name}"));
        }
        d
    }

    #[test]
    fn reference_lists_all_six_facets() {
        let t = reference_text();
        for f in ModuleFacet::ALL {
            assert!(t.contains(facet_label(f)), "reference missing {f:?}:\n{t}");
            assert!(
                t.contains(facet_description(f)),
                "reference missing description for {f:?}:\n{t}"
            );
        }
        // Exactly six numbered "  N. " entries — one per facet, no more.
        let numbered = t
            .lines()
            .filter(|l| l.trim_start().starts_with(|c: char| c.is_ascii_digit()))
            .count();
        assert_eq!(numbered, ModuleFacet::ALL.len(), "expected 6 facet lines");
    }

    #[test]
    fn facet_label_matches_serde() {
        // The CLI's kebab labels must not drift from the enum's JSON form.
        for f in ModuleFacet::ALL {
            let json = serde_json::to_string(&f).unwrap();
            assert_eq!(json, format!("\"{}\"", facet_label(f)));
        }
    }

    #[test]
    fn check_accepts_complete_canonical_descriptor() {
        let json = serde_json::to_string(&complete("Gateway")).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 1);
        assert_eq!(outcomes[0].name, "Gateway");
        assert!(outcomes[0].canonical);
        assert!(outcomes[0].result.is_ok());
    }

    #[test]
    fn check_rejects_incomplete_descriptor() {
        // State + Events declared; the first missing required facet is PolicyHooks.
        let d = ModuleDescriptor::new("Memory OS")
            .with(ModuleFacet::State, "kv + episodic")
            .with(ModuleFacet::Events, "memory_read / memory_write");
        let json = serde_json::to_string(&d).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 1);
        assert!(outcomes[0].canonical); // "Memory OS" is a canonical name…
        assert_eq!(
            outcomes[0].result,
            Err(FacetError::MissingFacet(ModuleFacet::PolicyHooks)),
            "…but it must still be rejected as incomplete"
        );
    }

    #[test]
    fn check_rejects_empty_facet() {
        let d = complete("Gateway").with(ModuleFacet::LearningSignal, "   ");
        let json = serde_json::to_string(&d).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(
            outcomes[0].result,
            Err(FacetError::EmptyFacet(ModuleFacet::LearningSignal))
        );
    }

    #[test]
    fn check_parses_array_and_flags_non_canonical() {
        let arr = vec![complete("Gateway"), complete("my-custom-module")];
        let json = serde_json::to_string(&arr).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 2);
        assert!(outcomes[0].canonical);
        assert!(!outcomes[1].canonical);
        assert!(outcomes.iter().all(|o| o.result.is_ok()));
    }

    #[test]
    fn check_reports_invalid_json_as_error() {
        assert!(check_json("not json").is_err());
    }
}
