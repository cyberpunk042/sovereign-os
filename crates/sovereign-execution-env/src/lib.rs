//! `sovereign-execution-env` — E0553: Execute + Observe (lifecycle steps 7-8).
//!
//! "Every execution emits trace events. Observation is ground truth for the
//! workflow." Execution happens in one of nine bounded environments, each with
//! a different isolation level (the policy fabric uses it for risk), and Observe
//! captures ten categories of ground truth. This crate fixes both taxonomies.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// How contained an execution environment is. Higher = stronger isolation.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum IsolationLevel {
    /// Runs inside the daemon process (a trusted in-process service).
    InProcess,
    /// A host process (no namespace isolation).
    HostProcess,
    /// An application sandbox (e.g. a browser sandbox).
    Sandboxed,
    /// A cgroup/namespace container.
    Container,
    /// A full virtual machine.
    Vm,
}

/// The 9 bounded execution environments (E0553).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ExecutionEnv {
    /// A model inference server.
    ModelServer,
    /// A language REPL.
    Repl,
    /// A shell.
    Shell,
    /// A container.
    Container,
    /// A virtual machine.
    Vm,
    /// A browser.
    Browser,
    /// The memory service.
    MemoryService,
    /// A symbolic planner.
    SymbolicPlanner,
    /// The policy engine.
    PolicyEngine,
}

impl ExecutionEnv {
    /// All 9 environments.
    pub const ALL: [ExecutionEnv; 9] = [
        ExecutionEnv::ModelServer,
        ExecutionEnv::Repl,
        ExecutionEnv::Shell,
        ExecutionEnv::Container,
        ExecutionEnv::Vm,
        ExecutionEnv::Browser,
        ExecutionEnv::MemoryService,
        ExecutionEnv::SymbolicPlanner,
        ExecutionEnv::PolicyEngine,
    ];

    /// The isolation level this environment provides.
    #[must_use]
    pub fn isolation(self) -> IsolationLevel {
        match self {
            ExecutionEnv::ModelServer
            | ExecutionEnv::MemoryService
            | ExecutionEnv::SymbolicPlanner
            | ExecutionEnv::PolicyEngine => IsolationLevel::InProcess,
            ExecutionEnv::Repl | ExecutionEnv::Shell => IsolationLevel::HostProcess,
            ExecutionEnv::Browser => IsolationLevel::Sandboxed,
            ExecutionEnv::Container => IsolationLevel::Container,
            ExecutionEnv::Vm => IsolationLevel::Vm,
        }
    }
}

/// The 10 observation categories captured during Observe (E0553). "Observation
/// is ground truth for the workflow."
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ObservationCategory {
    /// stdout / stderr.
    Output,
    /// process exit code.
    ExitCode,
    /// files changed.
    FilesChanged,
    /// network touched.
    NetworkTouched,
    /// tokens used.
    TokensUsed,
    /// latency.
    Latency,
    /// GPU / CPU pressure.
    HardwarePressure,
    /// model output.
    ModelOutput,
    /// tool output.
    ToolOutput,
    /// test results.
    TestResults,
}

impl ObservationCategory {
    /// All 10 categories.
    pub const ALL: [ObservationCategory; 10] = [
        ObservationCategory::Output,
        ObservationCategory::ExitCode,
        ObservationCategory::FilesChanged,
        ObservationCategory::NetworkTouched,
        ObservationCategory::TokensUsed,
        ObservationCategory::Latency,
        ObservationCategory::HardwarePressure,
        ObservationCategory::ModelOutput,
        ObservationCategory::ToolOutput,
        ObservationCategory::TestResults,
    ];
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nine_environments_ten_observations_distinct() {
        use std::collections::HashSet;
        assert_eq!(ExecutionEnv::ALL.len(), 9);
        assert_eq!(ExecutionEnv::ALL.iter().collect::<HashSet<_>>().len(), 9);
        assert_eq!(ObservationCategory::ALL.len(), 10);
        assert_eq!(
            ObservationCategory::ALL
                .iter()
                .collect::<HashSet<_>>()
                .len(),
            10
        );
    }

    #[test]
    fn isolation_ordering_is_sane() {
        // A VM isolates more than a container, which isolates more than a host
        // shell, which isolates more than an in-process service.
        assert!(ExecutionEnv::Vm.isolation() > ExecutionEnv::Container.isolation());
        assert!(ExecutionEnv::Container.isolation() > ExecutionEnv::Shell.isolation());
        assert!(ExecutionEnv::Shell.isolation() > ExecutionEnv::ModelServer.isolation());
        // The four trusted services are all in-process.
        for e in [
            ExecutionEnv::ModelServer,
            ExecutionEnv::MemoryService,
            ExecutionEnv::SymbolicPlanner,
            ExecutionEnv::PolicyEngine,
        ] {
            assert_eq!(e.isolation(), IsolationLevel::InProcess, "{e:?}");
        }
    }

    #[test]
    fn shell_is_riskier_than_container() {
        // The policy fabric reads this: a shell (host process) is less isolated
        // than a container, so the same action is higher risk in a shell.
        assert!(ExecutionEnv::Shell.isolation() < ExecutionEnv::Container.isolation());
    }

    #[test]
    fn serde_kebab() {
        assert_eq!(
            serde_json::to_string(&ExecutionEnv::SymbolicPlanner).unwrap(),
            "\"symbolic-planner\""
        );
        assert_eq!(
            serde_json::to_string(&ObservationCategory::HardwarePressure).unwrap(),
            "\"hardware-pressure\""
        );
        assert_eq!(
            serde_json::to_string(&IsolationLevel::Vm).unwrap(),
            "\"vm\""
        );
    }
}
