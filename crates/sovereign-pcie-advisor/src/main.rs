//! `sovereign-pcie-advisor` — print the recommended ProArt X870E-Creator PCIe layout,
//! or validate a proposed one against the lane-sharing trap (E0027).
//!
//! Default: print the slot map + recommended layout + the validation result.
//! `--check <file.json>` loads a `[{slot, device}, …]` placement array and validates
//! it, exiting non-zero on a lane-sharing / duplicate-slot conflict — so a proposed
//! hardware population is caught before it silently halves a GPU's bandwidth. Slot
//! ranges come from `sovereign-pcie-topology`, the single source of truth.

#![forbid(unsafe_code)]

use sovereign_pcie_advisor::{check, recommended_advisory};
use sovereign_pcie_topology::Placement;

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "--help" || a == "-h") {
        println!(
            "sovereign-pcie-advisor — recommend / validate the X870E-Creator PCIe layout\n\n\
             USAGE:\n\
             \x20   sovereign-pcie-advisor                 print the recommended layout + validation\n\
             \x20   sovereign-pcie-advisor --check FILE    validate a JSON [{{slot,device}}] array\n\
             \x20   sovereign-pcie-advisor --help          print this help and exit"
        );
        return;
    }

    if let Some(path) = args
        .iter()
        .position(|a| a == "--check")
        .and_then(|i| args.get(i + 1))
    {
        let placements: Vec<Placement> = match std::fs::read_to_string(path)
            .map_err(|e| e.to_string())
            .and_then(|c| serde_json::from_str(&c).map_err(|e| e.to_string()))
        {
            Ok(p) => p,
            Err(e) => {
                eprintln!("sovereign-pcie-advisor: --check {path}: {e}");
                std::process::exit(2);
            }
        };
        match check(&placements) {
            Ok(()) => println!(
                "OK — no lane-sharing conflict in {} placement(s)",
                placements.len()
            ),
            Err(e) => {
                eprintln!("CONFLICT — {e}");
                std::process::exit(1);
            }
        }
        return;
    }

    print!("{}", recommended_advisory());
}
