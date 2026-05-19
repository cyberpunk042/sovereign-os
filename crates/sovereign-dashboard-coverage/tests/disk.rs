//! Integration test that runs verify_on_disk against the actual repo.

use sovereign_dashboard_coverage::CoverageManifest;
use std::path::Path;

#[test]
fn canonical_manifest_verifies_against_real_repo_tree() {
    // Walk up from this crate's manifest dir to the workspace root,
    // then run verify_on_disk against it.
    let here = Path::new(env!("CARGO_MANIFEST_DIR"));
    let repo_root = here.parent().unwrap().parent().unwrap();
    let m = CoverageManifest::canonical();
    m.verify_on_disk(repo_root).unwrap_or_else(|e| {
        panic!("real-repo coverage gap: {e}");
    });
}
