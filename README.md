# AML Agent Research

Research and disposable prototypes for investigating synthetic transaction graphs with language models, bounded navigation tools, and independently verified evidence.

The current focus is temporal return cycles: finding ordered transactions that form a directed cycle, checking them in code, and measuring model behavior across context sizes and graph groupings. A structural cycle is not proof of money laundering. These experiments do not establish a production detector or population-level accuracy.

## Start here

- [Research overview](research/README.md)
- [Local Python prototype](prototype/local-data/README.md)
- [Cycle rules and tool workflow](prototype/local-data/CYCLE-PROTOTYPE.md)
- [Context, grouping, and model evaluations](experiments/2026-10-24-cycle-context/README.md)
- [Compact transaction matches with confidence](experiments/2026-10-24-cycle-context/COMPACT-CYCLE-DETECTION.md)
- [Dataset source and licensing](data/README.md)

## Local checks

The core Python prototype uses the standard library and SQLite. From the repository root:

```sh
python3 -m unittest discover -s prototype/local-data -p 'test_cycle*.py'
python3 -m unittest discover -s prototype/local-data -p 'test_model.py'
```

Individual experiments may need additional dependencies; see their local documentation and requirements files.

## Data and credentials

Obtain the source data separately using the dataset documentation, then follow the import instructions in the prototype README. Source datasets retain their publisher's license.

Hosted NVIDIA calls read `NVIDIA_API_KEY` from the environment or a local ignored `prototype/local-data/.private/nvidia-key` file. Supply your own credential securely; never commit it. Live evaluation scripts can incur provider charges.

This public repository includes source code, tests, research notes, and summary reports. Raw transaction datasets, local databases, credentials, downloaded tokenizer assets, model input packets, raw model responses, and local handoff notes are excluded. Some historical report links refer to excluded local artifacts; reproducing those reports requires regenerating their inputs. Saved reports describe their original runs and do not imply that raw evidence is distributed here.
