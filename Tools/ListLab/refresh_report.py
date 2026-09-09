"""Render List refresh per-run evidence with ReportLab charts; no Unity operations."""
import argparse,json,math,statistics
from pathlib import Path
from reportlab.graphics.shapes import Drawing,String,Rect
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.graphics import renderSVG,renderPM
from reportlab.lib import colors
PROFILES=("idle","sparse","burst","high","batch")
def main():
    p=argparse.ArgumentParser();p.add_argument("--verification",type=Path,required=True);p.add_argument("--plan",type=Path,required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    v=json.loads(a.verification.read_text());plan=json.loads(a.plan.read_text());assert v["status"]=="pass"
    details={d["runId"]:d for d in v["details"]};comparisons={c["group"]:c for c in v["comparisons"]}
    groups=[f"{b}-{f}-fps-1" for b in ("normal","virtual") for f in PROFILES]+["virtual-high-fps60"]
    d=Drawing(1120,770)
    d.add(Rect(0,0,1120,770,fillColor=colors.white,strokeColor=None))
    d.add(String(24,742,"List refresh: five independent Player repeats per policy",fontName="Helvetica-Bold",fontSize=18,fillColor=colors.HexColor("#142536")))
    d.add(String(24,723,"p95 frame interval (ms). Each panel has its own y scale. 300 warmup + 1800 measured frames per process.",fontSize=10,fillColor=colors.HexColor("#475569")))
    d.add(String(760,742,"Window",fontSize=11,fillColor=colors.HexColor("#64748b")));d.add(String(855,742,"Target",fontSize=11,fillColor=colors.HexColor("#0f766e")))
    for gi,group in enumerate(groups):
        x=24+(gi%4)*278;y=495-(gi//4)*230;c=comparisons[group]
        plot=LinePlot();plot.x=x+34;plot.y=y+45;plot.width=210;plot.height=140
        plot.data=[list(enumerate(c["windowP95"],1)),list(enumerate(c["targetP95"],1))]
        plot.joinedLines=1;plot.xValueAxis.valueMin=1;plot.xValueAxis.valueMax=5;plot.xValueAxis.valueSteps=[1,2,3,4,5]
        maximum=max(c["windowP95"]+c["targetP95"]);limit=math.ceil(maximum*1.08) if maximum>=2 else math.ceil(maximum*1.08*5)/5
        plot.yValueAxis.valueMin=0;plot.yValueAxis.valueMax=limit;plot.yValueAxis.valueSteps=[limit*i/4 for i in range(5)]
        plot.yValueAxis.labelTextFormat="%.2f" if maximum<2 else "%.1f"
        plot.xValueAxis.labels.fontSize=8;plot.yValueAxis.labels.fontSize=8
        for i,color in enumerate(("#64748b","#0f766e")):
            plot.lines[i].strokeColor=colors.HexColor(color);plot.lines[i].strokeWidth=1.4
            plot.lines[i].symbol=makeMarker("FilledCircle");plot.lines[i].symbol.size=3.5
        d.add(plot)
        title=group.replace("-fps-1"," / uncapped").replace("-fps60"," / 60 FPS")
        d.add(String(x,y+206,title,fontName="Helvetica-Bold",fontSize=10))
        d.add(String(x+34,y+25,"Independent repeat",fontSize=8,fillColor=colors.HexColor("#475569")))
        d.add(String(x,y+9,c["result"]+"; medians "+f'{statistics.median(c["windowP95"]):.3f} / {statistics.median(c["targetP95"]):.3f}'+" ms",fontSize=9,fillColor=colors.HexColor("#0f766e" if c["result"]=="improved" else "#92400e")))
    a.output.mkdir(parents=True,exist_ok=True)
    svg=a.output/"list-refresh-p95.svg";png=a.output/"list-refresh-p95.png"
    if svg.exists() or png.exists():raise FileExistsError("Refuse overwrite chart")
    renderSVG.drawToFile(d,str(svg))
    try:renderPM.drawToFile(d,str(png),fmt="PNG",dpi=130)
    except Exception as e:print("PNG unavailable:",str(e))
    rows=[]
    for group in groups:
        c=comparisons[group];pair={k:[] for k in ("window","target")}
        for r in sorted(plan["runs"],key=lambda r:r["runIndex"]):
            if r["groupId"]==group:pair[r["variant"]].append(details[r["runId"]])
        w=statistics.median(c["windowP95"]);t=statistics.median(c["targetP95"])
        rows.append(dict(group=group,windowMedianP95=w,targetMedianP95=t,relativePercent=(t-w)/w*100,result=c["result"],
            windowP95=c["windowP95"],targetP95=c["targetP95"],windowP99=[r["frameP99"] for r in pair["window"]],targetP99=[r["frameP99"] for r in pair["target"]],
            windowOverBudget=[r["overBudgetRatio"] for r in pair["window"]],targetOverBudget=[r["overBudgetRatio"] for r in pair["target"]],
            windowBind=[r["bindDelta"] for r in pair["window"]],targetBind=[r["bindDelta"] for r in pair["target"]]))
    with (a.output/"comparison-table.json").open("x",encoding="utf-8") as f:json.dump(rows,f,indent=2)
    print(json.dumps(dict(svg=str(svg),png=str(png) if png.exists() else None,groups=len(rows))))
if __name__=="__main__":main()
