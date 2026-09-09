"""Verify real Editor traces and reject corrupt fixture copies (never edit source evidence)."""
import argparse,csv,json,shutil,uuid
from pathlib import Path
from refresh_verify import verify_trace
def main():
    p=argparse.ArgumentParser();p.add_argument("--runs",type=Path,required=True);p.add_argument("--fixtures",type=Path,required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    good=[];chosen=None
    for d in sorted(a.runs.glob("refresh-integration-*")):
        cfg=json.loads((d/"config.json").read_text());m=json.loads((d/"refresh-metrics.json").read_text());s=json.loads((d/"summary.json").read_text())
        verify_trace(d,cfg,m,s);good.append(cfg["caseId"])
        if cfg["caseId"]=="listrefresh-virtual-1000-target-high":chosen=d
    expected={f"listrefresh-{b}-1000-{p}-{f}" for b in ("normal","virtual") for p in ("window","target") for f in ("idle","sparse","burst","high","batch")}
    if set(good)!=expected:raise ValueError("Require all 20 real Runner cases")
    fixtures=a.fixtures/uuid.uuid4().hex;fixtures.mkdir(parents=True,exist_ok=False);rejected=[]
    for field in ("label_checksum","state_mask","target_mask","updates","bind_count","leased","settled_frame"):
        d=fixtures/field;d.mkdir()
        for name in ("config.json","refresh-metrics.json","summary.json","samples.csv","refresh-samples.csv"):shutil.copy2(chosen/name,d/name)
        with (d/"refresh-samples.csv").open(newline="") as f:r=csv.DictReader(f);columns=r.fieldnames;data=list(r)
        data[0][field]=str(int(data[0][field])+1)
        with (d/"refresh-samples.csv").open("w",newline="") as f:w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(data)
        try:verify_trace(d,json.loads((d/"config.json").read_text()),json.loads((d/"refresh-metrics.json").read_text()),json.loads((d/"summary.json").read_text()))
        except ValueError as e:rejected.append(dict(field=field,reason=str(e)))
        else:raise AssertionError("Corruption accepted: "+field)
    result=dict(status="pass",actualVerified=len(good),cases=good,rejected=rejected,fixtureDirectory=str(fixtures))
    with a.output.open("x",encoding="utf-8") as f:json.dump(result,f,indent=2)
    print(json.dumps(dict(status="pass",actualVerified=len(good),rejected=len(rejected))))
if __name__=="__main__":main()
