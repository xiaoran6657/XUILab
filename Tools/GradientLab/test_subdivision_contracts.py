"""Negative frozen-plan and paired-noise checks; no Unity/Player execution."""
import copy,tempfile,unittest
from pathlib import Path
from subdivision_plan import make_plan,validate_subdivision
from subdivision_report import compare

class SubdivisionContracts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);control=root/"control";control.write_text("{}")
        manifest=root/"manifest"
        manifest.write_text('{"schemaVersion":"xuilab.gradient.build/v1","candidateId":"fixture","buildId":"fixture","sourceRevision":"fixture","dirty":true}')
        self.plan=make_plan("fixture","fixture","fixture","fixture",True,control,control,control,manifest)
    def test_incomplete_reordered_or_altered_protocol_is_rejected(self):
        for change in (
            lambda p:p["runs"].pop(),
            lambda p:p["runs"].reverse(),
            lambda p:p["runs"][0].update(warmupFrames=299),
            lambda p:p["runs"][0]["parameters"].update(halfPeriodFrames=299),
            lambda p:p["runs"][0]["parameters"].update(continueWarmup=False),
            lambda p:p["runs"][0]["parameters"].update(transitionFrom=.25),
            lambda p:p["runs"][0]["parameters"].update(segments=12),
            lambda p:p["artifacts"].pop(),
            lambda p:p["quality"].update(threshold=.1),
        ):
            value=copy.deepcopy(self.plan);change(value)
            with self.assertRaises(ValueError):validate_subdivision(value)
    def test_expected_plan_is_complete(self):
        self.assertEqual(len(validate_subdivision(self.plan)["runs"]),160)
    def test_comparison_requires_four_pairs_and_exceeds_noise(self):
        self.assertEqual(compare([10]*5,[8]*5)["result"],"improved")
        self.assertEqual(compare([10]*5,[12]*5)["result"],"regressed")
        self.assertEqual(compare([10]*5,[9.5]*5)["result"],"inconclusive")
        self.assertEqual(compare([10]*5,[1,8,8,11,11])["result"],"inconclusive")
        self.assertEqual(compare([10]*5,[8,8,8,8,30])["result"],"inconclusive")
        with self.assertRaises(ValueError):compare([10]*4,[8]*4)

if __name__=="__main__":unittest.main()

