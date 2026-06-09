//! `sovereign-branch-tree` — M007 branch primitive.
//!
//! The dump's execution model is built on a **branch** primitive: the
//! runtime forks branches to explore, then commits or prunes them. This
//! crate is that primitive — the tree the rest of the system decorates (the
//! value plane scores a branch, the control word annotates it, the critic
//! prunes it).
//!
//! - [`BranchTree::fork`] spawns a child of an *active* branch (depth + 1).
//! - [`BranchTree::commit`] / [`BranchTree::prune`] settle a branch;
//!   pruning **cascades** to all descendants.
//! - [`BranchTree::lineage`] returns the root→branch path; [`BranchTree::active`]
//!   lists the live frontier.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;

/// Schema version of the branch-tree surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Id of the root branch.
pub const ROOT: u64 = 0;

/// Lifecycle state of a branch.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum BranchState {
    /// Live — may fork, commit, or be pruned.
    Active,
    /// Settled as the chosen path.
    Committed,
    /// Abandoned (also set on descendants of a pruned branch).
    Pruned,
}

/// A node in the branch tree.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Branch {
    /// Branch id.
    pub id: u64,
    /// Parent id (`None` for the root).
    pub parent: Option<u64>,
    /// Lifecycle state.
    pub state: BranchState,
    /// Depth from the root (root = 0).
    pub depth: u32,
}

/// Branch-tree errors.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum BranchError {
    /// Referenced branch id does not exist.
    #[error("unknown branch {0}")]
    Unknown(u64),
    /// Tried to fork/commit a branch that is not active.
    #[error("branch {id} is not active (state {state:?})")]
    NotActive {
        /// The branch.
        id: u64,
        /// Its current state.
        state: BranchState,
    },
}

/// A tree of execution branches rooted at [`ROOT`].
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BranchTree {
    branches: HashMap<u64, Branch>,
    next_id: u64,
}

impl Default for BranchTree {
    fn default() -> Self {
        Self::new()
    }
}

impl BranchTree {
    /// A tree with a single active root branch.
    pub fn new() -> Self {
        let mut branches = HashMap::new();
        branches.insert(
            ROOT,
            Branch {
                id: ROOT,
                parent: None,
                state: BranchState::Active,
                depth: 0,
            },
        );
        Self {
            branches,
            next_id: ROOT + 1,
        }
    }

    /// Fork a new child of an active `parent`; returns the child's id.
    pub fn fork(&mut self, parent: u64) -> Result<u64, BranchError> {
        let p = *self
            .branches
            .get(&parent)
            .ok_or(BranchError::Unknown(parent))?;
        if p.state != BranchState::Active {
            return Err(BranchError::NotActive {
                id: parent,
                state: p.state,
            });
        }
        let id = self.next_id;
        self.next_id += 1;
        self.branches.insert(
            id,
            Branch {
                id,
                parent: Some(parent),
                state: BranchState::Active,
                depth: p.depth + 1,
            },
        );
        Ok(id)
    }

    /// Commit an active branch.
    pub fn commit(&mut self, id: u64) -> Result<(), BranchError> {
        let b = self.branches.get_mut(&id).ok_or(BranchError::Unknown(id))?;
        if b.state != BranchState::Active {
            return Err(BranchError::NotActive { id, state: b.state });
        }
        b.state = BranchState::Committed;
        Ok(())
    }

    /// Prune a branch and all of its descendants. Returns how many branches
    /// were newly marked pruned.
    pub fn prune(&mut self, id: u64) -> Result<usize, BranchError> {
        if !self.branches.contains_key(&id) {
            return Err(BranchError::Unknown(id));
        }
        // Collect the subtree (id + descendants) by repeated child scans.
        let mut subtree = vec![id];
        let mut i = 0;
        while i < subtree.len() {
            let cur = subtree[i];
            for (&bid, b) in &self.branches {
                if b.parent == Some(cur) && !subtree.contains(&bid) {
                    subtree.push(bid);
                }
            }
            i += 1;
        }
        let mut pruned = 0;
        for bid in subtree {
            let b = self.branches.get_mut(&bid).expect("in tree");
            if b.state != BranchState::Pruned {
                b.state = BranchState::Pruned;
                pruned += 1;
            }
        }
        Ok(pruned)
    }

