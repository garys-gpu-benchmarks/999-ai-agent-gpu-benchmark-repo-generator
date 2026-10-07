# Raw-output parser contract

Every generated `benchmark_specification.json` must contain:

- `Raw Output Format`: the exact producer and serialization format.
- `Raw Output Example`: a representative captured record or table description.

The extractor adds these fields when the workbook stores the information in `Output Records and Success Criteria (Multirow)`. Workload-specific parsers must still validate that the format names their producer (for example, RCCL or rocHPL) before accepting results.

During generation, before remote validation, run:

```bash
bash scripts/self_check_generated_repo.sh
```

This catches missing parser contracts, canonical shell helpers, and incomplete generated trees before spending time on setup or GPU execution. `self_check_generated_repo.sh` is a generation-time-only script and is stripped from published workload repos by `prepare_github_publish.sh`; a published clone validates results with `scripts/validate_results.py` instead.
# Raw Output Parser Contract

Generated `scripts/parse_results.py` must parse real tool output captured by `run_benchmark.sh`, not only synthetic examples from `benchmark_specification.json`.

## Required Inputs

The parser must read:

- `benchmark_specification.json`
- the `Raw Output Format` field
- the `Raw Output Example` field
- the actual raw output file passed by `--raw-file`

The raw output file is authoritative for observed syntax. If real output differs from the example, update the parser to support the real syntax and preserve the example as an additional fixture shape when useful.

When a benchmark emits a human-readable progress table followed by a final summary score, parse both the progress rows and the final score. Use the final score for the throughput metric and derive elapsed time only from emitted timing fields; never treat an unrecognized but successful summary as an empty run.

## Required Parser Behavior

Generated parsers must:

1. Strip ANSI color/control sequences and NUL bytes before matching text.
2. Preserve the original raw output file unchanged.
3. Prefer structured parsing over brittle single-line assumptions.
4. Parse tables by splitting rows into cells when the tool emits table output.
5. Accept expected success/failure spelling variants such as `PASS`, `FAIL`, `PASSED`, `FAILED`, `OK`, and `ERROR` when the tool uses them.
6. Convert units at parse time and document conversions in code comments.
7. Preserve failed sample rows with `status = 'error'` and `error_message` rather than silently dropping them.
8. Exit with a clear error when no supported output shape is detected.
9. Skip repeated table headers emitted before later sweep blocks. A repeated header row must not become an error sample.

For SGLang serving output, support the human-readable labels `Mean/Median/P95/P99 E2E Latency`, `Mean/Median/P95/P99 TTFT`, and `Mean/Median/P95/P99 TPOT`. `Inter-Token Latency (ITL)` is a separate metric and must not overwrite TPOT columns. Preserve raw output because SGLang may report HTTP 503 while the model and first-use AITER kernels are still warming up.

## Vendor CLI compatibility

Generated runners must probe optional vendor flags against the installed executable rather than assuming that every flag in a matrix example exists in every tool release. An unsupported optional flag must be omitted with a warning, and the effective command must be persisted in the run transcript. For rocblas-bench, parsers must accept both the example `function,precision,...` CSV header and the tool-version variant beginning with `transA,transB` and ending with `rocblas-Gflops,us`.

MIOpenDriver convolution output commonly uses a `stats:` CSV table:

```text
stats: name, n, c, ho, wo, y, x, k, flopCnt, bytesRead, bytesWritten, GFLOPs, GB/s, timeMs
stats: fwd-conv3x3u1, 32, 64, 56, 56, 3, 3, 64, 7398752256, 12918784, 12845056, 88716, 309, 0.083398
```

Generated parsers for this output must strip the `stats:` prefix, map `name` to the solver column, convert `GFLOPs` to TFLOPS using `GFLOPs / 1000`, map `GB/s` to the bandwidth column, and map `timeMs` to kernel time in milliseconds. Headers may repeat for every invocation; rows whose first cell is `name` or `solver` must be skipped.

For standard MIOpenDriver convolution direction flags, `-F 1` means forward convolution and `-F 2` means backward-data convolution. Preserve the direction metadata in each sample and do not label backward-data output as forward merely because the executable name remains `convfp16`.

When a sweep point returns a non-zero exit code, the runner must preserve its output and continue with remaining points. The point must be recorded as skipped or failed in the run artifact rather than causing the entire process to terminate before parsing successful points.

## Availability and partial-run semantics

Missing tool fields must not be represented as measured zeroes. A parser must either derive a metric with a documented formula or persist an explicit availability marker such as `NULL` plus `metric_status = 'unavailable'`. The summary JSON must expose unavailable metrics and skipped sweep points.

Runs with expected unsupported combinations should be reported as `partial` unless configuration explicitly excludes those combinations. A run may be reported `ok` only when every configured point completed and every required metric was measured or derived.

## Correctness/Tolerance Workloads

For tensor or numerical correctness workloads that compare accelerator output against CPU, FP64, or other reference outputs:

1. Use allclose-style semantics: absolute tolerance gates near-zero reference values, while relative tolerance applies to stable non-zero denominators.
2. Avoid relative-error explosions on near-zero references; clamp the relative denominator to a documented floor (for example `max(abs(reference), 1.0)`) or use an equivalent `abs(diff) <= atol + rtol * abs(reference)` compliance check.
3. Keep sample execution observable and bounded. Python workload harnesses should print progress before importing/initializing heavyweight frameworks and before each sample, and should provide a configurable per-sample timeout or clear failure mode for accelerator runtime initialization hangs.
4. Preserve failed tolerance samples with `status = 'error'` and `error_message`, rather than dropping them or converting them to PASS.

## Required Fixture Coverage

Before reporting completion, test the parser with:

- a synthetic/example fixture from `benchmark_specification.json`,
- one captured real output fixture from the target tool when available,
- a failure or non-PASS fixture when the tool exposes one.

For RVS-style outputs, parser fixtures must include:

- summary table rows such as `| action_1 | MEM | PASS |`,
- ANSI-colored result cells such as `\x1b[32mPASS\x1b[0m`,
- failure rows such as `| action_1 | MEM | FAIL |`.

## Output Contract

The parser must write:

- `results/benchmark.db`
- `results/summary.json`
- per-run `samples.csv`
- per-run `samples.json`
- per-run raw exports such as `raw_results.csv` and `raw_results.jsonl`

The database schema and summary metric names must remain consistent with `SPEC.md`, `README.md`, and `docs/run-output-contract.md`.
