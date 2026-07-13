//! `sovereign-inheritance-check` — print the canonical M042 durable-inheritance
//! manifest, or verify the 8 artifacts exist under a target root.
//!
//! Default: print the 8-artifact manifest (position, path, what each carries).
//! `--check ROOT` reports which of `<ROOT>/docs/{VISION.md,…}` are present vs missing,
//! exiting non-zero if any are missing — so "does the box carry its executable
//! memory?" is a verifiable check. The artifact set comes from
//! `sovereign-inheritance-artifacts`, the single source of truth.

#![forbid(unsafe_code)]

use std::path::Path;

use sovereign_inheritance_check::{check_under, manifest_text};

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "--help" || a == "-h") {
        println!(
            "sovereign-inheritance-check — the M042 durable-inheritance artifacts\n\n\
             USAGE:\n\
             \x20   sovereign-inheritance-check                print the canonical 8-artifact manifest\n\
             \x20   sovereign-inheritance-check --check ROOT   verify the artifacts exist under ROOT\n\
             \x20   sovereign-inheritance-check --help         print this help and exit"
        );
        return;
    }

    if let Some(root) = args
        .iter()
        .position(|a| a == "--check")
        .and_then(|i| args.get(i + 1))
    {
        let (present, missing) = check_under(Path::new(root));
        println!("present ({}/8):", present.len());
        for p in &present {
            println!("  ✓ {p}");
        }
        if !missing.is_empty() {
            println!("missing ({}/8):", missing.len());
            for m in &missing {
                println!("  ✗ {m}");
            }
            std::process::exit(1);
        }
        return;
    }

    print!("{}", manifest_text());
}