    /// Look up a branch.
    pub fn get(&self, id: u64) -> Option<&Branch> {
        self.branches.get(&id)
    }

    /// Total branches (any state).
    pub fn len(&self) -> usize {
        self.branches.len()
    }

    /// Always false — the tree always has at least the root.
    pub fn is_empty(&self) -> bool {
        self.branches.is_empty()
    }

    /// Ids of all active branches, ascending.
    pub fn active(&self) -> Vec<u64> {
        let mut out: Vec<u64> = self
            .branches
            .values()
            .filter(|b| b.state == BranchState::Active)
            .map(|b| b.id)
            .collect();
        out.sort_unstable();
        out
    }

    /// Root→`id` path of ids, or `None` if `id` is unknown.
    pub fn lineage(&self, id: u64) -> Option<Vec<u64>> {
        let mut chain = Vec::new();
        let mut cur = Some(id);
        while let Some(c) = cur {
            let b = self.branches.get(&c)?;
            chain.push(c);
            cur = b.parent;
        }
        chain.reverse();
        Some(chain)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn root_is_active() {
        let t = BranchTree::new();
        assert_eq!(t.get(ROOT).unwrap().state, BranchState::Active);
        assert_eq!(t.active(), vec![ROOT]);
    }

    #[test]
    fn fork_creates_child_with_depth() {
        let mut t = BranchTree::new();
        let c = t.fork(ROOT).unwrap();
        let b = t.get(c).unwrap();
        assert_eq!(b.parent, Some(ROOT));
        assert_eq!(b.depth, 1);
        let gc = t.fork(c).unwrap();
        assert_eq!(t.get(gc).unwrap().depth, 2);
    }

    #[test]
    fn cannot_fork_non_active() {
        let mut t = BranchTree::new();
        let c = t.fork(ROOT).unwrap();
        t.prune(c).unwrap();
        assert!(matches!(
            t.fork(c).unwrap_err(),
            BranchError::NotActive { .. }
        ));
        assert!(matches!(
            t.fork(999).unwrap_err(),
            BranchError::Unknown(999)
        ));
    }

    #[test]
    fn prune_cascades_to_descendants() {
        let mut t = BranchTree::new();
        let a = t.fork(ROOT).unwrap();
        let b = t.fork(a).unwrap();
        let c = t.fork(b).unwrap();
        let sibling = t.fork(ROOT).unwrap();
        let pruned = t.prune(a).unwrap();
        assert_eq!(pruned, 3); // a, b, c
        for id in [a, b, c] {
            assert_eq!(t.get(id).unwrap().state, BranchState::Pruned);
        }
        // sibling untouched
        assert_eq!(t.get(sibling).unwrap().state, BranchState::Active);
    }

    #[test]
    fn commit_settles_branch() {
        let mut t = BranchTree::new();
        let c = t.fork(ROOT).unwrap();
        t.commit(c).unwrap();
        assert_eq!(t.get(c).unwrap().state, BranchState::Committed);
        // can't commit twice
        assert!(matches!(
            t.commit(c).unwrap_err(),
            BranchError::NotActive { .. }
        ));
    }

    #[test]
    fn active_set_reflects_lifecycle() {
        let mut t = BranchTree::new();
        let a = t.fork(ROOT).unwrap();
        let b = t.fork(ROOT).unwrap();
        t.commit(a).unwrap();
        // root + b active; a committed
        assert_eq!(t.active(), vec![ROOT, b]);
    }

    #[test]
    fn lineage_is_root_to_branch() {
        let mut t = BranchTree::new();
        let a = t.fork(ROOT).unwrap();
        let b = t.fork(a).unwrap();
        assert_eq!(t.lineage(b).unwrap(), vec![ROOT, a, b]);
        assert!(t.lineage(404).is_none());
    }

    #[test]
    fn prune_is_idempotent_count() {
        let mut t = BranchTree::new();
        let a = t.fork(ROOT).unwrap();
        assert_eq!(t.prune(a).unwrap(), 1);
        assert_eq!(t.prune(a).unwrap(), 0); // already pruned
    }

    #[test]
    fn serde_round_trip() {
        let mut t = BranchTree::new();
        t.fork(ROOT).unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: BranchTree = serde_json::from_str(&j).unwrap();
        assert_eq!(back.len(), t.len());
        assert_eq!(back.active(), t.active());
    }
}
