#!/usr/bin/env python3
"""scripts/inference/train/unsloth-lora.py — the GPU-side LoRA/QLoRA trainer the
adapter-train planner (SDD-721) invokes on SAIN-01. This is the real Stage-4
producer: it loads the UNPACKED safetensors base, attaches a LoRA adapter,
fine-tunes on the curated chat dataset, and writes the adapter to `--out`.

Runs on the box (needs CUDA + the model weights + unsloth/trl/peft) — it cannot
run in CI, which is exactly why the rest of the foundry (planner, curator, gate,
transport) is CI-testable and this is the one hardware-gated leaf. The argv is
the contract adapter-train.py emits:

  unsloth-lora.py --base <unpacked> --dataset <chat.jsonl> --method qlora|lora
                  --epochs N --r R --alpha A --lr LR --out <dir> [--load-in-4bit]

TERNARY CAVEAT (enforced): the base MUST be the unpacked FP16 safetensors
(`prism-ml/Ternary-Bonsai-*-unpacked`), never a packed ternary/GGUF — you cannot
LoRA-train a 1.58-bit base. The adapter is served over the ternary GGUF (SDD-715)
after training. This script refuses a `.gguf`/packed base.

Dataset: JSONL chat format from adapter-dataset.py (SDD-722), one example per
line: {"messages": [{"role","content"}, ...]}.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _refuse_packed_base(base: str) -> None:
    low = base.lower()
    if low.endswith(".gguf") or "gguf" in low or "-q2_0" in low or "1.58bit" in low:
        sys.exit(
            f"unsloth-lora: refusing to train on {base!r} — it looks packed/ternary. "
            "Train the FP16 LoRA on the UNPACKED safetensors base "
            "(e.g. prism-ml/Ternary-Bonsai-27B-unpacked); the adapter is served "
            "over the ternary GGUF after training (SDD-715)."
        )


def _load_dataset(path: Path):
    """Load the chat-format JSONL (adapter-dataset.py output) into a HF Dataset
    of {'messages': [...]} rows. Fails loudly on an empty/malformed set."""
    from datasets import Dataset  # noqa: PLC0415 (heavy; import at runtime only)

    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        msgs = rec.get("messages")
        if isinstance(msgs, list) and msgs:
            rows.append({"messages": msgs})
    if not rows:
        sys.exit(f"unsloth-lora: dataset {path} has no usable examples")
    return Dataset.from_list(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", required=True, help="UNPACKED safetensors base (not a ternary GGUF)")
    ap.add_argument("--dataset", required=True, help="chat-format JSONL from adapter-dataset.py")
    ap.add_argument("--method", choices=["qlora", "lora"], default="qlora")
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--r", type=int, default=16)
    ap.add_argument("--alpha", type=int, default=32)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--out", required=True, help="output adapter dir")
    ap.add_argument("--load-in-4bit", action="store_true", help="QLoRA 4-bit base (set by --method qlora)")
    ap.add_argument("--max-seq-len", type=int, default=2048)
    args = ap.parse_args(argv)

    _refuse_packed_base(args.base)
    dataset_path = Path(args.dataset)
    if not dataset_path.is_file():
        sys.exit(f"unsloth-lora: no such dataset: {dataset_path}")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # Heavy imports live here so `--help` and the ternary/dataset guards run
    # without a GPU or the training stack installed.
    from unsloth import FastLanguageModel  # noqa: PLC0415
    from trl import SFTConfig, SFTTrainer  # noqa: PLC0415

    load_in_4bit = args.load_in_4bit or args.method == "qlora"
    print(f"[unsloth-lora] loading base {args.base}  (4bit={load_in_4bit}, seq={args.max_seq_len})")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base,
        max_seq_length=args.max_seq_len,
        load_in_4bit=load_in_4bit,
        dtype=None,  # unsloth picks bf16/fp16 per GPU (Turing → fp16)
    )

    print(f"[unsloth-lora] attaching LoRA  r={args.r} alpha={args.alpha}")
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.r,
        lora_alpha=args.alpha,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        bias="none",
        use_gradient_checkpointing="unsloth",
    )

    dataset = _load_dataset(dataset_path)

    def _format(batch):
        return {"text": [tokenizer.apply_chat_template(m, tokenize=False,
                                                       add_generation_prompt=False)
                         for m in batch["messages"]]}

    dataset = dataset.map(_format, batched=True, remove_columns=["messages"])

    print(f"[unsloth-lora] training {len(dataset)} examples × {args.epochs} epoch(s)  lr={args.lr}")
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=SFTConfig(
            output_dir=str(out / "checkpoints"),
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            warmup_steps=5,
            num_train_epochs=args.epochs,
            learning_rate=args.lr,
            logging_steps=1,
            optim="adamw_8bit",
            seed=42,
            report_to="none",
            dataset_text_field="text",
            max_seq_length=args.max_seq_len,
        ),
    )
    stats = trainer.train()

    print(f"[unsloth-lora] saving adapter → {out}")
    model.save_pretrained(str(out))
    tokenizer.save_pretrained(str(out))
    (out / "train-summary.json").write_text(json.dumps({
        "base": args.base,
        "dataset": str(dataset_path),
        "method": args.method,
        "epochs": args.epochs,
        "r": args.r,
        "alpha": args.alpha,
        "lr": args.lr,
        "examples": len(dataset),
        "train_runtime_s": getattr(stats, "metrics", {}).get("train_runtime"),
        "train_loss": getattr(stats, "metrics", {}).get("train_loss"),
    }, indent=2) + "\n", encoding="utf-8")
    print(f"[unsloth-lora] done. adapter at {out}; "
          f"next: adapter-decide register + adapter-eval + adapter-gate + adapter-transport")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
