"""Read-only static roadmap coverage and new-task acceptance binding checks."""
import argparse
import json
from pathlib import Path
import re

from check_pm import Checker

TASK = re.compile(r'M[0-4]-(?:\d+|[LG]\d+)')


def require(value, message):
    if not value:
        raise ValueError(message)


def check(root):
    root = root.resolve()
    errors = []
    try:
        data = json.loads((root/'Docs/Agents/acceptance-map.json').read_text(encoding='utf-8'))
        require(data['schemaVersion'] == 'xuilab.acceptance-map/v1', 'unknown map schema')
        tasks = data['tasks']; criteria = data['criteria']
        require(isinstance(tasks, list) and isinstance(criteria, list), 'map lists missing')
        task_ids = [row['taskId'] for row in tasks]
        ids = [row['id'] for row in criteria]
        require(len(task_ids) == len(set(task_ids)), 'duplicate task IDs')
        require(len(ids) == len(set(ids)), 'duplicate acceptance IDs')
        roadmap = (root/'Docs/MVP/ROADMAP.md').read_text(encoding='utf-8')
        expected_rows = {}
        for line in roadmap.splitlines():
            cells = [part.strip() for part in line.strip('|').split('|')]
            if cells and TASK.fullmatch(cells[0]): expected_rows[cells[0]] = line
        require(set(task_ids) == set(expected_rows), 'roadmap task coverage mismatch')
        by_task = {row['taskId']: row for row in tasks}
        by_id = {row['id']: row for row in criteria}
        forbidden = {'state','result','candidate','accepted','owner','done'}
        sources = {}
        def source(name):
            path = (root/name).resolve()
            require(path.is_relative_to(root) and path.is_file(), 'source missing or escapes root')
            if name not in sources: sources[name] = path.read_text(encoding='utf-8')
            return sources[name]
        for row in tasks:
            require(not (forbidden & row.keys()), 'dynamic state forbidden in map')
            require(row['stage'] == row['taskId'].split('-')[0], 'wrong stage')
            source(row['source'])
            require(row['evidenceKinds'] and all(isinstance(v,str) and v for v in row['evidenceKinds']), 'evidence kinds missing')
            require(isinstance(row['dependsOn'],list) and len(row['dependsOn']) == len(set(row['dependsOn'])), 'invalid dependencies')
            require(all(dep in by_task and dep != row['taskId'] for dep in row['dependsOn']), 'unknown/self dependency')
            for dep in row.get('conditionalDependsOn',[]):
                require(dep['taskId'] in by_task and dep['condition'], 'invalid conditional dependency')
            require(row['acceptanceIds'] and len(row['acceptanceIds']) == len(set(row['acceptanceIds'])), 'empty/duplicate binding')
            for cid in row['acceptanceIds']:
                require(cid in by_id and by_id[cid]['taskId'] == row['taskId'], 'wrong task acceptance binding')
            delivery = by_id[row['taskId']+'-DELIVERY']
            require(delivery['sourceText'] == expected_rows[row['taskId']], 'roadmap delivery changed; revise map explicitly')
        for row in criteria:
            require(not (forbidden & row.keys()), 'dynamic criterion state forbidden')
            require(row['requirement'] == 'required', 'required criterion weakened')
            require(row['taskId'] in by_task and row['id'] in by_task[row['taskId']]['acceptanceIds'], 'unbound criterion')
            require(row['description'] and row['sourceText'] in source(row['source']).splitlines(), 'source quote changed or missing')
        for stage in ('M0','M1','M2','M3','M4'):
            stage_rows = [r for r in tasks if r['stage']==stage]
            path = stage_rows[0]['source']
            require(all(r['source']==path for r in stage_rows), 'stage source mismatch')
            section = source(path).split('## 9.',1)[1].split('\n## ',1)[0]
            quotes = [line for line in section.splitlines() if line.startswith('- ') or line.startswith('学习检查：')]
            mapped = [r for r in criteria if r['id'].startswith(stage+'-EXIT-')]
            require(len(mapped)==len(quotes) and {r['sourceText'] for r in mapped}==set(quotes), 'stage exit coverage mismatch')
        visiting, visited = set(), set()
        def visit(tid):
            require(tid not in visiting, 'dependency cycle')
            if tid in visited:return
            visiting.add(tid)
            deps=by_task[tid]['dependsOn']+[r['taskId'] for r in by_task[tid].get('conditionalDependsOn',[])]
            for dep in deps:visit(dep)
            visiting.remove(tid);visited.add(tid)
        for tid in task_ids:visit(tid)
        # Legacy historical records are not retroactively migrated or accepted.
        for tid,row in by_task.items():
            status=root/'Docs/PM/Tasks'/tid/'TASK_STATUS.md'
            if not status.exists() or '- pm_schema: xuilab.pm/v1' not in status.read_text(encoding='utf-8'):continue
            brief=(status.parent/'TASK_BRIEF.md').read_text(encoding='utf-8')
            require('## 路线图验收映射' in brief, f'{tid}: missing Brief mapping')
            section=brief.split('## 路线图验收映射',1)[1].split('\n## ',1)[0]
            bindings=[]
            for line in section.splitlines():
                cells=[part.strip() for part in line.strip('|').split('|')]
                if len(cells)==2 and cells[0] in by_id:bindings.append(cells)
            require(len(bindings)==len(row['acceptanceIds']) and {a for a,b in bindings}==set(row['acceptanceIds']), f'{tid}: required bindings missing/duplicated')
            matrix=brief.split('## 验收矩阵',1)[1].split('\n## ',1)[0]
            required=set()
            for line in matrix.splitlines():
                cells=[p.strip() for p in line.strip('|').split('|')]
                if len(cells)>=3 and cells[1]=='required':required.add(cells[0])
            require(all(b in required for a,b in bindings), f'{tid}: binding must target required Brief ID')
    except (OSError,ValueError,KeyError,TypeError,AttributeError,IndexError,AssertionError) as exc:
        errors.append(str(exc) or type(exc).__name__)
    checker=Checker(root)
    for path in (root/'.agents/skills').glob('*/SKILL.md'):
        checker.links(path,checker.read(path))
    errors.extend(checker.result.errors)
    return errors


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    args=parser.parse_args();errors=check(args.root)
    for error in errors:print('ERROR:',error)
    print('Acceptance mapping '+('FAIL' if errors else 'PASS')+'; structure only, no task acceptance inferred')
    return 1 if errors else 0


if __name__=='__main__':raise SystemExit(main())
