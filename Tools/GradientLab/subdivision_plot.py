"""Plot verified G1 results; optional local matplotlib dependencies, no sampling."""
import argparse,csv,json,os,sys
from pathlib import Path
import gradient_experiment as contracts
from player_verify import read,need

def render(report_path,output,deps=None):
    need(not output.exists(),"Plot output must be new");output.mkdir(parents=True)
    if deps:sys.path.insert(0,str(deps.resolve()))
    os.environ["MPLCONFIGDIR"]=str(output/".matplotlib-cache")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    r=read(report_path);need(r["status"]=="pass" and r["runCount"]==160,"Verified complete report required")
    segments=[8,16,32,64];groups={(g["scenario"],g["segments"]):g for g in r["groups"]}
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False})
    fig,axes=plt.subplots(1,3,figsize=(15,4.8));colors=["#3988af","#4b9986","#8069a0","#d18b46"]
    ax=axes[0]
    for scenario,label,color in (("large-static-05","bias 0.05","#3988af"),("large-static-95","bias 0.95","#d18b46")):
        values=[groups[scenario,s]["statistics"]["qualityMaxError"]["median"] for s in segments]
        ax.plot(segments,values,"o-",label=label,color=color)
    ax.axhline(.01,color="#b34f53",ls="--",label="Target 0.01")
    ax.set_yscale("log");ax.set_xticks(segments);ax.set_xlabel("Uniform segments");ax.set_ylabel("Continuous RGBA max error")
    ax.set_title("Quality: all four exceed target");ax.legend(fontsize=9);ax.grid(axis="y",alpha=.2)
    ax=axes[1]
    for i,s in enumerate(segments):
        g=groups["grid-dynamic",s];stat=g["statistics"]["p95"];v=stat["median"]
        ax.errorbar(i,v,yerr=[[v-stat["minimum"]],[stat["maximum"]-v]],fmt="o",color=colors[i],capsize=5)
        ax.scatter([i+(j-2)*.035 for j in range(5)],[x["p95"] for x in g["runs"]],color=colors[i],alpha=.45,s=20)
        ax.text(i,v+.8,f"{v:.2f}",ha="center",fontsize=10)
    ax.axhline(16.6666667,color="#b34f53",ls="--",lw=1);ax.set_ylim(0,19)
    ax.set_xticks(range(4),segments);ax.set_xlabel("Uniform segments");ax.set_ylabel("Frame interval p95 (ms)")
    ax.set_title("100 dynamic components");ax.grid(axis="y",alpha=.2)
    ax=axes[2]
    for scenario,label,color in (("large-static-05","1 component","#3988af"),("grid-static-05","100 components","#d18b46")):
        stats=[groups[scenario,s]["statistics"]["coldPrepareMs"] for s in segments];values=[x["median"] for x in stats]
        ax.errorbar(segments,values,yerr=[[x["median"]-x["minimum"] for x in stats],[x["maximum"]-x["median"] for x in stats]],fmt="o-",label=label,color=color,capsize=4)
    ax.set_xticks(segments);ax.set_xlabel("Uniform segments");ax.set_ylabel("Cold Prepare wall time (ms)")
    ax.set_title("Creation + initial Canvas flush");ax.legend(fontsize=9);ax.grid(axis="y",alpha=.2)
    fig.suptitle("Fixed subdivisions: quality and measured cost",fontsize=16)
    fig.text(.015,.025,"Five processes per configuration; markers/whiskers show median and full range. Frame interval is not CPU/GPU time.\nQuality excludes Color32 quantization; all dynamic configurations are quality_limited. Dirty-source exploratory candidate, Windows Development Player.",fontsize=9,color="#444444")
    fig.tight_layout(rect=(0,.10,1,.94));fig.savefig(output/"quality-cost.png",dpi=180);fig.savefig(output/"quality-cost.svg");plt.close(fig)
    with (output/"group-statistics.csv").open("x",newline="",encoding="utf-8") as f:
        writer=csv.writer(f);writer.writerow(["scenario","segments","metric","median","minimum","maximum","range","mad"])
        for g in r["groups"]:
            for metric,s in g["statistics"].items():writer.writerow([g["scenario"],g["segments"],metric,*[s[k] for k in ("median","minimum","maximum","range","mad")]])
    contracts.write_json_new(output/"plot-manifest.json",dict(reportSha256=contracts.sha256_file(report_path),toolSha256=contracts.sha256_file(Path(__file__)),matplotlibVersion=matplotlib.__version__,files={n:contracts.sha256_file(output/n) for n in ("quality-cost.png","quality-cost.svg","group-statistics.csv")}))

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--report",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--deps",type=Path);a=p.parse_args();render(a.report,a.output,a.deps)
