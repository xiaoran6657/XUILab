"""Recompute the frozen M3-L1 diagnostic. Never runs Unity or modifies Runtime."""
import argparse
import hashlib
import json
from pathlib import Path

def require(condition, message):
    if not condition:
        raise ValueError(message)

def verify(path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    require(raw["schema"] == "xuilab.list.refresh-trace/v1", "schema")
    require(raw["candidate"] == "list-refresh-trace-r1", "candidate")
    names = {"middle", "first_partial", "last_partial", "off_prefetch", "off_far", "moving", "template", "insert", "delete"}
    traces = raw["traces"]
    require(len(traces) == 18, "trace count")
    require({(t["backend"], t["name"]) for t in traces} == {(b,n) for b in ("normal","virtual") for n in names}, "case identity")
    rows = []
    for t in traces:
        label = t["backend"] + "/" + t["name"]
        snaps = t["snapshots"]
        reset = t["name"] in {"template","insert","delete"}
        require([s["phase"] for s in snaps[:4]] == ["before","immediate_after_dispatch","after_natural_frame","after_explicit_canvas_flush"], label+" phases")
        require(len(snaps) == (5 if t["name"].startswith("off_") else 4), label+" phases count")
        b, immediate, natural, flushed = snaps[:4]
        require(b["frame"] == immediate["frame"] < natural["frame"] == flushed["frame"], label+" frame boundary")
        visible = [c["key"] for c in b["cells"] if (c["key"]+1)*48 > b["offset"] and c["key"]*48 < b["offset"]+384]
        require(visible == t["visibleBefore"],label+" visibility")
        require(t["targetVisible"] == (t["target"] in visible), label+" target visibility")
        require(t["scannedCells"] == len(b["cells"]) == (13 if t["backend"]=="virtual" else 1000), label+" scan scope")
        require(t["dataMutationOperations"] == 1, label+" mutation count")
        for s in snaps:
            cells=s["cells"]
            require(s["stateValid"] and not s["stateReason"], label+" runtime invariant")
            require(len({c["instance"] for c in cells}) == len(cells) == len({c["key"] for c in cells}), label+" unique mapping")
            require(all(c["key"]==c["index"] and c["visible"]==((c["key"]+1)*48>s["offset"] and c["key"]*48<s["offset"]+384) for c in cells), label+" index/visible")
            require(s["leased"] == len(cells) and s["unique"]==s["leased"]+s["cached"]==s["created"]-s["destroyed"],label+" pool")
            for g in s["graphics"]:
                require(g["vertexDirty"]==len(g["vertexDirtyIndices"]) and g["layoutDirty"]==len(g["layoutDirtyIndices"]) and g["meshCalls"]==len(g["meshIndices"]), label+" event attribution")
                require((g["meshCalls"]==0 and g["vertices"]==-1) or (g["meshCalls"]>0 and g["vertices"]>=0),label+" mesh unavailable")
            if s["phase"] in {"before","after_natural_frame","after_explicit_canvas_flush","after_target_reentry"}:
                require(all(abs(c["top"]-c["key"]*48)<.05 and abs(c["height"]-48)<.05 for c in cells),label+" geometry")
        before_by_instance={c["instance"]:c for c in b["cells"]}
        rebound=[c["key"] for c in immediate["cells"] if c["instance"] in before_by_instance and c["binds"]>before_by_instance[c["instance"]]["binds"]]
        require(rebound==t["reboundIndices"],label+" rebound identities")
        binds=immediate["binds"]-b["binds"]
        require(binds==t["totalBinds"],label+" bind total")
        if not reset:
            require(binds==len(visible)==9 and rebound==visible, label+" baseline window rebind")
            require(t["targetBinds"]==int(t["targetVisible"]),label+" target bind")
            require(immediate["created"]==b["created"] and immediate["destroyed"]==b["destroyed"],label+" no creation")
            require(immediate["unbinds"]-b["unbinds"]==binds,label+" rebind unbind")
            for c in immediate["cells"]:
                old=before_by_instance[c["instance"]]
                require((c["key"],c["index"],c["id"],c["template"])==(old["key"],old["index"],old["id"],old["template"]),label+" mapping stability")
                expected=t["replacementLabel"] if c["key"]==t["target"] and t["targetVisible"] else old["label"]
                require(c["label"]==expected,label+" label publication")
                require(c["binds"]-old["binds"]==int(c["key"] in visible),label+" individual bind")
            require(sum(g["vertexDirty"] for g in immediate["graphics"])==18,label+" vertex dirty")
            require(sum(g["layoutDirty"] for g in immediate["graphics"])==9,label+" layout dirty")
        else:
            require(t["newCellInitialDirty"].startswith("unavailable"), label+" missing reset dirty boundary")
            require(binds==len(immediate["cells"]),label+" reset bind count")
            require(t["anchorBefore"]==t["anchorAfter"],label+" reset anchor")
            for c in immediate["cells"]:
                original_index=c["key"]
                if t["name"]=="insert": original_index=c["key"]-1 if c["key"]>5 else c["key"]
                if t["name"]=="delete": original_index=c["key"]+1 if c["key"]>=5 else c["key"]
                expected_id=10001 if t["name"]=="insert" and c["key"]==5 else original_index+1
                expected_template=0 if expected_id==10001 else original_index%2
                if t["name"]=="template" and c["key"]==t["target"]: expected_template=1-expected_template
                require((c["id"],c["template"])==(expected_id,expected_template),label+" reset mapping")
        if t["name"].startswith("off_"):
            reentry=snaps[4]
            target=next(c for c in reentry["cells"] if c["key"]==t["target"])
            require(target["visible"] and target["label"]==t["reentryLabel"],label+" reentry")
            stale=target["label"]!=t["replacementLabel"]
            require(stale==t["reentryStale"]==(t["backend"]=="normal" or t["name"]=="off_prefetch"),label+" stale baseline")
        if t["name"]=="moving":
            require(abs(t["movingBeforeMutation"]-t["movingStart"])>.01 and abs(b["velocity"])>0,label+" natural movement")
            require(abs(natural["offset"]-b["offset"])>.001,label+" moving during dispatch")
        rows.append(dict(backend=t["backend"],case=t["name"],target=t["target"],targetBind=t["targetBinds"],totalBind=binds,
                         scanned=len(b["cells"]),vertexDirty=sum(g["vertexDirty"] for g in immediate["graphics"]),
                         layoutDirty=sum(g["layoutDirty"] for g in immediate["graphics"]),
                         meshProbeCalls=sum(g["meshCalls"] for g in flushed["graphics"]),
                         canvasEvents=flushed["canvasEvents"],reentryStale=t["reentryStale"] if t["name"].startswith("off_") else None))
    return dict(schema="xuilab.list.refresh-trace-verification/v1",candidate=raw["candidate"],correctness="pass_for_diagnostic_contract",
                performance="not_assessed",traceSha256=hashlib.sha256(path.read_bytes()).hexdigest(),rows=rows,
                limitations=["Editor observations only","Reset initial new-cell dirty is unavailable","Canvas event is not a rebuild count","Baseline stale label is observed behavior, not a public update API"])
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trace",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    result=verify(a.trace)
    with a.output.open("x",encoding="utf-8") as f: json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!="rows"},ensure_ascii=False))
if __name__=="__main__": main()
