"""Export a frozen, explicitly allowlisted showcase bundle; never publish or use Git."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import struct

SCHEMA = 'xuilab.public-assets/v1'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def safe_join(root, relative):
    root = Path(root).absolute()
    if not isinstance(relative, str) or '\\' in relative or ':' in relative:
        raise ValueError('portable relative path required')
    parts = relative.split('/')
    if not parts or any(not p or p in ('..', '.') or p.rstrip(' .') != p for p in parts):
        raise ValueError('unsafe path')
    if any(re.fullmatch(r'(?i)(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', part) for part in parts):
        raise ValueError('reserved Windows path')
    path = root.joinpath(*parts)
    for parent in (path, *path.parents):
        if parent.exists() or parent.is_symlink():
            info = parent.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('symlink/reparse point rejected')
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('path escapes root')
    return path

def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs)

def inspect_text(path):
    if path.suffix.lower() not in ('.json', '.md', '.csv', '.txt', '.vtt'):
        return
    inspect_public_text(path.read_text(encoding='utf-8'),path.name)

def inspect_public_text(text, name='metadata'):
    rules = [r'(?i)\b[a-z]:[\\/]', r'(?i)(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}',
             r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
             r'(?i)[\\/]Users[\\/][^\\/\s]+', r'(?i)\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b']
    if any(re.search(rule, text) for rule in rules):
        raise ValueError('public text contains a blocked identity/credential pattern: ' + name)

def validate_plan(plan):
    if plan.get('schema') != SCHEMA or not isinstance(plan.get('files'), list):
        raise ValueError('invalid plan schema')
    seen = set()
    for item in plan['files']:
        name = item['path'].casefold()
        if name in seen or name == 'manifest.json': raise ValueError('duplicate/reserved output')
        seen.add(name)
        if not re.fullmatch('[a-f0-9]{64}', item['sha256']): raise ValueError('invalid digest')
        if not isinstance(item['bytes'], int) or item['bytes'] < 0: raise ValueError('invalid size')
    if not seen: raise ValueError('empty export rejected')

def export(root, plan_path, output):
    plan = read_json(plan_path)
    validate_plan(plan)
    output = Path(output).absolute()
    # Validate the whole selection before creating or copying anything.
    if output.exists(): raise ValueError('output must be a new directory')
    sources = []
    for item in plan['files']:
        source = safe_join(root, item['source'])
        target = safe_join(output, item['path'])
        if not source.is_file() or source.stat().st_size != item['bytes'] or digest(source) != item['sha256']:
            raise ValueError('frozen source mismatch: ' + item['source'])
        inspect_text(source)
        if source.suffix == '.png':
            data = source.read_bytes()
            if data[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack('>II',data[16:24]) != (item['width'],item['height']):
                raise ValueError('PNG dimensions mismatch')
        sources.append((source, target))
    public = {k:v for k,v in plan.items() if k != 'files'}
    public['files'] = [{k:v for k,v in item.items() if k != 'source'} for item in plan['files']]
    public['inputPlanSha256'] = digest(plan_path)
    payload=json.dumps(public,ensure_ascii=False,indent=2)+'\n'
    inspect_public_text(payload)
    output.mkdir(parents=True)
    for source, target in sources:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (output/'manifest.json').write_text(payload,encoding='utf-8')
    return verify(output)

def verify(root, expected_manifest_sha256=None):
    root = Path(root).absolute()
    manifest_path = safe_join(root, 'manifest.json')
    if expected_manifest_sha256 is not None and digest(manifest_path) != expected_manifest_sha256:
        raise ValueError('external manifest hash mismatch')
    inspect_text(manifest_path)
    manifest = read_json(manifest_path)
    validate_plan(manifest)
    expected = {'manifest.json'}
    for item in manifest['files']:
        target = safe_join(root,item['path'])
        if not target.is_file() or target.stat().st_size != item['bytes'] or digest(target) != item['sha256']:
            raise ValueError('asset mismatch: ' + item['path'])
        inspect_text(target)
        expected.add(item['path'])
    actual = set()
    # Reject reparse points before traversing their children.
    pending = [root]
    while pending:
        for child in pending.pop().iterdir():
            safe_join(root, child.relative_to(root).as_posix())
            if child.is_dir(): pending.append(child)
            else: actual.add(child.relative_to(root).as_posix())
    if actual != expected: raise ValueError('unexpected or missing asset')
    return {'status':'pass','files':len(manifest['files']),'manifestSha256':digest(manifest_path),'externalManifestHash':'matched' if expected_manifest_sha256 else 'not_supplied'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    e=sub.add_parser('export');e.add_argument('--root',type=Path,required=True);e.add_argument('--plan',type=Path,required=True);e.add_argument('--output',type=Path,required=True)
    v=sub.add_parser('verify');v.add_argument('--root',type=Path,required=True);v.add_argument('--expected-manifest-sha256',required=True)
    args=parser.parse_args()
    try:
        result=export(args.root,args.plan,args.output) if args.command=='export' else verify(args.root,args.expected_manifest_sha256)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps({'status':'fail','error':str(exc)},ensure_ascii=False));return 1
    print(json.dumps(result));return 0

if __name__=='__main__': raise SystemExit(main())
