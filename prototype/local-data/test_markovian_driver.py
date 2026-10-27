"""Offline adapter test using the pinned real engine and a scripted case worker."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
SOURCE=HERE/'generated/meterless-source'

@unittest.skipUnless(shutil.which('node') and SOURCE.exists(),'Optional pinned Meterless checkout and Node are required')
class MarkovianDriverTests(unittest.TestCase):
    def test_engine_session_ceiling_does_not_stop_case(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            shutil.copy2(HERE/'markovian_driver.mjs',root/'markovian_driver.mjs')
            (root/'generated').mkdir();(root/'generated/meterless-source').symlink_to(SOURCE,target_is_directory=True)
            (root/'chunk_case.py').write_text('''import sys,json
from pathlib import Path
action=sys.argv[1];root=Path(sys.argv[2]);root.mkdir(exist_ok=True);f=root/'state.json'
s=json.loads(f.read_text()) if f.exists() else {'status':'active','chunks':0}
if action=='segment':
 s['chunks']+=1
 if s['chunks']==35:s['status']='frontier_exhausted'
if action=='review':s['reviewed']=True
f.write_text(json.dumps(s))
print(json.dumps({'chunk':s['chunks'],'stored_rows':s['chunks'],'pending_scopes':1 if s['status']=='active' else 0,'status':s['status'],'checkpoint':{'summary':'Continue saved case'}}))
''')
            run=root/'run'
            result=subprocess.run(['node','--experimental-transform-types',str(root/'markovian_driver.mjs'),str(run)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            state=json.loads((run/'state.json').read_text())
            self.assertEqual(state['chunks'],35);self.assertTrue(state['reviewed'])
            self.assertEqual(json.loads((run/'meterless-result-1.json').read_text())['status'],'max-chunks')
            self.assertEqual(json.loads((run/'meterless-result-2.json').read_text())['status'],'completed')

if __name__=='__main__':unittest.main()
