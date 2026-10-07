#!/usr/bin/env python3
"""Resolve a usable local Hugging Face snapshot without requiring every repo file."""

from __future__ import annotations

import json
import os
from pathlib import Path


def hub_root() -> Path:
    hf_home = Path(os.environ.get("HF_HOME") or (Path.home() / ".cache/huggingface"))
    return hf_home / "hub"


def snapshot_dirs(repo_id: str) -> list[Path]:
    name = "models--" + repo_id.replace("/", "--")
    root = hub_root() / name / "snapshots"
    if not root.is_dir():
        return []
    return [path for path in root.iterdir() if path.is_dir()]


def _nonempty_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _index_shard_names(index_path: Path) -> list[str]:
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    names: list[str] = []
    for name in (payload.get("weight_map") or {}).values():
        if isinstance(name, str) and name not in names:
            names.append(name)
    return names


def has_causal_lm_weights(snapshot: Path) -> bool:
    """True only for a Transformers checkpoint.

    consolidated.safetensors is not a Transformers checkpoint. It is Mistral's
    original layout. A symlink named model.safetensors still leaves every
    Hugging Face key missing.
    """
    if not _nonempty_file(snapshot / "config.json"):
        return False
    index_path = snapshot / "model.safetensors.index.json"
    if _nonempty_file(index_path):
        names = _index_shard_names(index_path)
        return bool(names) and all(_nonempty_file(snapshot / name) for name in names)
    return any(_nonempty_file(snapshot / name) for name in ("model.safetensors", "pytorch_model.bin"))


def has_usable_tokenizer(snapshot: Path) -> bool:
    """Accept tokenizer.json or tokenizer.model. tokenizer.model.v3 does not count."""
    for name in ("tokenizer.json", "tokenizer.model"):
        path = snapshot / name
        if _nonempty_file(path):
            return True
    return False


def find_weight_snapshot(repo_id: str) -> Path | None:
    for snapshot in snapshot_dirs(repo_id):
        if has_causal_lm_weights(snapshot):
            return snapshot
    return None


def find_local_causal_lm(repo_id: str) -> Path | None:
    for snapshot in snapshot_dirs(repo_id):
        if has_causal_lm_weights(snapshot) and has_usable_tokenizer(snapshot):
            return snapshot
    return None


def reject_missing_causal_weights(loading_info: dict) -> None:
    """Stop when Transformers initialized causal-LM weights instead of loading them.

    Tied lm_head.weight may be absent from the checkpoint. Every other missing
    key means the file was not a Hugging Face Mistral checkpoint.
    """
    missing = [key for key in (loading_info.get("missing_keys") or []) if key != "lm_head.weight"]
    if not missing:
        return
    preview = ", ".join(missing[:8])
    raise SystemExit(
        f"[FAIL] Mistral load left {len(missing)} weights missing ({preview}). "
        "consolidated.safetensors is not a Transformers checkpoint."
    )


def require_local_causal_lm(repo_id: str) -> Path:
    snapshot = find_local_causal_lm(repo_id)
    if snapshot is None:
        raise FileNotFoundError(
            f"Cached Hugging Face weights for {repo_id} were not found under {hub_root()}. "
            "Prefetch model.safetensors or the model-*-of-*.safetensors shards. "
            "Do not require consolidated.safetensors."
        )
    return snapshot
