"""Controlled synthetic verifier tests, never Windows execution evidence."""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from player_plan import make_plan
from player_verify import verify_run,EvidenceError


def f32(x):return struct.unpack("f",struct.pack("f",x))[0]
def dump(path,value):path.write_text(json.dumps(value,allow_nan=False),encoding="utf-8")
def csv_text(columns,data):
    out=io.StringIO(newline="");w=csv.writer(out,lineterminator="\n");w.writerow(columns);w.writerows(data);return out.getvalue()

class PlayerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);gate_path=self.root/"gate.json";dump(gate_path,{"fixture":True});self.gate={"fixture":True}
        build_path=self.root/"build.json";dump(build_path,dict(schemaVersion="xuilab.gradient.build/v1",candidateId="fixture-candidate",buildId="fixture-build",sourceRevision="fixture-source",dirty=True))
        self.plan=make_plan("fixture-plan","fixture-candidate","fixture-build","fixture-source",gate_path,True,gate_path,build_path)
        self.run=copy.deepcopy(next(r for r in self.plan["runs"] if r["caseId"]=="gradient-grid-100-static-horizontal-25"));self.run.update(runId="fixture-run",runIndex=1,plannedRepeatCount=1,warmupFrames=4,measureFrames=8,sampleCapacity=8)
        self.plan["runs"]=[self.run];self.plan["evidenceKind"]="fixture";self.plan_hash="0"*64
        self.directory=self.root/"fixture-run";self.directory.mkdir();p=self.run["parameters"]
        cfg={k:self.run[k] for k in ("runId","caseId","runIndex","plannedRepeatCount","warmupFrames","measureFrames","sampleCapacity","frameBudgetMs")}
        cfg.update({k:self.plan[k] for k in ("candidateId","buildId","sourceRevision","dirty")});cfg.update(faultPlan={"mode":"none"},tier="windows-development-player",targetFrameRate=-1,vSyncCount=0,seriesId=self.plan["planId"],protocolVersion=self.plan["protocolVersion"],caseVersion="1")
        cfg.update(schemaVersion="xuilab.benchmark.config/v1",enableProfilerRecorders=True,requiredMetrics=["Frame Interval"],optionalMetrics=["Main Thread","GC Allocated In Frame","System Used Memory"],cpuIterationsPerFrame=0,allocationBytesPerFrame=0,quitWhenDone=True)
        dump(self.directory/"config.json",cfg)
        env=dict(unityVersion="2022.3.45f1c1",screenWidth=960,screenHeight=540,graphicsDeviceType="Direct3D11",qualityLevel="High Fidelity",scriptingBackend="mono",buildType="development",targetFrameRate=-1,vSyncCount=0,tier="windows-development-player")
        env["schemaVersion"]="xuilab.benchmark.environment/v1"
        dump(self.directory/"environment.json",env)
        dump(self.directory/"gradient-binding.json",dict(run=self.run,planSha256=self.plan_hash,colorSpace="Linear",preflight=self.gate,startFocus=True,observedFocusAtExport=True,buildManifestSha256=p["buildManifestSha256"]))
        core=[[i,100+i,16*(i+1),16,"","",""] for i in range(8)]
        self.write_csv("samples.csv",["sample_index","unity_frame","elapsed_ms","frame_interval_ms","main_thread_ns","gc_allocated_bytes","system_used_memory_bytes"],core)
        trace=[[i,99+i,100+i,.25,100,0,0,0,6600,6400,3200,0] for i in range(8)]
        self.write_csv("gradient-samples.csv",["sample_index","action_frame","settled_frame","bias","visible","culled","dirty_delta","rebuild_delta","vertices","triangles","segments","changed_count"],trace)
        start=[f32(x) for x in p["startRgba"]];end=[f32(x) for x in p["endRgba"]]
        def color(t):
            w=t/(3-2*t);return [start[c]+(end[c]-start[c])*w for c in range(4)]
        nodes=[[f32(x) for x in color(i/32)] for i in range(33)]
        def quant(x):return int(f32(f32(x*255)+.5)//1)
        scan=[[0,.25,i,i/32,*n,*[quant(x) for x in n]] for i,n in enumerate(nodes)]
        self.write_csv("quality-scan.csv",["scan_index","bias","node_index","t","r","g","b","a","quant_r","quant_g","quant_b","quant_a"],scan)
        samples=[];maximum=0
        for i in range(4097):
            t=i/4096;cell=min(31,int(t*32));u=t*32-cell;expected=color(t);actual=[nodes[cell][c]+(nodes[cell+1][c]-nodes[cell][c])*u for c in range(4)]
            maximum=max(maximum,max(abs(a-b) for a,b in zip(expected,actual)));samples.append(dict(t=t,expectedRgba=expected,actualRgba=actual))
        q={"schemaVersion":"xuilab.gradient.quality/v1","runId":self.run["runId"],"contractId":self.plan["contractId"],"contractSha256":self.plan["contractSha256"],"evidenceKind":"fixture",**self.plan["quality"],"colorSpace":"encoded-rgb","alphaMode":"straight-rgba-equal-weight","samples":samples}
        dump(self.directory/"quality.json",q)
        metrics=dict(runId=self.run["runId"],caseId=self.run["caseId"],sampleCount=8,totalDirty=0,totalRebuild=0,cleanupActiveObjects=0,correctness="pass",qualityMaxError=maximum,quantizationMaxError=max(abs(x-quant(x)/255) for n in nodes for x in n))
        dump(self.directory/"gradient-metrics.json",metrics)
        width=900/p["geometry"]["columns"]*.9;height=480/p["geometry"]["rows"]*.9
        verts=[dict(position=[-width/2+i/32*width,y,0],rgba=[quant(x) for x in nodes[i]]) for i in range(33) for y in (-height/2,height/2)]
        indices=[v for i in range(32) for v in (2*i,2*i+1,2*i+3,2*i+3,2*i+2,2*i)]
        dump(self.directory/"gradient-mesh.json",dict(elementIndex=0,bias=.25,mode="FixedSegments",vertices=verts,indices=indices))
        summary=dict(runId=self.run["runId"],planId=self.plan["planId"],contractId=self.plan["contractId"],contractSha256=self.plan["contractSha256"],evidenceKind="fixture",sampleCount=8,p50FrameIntervalMs=16,p95FrameIntervalMs=16,p99FrameIntervalMs=16,maxFrameIntervalMs=16,overBudgetRatio=0,meanMainThreadNanoseconds=None,totalGcAllocatedBytes=None,lastSystemUsedMemoryBytes=None,correctness="pass",measurementValidity="valid",state="completed",qualityStatus="pass",processSuccess=True,exitCode=0,exportSucceeded=True,cleanupSucceeded=True,failureCode="none",failureReason="")
        dump(self.directory/"summary.json",summary)
        (self.directory/"report.md").write_text("Controlled fixture only",encoding="utf-8");(self.directory/"events.log").write_text("fixture completed",encoding="utf-8")
        identity={k:self.plan[k] for k in ("planId","contractId","contractSha256","evidenceKind","candidateId","buildId","sourceRevision","dirty")};identity.update(runId=self.run["runId"],planSha256=self.plan_hash,buildManifestSha256=p["buildManifestSha256"])
        dump(self.directory/"identity.json",identity);self.rehash()
    def tearDown(self):self.temp.cleanup()
    def write_csv(self,name,columns,data):(self.directory/name).write_text(csv_text(columns,data),encoding="utf-8")
    def rehash(self):
        p=self.directory/"identity.json";identity=json.loads(p.read_text());identity["configSha256"]=hashlib.sha256((self.directory/"config.json").read_bytes()).hexdigest();identity["artifactSha256"]={n:hashlib.sha256((self.directory/n).read_bytes()).hexdigest() for n in self.plan["artifacts"] if n!="identity.json"};dump(p,identity)
    def verify(self):return verify_run(self.directory,self.plan,self.run,self.plan_hash,self.root,self.gate)
    def test_coherent_fixture(self):self.assertEqual(self.verify()[1]["rawEvidence"],"verified")
    def test_shifted_action_frame_rejected_after_rehash(self):
        p=self.directory/"gradient-samples.csv";p.write_text(p.read_text().replace("0,99,100,","0,98,100,",1));self.rehash()
        with self.assertRaises(EvidenceError):self.verify()
    def test_frame_value_rejected_after_rehash(self):
        p=self.directory/"samples.csv";p.write_text(p.read_text().replace("0,100,16,16,","0,100,16,17,",1));self.rehash()
        with self.assertRaises(EvidenceError):self.verify()
    def test_candidate_rejected_after_rehash(self):
        p=self.directory/"config.json";v=json.loads(p.read_text());v["candidateId"]="other";dump(p,v);self.rehash()
        with self.assertRaises(EvidenceError):self.verify()
    def test_quality_node_rejected_after_rehash(self):
        p=self.directory/"quality-scan.csv";lines=p.read_text().splitlines();row=lines[1].split(',');row[4]="0.5";lines[1]=','.join(row);p.write_text('\n'.join(lines)+'\n');self.rehash()
        with self.assertRaises(EvidenceError):self.verify()
    def test_mesh_index_rejected_after_rehash(self):
        p=self.directory/"gradient-mesh.json";v=json.loads(p.read_text());v["indices"][0]=99;dump(p,v);self.rehash()
        with self.assertRaises(EvidenceError):self.verify()
    def test_startup_focus_loss_not_erased(self):
        p=self.directory/"gradient-binding.json";v=json.loads(p.read_text());v["startFocus"]=False;dump(p,v);self.rehash()
        with self.assertRaises(EvidenceError):self.verify()
    def test_binding_build_mismatch_rejected(self):
        p=self.directory/"gradient-binding.json";v=json.loads(p.read_text());v["buildManifestSha256"]="f"*64;dump(p,v);self.rehash()
        with self.assertRaises(EvidenceError):self.verify()
    def test_invalid_terminal_rejected_after_rehash(self):
        path=self.directory/"summary.json";original=json.loads(path.read_text())
        for key,value in (("state","failed"),("state","cancelled"),("correctness","fail"),("measurementValidity","invalid"),("processSuccess",False),("exitCode",1)):
            with self.subTest(key=key,value=value):
                changed=copy.deepcopy(original);changed[key]=value;dump(path,changed);self.rehash()
                with self.assertRaises(EvidenceError):self.verify()
        dump(path,original);self.rehash()
    def test_mesh_malformed_rejected_after_rehash(self):
        path=self.directory/"gradient-mesh.json";original=json.loads(path.read_text())
        variants=[]
        for value in ([],[255],[1,2,3,256]):
            v=copy.deepcopy(original);v["vertices"][0]["rgba"]=value;variants.append(v)
        v=copy.deepcopy(original);v["elementIndex"]=1;variants.append(v)
        v=copy.deepcopy(original);v["vertices"][2]["position"][0]+=.1;variants.append(v)
        v=copy.deepcopy(original);v["vertices"][0]["position"][2]=1;variants.append(v)
        v=copy.deepcopy(original);v["indices"][:3]=[0,0,0];variants.append(v)
        for index,v in enumerate(variants):
            with self.subTest(index=index):
                dump(path,v);self.rehash()
                with self.assertRaises(EvidenceError):self.verify()
        dump(path,original);self.rehash()
    def test_quality_other_planned_run_rejected(self):
        other=copy.deepcopy(self.run);other["runId"]="another-run";other["groupId"]="another-group";self.plan["runs"].append(other)
        path=self.directory/"quality.json";v=json.loads(path.read_text());v["runId"]=other["runId"];dump(path,v);self.rehash()
        with self.assertRaises(EvidenceError):self.verify()
    def test_player_plan_requires_shared_manifest_hash(self):
        import gradient_experiment as contracts
        plan=copy.deepcopy(self.plan);plan["evidenceKind"]="windows-development-player"
        other=copy.deepcopy(plan["runs"][0]);other["groupId"]="second-group";other["runId"]="second-run";plan["runs"].append(other)
        for value in (None,"","z"*64,"a"*64):
            with self.subTest(value=value):
                other["parameters"]["buildManifestSha256"]=value
                with self.assertRaises(contracts.GradientToolError):contracts.validate_plan(plan)
    def test_core_uppercase_config_hash_accepted(self):
        path=self.directory/"identity.json";v=json.loads(path.read_text());v["configSha256"]=v["configSha256"].upper();dump(path,v)
        self.assertEqual(self.verify()[1]["rawEvidence"],"verified")
    def test_missing_cpu_is_not_zero(self):
        p=self.directory/"summary.json";v=json.loads(p.read_text());v["meanMainThreadNanoseconds"]=0;dump(p,v);self.rehash()
        with self.assertRaises(EvidenceError):self.verify()
class BuildEvidenceTests(unittest.TestCase):
    def setUp(self):
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"UnityOperations"))
        from operation_journal import Journal,digest
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        for folder in ("XUILab/Assets","XUILab/Packages","XUILab/ProjectSettings"):
            directory=self.root/folder;directory.mkdir(parents=True);(directory/"fixture.txt").write_text("controlled synthetic source")
        inputs={p.relative_to(self.root).as_posix():digest(p) for p in self.root.rglob("*.txt")}
        self.player=self.root/"Artifacts/fixture/build/Fixture.exe";self.player.parent.mkdir(parents=True)
        self.path=self.player.parent.parent/"build.json"
        self.plan=dict(candidateId="fixture",buildId="fixture",sourceRevision="fixture",dirty=True)
        request=dict(schema="xuilab.unity-operation/v1",kind="build",task="M2-04",candidate="fixture",attempt="fixture",project="XUILab",editor="2022.3.45f1c1",instance="fixture",operator="fixture",parameters=dict(platform="StandaloneWindows64",output_path=self.player.relative_to(self.root).as_posix()),inputs=inputs,before={k:False for k in ("playing","paused","compiling","importing","tests_running","build_running","prefab_stage","dirty_scene")},restore_expected=dict(playing=False),artifacts=[self.player.relative_to(self.root).as_posix()])
        journal=Journal(self.root);operation=journal.prepare(request);journal.claim(operation)
        envelope=dict(operation=operation,project_root=str(self.root/"XUILab"),candidate="fixture",instance="fixture",observed_at="2026-01-01T00:00:01Z",response=dict(success=True,data=dict(job_id="fixture")))
        journal.receipt(operation,envelope);self.player.write_bytes(b"synthetic nonexecutable fixture")
        envelope=copy.deepcopy(envelope);envelope["observed_at"]="2026-01-01T00:00:03Z";envelope["response"]["data"].update(result="succeeded",platform="StandaloneWindows64",output_path=request["parameters"]["output_path"],errors=0,completed_at="2026-01-01T00:00:02Z")
        journal.terminal(operation,envelope)
        self.manifest=dict(schemaVersion="xuilab.gradient.build/v1",**self.plan,player="build/Fixture.exe",files={"build/Fixture.exe":digest(self.player)},sourceInputs=inputs,buildOperation=operation,buildRequestSha256=digest(journal.directory(operation)/"request.json"),buildTerminalSha256=digest(journal.directory(operation)/"terminal.json"));dump(self.path,self.manifest)
    def tearDown(self):self.temp.cleanup()
    def check(self):
        from player_launch import check_build
        return check_build(self.path,self.player,self.plan,self.root)
    def test_coherent_synthetic_build(self):self.assertEqual(self.check()["candidateId"],"fixture")
    def test_empty_and_incomplete_sources_rejected(self):
        for sources in ({},{next(iter(self.manifest["sourceInputs"])):next(iter(self.manifest["sourceInputs"].values()))}):
            with self.subTest(sources=sources):
                value=copy.deepcopy(self.manifest);value["sourceInputs"]=sources;dump(self.path,value)
                with self.assertRaises(EvidenceError):self.check()
    def test_undeclared_build_file_rejected(self):
        (self.player.parent/"undeclared.dat").write_bytes(b"extra")
        with self.assertRaises(EvidenceError):self.check()
    def test_wrong_build_journal_rejected(self):
        value=copy.deepcopy(self.manifest);value["buildTerminalSha256"]="0"*64;dump(self.path,value)
        with self.assertRaises(EvidenceError):self.check()

if __name__=="__main__":unittest.main()
