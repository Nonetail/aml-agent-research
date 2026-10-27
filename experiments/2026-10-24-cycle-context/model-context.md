# Family 1 model and context measurements — 2026-10-24

The configured NVIDIA model advertises up to 1M tokens. That is not evidence that
200k tokens is a reliable cycle-detection operating point. Local token measurement
shows that 1,500 transactions fit comfortably under 200k only after compacting the
current raw dictionaries; quality must be measured with live inference.

## Model, endpoint and published limits

`prototype/local-data/model.py` uses `nvidia/nemotron-3.5-lightning-30b-a3b` at
`https://integrate.api.nvidia.com/v1/chat/completions`, temperature 0,
`enable_thinking=False`, and explicit caller-selected `max_tokens`. Its transport
timeout is 90 seconds and response-read limit is 2,000,000 bytes.

The [NVIDIA hosted model card](https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b/modelcard)
identifies the model as the NVFP4 checkpoint and advertises up to 1M tokens. The
[NVIDIA inference API reference](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-5-lightning-30b-a3b-infer)
documents `max_tokens` from 1 to 32,768, default 16,384. This is an **output** limit.
The sources inspected do not separately establish a hard hosted input cap or
guarantee acceptance of a particular long request. A successful live call can
establish acceptance at its measured size; it cannot establish the endpoint's
maximum.

The [official NVFP4 checkpoint](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4)
was pinned at revision `bee7596271d1495f6992ae224aefde4410e816b8`.
Its downloaded `config.json` has `max_position_embeddings=1048576`, while
`tokenizer_config.json` has `model_max_length=262144`. These are different metadata
fields; neither should silently become an empirically verified endpoint limit.
The BF16 card also explains hardware-dependent deployment limits, including a
256K single-H100 recipe and 1M multi-GPU/Blackwell recipes, illustrating why model
capacity and a serving deployment's allocation are distinct.

## Exact local counting and calibration

`tokenizer/` contains only the official public tokenizer/config/template files,
no weights. `tokenizer/provenance.json` records repository, immutable revision,
sizes and SHA-256 hashes. The tokenizer class in metadata is
`PreTrainedTokenizerFast`; Transformers 5.20.2 loads it as `TokenizersBackend`.
The measured runtime is Python 3.12.13, tokenizers 0.23.3 and Jinja2 3.1.6.
`tokenizer-requirements.txt` records the installed dependencies.

`context_tokens.py` exports `ContextTokens`:

```python
counter = ContextTokens()
prompt_tokens = counter.count_request(request)
decision = counter.admission(request, context_cap=200000, safety_tokens=4096)
```

The helper applies the checkpoint's actual chat template to system/user messages,
tool schemas and the generation prefix, with thinking disabled. Like the current
adapter, it removes `uniqueItems` before rendering tools. It counts the rendered
prompt once using the downloaded tokenizer. HTTP JSON escaping, `tool_choice`
transport fields and `max_tokens` are not themselves prompt text in this template.
The output reserve is counted separately. The local exact count is a count of the
public template, not an assertion that provider-side framing is byte-identical.

Read-only calibration against the first six saved successful calls in
`generated/batch-agent-full-500-v1/ledger.sqlite` found provider `prompt_tokens`
exactly **one token below** the local count in all six cases, spanning navigator
and reviewer calls. `historical-token-calibration.json` retains the comparisons.
This supports using the local count conservatively, with explicit safety and
output reserves, and checking each new response's usage for drift. No new hosted
inference was performed for this context-measurement work.

## Measured family 1 request sizes

`measure_context.py` reads only the first 10,000 external source edges by original
row ordinal, within `[2022/09/01 00:00, 2022/09/11 00:00)`. It uses the label-free
`CycleTools` projection and opens the source read-only. This is a reproducible
sizing sample, not a representative customer distribution or a model-quality
benchmark. SHA-256 of the source CSV is
`b19d39f515523373f991b689c07e11e7b0b95c17a2c27a87d91584ae16c5b040`.

