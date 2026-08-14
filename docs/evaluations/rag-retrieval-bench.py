"""Retrieval benchmark with VERIFIED ground truth, measured stage by stage.

The first version of this benchmark labelled one document per query from its
filename. That was wrong twice over: "how are language models split across the
graphics cards" is answered by the GPU-topology and model-runtime-actuation SDDs
as much as by the inference-backend-stack one, and scoring those as failures
made the retriever look worse than it was.

Ground truth here was checked against document CONTENT (grep for the concepts,
then read the headers), and a query may have several correct answers — because
several documents genuinely answer it. Any of them counts as a hit.

Measures hybrid / dense / fused in one run via the `stage` parameter, so the
three numbers come from one daemon and one corpus and cannot drift apart.
"""

import json
import sys
import urllib.request

PORT = sys.argv[1] if len(sys.argv) > 1 else "8787"
K = 5

# (query, {any of these documents is correct}, is_paraphrase)
CASES = [
    # --- literal: query shares vocabulary with the document ---
    ("how does the ZFS root layout work", {"sdd__017-zfs-root-layout"}, False),
    ("inference backend stack tiers", {"sdd__011-inference-backend-stack"}, False),
    ("cockpit demo mode", {"sdd__116-cockpit-demo-mode"}, False),
    ("inference model provisioning", {"sdd__702-inference-model-provisioning"}, False),
    ("session reaper per session zfs", {"sdd__065-session-reaper-per-session-zfs"}, False),
    ("how do I build the system", {"src__ops__build"}, False),
    ("inference service hardening doctrine",
     {"sdd__036-inference-service-hardening-doctrine"}, False),
    ("cockpit hotswap controls", {"sdd__600-cockpit-hotswap-controls"}, False),
    # --- paraphrase: same meaning, deliberately different words ---
    ("which filesystem holds the operating system datasets",
     {"sdd__017-zfs-root-layout"}, True),
    ("how are language models split across the graphics cards",
     {"sdd__011-inference-backend-stack",
      "sdd__993-sain-gpu-topology",
      "sdd__049-model-runtime-actuation"}, True),
    ("what stops the dashboard showing invented numbers",
     {"sdd__102-cockpit-status-honesty", "sdd__116-cockpit-demo-mode"}, True),
    ("swapping a running model without downtime",
     {"sdd__600-cockpit-hotswap-controls",
      "sdd__702-inference-model-provisioning",
      "sdd__049-model-runtime-actuation"}, True),
    ("locking down the daemons that serve predictions",
     {"sdd__036-inference-service-hardening-doctrine",
      "sdd__024-server-hardening-posture"}, True),
    ("compiling the project from source on a workstation",
     {"src__ops__build"}, True),
]


def search(query, stage, k=K):
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/v1/corpus/search",
        data=json.dumps({"query": query, "k": k, "stage": stage}).encode(),
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())["hits"]


def doc_of(chunk_id):
    return chunk_id.rsplit("#", 1)[0].removesuffix(".md")


def score(stage):
    out = {"lit": [0, 0, 0.0], "para": [0, 0, 0.0]}  # hits, n, mrr_sum
    detail = []
    for query, expected, is_para in CASES:
        docs = [doc_of(h["id"]) for h in search(query, stage)]
        rank = next(
            (i + 1 for i, d in enumerate(docs) if any(d.startswith(e) for e in expected)),
            None,
        )
        bucket = out["para" if is_para else "lit"]
        bucket[1] += 1
        if rank:
            bucket[0] += 1
            bucket[2] += 1.0 / rank
        detail.append((is_para, query, rank))
    return out, detail


def main():
    results = {}
    for stage in ("hybrid", "dense", "fused"):
        results[stage] = score(stage)

    print("%-52s %s" % ("query", "  ".join("%-8s" % s for s in ("hybrid", "dense", "fused"))))
    print("-" * 90)
    for i, (is_para, query, _) in enumerate(results["fused"][1]):
        ranks = []
        for stage in ("hybrid", "dense", "fused"):
            r = results[stage][1][i][2]
            ranks.append("%-8s" % (r if r else "MISS"))
        tag = "P" if is_para else "L"
        print("%s %-50s %s" % (tag, query[:50], "  ".join(ranks)))
    print()
    print("%-10s %-22s %-22s %s" % ("", "literal", "paraphrase", "overall"))
    for stage in ("hybrid", "dense", "fused"):
        o = results[stage][0]
        lit, para = o["lit"], o["para"]
        th, tn = lit[0] + para[0], lit[1] + para[1]
        tm = (lit[2] + para[2]) / tn
        print("%-10s hit@%d %d/%d MRR %.3f   hit@%d %d/%d MRR %.3f   hit@%d %d/%d MRR %.3f" % (
            stage, K, lit[0], lit[1], lit[2] / lit[1],
            K, para[0], para[1], para[2] / para[1],
            K, th, tn, tm))


if __name__ == "__main__":
    main()
