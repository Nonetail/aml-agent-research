"""Check full-row duplicates without emitting or choosing individual cases."""
from pathlib import Path
from collections import Counter
from itertools import groupby
import argparse
import hashlib
import json
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--data-dir", type=Path, default=ROOT.parents[1] / "data")
DATA = parser.parse_args().data_dir
source = DATA / "HI-Small_Trans.csv"
with tempfile.TemporaryDirectory(prefix="aml-duplicate-audit-") as tmp:
    unsorted = Path(tmp) / "digests"
    ordered = Path(tmp) / "sorted"
    with source.open("rb") as inp, unsorted.open("wb") as out:
        next(inp)
        for raw in inp:
            out.write(hashlib.blake2b(raw.rstrip(b"\r\n"), digest_size=16).hexdigest().encode() + b"\n")
    subprocess.run(["sort", "-o", str(ordered), str(unsorted)], env={**os.environ, "LC_ALL": "C"}, check=True)
    repeated = {}
    with ordered.open() as inp:
        for digest, lines in groupby(inp):
            n = sum(1 for _ in lines)
            if n > 1:
                repeated[digest.strip()] = n
    exact = Counter()
    if repeated:
        with source.open("rb") as inp:
            next(inp)
            for raw in inp:
                row = raw.rstrip(b"\r\n")
                if hashlib.blake2b(row, digest_size=16).hexdigest() in repeated:
                    exact[row] += 1
    result = {
        "method": "128-bit BLAKE2b full-row digests grouped by external sort; matches verified against raw full rows",
        "duplicate_full_row_groups": len(repeated),
        "duplicate_extra_rows": sum(n - 1 for n in repeated.values()),
        "multiplicity_histogram": dict(Counter(repeated.values())),
        "verified_full_row_groups": sum(n > 1 for n in exact.values()),
        "verified_duplicate_extra_rows": sum(n - 1 for n in exact.values() if n > 1),
        "digest_collisions_detected": len(exact) - len(repeated),
    }
(ROOT / "duplicate-profile.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