Both requests include the current `REVIEWER_SYSTEM`, current assessment function
schema, source hash, time scope, max-edges/duration settings, empty scopes and
empty verified candidates. A short instruction explains evidence-only review.
The raw variant retains the exact current row dictionaries, including repeated
64-character source hashes in transaction IDs and raw-bank fields. The CSV variant
uses existing `chunk_case.compact()` fields, `T<original row ordinal>` IDs and one
shared source hash. Exact bank/account identifiers remain; amounts, currencies,
timestamps and payment format are retained. CSV omits redundant raw-bank spelling
fields; canonical bank/account identity follows the existing importer contract.

The reviewer system alone costs **990 tokens**; navigator system costs **719**.
For these standardized empty requests, complete fixed cost is **1,791 raw-JSON
tokens** or **1,819 CSV tokens**, including tool schema and template. Actual
workflow packets also contain variable coverage, scopes, candidate facts and
previous reviews; count their actual final request instead of assuming this fixed
cost applies to them.

| Rows | Raw dictionaries: prompt | Compact CSV: prompt | CSV + 4,096 output + 4,096 safety |
|---:|---:|---:|---:|
| 500 | 99,366 | 38,785 | 46,977 |
| 1,000 | 197,959 | 76,469 | 84,661 |
| 1,500 | 297,292 | 114,514 | 122,706 |
| 2,000 | 397,152 | 152,815 | 161,007 |
| 3,000 | 597,803 | 229,879 | 238,071 |
| 4,000 | 799,847 | 308,095 | 316,287 |
| 5,000 | 1,002,022 | 386,296 | 394,488 |

The 1,500-row CSV packet adds **112,695 evidence tokens** over its empty request,
about **75.13 tokens per row** in this sample. Raw dictionaries add 295,501 tokens,
about 197.00 per row. Earlier o200k/cl100k results used different tokenizers and
account-alias representations; they cannot substitute for these NVIDIA counts.

Prefix search with the same complete request and 8,192 total reserved tokens gives:

| Total planning cap | Raw dictionary rows | Compact CSV rows |
|---:|---:|---:|
| 120,000 | 563 | 1,463 |
| 200,000 | 968 | 2,510 |
| 262,144 | 1,281 | 3,307 |

At 200k, the CSV fitting prefix has 191,801 prompt tokens; the next row gives
191,875. Adding 8,192 produces 199,993 and 200,067, respectively. Each listed
boundary was checked both at the fitting prefix and its immediately following
prefix. These are sample-specific capacity measurements, not globally valid row
ceilings. Complete candidate support, overlap duplication, longer identifiers,
metadata and output demand all affect the usable size. Grouping and overlap must
be evaluated separately for detection accuracy and charged tokens.

## Existing configuration audit

The saved `batch-agent-full-500-v1` configuration has `row_ceiling=500`,
`context_budget=24000`, `burst_rows=1500`, `burst_pages=100`, and continuous mode.
The older live-500 run has the same row/context/burst limits with eight burst
pages. `batch-agent-live-v1` has `row_ceiling=150`.

The `context_budget` implementation is a UTF-8 request-byte proxy plus reserves,
not a model tokenizer count. `burst_rows=1500` is retrieval work per checkpoint,
not 1,500 rows shown to the model. The family 1 `CycleWorkflow.packet()` instead
sets `max_tokens=4096` and explicitly marks admission `not_evaluated`; its
`candidate_limit` is an assembly limit, not a measured context threshold.

## Reproduce

```sh
uv venv /tmp/aml-nemotron-tokenizer-venv
uv pip install --python /tmp/aml-nemotron-tokenizer-venv/bin/python -r experiments/2026-10-24-cycle-context/tokenizer-requirements.txt
/tmp/aml-nemotron-tokenizer-venv/bin/python experiments/2026-10-24-cycle-context/measure_context.py
```

`context-measurements.json` contains exact counts, checked boundaries, runtime
versions, source identity and a hash of the sampled row-ID sequence. Re-running
the script performs local counting only; it does not load credentials, invoke
the hosted model, or modify existing run ledgers.
