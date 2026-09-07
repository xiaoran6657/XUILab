"""Revalidate a portable bundle and derive matrix comparison SVG/JSON/Markdown."""
import argparse
import html
import json
from pathlib import Path
import sys

from evidence_bundle import audit, write_new
from verify_list_runs import _assert_no_reparse_components


def comparison(report):
    if report is None or report['plan'] != 'matrix' or report['runCount'] != 50:
        raise ValueError('chart requires a complete verified 50-run matrix')
    groups = {(r['caseId'], r['targetFrameRate']): r for r in report['aggregates']}
    rows = []
    for count, profile, fps in [(100,'scroll',-1), (100,'lifecycle',-1), (1000,'scroll',-1),
                                 (1000,'lifecycle',-1), (1000,'scroll',60)]:
        a,b = (groups[(f'list-{backend}-{count}-{profile}',fps)]['p95FrameIntervalMs']
               for backend in ('normal','virtual'))
        distinct = a['minimum'] > b['maximum'] or b['minimum'] > a['maximum']
        robust = abs(a['median']-b['median']) > a['mad']+b['mad']
        direction = ('improved' if b['median'] < a['median'] else 'regressed') if distinct and robust else 'inconclusive'
        rows.append({'count':count, 'profile':profile, 'fps':fps, 'normal':a, 'virtual':b, 'comparison':direction})
    return rows


def svg(rows, report):
    escape = lambda s: html.escape(str(s), quote=True)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1040 600" role="img" aria-labelledby="title desc">',
             '<title id="title">List Lab per-run p95 frame interval</title>',
             '<desc id="desc">Five processes per backend; dots are medians, lines are minimum to maximum. Frame interval is not component CPU time.</desc>',
             '<rect width="1040" height="600" fill="#f6f8fb"/>',
             '<g font-family="Arial, sans-serif" fill="#182b43">']
    def text(x,y,value,size=12,color='#182b43'):
        parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}">{escape(value)}</text>')
    text(32,38,'List Lab | per-run p95 frame interval',24)
    text(32,65,'5 processes per backend | dots: median | lines: min–max')
    text(32,85,'Historical candidate; frame interval is not component CPU time.')
    maximum = max(s['maximum'] for r in rows for s in (r['normal'],r['virtual'])) * 1.15
    if maximum <= 0:
        raise ValueError('p95 scale must be positive')
    pos = lambda v: 320 + v/maximum*615
    for tick in range(6):
        v=maximum*tick/5; x=pos(v)
        parts.append(f'<path d="M {x:.2f} 110 V 460" stroke="#dce2e9"/>')
        text(round(x-12,2),485,f'{v:.1f}',11)
    for i,row in enumerate(rows):
        y=138+i*68
        text(32,y, f"N={row['count']} {row['profile']} / " + ('uncapped' if row['fps']==-1 else '60 FPS'))
        text(32,y+19,row['comparison'],11)
        for offset,backend,color in [(0,'normal','#527fbf'),(22,'virtual','#008b83')]:
            stat=row[backend]; yy=y+offset
            parts.append(f'<path d="M {pos(stat["minimum"]):.2f} {yy} H {pos(stat["maximum"]):.2f}" stroke="{color}" stroke-width="3"/>')
            parts.append(f'<circle cx="{pos(stat["median"]):.2f}" cy="{yy}" r="4" fill="{color}"/>')
            text(round(pos(stat['maximum'])+8,2), yy+4, f'{stat["median"]:.2f}', 11, color)
    text(750,510,'Frame interval (ms)')
    text(32,515,'Normal ScrollRect',13,'#527fbf'); text(205,515,'Virtual window',13,'#008b83')
    text(32,551,report['candidateId']+' | '+report['buildId'],11)
    text(32,575,'Exploratory comparison: disjoint ranges and median difference > sum of MADs; otherwise inconclusive.',10)
    parts.append('</g></svg>')
    return '\n'.join(parts)+'\n'


def generate(bundle, out, expected_index=None):
    bundle, out = Path(bundle).absolute(), Path(out).absolute()
    if out == bundle or bundle in out.parents:
        raise ValueError('derived output must be outside immutable bundle')
    result = audit(bundle, expected_index)
    report = result['plans'].get('matrix',{}).get('report')
    rows = comparison(report)
    drawing = svg(rows, report)
    lines = ['# List Lab derived matrix', '',
             'Recomputed from original raw bytes. Per-run statistics; no frame concatenation.', '',
             f"Candidate: `{report['candidateId']}`; build: `{report['buildId']}`.",
             f"Bundle index SHA-256: `{result['indexSha256']}`.", '',
             '| N / action / FPS | Normal median [min, max]; MAD / IQR ms | Virtual median [min, max]; MAD / IQR ms | Comparison |',
             '| --- | --- | --- | --- |']
    def fmt(s):
        return f"{s['median']:.3f} [{s['minimum']:.3f}, {s['maximum']:.3f}]; {s['mad']:.3f} / {s['iqr']:.3f}"
    for row in rows:
        lines.append(f"| {row['count']} / {row['profile']} / {row['fps']} | {fmt(row['normal'])} | {fmt(row['virtual'])} | {row['comparison']} |")
    lines += ['', 'Direction is exploratory, not a significance test. Missing optional metrics remain unavailable.',
              'Stress failures are retained in audit.json and are not plotted as successful observations.']
    _assert_no_reparse_components(out, 'chart output'); out.mkdir(parents=True, exist_ok=False)
    write_new(out/'audit.json',result)
    write_new(out/'comparison.json',rows)
    with (out/'p95-comparison.svg').open('x',encoding='utf-8',newline='\n') as f: f.write(drawing)
    with (out/'tables.md').open('x',encoding='utf-8',newline='\n') as f: f.write('\n'.join(lines)+'\n')
    return {'output':str(out), 'indexSha256':result['indexSha256'], 'matrixRuns':report['runCount'], 'rows':len(rows)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True); parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--expected-index-sha256')
    args=parser.parse_args(argv)
    try:
        print(json.dumps(generate(args.bundle,args.out,args.expected_index_sha256),indent=2)); return 0
    except Exception as exc:
        print('ANALYSIS FAILED: '+str(exc),file=sys.stderr); return 1


if __name__=='__main__': raise SystemExit(main())
