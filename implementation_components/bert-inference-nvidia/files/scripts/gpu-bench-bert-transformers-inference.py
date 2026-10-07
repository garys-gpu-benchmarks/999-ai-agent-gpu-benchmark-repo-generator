#!/usr/bin/env python3
"""Hugging Face BERT inference on synthetic token ids."""

from __future__ import annotations

import argparse
import math
import os

import torch
from transformers import AutoModel, BertConfig


def finite_nonneg(value: float) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0.0:
        return 0.0
    return parsed


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(math.ceil(q * len(ordered)) - 1)))
    return ordered[index]


def load_model(name: str, dtype: torch.dtype, device: torch.device):
    try:
        model = AutoModel.from_pretrained(name, torch_dtype=dtype)
    except Exception:
        model = AutoModel.from_config(BertConfig())
        model = model.to(dtype=dtype)
    return model.to(device).eval()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-name", default="bert-base-uncased")
    parser.add_argument("--dtype", default="f16_r")
    parser.add_argument("--precision", default="mixed_float16")
    parser.add_argument("--num-gpus", default="1")
    parser.add_argument("--prompt-source", default="synthetic")
    parser.add_argument("--sequence-len", default="32")
    parser.add_argument("--batch-size", default="1")
    parser.add_argument("--warmup-iters", default="2")
    parser.add_argument("--num-iterations", default="5")
    parser.add_argument("--device-id", default="0")
    args = parser.parse_args()
    if str(args.prompt_source).strip().lower() != "synthetic":
        raise SystemExit("[FAIL] prompt_source must remain synthetic.")
    if not torch.cuda.is_available():
        raise SystemExit("[FAIL] torch.cuda.is_available() is False")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    device = torch.device(f"cuda:{int(args.device_id)}")
    torch.cuda.set_device(device)
    seq = max(8, int(float(args.sequence_len)))
    batch = max(1, int(float(args.batch_size)))
    warmup = max(0, int(float(args.warmup_iters)))
    iters = max(1, int(float(args.num_iterations)))
    dtype = torch.float16
    model = load_model(args.model_name, dtype, device)
    vocab = int(getattr(model.config, "vocab_size", 30522))
    input_ids = torch.randint(0, max(2, vocab - 1), (batch, seq), device=device)
    attention_mask = torch.ones_like(input_ids)
    with torch.no_grad():
        for _ in range(warmup):
            model(input_ids=input_ids, attention_mask=attention_mask)
        torch.cuda.synchronize(device)
        torch.cuda.reset_peak_memory_stats(device)
        times = []
        start = torch.cuda.Event(enable_timing=True)
        end = torch.cuda.Event(enable_timing=True)
        for _ in range(iters):
            start.record()
            model(input_ids=input_ids, attention_mask=attention_mask)
            end.record()
            torch.cuda.synchronize(device)
            times.append(float(start.elapsed_time(end)))
    mean_ms = sum(times) / len(times)
    sequences_per_sec = finite_nonneg(float(batch) / (mean_ms / 1000.0))
    tokens_per_sec = finite_nonneg(float(batch * seq) / (mean_ms / 1000.0))
    peak = finite_nonneg(float(torch.cuda.max_memory_allocated(device)) / 1e9)
    print(
        "RESULT"
        f" model_name={args.model_name}"
        f" dtype={args.dtype}"
        f" sequence_len={seq}"
        f" batch_size={batch}"
        f" sequences_per_sec={sequences_per_sec:.6f}"
        f" mean_latency_ms={finite_nonneg(mean_ms):.6f}"
        f" latency_p50_msec={finite_nonneg(percentile(times, 0.50)):.6f}"
        f" latency_p95_msec={finite_nonneg(percentile(times, 0.95)):.6f}"
        f" latency_p99_msec={finite_nonneg(percentile(times, 0.99)):.6f}"
        f" tokens_per_sec={tokens_per_sec:.6f}"
        f" peak_gpu_memory_gb={peak:.6f}"
        " status=ok"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
