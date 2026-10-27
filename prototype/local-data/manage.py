"""Remove disposable output or create a small source-only handover ZIP."""
import argparse
from pathlib import Path
import shutil
import zipfile

HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('action', choices=['clean','pack','forget-key'])
args=p.parse_args()
if args.action=='clean':
    for name in ('generated','__pycache__'):
        target=HERE/name
        if target.is_symlink():
            target.unlink()
        elif target.exists():
            shutil.rmtree(target)
    print('Removed local generated databases, receipts, verification output, bundle and bytecode. Source/data untouched.')
elif args.action=='forget-key':
    target=HERE/'.private'
    if target.is_symlink(): target.unlink()
    elif target.exists(): shutil.rmtree(target)
    print('Removed local credential folder only.')
else:
    output=HERE/'generated'
    output.mkdir(exist_ok=True)
    target=output/'local-data-prototype.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(HERE.iterdir()):
            if path.is_file() and (path.suffix in ('.py','.md','.json','.mjs') or path.name=='.gitignore'):
                archive.write(path,Path('local-data-prototype')/path.name)
    print(target)
