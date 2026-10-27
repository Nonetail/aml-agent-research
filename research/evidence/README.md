# Evidence and reproduction

Research snapshot: 23 October 2026. These files preserve publisher metadata, locally measured aggregate results and targeted framework probes. They do not contain detection-performance results.

## Data evidence

| Artifact | Meaning |
|---|---|
| [download-manifest.json](download-manifest.json) | Download URLs, publisher version, sizes and SHA-256 hashes; package paths are relative to the package root |
| [hi-small-profile.json](hi-small-profile.json) | Full transaction profile without label-value aggregates |
| [evaluator-hi-small-profile.json](evaluator-hi-small-profile.json) | Full profile including label aggregates and publisher primary/tail activity periods; evaluator material |
| [accounts-profile.json](accounts-profile.json) | Metadata key, entity and completeness counts |
| [patterns-profile.json](patterns-profile.json) | Publisher pattern types/counts/date range; evaluator material |
| [join-validation.json](join-validation.json) | Prefix and pattern-account join checks, pattern start/end histograms; evaluator material |
| [duplicate-profile.json](duplicate-profile.json) | Full-file repeated-row audit, confirmed against exact row bytes |
| [kaggle-view.json](kaggle-view.json), [kaggle-list.json](kaggle-list.json), [kaggle-description.md](kaggle-description.md) | Publisher metadata/description snapshots; descriptions can be inconsistent with measured files |
| [HI-Small_Trans-prefix.csv](HI-Small_Trans-prefix.csv) | Initial complete records from the source download, including labels; evaluator material |

The full transaction profile checks all active account joins and all publisher pattern-row matches. The prefix-only and pattern-only join checks have narrower scope. No date partition is designated as development or test in this package. Primary/tail dates describe the publisher's dataset generation window, not an evaluation split.

Run from the package root with Python 3:

```sh
python3 research/evidence/profile_hi_small.py
python3 research/evidence/audit_duplicates.py
```

Both scripts resolve the bundled `data/` directory relative to their own location and accept `--data-dir` for an alternative location. The profiler verifies the transaction file hash and recreates the two transaction profiles. If the transaction file is absent it attempts to download that file; account and pattern files must already exist. The duplicate auditor uses the system `sort` command and temporary disk space, then deletes its temporary files. It recreates the duplicate profile. These two scripts do not regenerate the separately recorded account/pattern/prefix profiles or publisher metadata snapshots.

## Framework evidence

[engine-probe.mjs](engine-probe.mjs) exercises source version `1742dec56a66e58eef9dda2d2b865823758ca8cd` of [Meterless](https://github.com/Meterless/Meterless/tree/1742dec56a66e58eef9dda2d2b865823758ca8cd), using mock responses and independent toy fixtures. [engine-probe-results.json](engine-probe-results.json) records the resulting observations. The upstream checkout is not bundled.

With an unmodified checkout at that revision, run from the package root:

```sh
node --experimental-transform-types --disable-warning=ExperimentalWarning research/evidence/engine-probe.mjs /absolute/path/to/pinned/Meterless
```

The recorded runtime was Node v24.16.0. The probe creates a temporary history directory, makes no model-provider calls, and checks a small set of behaviors rather than the full conformance suite. See the [framework report](../agent-frameworks.md) for interpretations and implementation-source links.
