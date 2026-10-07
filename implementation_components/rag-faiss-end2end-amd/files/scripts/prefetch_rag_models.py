#!/usr/bin/env python3
"""Download public RAG assets; reuse a local Mistral-7B-v0.3 snapshot when it is complete.

consolidated.safetensors is not a Transformers checkpoint. When the cache has
only that file, download model.safetensors.index.json and every shard it names.
Leave consolidated.safetensors on disk for vLLM. tokenizer.model.v3 does not
count; fetch tokenizer.json and tokenizer.model before skipping the repo.
"""

from __future__ import annotations

import json

from huggingface_hub import hf_hub_download, snapshot_download

from rag_model_paths import find_local_causal_lm, snapshot_dirs

MISTRAL_REPO = "mistralai/Mistral-7B-v0.3"
TOKENIZER_FILES = (
    "tokenizer.json",
    "tokenizer.model",
    "tokenizer_config.json",
    "special_tokens_map.json",
)
HF_WEIGHT_INDEX = "model.safetensors.index.json"


def _entry_not_found():
    try:
        from huggingface_hub.utils import EntryNotFoundError
    except ImportError:
        return ()
    return EntryNotFoundError


def _download_tokenizer_files(repo_id: str) -> None:
    missing = _entry_not_found()
    for name in TOKENIZER_FILES:
        try:
            hf_hub_download(repo_id, name)
        except missing:
            continue


def _shard_names(index_path) -> list[str]:
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    names: list[str] = []
    for name in (payload.get("weight_map") or {}).values():
        if isinstance(name, str) and name not in names:
            names.append(name)
    return names


def _download_hf_causal_weights(repo_id: str) -> None:
    """Fetch the Hugging Face weight files. Do not rename consolidated.safetensors."""
    missing = _entry_not_found()
    try:
        hf_hub_download(repo_id, HF_WEIGHT_INDEX)
    except missing:
        hf_hub_download(repo_id, "model.safetensors")
        return
    indexes = []
    for snapshot in snapshot_dirs(repo_id):
        index_path = snapshot / HF_WEIGHT_INDEX
        if index_path.is_file() and index_path.stat().st_size > 0:
            indexes.append(index_path)
    if not indexes:
        raise RuntimeError(f"{repo_id}: {HF_WEIGHT_INDEX} is not in the local snapshot")
    for name in _shard_names(indexes[0]):
        hf_hub_download(repo_id, name)


def ensure_mistral(repo_id: str = MISTRAL_REPO):
    found = find_local_causal_lm(repo_id)
    if found is not None:
        return found
    _download_tokenizer_files(repo_id)
    _download_hf_causal_weights(repo_id)
    found = find_local_causal_lm(repo_id)
    if found is not None:
        return found
    snapshot_download(repo_id)
    return find_local_causal_lm(repo_id) or repo_id


def main() -> int:
    mistral = ensure_mistral(MISTRAL_REPO)
    snapshot_download("BAAI/bge-small-en-v1.5")
    snapshot_download("BAAI/bge-reranker-base")
    from datasets import load_dataset

    dataset = load_dataset("rajpurkar/squad_v2", split="validation")
    print(f"prefetch ok mistral={mistral} embed=bge-small rerank=bge-reranker squad={len(dataset)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
