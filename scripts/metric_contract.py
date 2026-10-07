#!/usr/bin/env python3
# File: scripts/metric_contract.py
# Description: Shared blank / zero / positive metric rules and percentile-key helpers.
from __future__ import annotations

import re

NOT_MEASURED = ""
MASHED_PERCENTILE_RE = re.compile(r"^(?P<stem>.+)_p50_p95_p99(?P<suffix>_[A-Za-z0-9]+)?$")


def is_blank(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text.lower() in {"none", "null", "nan", "not measured", "not_measured"}


def coerce_metric_value(value: object, *, zero_ok: bool = False) -> object:
    """Blank is omitted. Do not coerce empty string to 0.0."""
    if is_blank(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return NOT_MEASURED
    if number != number or number in (float("inf"), float("-inf")):
        return NOT_MEASURED
    if number == 0.0 and not zero_ok:
        # A recorded 0 is still a number; callers decide whether 0 is valid.
        return number
    return number


def unmash_p50_key(key: str) -> str:
    """D2: a mashed p50_p95_p99 display key is the p50 key."""
    match = MASHED_PERCENTILE_RE.match(str(key or ""))
    if not match:
        return str(key or "")
    return f"{match.group('stem')}_p50{match.group('suffix') or ''}"


def split_percentile_keys(key: str) -> list[str]:
    """D3: expand mashed p50_p95_p99 into the three real keys."""
    match = MASHED_PERCENTILE_RE.match(str(key or ""))
    if not match:
        return [str(key or "")]
    stem = match.group("stem")
    suffix = match.group("suffix") or ""
    return [f"{stem}_p50{suffix}", f"{stem}_p95{suffix}", f"{stem}_p99{suffix}"]


def percentile_triplet(values: list, pct_fn) -> dict[str, object]:
    """Return p50/p95/p99 for a value list. Blanks stay blank."""
    cleaned = [item for item in values if not is_blank(item)]
    return {
        "p50": pct_fn(cleaned, 0.50) if cleaned else "",
        "p95": pct_fn(cleaned, 0.95) if cleaned else "",
        "p99": pct_fn(cleaned, 0.99) if cleaned else "",
    }


def emit_percentile_metrics(stem: str, suffix: str, values: list, pct_fn) -> dict[str, object]:
    """Emit the split p50, p95, and p99 keys. The mashed alias is not published."""
    triplet = percentile_triplet(values, pct_fn)
    return {
        f"{stem}_p50{suffix}": triplet["p50"],
        f"{stem}_p95{suffix}": triplet["p95"],
        f"{stem}_p99{suffix}": triplet["p99"],
    }


def itl_must_not_copy_tpot(itl_value: object, tpot_value: object) -> object:
    """D4: ITL is blank when it was not measured. Never copy TPOT."""
    if is_blank(itl_value):
        return ""
    if not is_blank(tpot_value) and str(itl_value) == str(tpot_value):
        return ""
    return itl_value


ITL_TPOT_PAIRS_MSEC = (
    ("inter_token_latency_itl_p50_msec", "time_per_output_token_tpot_p50_msec"),
    ("inter_token_latency_itl_p95_msec", "time_per_output_token_tpot_p95_msec"),
    ("inter_token_latency_itl_p99_msec", "time_per_output_token_tpot_p99_msec"),
)


def apply_itl_contract(metrics: dict, pairs: tuple[tuple[str, str], ...] = ITL_TPOT_PAIRS_MSEC) -> dict:
    """Blank every ITL column that repeats the paired TPOT column."""
    for itl_key, tpot_key in pairs:
        if itl_key in metrics:
            metrics[itl_key] = itl_must_not_copy_tpot(metrics.get(itl_key, ""), metrics.get(tpot_key, ""))
    return metrics
