"""Render full G2 report, retaining all repeats and the cross-day boundary."""
import argparse,csv,os,sys
from pathlib import Path
import gradient_experiment as c
from adaptive_verify import read,need

def render(report_path,output,deps=None):
    if deps:sys.path.insert(0,str(deps.resolve()))
    r=read(report_path);need(r["runCount"]==80 and r["status"]=="pass","Complete verified report required")
    need(not output.exists(),"New plot directory required");output.mkdir(parents=True)
    os.environ["MPLCONFIGDIR"]=str(output/".matplotlib-cache")
    import matplotlib;matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    groups={(g["scenario"],g["variant"]):g for g in r["groups"]};colors={"fixed32":"#386a99","adaptive64":"#d47932"}
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False})
    fig,axes=plt.subplots(1,3,figsize=(15,4.8))
    for variant,label in (("fixed32","Fixed 32"),("adaptive64","Adaptive 1..64")):
        g=groups["grid-dynamic",variant];axes[0].plot(range(1,6),[x["p95"] for x in g["runs"]],"o-",label=label,color=colors[variant])
    axes[0].axvspan(.8,1.2,color="#999999",alpha=.15);axes[0].set(xlabel="Independent repeat",ylabel="Frame interval p95 (ms)",xticks=range(1,6),title="100 changing gradients");axes[0].legend();axes[0].grid(axis="y",alpha=.2)
    for i,scenario in enumerate(("large-static-05","large-static-50","large-dynamic")):
        for j,variant in enumerate(("fixed32","adaptive64")):
            value=groups[scenario,variant]["statistics"]["qualityMaxError"]["median"]
            axes[1].bar(i+(j-.5)*.34,value,.32,color=colors[variant],label=variant if i==0 else None)
    axes[1].axhline(.01,color="#b54444",ls="--",label="Target 0.01");axes[1].set(xticks=range(3),xticklabels=["Extreme bias","Center bias","Dynamic"],ylabel="Continuous RGBA max error",title="Approximation before quantization");axes[1].legend(fontsize=8);axes[1].grid(axis="y",alpha=.2)
    for scenario,label,color in (("large-dynamic","1 component","#386a99"),("grid-dynamic","100 components","#d47932")):
        values=[x["selectionMs"] for x in groups[scenario,"adaptive64"]["runs"]]
        axes[2].plot(range(1,6),values,"o-",label=label,color=color)
    axes[2].set(xlabel="Independent repeat",ylabel="Selector total in 1800 frames (ms)",xticks=range(1,6),title="Steady selector cost, included in frames");axes[2].legend();axes[2].grid(axis="y",alpha=.2)
    fig.suptitle("Adaptive subdivision: quality, geometry and observed cost",fontsize=15)
    fig.text(.015,.02,"All five repeats retained. Gray repeat 1 is a cross-day pair; repeats 2–5 ran on the same day with the Editor closed.\nFrame interval is not CPU/GPU time. Fixed32 misses the 0.01 target at extreme bias. Failed attempts excluded and preserved.",fontsize=9)
    fig.tight_layout(rect=(0,.12,1,.94));fig.savefig(output/"quality-cost.png",dpi=180);fig.savefig(output/"quality-cost.svg");plt.close(fig)
    with (output/"group-statistics.csv").open("x",newline="",encoding="utf-8") as f:
        w=csv.writer(f);w.writerow(["scenario","variant","metric","median","minimum","maximum","range","mad"])
        for g in r["groups"]:
            for metric,s in g["statistics"].items():w.writerow([g["scenario"],g["variant"],metric,*[s[k] for k in ("median","minimum","maximum","range","mad")]])
    c.write_json_new(output/"plot-manifest.json",dict(reportSha256=c.sha256_file(report_path),toolSha256=c.sha256_file(Path(__file__)),matplotlibVersion=matplotlib.__version__,files={n:c.sha256_file(output/n) for n in ("quality-cost.png","quality-cost.svg","group-statistics.csv")}))
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--report",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--deps",type=Path);a=p.parse_args();render(a.report,a.output,a.deps)
