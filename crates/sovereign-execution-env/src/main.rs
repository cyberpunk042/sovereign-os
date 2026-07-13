//! `sovereign-execution-env` — reference the E0553 "execute + observe" taxonomy: the
//! 9 execution environments (each with its isolation level) and the 10 observation
//! categories a run is watched by. Nothing ran this model; this CLI makes it a
//! discoverable operator surface — "which environments run where, isolated how".

#![forbid(unsafe_code)]

use sovereign_execution_env::{ExecutionEnv, ObservationCategory};

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "--help" || a == "-h") {
        println!(
            "sovereign-execution-env — the E0553 execution environments + observation categories\n\n\
             USAGE:\n\
             \x20   sovereign-execution-env         list the 9 execution environments (with isolation)\n\
             \x20                                   + the 10 observation categories\n\
             \x20   sovereign-execution-env --help  print this help and exit"
        );
        return;
    }

    println!("Execution environments (E0553) — each with its isolation level:");
    for e in ExecutionEnv::ALL {
        let name = format!("{e:?}");
        println!("  {name:<16} → {:?}", e.isolation());
    }
    println!("\nObservation categories — what a run is watched by:");
    for c in ObservationCategory::ALL {
        println!("  {c:?}");
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_taxonomy_is_complete_and_every_env_maps_to_an_isolation_level() {
        assert_eq!(ExecutionEnv::ALL.len(), 9, "9 execution environments");
        assert_eq!(
            ObservationCategory::ALL.len(),
            10,
            "10 observation categories"
        );
        // every environment resolves an isolation level without panicking
        for e in ExecutionEnv::ALL {
            let _ = e.isolation();
        }
        // spot-check a couple of the security-relevant mappings
        use sovereign_execution_env::IsolationLevel;
        assert_eq!(ExecutionEnv::Vm.isolation(), IsolationLevel::Vm);
        assert_eq!(
            ExecutionEnv::ModelServer.isolation(),
            IsolationLevel::InProcess
        );
    }
}
