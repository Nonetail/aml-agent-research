"""Download the public v8 CSV in resumable, verified HTTP ranges."""
import concurrent.futures
import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parents[1] / 'data'
URL = 'https://www.kaggle.com/api/v1/datasets/download/ealtman2019/ibm-transactions-for-anti-money-laundering-aml/HI-Large_Trans.csv'
SIZE = 17052760651
CHUNK = 32 * 1024 * 1024
PATH = DATA / 'HI-Large_Trans.csv'
PARTIAL = PATH.with_suffix('.csv.partial')
STATE = ROOT / 'hi-large-download-progress.json'
MANIFEST = ROOT / 'hi-large-download-manifest.json'

if PATH.exists():
    assert PATH.stat().st_size == SIZE
    print('Complete CSV already exists.', flush=True)
    raise SystemExit

DATA.mkdir(parents=True, exist_ok=True)
request = urllib.request.Request(URL, headers={'Range': 'bytes=0-0'})
with urllib.request.urlopen(request, timeout=60) as response:
    assert response.status == 206
    assert response.headers['Content-Range'] == f'bytes 0-0/{SIZE}'
    signed_url = response.url
    response.read()

completed = set(json.loads(STATE.read_text())['completed_chunks']) if STATE.exists() else set()
if completed:
    assert PARTIAL.exists() and PARTIAL.stat().st_size == SIZE
fd = os.open(PARTIAL, os.O_RDWR | os.O_CREAT, 0o644)
os.ftruncate(fd, SIZE)
started = time.monotonic()

def fetch(chunk):
    start = chunk * CHUNK
    end = min(SIZE, start + CHUNK) - 1
    for attempt in range(4):
        try:
            request = urllib.request.Request(signed_url, headers={'Range': f'bytes={start}-{end}'})
            with urllib.request.urlopen(request, timeout=90) as response:
                assert response.status == 206
                assert response.headers['Content-Range'] == f'bytes {start}-{end}/{SIZE}'
                offset = start
                while block := response.read(1024 * 1024):
                    assert offset + len(block) <= end + 1
                    assert os.pwrite(fd, block, offset) == len(block)
                    offset += len(block)
                assert offset == end + 1
            return chunk
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))

chunks = (SIZE + CHUNK - 1) // CHUNK
last_report = 0
try:
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(fetch, c) for c in range(chunks) if c not in completed]
        for future in concurrent.futures.as_completed(futures):
            completed.add(future.result())
            state = {'url': URL, 'bytes': SIZE, 'chunk_bytes': CHUNK, 'completed_chunks': sorted(completed)}
            temporary = STATE.with_suffix('.tmp')
            temporary.write_text(json.dumps(state) + '\n')
            temporary.replace(STATE)
            now = time.monotonic()
            if now - last_report >= 10 or len(completed) == chunks:
                print(f'Downloaded {len(completed)}/{chunks} ranges; elapsed {now-started:.1f}s', flush=True)
                last_report = now
    assert len(completed) == chunks
    os.fsync(fd)
finally:
    os.close(fd)

digest = hashlib.sha256()
with PARTIAL.open('rb') as source:
    assert source.readline().startswith(b'Timestamp,From Bank,Account,To Bank,Account,')
    source.seek(0)
    while block := source.read(8 * 1024 * 1024):
        digest.update(block)
PARTIAL.rename(PATH)
manifest = {'source_url': URL, 'publisher_version': 8, 'filename': PATH.name,
            'bytes': SIZE, 'sha256': digest.hexdigest(), 'download_seconds': round(time.monotonic()-started, 3),
            'range_count': chunks, 'validation': 'Every byte range returned expected Content-Range and byte count; complete CSV header checked.'}
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, indent=2), flush=True)
