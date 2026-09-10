import csv,json,tempfile,unittest
from pathlib import Path
import public_evidence as e

class EvidenceChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.config={'runId':'run','candidateId':'m4-final-b017672','sourceRevision':'b0176724d58c7cda86b472340845d239714888d0','buildId':'test-build','caseId':'test-case','dirty':False,'warmupFrames':300,'measureFrames':1800}
        self.identity=dict(self.config)
        self.summary={'runId':'run','correctness':'pass','measurementValidity':'valid','processSuccess':True,'state':'completed','exitCode':0,'sampleCount':1800,'p50FrameIntervalMs':899.5,'p95FrameIntervalMs':1709.05,'p99FrameIntervalMs':1781.01}
        self.expected={'runId':'run','expectedBuildId':'test-build','expectedCaseId':'test-case','frameP50Ms':899.5,'frameP95Ms':1709.05,'frameP99Ms':1781.01}
        self.write();self.samples(list(range(1800)))
    def write(self):
        for name,data in [('config',self.config),('identity',self.identity),('summary',self.summary)]:
            (self.root/(name+'.json')).write_text(json.dumps(data),encoding='utf-8')
    def samples(self,values):
        with (self.root/'samples.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.writer(f);w.writerow(['sample_index','frame_interval_ms']);w.writerows(enumerate(values))
    def check(self):return e.measure(self.root,self.expected,'list')
    def test_known_interpolated_quantiles(self):self.assertAlmostEqual(self.check()['p95'],1709.05)
    def test_missing_samples_rejected(self):
        self.samples(list(range(1799)))
        with self.assertRaises(ValueError):self.check()
    def test_forged_report_rejected(self):
        self.expected['frameP95Ms']=1
        with self.assertRaises(ValueError):self.check()
    def test_nonfinite_samples_rejected(self):
        self.samples([float('nan')]+list(range(1,1800)))
        with self.assertRaises(ValueError):self.check()
    def test_failed_terminal_rejected(self):
        self.summary['processSuccess']=False;self.write()
        with self.assertRaises(ValueError):self.check()
    def test_mismatched_source_rejected(self):
        self.identity['sourceRevision']='other';self.write()
        with self.assertRaises(ValueError):self.check()
    def test_coherent_wrong_build_rejected(self):
        self.config['buildId']=self.identity['buildId']='other-build';self.write()
        with self.assertRaises(ValueError):self.check()
    def test_wrong_case_rejected(self):
        self.config['caseId']='other-case';self.write()
        with self.assertRaises(ValueError):self.check()
    def test_dirty_source_rejected(self):
        self.config['dirty']=True;self.write()
        with self.assertRaises(ValueError):self.check()

if __name__=='__main__':unittest.main()
