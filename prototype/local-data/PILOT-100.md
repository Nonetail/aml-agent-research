# Bounded 100-case development pilot

This pilot runs the existing NVIDIA-backed investigator and verified-path reviewer against the complete 5,078,345-row local database. Each case begins at a different transaction; this is not 100 repetitions of one investigation.

The manifest, seed inventory, evaluator references and Python source snapshot are frozen under `generated/pilot-100-v1/`. Run `python3 pilot.py run` from this directory. Finished cases are retained and skipped on restart; interrupted directories require explicit inspection. There are no automatic retries or prompt changes.

## Scope and limits

- Reporting interval: 4 September through 10 September 2022 inclusive; existing history authorization applies.
- 150 rows per investigator/reviewer working view; 25 rows per branch; model selects 1–4 branches.
- 120 fetched pages and 160 model calls per investigation, including checkpoints and review. No chunk-count cap. Review may remain deferred if navigation consumes the call allowance.
- Two simultaneous cases, each with independent state and database connections.
- Shared 60-million-token accounting ceiling. Before each request, reserve serialized request bytes plus requested output tokens plus 2,048; reconcile reported usage afterward. Missing usage retains the conservative reservation. This is an accounting safeguard, not a provider billing guarantee. Global-budget interruption may leave an open, uncertifiable chunk.
- Expected token use before execution: approximately 30–60 million based on earlier prototype runs. Currency pricing is unverified.

## Sampling and interpretation

Eighty label-free seeds are selected reproducibly with random seed 20261023. Take a reservoir of 300 external transactions per reporting day, rank them by summed incoming/outgoing transaction incidence of their two endpoint identities, and split each day's candidates into three activity bands. Sample four seeds in the first 17 day/band strata and three in the remaining four. Bands describe the sampled candidates, not exact population quantiles; endpoint incidence can double-count transfers. This is a stratified development sample, not an estimate of real-world prevalence.

Twenty separate challenges comprise five unused publisher groups per CYCLE, RANDOM, FAN-IN and FAN-OUT family. Groups must contain 3–20 edges, fit the reporting interval and match source rows unambiguously. Prior golden and reference-sweep groups are excluded. The initial 12-edge proposal yielded too few unused FAN-IN groups; the bound was increased before freezing or making any model calls.

Only the seed enters the runtime. Targets and family metadata stay in evaluator artifacts. Challenge additional-edge retrieval recall excludes the seed. Current greedy path generation does not represent every fan-in/fan-out motif. Neither reference retrieval nor structural verification establishes laundering detection accuracy.

## Smoke gate and reporting

The first ten cases include six ordinary seeds distributed across days and all four challenge families. Continue only when at least eight cases receive a full independent replay certificate and no clean case fails structural replay. Failed/open calls remain explicit uncertifiable execution failures. Preserve the baseline if this gate fails; do not silently retry, change prompts or replace cases.

Report exploration completion separately from review completion, retained rows, pending scopes, review packets, pages, calls, tokens, missing usage, latency, view changes and reference-edge retrieval. All attempted cases, including failures, remain in the reliability denominator. Full replay certifies the supported structural trace, not model summaries or economic interpretations.

Machine-readable case results and aggregate `results.json` are generated from saved artifacts. Frozen source hashes are checked before a run. No credentials are copied into the source snapshot.
