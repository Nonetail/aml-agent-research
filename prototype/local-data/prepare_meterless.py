"""Fetch and verify the optional pinned Markovian reference inside generated/."""
from pathlib import Path
import subprocess
from tools import HERE

REVISION='1742dec56a66e58eef9dda2d2b865823758ca8cd'
ROOT=HERE/'generated/meterless-source'
PREFIX='engines/markovian/reference'
if __name__=='__main__':
    ROOT.parent.mkdir(exist_ok=True)
    if not ROOT.exists():
        subprocess.run(['git','clone','--filter=blob:none','--no-checkout','https://github.com/Meterless/Meterless.git',str(ROOT)],check=True)
        subprocess.run(['git','-C',str(ROOT),'checkout',REVISION,'--',PREFIX,'LICENSE'],check=True)
    files=subprocess.check_output(['git','-C',str(ROOT),'ls-tree','-r','--name-only',REVISION,'--',PREFIX,'LICENSE'],text=True).splitlines()
    for name in files:
        expected=subprocess.check_output(['git','-C',str(ROOT),'show',f'{REVISION}:{name}'])
        if (ROOT/name).read_bytes()!=expected:
            raise SystemExit(f'Pinned source mismatch: {name}')
    print(f'Verified {len(files)} files at {REVISION}; source in {ROOT}')
