//! `sovereign-vm-channel` — E0120 / M00222–M00224: the Communication Boundary.
//!
//! The quarantined 4090 VM exchanges only **compact messages** with the host,
//! never bulk tensors. Communication crosses one of four narrow channels, in a
//! fixed set of message types, under one invariant (M00224): **VM output is a
//! candidate, never a commit** — the host AVX-512 layer policy-filters, the
//! oracle verifies, and only the host's replay log commits. This crate fixes
//! the channels, the message types, and that candidate invariant.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// The four Host↔4090 channels (M00222).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum VmChannel {
    /// virtio-vsock.
    VirtioVsock,
    /// gRPC over vsock.
    GrpcOverVsock,
    /// A Unix-socket proxy.
    UnixSocketProxy,
    /// An explicit-exchange shared folder.
    ExchangeSharedFolder,
}

impl VmChannel {
    /// All four channels.
    pub const ALL: [VmChannel; 4] = [
        VmChannel::VirtioVsock,
        VmChannel::GrpcOverVsock,
        VmChannel::UnixSocketProxy,
        VmChannel::ExchangeSharedFolder,
    ];
}

/// Which way a message flows across the boundary.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Direction {
    /// Host → VM (a request the host originates).
    ToVm,
    /// VM → Host (a result the VM produces — always a candidate).
    FromVm,
}

/// The eight Host↔4090 message types (M00223).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum VmMessage {
    /// Host → VM: draft this.
    DraftRequest,
    /// VM → Host: a draft.
    DraftResult,
    /// Host → VM: embed this.
    EmbeddingRequest,
    /// VM → Host: a rerank result.
    RerankResult,
    /// VM → Host: a vision/OCR result.
    VisionResult,
    /// VM → Host: a proposed tool plan.
    ToolPlan,
    /// VM → Host: a risk assessment.
    RiskAssessment,
    /// VM → Host: a proposed patch.
    PatchProposal,
}

impl VmMessage {
    /// All eight message types.
    pub const ALL: [VmMessage; 8] = [
        VmMessage::DraftRequest,
        VmMessage::DraftResult,
        VmMessage::EmbeddingRequest,
        VmMessage::RerankResult,
        VmMessage::VisionResult,
        VmMessage::ToolPlan,
        VmMessage::RiskAssessment,
        VmMessage::PatchProposal,
    ];

    /// Which direction this message flows.
    #[must_use]
    pub fn direction(self) -> Direction {
        match self {
            VmMessage::DraftRequest | VmMessage::EmbeddingRequest => Direction::ToVm,
            VmMessage::DraftResult
            | VmMessage::RerankResult
            | VmMessage::VisionResult
            | VmMessage::ToolPlan
            | VmMessage::RiskAssessment
            | VmMessage::PatchProposal => Direction::FromVm,
        }
    }

    /// The M00224 invariant: every VM **output** (`FromVm`) is a candidate that
    /// must be host-filtered + verified before commit — it is never trusted or
    /// committed directly. Host-originated requests (`ToVm`) are not candidates.
    #[must_use]
    pub fn is_candidate(self) -> bool {
        self.direction() == Direction::FromVm
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn four_channels_eight_messages() {
        assert_eq!(VmChannel::ALL.len(), 4);
        assert_eq!(VmMessage::ALL.len(), 8);
    }

    #[test]
    fn requests_go_to_vm_results_come_from_vm() {
        assert_eq!(VmMessage::DraftRequest.direction(), Direction::ToVm);
        assert_eq!(VmMessage::EmbeddingRequest.direction(), Direction::ToVm);
        assert_eq!(VmMessage::DraftResult.direction(), Direction::FromVm);
        assert_eq!(VmMessage::PatchProposal.direction(), Direction::FromVm);
    }

    #[test]
    fn every_vm_output_is_a_candidate_never_committed_directly() {
        // The M00224 invariant: all FromVm messages are candidates.
        for m in VmMessage::ALL {
            assert_eq!(
                m.is_candidate(),
                m.direction() == Direction::FromVm,
                "{m:?}"
            );
        }
        // The risky outputs in particular must be candidates.
        assert!(VmMessage::PatchProposal.is_candidate());
        assert!(VmMessage::ToolPlan.is_candidate());
        // Host requests are not candidates.
        assert!(!VmMessage::DraftRequest.is_candidate());
    }

    #[test]
    fn serde_kebab() {
        assert_eq!(
            serde_json::to_string(&VmChannel::VirtioVsock).unwrap(),
            "\"virtio-vsock\""
        );
        assert_eq!(
            serde_json::to_string(&VmMessage::PatchProposal).unwrap(),
            "\"patch-proposal\""
        );
        assert_eq!(
            serde_json::to_string(&Direction::FromVm).unwrap(),
            "\"from-vm\""
        );
    }
}
