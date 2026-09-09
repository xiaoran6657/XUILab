"""Deterministic M2 Player plan, frozen before launching any run."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
from gradient_experiment import validate_plan

ARTIFACTS = ["config.json", "environment.json", "identity.json", "samples.csv", "summary.json", "report.md", "events.log", "gradient-samples.csv", "gradient-metrics.json", "quality.json", "quality-scan.csv", "gradient-binding.json", "gradient-mesh.json"]

def groups():
    rows = []
    def add(layout, count, states, direction="Horizontal", bias=.25):
        for state in states:
            name = f"gradient-{layout}-{count}-{state}-{direction.lower()}-{round(bias*100):02d}"
            visible = min(count, 19) if layout == "clip" else count
            changed = (visible+9)//10 if state == "few" else visible if state == "all" else 0
            rows.append((name, {"layout":layout, "count":count, "state":state, "direction":direction, "bias":bias,
                "curve":"Linear" if state=="linear" else "Nonlinear", "segments":32,
                "startRgba":[.04,.75,.95,1.], "endRgba":[.95,.15,.4,.6],
                "visibleCount":visible, "changedIndices":list(range(changed)),
                "screenWidth":960,"screenHeight":540,"colorSpace":"Linear","qualityLevel":"High Fidelity",
                "graphicsApi":"Direct3D11","scriptingBackend":"Mono","development":True,
                "targetFrameRate":-1,"vSyncCount":0,"halfPeriodFrames":300,"geometryVersion":"gradient-layout-v1",
                "geometry":{"width":900,"height":450 if layout in ("clip","large") else 480,"columns":math.ceil(math.sqrt(count*900/480)) if layout in ("grid","split") else 1,
                    "rows":math.ceil(count/math.ceil(math.sqrt(count*900/480))) if layout in ("grid","split") else count,
                    "rectScale":.9 if layout in ("grid","split") else 1.,"rowHeight":24 if layout=="clip" else 0,"rowWidth":880 if layout=="clip" else 0,"offset":0,
                    "visibleIndices":list(range(visible)),"splitIndices":list(range(changed)) if layout=="split" else []},
                "actionKind":"same-value-setter" if state=="same" else "controller-progress" if changed else "none",
                "targetIndices":list(range(count if state=="same" else changed)),"setterCadence":"every-measure-frame" if state=="same" or changed else "none",
                "progressFrom":0,"progressTo":1,"easing":"Linear","restart":"half-period-boundary",
                "effectMode":"absent" if state=="image" else "disabled" if state=="disabled" else "linear" if state=="linear" else "fixed32",
                "expectedVertices":4 if state in ("image","disabled","linear") else 66,"expectedTriangles":2 if state in ("image","disabled","linear") else 64,
                "qualityColorSpace":"encoded-rgb","alphaMode":"straight-rgba-equal-weight"}))
    add("grid",100,["image","disabled","linear","static","same","few","all"])
    add("grid",100,["static"],"Vertical")
    for bias in (.05,.95): add("grid",100,["static"],bias=bias)
    add("grid",500,["static","all"])
    add("grid",1000,["static","all","few"])
    add("split",1000,["few"])
    add("clip",1000,["static","all","few"])
    add("large",1,["linear","static","all"])
    for count in (2000,5000): add("grid",count,["static","all"])
    return rows

def make_plan(plan_id, candidate, build, source, contract_path, dirty, gate_path, build_manifest_path, pilot=False):
    rows=groups()
    gate=Path(gate_path)
    manifest_path=Path(build_manifest_path);manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    expected={"schemaVersion":"xuilab.gradient.build/v1","candidateId":candidate,"buildId":build,"sourceRevision":source,"dirty":dirty}
    if any(manifest.get(k)!=v for k,v in expected.items()):raise ValueError("Build manifest identity mismatch")
    for _,params in rows:
        params["preflightSha256"]=hashlib.sha256(gate.read_bytes()).hexdigest()
        params["buildManifestSha256"]=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if pilot: rows=[r for r in rows if r[0] in {"gradient-grid-100-static-horizontal-25","gradient-grid-100-all-horizontal-25","gradient-clip-1000-few-horizontal-25"}]
    repeats=1 if pilot else 5
    runs=[]
    for repeat in range(1,repeats+1):
        for name,params in (rows if repeat%2 else list(reversed(rows))):
            runs.append({"runId":f"{plan_id}-{name}-r{repeat}","groupId":name,"caseId":name,"variant":params["state"],"runIndex":repeat,"plannedRepeatCount":repeats,
                "warmupFrames":300,"measureFrames":1800,"sampleCapacity":1800,"frameBudgetMs":16.6666667,"timeoutSeconds":180,"parameters":params})
    result={"schemaVersion":"xuilab.gradient.plan/v1","status":"frozen","planId":plan_id,"experimentId":"gradient-baseline-v1","protocolVersion":"xuilab.benchmark.protocol/v1",
        "contractId":"gradient-schlick-v1","contractSha256":hashlib.sha256(Path(contract_path).read_bytes()).hexdigest(),"candidateId":candidate,"buildId":build,"sourceRevision":source,"dirty":dirty,"evidenceKind":"windows-development-player",
        "budget":{"perRunWallClockSeconds":180,"totalWallClockSeconds":180*len(runs)},
        "quality":{"metricId":"rgba-max-absolute-error","threshold":.01,"referenceId":"schlick-dense4097-v1","aggregation":"max-absolute-rgba"},
        "comparison":None,"artifacts":ARTIFACTS,"runs":runs}
    return validate_plan(result,require_frozen=True)

def main():
    p=argparse.ArgumentParser();p.add_argument("--output",required=True);p.add_argument("--plan-id",required=True);p.add_argument("--candidate",required=True);p.add_argument("--build",required=True);p.add_argument("--source",required=True);p.add_argument("--contract",default="Docs/Experiments/GRADIENT_CONTRACT.md");p.add_argument("--pilot",action="store_true");p.add_argument("--dirty",choices=["true","false"],required=True);p.add_argument("--gate",required=True);p.add_argument("--build-manifest",required=True);a=p.parse_args()
    value=make_plan(a.plan_id,a.candidate,a.build,a.source,a.contract,a.dirty=="true",a.gate,a.build_manifest,a.pilot)
    with Path(a.output).open("x",encoding="utf-8",newline="\n") as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write("\n")
    print(json.dumps({"runs":len(value["runs"]),"sha256":hashlib.sha256(Path(a.output).read_bytes()).hexdigest()}))
if __name__=="__main__": main()
