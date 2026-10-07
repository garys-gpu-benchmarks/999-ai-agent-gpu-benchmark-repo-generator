#!/usr/bin/env python3
"""Finish the safetensors index shard set before sglang.launch_server.

Given a repo id, SGLang can find consolidated.safetensors, skip the shard
download, then fetch model.safetensors.index.json and drop the consolidated
file. The weight list is empty and the server exits. This script downloads
the index and every shard it names, then prints the snapshot directory.
consolidated.safetensors is left in place for vLLM and RAG.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def index_shard_names(index_path: Path) -> list[str]:
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    names: list[str] = []
    for name in (payload.get("weight_map") or {}).values():
        if isinstance(name, str) and name not in names:
            names.append(name)
    return names


def shards_complete(snapshot: Path) -> bool:
    index_path = snapshot / "model.safetensors.index.json"
    if not index_path.is_file() or index_path.stat().st_size <= 0:
        return False
    names = index_shard_names(index_path)
    if not names:
        return False
    for name in names:
        path = snapshot / name
        if not path.is_file() or path.stat().st_size <= 0:
            return False
    return True


def snapshot_dirs(repo_id: str) -> list[Path]:
    hf_home = Path(os.environ.get("HF_HOME") or (Path.home() / ".cache/huggingface"))
    root = hf_home / "hub" / ("models--" + repo_id.replace("/", "--")) / "snapshots"
    if not root.is_dir():
        return []
    return [path for path in root.iterdir() if path.is_dir()]


def ensure_index_shards(repo_id: str) -> Path:
    from huggingface_hub import hf_hub_download

    index_name = "model.safetensors.index.json"
    try:
        hf_hub_download(repo_id, index_name)
    except Exception as exc:
        raise SystemExit(f"[FAIL] {repo_id}: cannot fetch {index_name}: {exc}") from exc
    candidates = snapshot_dirs(repo_id)
    indexed = [path for path in candidates if (path / index_name).is_file() and (path / index_name).stat().st_size > 0]
    if not indexed:
        raise SystemExit(f"[FAIL] {repo_id}: {index_name} is not in the local snapshot")
    snapshot = next((path for path in indexed if shards_complete(path)), indexed[0])
    missing = [
        name
        for name in index_shard_names(snapshot / index_name)
        if not (snapshot / name).is_file() or (snapshot / name).stat().st_size <= 0
    ]
    for name in missing:
        try:
            hf_hub_download(repo_id, name)
        except Exception as exc:
            raise SystemExit(f"[FAIL] {repo_id}: cannot fetch shard {name}: {exc}") from exc
    complete = [path for path in snapshot_dirs(repo_id) if shards_complete(path)]
    if not complete:
        raise SystemExit(f"[FAIL] {repo_id}: index shards are still missing after download")
    return complete[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", default="mistralai/Mistral-7B-v0.3")
    args = parser.parse_args(argv)
    snapshot = ensure_index_shards(args.model_id)
    print(snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
