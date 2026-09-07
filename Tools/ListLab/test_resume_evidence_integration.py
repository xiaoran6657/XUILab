"""Optional real-child orchestration test using a verified historical core bundle.

Children COPY historical fixture bytes; they do not measure or run Unity.
Set XUILAB_TEST_EVIDENCE_BUNDLE to enable during unittest discovery, or use CLI.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from evidence_bundle import audit, check_integrity, sha
import resume_list_plan as resume


def exercise(bundle_path, expected_index=None):
    bundle_path=Path(bundle_path).absolute()
    report=audit(bundle_path,expected_index)
    index,_=check_integrity(bundle_path,expected_index)
    catalog=index['catalog']; original=bundle_path/catalog['artifactRoot']
    manifest_source=original/catalog['plans']['pilot']
    spawned=[]
    with tempfile.TemporaryDirectory(prefix='xuilab-resume-copy-fixture-') as temp:
        work=Path(temp).resolve(); manifest=work/manifest_source.name
        shutil.copyfile(manifest_source,manifest)
        frozen=sha(manifest); python=Path(sys.executable).resolve()
        hashes=work/'copy-fixture-build-hashes.json'
        hashes.write_text(json.dumps({str(python):sha(python)}),encoding='utf-8')
        copier='import pathlib,shutil,sys; shutil.copytree(pathlib.Path(sys.argv[1])/sys.argv[3],pathlib.Path(sys.argv[2])/sys.argv[3])'
        def start(command):
            run_id=command[command.index('--xuilab-run-id')+1]
            child=subprocess.Popen([str(python),'-B','-c',copier,str(original),str(work),run_id],
                                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            spawned.append(child)
            return child
        with mock.patch.object(resume,'_start_player',side_effect=start):
            first=resume.execute_plan(work,manifest,python,recorded_root=catalog['recordedRoot'],build_hashes_path=hashes)
            second=resume.execute_plan(work,manifest,python,recorded_root=catalog['recordedRoot'],build_hashes_path=hashes)
        if first['counts'] != {'completed':4} or second['counts'] != {'completed':4} or len(spawned)!=4:
            raise AssertionError('four completed copies must not be launched again')
        if frozen != sha(manifest) or any(p.poll()!=0 for p in spawned):
            raise AssertionError('manifest changed or child did not finish successfully')
        for row in first['runs']:
            for source in (original/row['runId']).iterdir():
                if sha(source)!=sha(work/row['runId']/source.name):
                    raise AssertionError('historical bytes changed')
        return {'fixtureOnly':True,'unityPlayer':'not_run','childKind':'Python historical-artifact copier',
                'realChildren':len(spawned),'secondResumeChildren':0,'completed':4,
                'strictRawValidation':True,'manifestUnchanged':True,'indexSha256':report['indexSha256']}


class HistoricalCopyIntegration(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('XUILAB_TEST_EVIDENCE_BUNDLE'),'optional historical evidence bundle not provided')
    def test_real_children_copy_validate_and_do_not_repeat(self):
        self.assertEqual(4,exercise(os.environ['XUILAB_TEST_EVIDENCE_BUNDLE'])['completed'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--expected-index-sha256')
    args=parser.parse_args()
    print(json.dumps(exercise(args.bundle,args.expected_index_sha256),indent=2))
