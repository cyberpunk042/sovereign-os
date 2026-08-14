"""Does RAG change the ANSWER, not just the ranking?

The retrieval benchmark measures whether the right passage is returned. That is
necessary and not sufficient: a pipeline can retrieve perfectly and still ground
nothing (it did — the proxy relay forwarded requests verbatim for a whole day
while retrieval improved). This measures the other half.

METHOD
    Each question names facts that appear ONLY in this system's own docs — a ZFS
    pool called `tank`, an OcuLink-to-M.2 adapter, Pulse pinned to CCD 0. A model
    answering from weights alone cannot produce them; it produces a plausible
    generic answer instead, which is exactly the failure mode being measured.

    Score = fraction of required facts present in the answer. Facts are matched
    as case-insensitive regexes, and alternatives within a fact are OR-ed, so
    "ZFS pool tank" and "the tank pool" both count.

    A/B against two gateways that differ ONLY in whether a corpus is loaded, so
    the model, the routing and the prompt path are identical and the corpus is
    the single variable.

WHAT THIS DOES NOT MEASURE
    Whether the answer is well written, complete, or free of other errors. It
    measures grounding: did the system's own knowledge reach the reply. A high
    score with a badly written answer is still a pass here, and correctly so —
    prose quality is a different evaluation.

Usage: python3 rag-answer-grounding-bench.py <rag-on-port> <rag-off-port>
"""

import json
import re
import sys
import urllib.request

# (question, [required facts]) — each fact is a regex; alternatives OR-ed inside.
#
# Facts must be things a model CANNOT plausibly guess. `tank` was in an earlier
# version and is removed: it is the conventional ZFS pool name in every tutorial,
# and the RAG-OFF model produced it unprompted. A fact a guess can satisfy
# measures nothing about grounding.
#
# Assignment questions ("which GPU runs which tier") are scored as ONE ordered
# fact, not two token presences: an answer naming both cards while swapping them
# is wrong, and two independent regexes would score it full marks.
CASES = [
    ("Which ZFS pool holds this system's datasets, and name two of its datasets.",
     [r"tank/(models|context|agents)"]),
    ("How is the RTX 4090 attached to SAIN-01?",
     [r"oculink"]),
    ("Which CPU cores does the Pulse tier run on, and with which engine?",
     [r"ccd\s*0|cores?\s*0[-–]5", r"bitnet"]),
    ("What recordsize is the ZFS dataset holding models tuned to?",
     [r"\b1\s*m\b|1\s*mib|1048576"]),
    ("Which GPU runs the Logic Engine on this machine, and which runs Oracle Core?",
     [r"logic[^.]{0,40}5090"]),
    ("Name the three tiers of the Genesis Trinity in this system.",
     [r"pulse", r"logic", r"oracle"]),
]

# The model is non-deterministic: run to run the same question can answer
# correctly, vaguely, or not at all. One sample per cell is noise, and an earlier
# version of this file reported one.
SAMPLES = 3


def ask(port, question, max_tokens=2000):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps({
            "model": "auto",
            "messages": [{"role": "user", "content": question}],
            "max_tokens": max_tokens,
        }).encode(),
        headers={"content-type": "application/json"},
    )
    parts = []
    with urllib.request.urlopen(req, timeout=240) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data: ") or "[DONE]" in line:
                continue
            try:
                delta = json.loads(line[6:])["choices"][0].get("delta", {})
            except Exception:
                continue
            if delta.get("content"):
                parts.append(delta["content"])
    return "".join(parts).strip()


def score(answer, facts):
    return sum(1 for f in facts if re.search(f, answer, re.I))


def main():
    on_port = sys.argv[1] if len(sys.argv) > 1 else "8793"
    off_port = sys.argv[2] if len(sys.argv) > 2 else "8794"

    tot_on = tot_off = 0.0
    tot_facts = 0
    print("%-52s %-13s %-13s  (mean of %d samples)" % (
        "question", "RAG on", "RAG off", SAMPLES))
    print("-" * 84)
    answers = []
    for q, facts in CASES:
        on_runs = [ask(on_port, q) for _ in range(SAMPLES)]
        off_runs = [ask(off_port, q) for _ in range(SAMPLES)]
        s_on = sum(score(a, facts) for a in on_runs) / SAMPLES
        s_off = sum(score(a, facts) for a in off_runs) / SAMPLES
        tot_on += s_on
        tot_off += s_off
        tot_facts += len(facts)
        print("%-52s %-13s %-13s" % (
            q[:52], f"{s_on:.1f}/{len(facts)}", f"{s_off:.1f}/{len(facts)}"))
        answers.append((q, on_runs[0], off_runs[0]))
    print("-" * 84)
    print("%-52s %-13s %-13s" % (
        "grounded facts recalled", f"{tot_on:.1f}/{tot_facts}", f"{tot_off:.1f}/{tot_facts}"))

    print("\n\nANSWERS\n" + "=" * 80)
    for q, a_on, a_off in answers:
        print(f"\nQ: {q}")
        print(f"  RAG ON : {a_on[:300]}")
        print(f"  RAG OFF: {a_off[:300]}")


if __name__ == "__main__":
    main()
