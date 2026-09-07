"""Boundary and relocation regressions using temporary files, never a Player."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import evidence_bundle as bundle
from analyze_list_evidence import comparison, generate
from test_verify_list_runs import ListVerifierFixture
from verify_list_runs import _validate_run, VerificationError


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name); self.repo=self.base/'repo'; self.repo.mkdir()
        self.out=self.base/'bundle'
        for name,data in [('data/plan.json',b'{}'),('data/raw.txt',b'raw evidence'),('build/test.exe',b'not executable')]:
            p=self.repo/name; p.parent.mkdir(exist_ok=True); p.write_bytes(data)
        snapshot=self.repo/'snapshot.sha256'
        snapshot.write_text(''.join(bundle.sha(self.repo/n)+'  '+n+'\n' for n in ('data/plan.json','data/raw.txt','build/test.exe')),encoding='utf-8')
        self.catalog=dict(schemaVersion='xuilab.evidence.catalog/v1',evidenceId='test',candidateId='test',buildId='test',sourceRevision='test',recordedRoot='G:/old/data',artifactRoot='data',buildRoot='build',player='build/test.exe',plans={'pilot':'plan.json'},scope='test fixture only',snapshots=[dict(path='snapshot.sha256',sha256=bundle.sha(snapshot),prefixes=['data','build'])])
        self.cat=self.repo/'catalog.json'; bundle.write_new(self.cat,self.catalog)

    def pack(self): return bundle.pack(self.repo,self.cat,self.out)

    def rewrite_index(self, mutator):
        p=self.out/'bundle.json'; value=json.loads(p.read_text()); mutator(value)
        p.write_text(json.dumps(value),encoding='utf-8')

    def test_relocated_package_keeps_exact_bytes(self):
        result=self.pack(); moved=self.base/'elsewhere'; shutil.copytree(self.out,moved)
        index,digest=bundle.check_integrity(moved,result['indexSha256'])
        self.assertEqual(4,len(index['files'])); self.assertEqual(result['indexSha256'],digest)
        self.assertEqual((self.repo/'data/raw.txt').read_bytes(),(moved/'data/raw.txt').read_bytes())

    def test_tampered_file_rejected(self):
        self.pack(); (self.out/'data/raw.txt').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'mismatch'): bundle.check_integrity(self.out)

    def test_missing_file_rejected(self):
        self.pack(); (self.out/'data/raw.txt').unlink()
        with self.assertRaisesRegex(ValueError,'mismatch'): bundle.check_integrity(self.out)

    def test_extra_file_rejected(self):
        self.pack(); (self.out/'extra').write_bytes(b'new')
        with self.assertRaisesRegex(ValueError,'unindexed'): bundle.check_integrity(self.out)

    def test_index_cannot_drop_snapshot_member(self):
        self.pack(); (self.out/'data/raw.txt').unlink()
        self.rewrite_index(lambda i:i['files'].__setitem__(slice(None),[f for f in i['files'] if f['path']!='data/raw.txt']))
        with self.assertRaisesRegex(ValueError,'selection'): bundle.check_integrity(self.out)

    def test_index_pin_detects_changed_catalog(self):
        result=self.pack(); self.rewrite_index(lambda i:i['catalog'].__setitem__('recordedRoot','G:/different'))
        with self.assertRaisesRegex(ValueError,'index SHA'): bundle.check_integrity(self.out,result['indexSha256'])

    def test_duplicate_and_unsafe_paths_rejected(self):
        for name in ('../x','/x','C:/x','a\\b','a//b','NUL.txt','a/../b','x:stream','a.','a '):
            with self.subTest(name=name), self.assertRaises(ValueError): bundle.relative(name)
        self.pack(); self.rewrite_index(lambda i:i['files'].append(i['files'][0]))
        with self.assertRaisesRegex(ValueError,'duplicate'): bundle.check_integrity(self.out)

    def test_pack_never_merges_or_overwrites(self):
        self.pack(); digest=bundle.sha(self.out/'bundle.json')
        with self.assertRaises(FileExistsError): self.pack()
        self.assertEqual(digest,bundle.sha(self.out/'bundle.json'))

    def test_changed_source_rejected_before_output(self):
        (self.repo/'data/raw.txt').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'source hash'): self.pack()
        self.assertFalse(self.out.exists())

    @unittest.skipUnless(os.name=='nt','Windows junction')
    def test_junction_target_never_traversed(self):
        target=self.base/'target'; target.mkdir(); link=self.repo/'link'
        result=subprocess.run(['cmd','/c','mklink','/J',str(link),str(target)],capture_output=True)
        self.assertEqual(0,result.returncode)
        try:
            with self.assertRaisesRegex(VerificationError,'reparse'): bundle.inside(self.repo,'link/file')
        finally: os.rmdir(link)

    def test_relocation_requires_exact_explicit_original_root(self):
        raw=self.base/'original'; raw.mkdir(); fixture=ListVerifierFixture(raw,repeats=1)
        moved=self.base/'moved'; shutil.copytree(raw,moved); spec=fixture.manifest['runs'][0]
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (moved/spec['runId']).iterdir()}
        with self.assertRaisesRegex(VerificationError,'outputDirectory'):
            _validate_run(moved,spec,fixture.manifest)
        with self.assertRaisesRegex(VerificationError,'outputDirectory'):
            _validate_run(moved,spec,fixture.manifest,recorded_root='G:/wrong')
        result=_validate_run(moved,spec,fixture.manifest,recorded_root=str(raw))
        self.assertEqual(spec['runId'],result['record']['runId'])
        self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (moved/spec['runId']).iterdir()})

    def test_analysis_rejects_invalid_or_partial_input_before_output(self):
        self.pack()
        with self.assertRaises(Exception): generate(self.out,self.base/'charts')
        self.assertFalse((self.base/'charts').exists())
        with self.assertRaisesRegex(ValueError,'complete'): comparison(None)

    def test_receipt_identity_and_conflicting_data_rejected(self):
        root=self.base/'receipts'; root.mkdir(); p=root/'run-receipt.json'
        receipt=dict(runId='run',pid=1,exitCode=0,durationSeconds=1,completedUtc='2026-09-07T00:00:00Z',artifactSetSha256='A'*64)
        bundle.write_new(p,receipt)
        bundle.check_receipt(root,{'runId':'run'},{'artifactSetSha256':'A'*64})
        with self.assertRaisesRegex(ValueError,'receipt'):
            bundle.check_receipt(root,{'runId':'run'},{'artifactSetSha256':'B'*64})


if __name__=='__main__': unittest.main()
