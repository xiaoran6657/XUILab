import copy,csv,json,math,tempfile,unittest
from pathlib import Path
from adaptive_plan import planned_runs,validate_adaptive,ARTIFACTS
from adaptive_math import select,f32
from adaptive_verify import verify_selection,SELECTION_COLUMNS,EvidenceError

class AdaptiveContracts(unittest.TestCase):
    def plan(self,pilot=False):
        runs=planned_runs("fixture","1"*64,"2"*64,"3"*64,pilot)
        return dict(schemaVersion="xuilab.gradient.plan/v1",status="frozen",planId="fixture",experimentId="gradient-adaptive-v1",protocolVersion="xuilab.benchmark.protocol/v1",contractId="gradient-schlick-v1",contractSha256="0"*64,candidateId="fixture",buildId="fixture",sourceRevision="fixture",dirty=True,evidenceKind="windows-development-player",budget=dict(perRunWallClockSeconds=180,totalWallClockSeconds=180*len(runs)),quality=dict(metricId="rgba-max-absolute-error",threshold=.01,referenceId="schlick-dense4097-v1",aggregation="max-absolute-rgba"),comparison=None,artifacts=ARTIFACTS,runs=runs)
    def test_exact_plans_and_mutants(self):
        for pilot in (False,True):
            p=self.plan(pilot);self.assertEqual(len(validate_adaptive(p)["runs"]),4 if pilot else 80)
        mutations=[lambda p:p["runs"].reverse(),lambda p:p["runs"].pop(),lambda p:p["artifacts"].pop(),lambda p:p["runs"][0]["parameters"].update(tolerance=.02),lambda p:p["runs"][0]["parameters"].update(maxSegments=65),lambda p:p["runs"][0]["parameters"].update(effectMode="fixed32"),lambda p:p["runs"][0]["parameters"].update(selectionAlgorithm="other"),lambda p:p["runs"][0].update(measureFrames=1799),lambda p:p["runs"][0].update(variant="adaptive64")]
        for mutation in mutations:
            p=copy.deepcopy(self.plan());mutation(p)
            with self.assertRaises(ValueError):validate_adaptive(p)
    def test_error_bound_and_explicit_cap(self):
        start=(.04,.75,.95,1);end=(.95,.15,.4,.6)
        for bias in (.05,.1,.25,.5,.75,.9,.95):
            nodes,error,limited=select(start,end,bias);self.assertFalse(limited);self.assertLessEqual(error,.01)
            a=(1-f32(bias))/f32(bias);span=max(abs(f32(x)-f32(y)) for x,y in zip(start,end))
            worst=0
            for l,r in zip(nodes,nodes[1:]):
                self.assertGreater(r,l)
                for j in range(257):
                    t=l+(r-l)*j/256;exact=t/(a+(1-a)*t);chord=l/(a+(1-a)*l)+(r/(a+(1-a)*r)-l/(a+(1-a)*l))*j/256
                    worst=max(worst,abs(exact-chord)*span)
            self.assertLessEqual(worst,error)
        self.assertEqual(len(select(start,end,.5)[0])-1,1)
        self.assertTrue(select(start,end,.05,1,4)[2])
    def test_selection_trace_rejects_mismatched_work_geometry_and_bound(self):
        run=self.plan()["runs"][1];p=run["parameters"];nodes,error,limited=select(tuple(p["startRgba"]),tuple(p["endRgba"]),p["bias"]);n=len(nodes)-1
        trace=[dict(bias=str(p["bias"]),rebuild_delta="0",segments=str(n),vertices=str(2*(n+1)),triangles=str(2*n))]
        row=dict(zip(SELECTION_COLUMNS,["0","0","0","0",str(n),str(n),"0",repr(error)]))
        metrics=dict(subdivisionMode="adaptive",selectionAlgorithm=p["selectionAlgorithm"],selectionCalls=0,selectionCacheHits=0,selectionTicks=0,minSelectedSegments=n,maxSelectedSegments=n,qualityLimitedObservations=0,coldSelectionCalls=1,coldSelectionCacheHits=0,maximumEstimatedError=error,selectionFrequency=10000000,coldSelectionTicks=100,selectionTimingMeaning="Stopwatch elapsed ticks include cache lookup and instrumentation; not whole-frame CPU time")
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            def save(value):
                with (folder/"selection-samples.csv").open("w",newline="") as f:
                    w=csv.DictWriter(f,fieldnames=SELECTION_COLUMNS);w.writeheader();w.writerow(value)
            save(row);self.assertEqual(verify_selection(folder,run,metrics,trace)["minSegments"],n)
            for key,value in (("selection_calls","1"),("cache_hits","1"),("selection_ticks","1"),("min_segments",str(n+1)),("quality_limited","1"),("estimated_error","0")):
                bad=dict(row);bad[key]=value;save(bad)
                with self.assertRaises(EvidenceError):verify_selection(folder,run,metrics,trace)
            save(row);bad=copy.deepcopy(trace);bad[0]["vertices"]="4"
            with self.assertRaises(EvidenceError):verify_selection(folder,run,metrics,bad)

if __name__=="__main__":unittest.main()
