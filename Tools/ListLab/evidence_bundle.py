"""Portable, byte-preserving List Lab evidence directories. Python stdlib only."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import sys

from verify_list_runs import (_assert_no_reparse_components, _load_manifest,
                              _read_json, _validate_plan_manifest, _validate_run, verify)

SCHEMA = 'xuilab.evidence.bundle/v1'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest().upper()


def relative(value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError('expected portable relative path')
    parts = value.split('/')
    if (PurePosixPath(value).is_absolute() or PureWindowsPath(value).drive or
            any(p in ('', '.', '..') or p.endswith((' ', '.')) or
                re.search(r'[<>:"|?*\x00-\x1f]', p) or
                p.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(i) for i in range(1,10)), *('LPT'+str(i) for i in range(1,10))}
                for p in parts)):
        raise ValueError('unsafe relative path: ' + value)
    return value


def inside(root, name):
    path = Path(root) / relative(name)
    _assert_no_reparse_components(path, 'evidence path')
    return path


def digest(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9A-Fa-f]{64}', value):
        raise ValueError('invalid SHA-256')
    return value.upper()


def write_new(path, value):
    _assert_no_reparse_components(path, 'new output')
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def catalog_validate(catalog):
    fields = {'schemaVersion', 'evidenceId', 'candidateId', 'buildId', 'sourceRevision',
              'recordedRoot', 'artifactRoot', 'buildRoot', 'player', 'plans', 'snapshots', 'scope'}
    if not isinstance(catalog, dict) or set(catalog) != fields or catalog['schemaVersion'] != 'xuilab.evidence.catalog/v1':
        raise ValueError('invalid evidence catalog')
    for key in ('evidenceId', 'candidateId', 'buildId', 'sourceRevision', 'recordedRoot', 'scope'):
        if not isinstance(catalog[key], str) or not catalog[key].strip():
            raise ValueError('missing catalog ' + key)
    for key in ('artifactRoot', 'buildRoot', 'player'):
        relative(catalog[key])
    if not catalog['player'].startswith(catalog['buildRoot'] + '/'):
        raise ValueError('player outside build root')
    if not isinstance(catalog['plans'], dict) or not catalog['plans'] or set(catalog['plans']) - {'pilot','matrix','stress'}:
        raise ValueError('invalid catalog plans')
    for name in catalog['plans'].values():
        relative(name)
        if '/' in name:
            raise ValueError('manifest must be directly in artifact root')
    if not isinstance(catalog['snapshots'], list) or not catalog['snapshots']:
        raise ValueError('snapshots required')
    for item in catalog['snapshots']:
        if not isinstance(item, dict) or set(item) != {'path', 'sha256', 'prefixes'}:
            raise ValueError('invalid snapshot selector')
        relative(item['path']); digest(item['sha256'])
        if not isinstance(item['prefixes'], list) or not item['prefixes']:
            raise ValueError('snapshot needs explicit prefixes')
        for prefix in item['prefixes']:
            relative(prefix)
    return catalog


def selected_files(repo, catalog):
    """Select only files pinned by the catalog's immutable historical snapshots."""
    selected = {}
    folded = {}
    def add(name, expected):
        relative(name); expected = digest(expected)
        if name.casefold() in folded and folded[name.casefold()] != name:
            raise ValueError('case-colliding paths')
        if name in selected and selected[name] != expected:
            raise ValueError('conflicting snapshot hashes')
        selected[name] = expected
        folded[name.casefold()] = name
    for entry in catalog['snapshots']:
        path = inside(repo, entry['path'])
        if sha(path) != digest(entry['sha256']):
            raise ValueError('snapshot changed: ' + entry['path'])
        add(entry['path'], entry['sha256'])
        matches = {p: 0 for p in entry['prefixes']}
        seen = set()
        for line in path.read_text(encoding='utf-8').splitlines():
            expected, name = line.split('  ', 1)
            relative(name); digest(expected)
            if name.casefold() in seen:
                raise ValueError('duplicate snapshot path')
            seen.add(name.casefold())
            for prefix in matches:
                if name == prefix or name.startswith(prefix + '/'):
                    add(name, expected); matches[prefix] += 1
        if not all(matches.values()):
            raise ValueError('empty snapshot selection')
    if catalog['player'] not in selected:
        raise ValueError('player is not pinned')
    for filename in catalog['plans'].values():
        if catalog['artifactRoot'] + '/' + filename not in selected:
            raise ValueError('plan is not pinned')
    return selected


def pack(repo, catalog_path, out):
    repo, out = Path(repo).absolute(), Path(out).absolute()
    _assert_no_reparse_components(catalog_path, 'catalog')
    catalog = catalog_validate(_read_json(Path(catalog_path)))
    selected = selected_files(repo, catalog)
    # All inputs must validate before creating output. Never merge into a directory.
    for name, expected in selected.items():
        if sha(inside(repo, name)) != expected:
            raise ValueError('source hash mismatch: ' + name)
    _assert_no_reparse_components(out, 'bundle output')
    if out == repo or repo in out.parents and any(out == inside(repo, n).parent or out in inside(repo, n).parents for n in selected):
        raise ValueError('output overlaps selected inputs')
    out.mkdir(parents=True, exist_ok=False)
    files = []
    for name, expected in sorted(selected.items()):
        target = inside(out, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as dest, inside(repo, name).open('rb') as source:
            shutil.copyfileobj(source, dest)
        if sha(target) != expected:
            raise ValueError('input changed during copy: ' + name)
        files.append({'path': name, 'sha256': expected, 'size': target.stat().st_size})
    write_new(out/'bundle.json', {'schemaVersion': SCHEMA, 'catalog': catalog, 'files': files})
    return {'bundle': str(out), 'indexSha256': sha(out/'bundle.json'), 'fileCount': len(files)}


def check_integrity(bundle, expected_index=None):
    bundle = Path(bundle).absolute()
    _assert_no_reparse_components(bundle, 'bundle')
    index_path = inside(bundle, 'bundle.json')
    index_sha = sha(index_path)
    if expected_index is not None and index_sha != digest(expected_index):
        raise ValueError('bundle index SHA mismatch')
    index = _read_json(index_path)
    if not isinstance(index, dict) or set(index) != {'schemaVersion','catalog','files'} or index['schemaVersion'] != SCHEMA:
        raise ValueError('invalid bundle index')
    catalog_validate(index['catalog'])
    if not isinstance(index['files'], list) or not index['files']:
        raise ValueError('empty bundle')
    expected, folded = {}, set()
    for item in index['files']:
        if not isinstance(item, dict) or set(item) != {'path','sha256','size'}:
            raise ValueError('invalid file entry')
        name = relative(item['path'])
        if name == 'bundle.json' or name.casefold() in folded or type(item['size']) is not int or item['size'] < 0:
            raise ValueError('duplicate/reserved path or invalid size')
        folded.add(name.casefold()); expected[name] = digest(item['sha256'])
        path = inside(bundle, name)
        if not path.is_file() or path.stat().st_size != item['size'] or sha(path) != expected[name]:
            raise ValueError('bundle file mismatch: ' + name)
    actual = set()
    for parent, dirs, files in os.walk(bundle, followlinks=False):
        for name in dirs + files:
            _assert_no_reparse_components(Path(parent)/name, 'bundle member')
        actual.update((Path(parent)/name).relative_to(bundle).as_posix() for name in files)
    if actual != set(expected) | {'bundle.json'}:
        raise ValueError('bundle contains unindexed files')
    # Reconstruct the selection from pinned snapshots, preventing an index from
    # silently dropping a raw file or changing historical hashes.
    if selected_files(bundle, index['catalog']) != expected:
        raise ValueError('bundle selection differs from historical snapshots')
    return index, index_sha


def check_receipt(root, spec, record):
    path = inside(root, spec['runId'] + '-receipt.json')
    receipt = _read_json(path)
    if (receipt.get('runId') != spec['runId'] or type(receipt.get('exitCode')) is not int or
            receipt['exitCode'] != 0 or type(receipt.get('pid')) is not int or receipt['pid'] <= 0 or
            digest(receipt.get('artifactSetSha256')) != digest(record['artifactSetSha256']) or
            not isinstance(receipt.get('completedUtc'), str) or not receipt['completedUtc']):
        raise ValueError('invalid or mismatched receipt: ' + spec['runId'])
    duration = receipt.get('durationSeconds')
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0:
        raise ValueError('invalid receipt duration')


def check_failure(path, run_id):
    _assert_no_reparse_components(path, 'failure')
    failure = _read_json(path)
    if (not isinstance(failure, dict) or failure.get('runId') != run_id or
            type(failure.get('timeout')) is not bool or
            not isinstance(failure.get('reason'), str) or not failure['reason'].strip() or
            type(failure.get('durationSeconds')) not in (int, float) or
            not math.isfinite(failure['durationSeconds']) or failure['durationSeconds'] < 0 or
            failure.get('pid') is not None and (type(failure['pid']) is not int or failure['pid'] <= 0) or
            failure.get('exitCode') is not None and type(failure['exitCode']) is not int):
        raise ValueError('invalid failure sidecar: ' + run_id)
    return failure


def audit(bundle, expected_index=None):
    index, index_sha = check_integrity(bundle, expected_index)
    catalog = index['catalog']; root = inside(bundle, catalog['artifactRoot'])
    plans = {}
    for plan, filename in catalog['plans'].items():
        manifest = _load_manifest(inside(root, filename))
        _validate_plan_manifest(manifest, plan)
        for key in ('candidateId','buildId','sourceRevision'):
            if manifest[key] != catalog[key]:
                raise ValueError('manifest/catalog identity mismatch: ' + key)
        records, failures = [], []
        for spec in manifest['runs']:
            fail_path = inside(root, spec['runId'] + '-orchestration-failure.json')
            if fail_path.exists():
                check_failure(fail_path, spec['runId'])
                if inside(root, spec['runId'] + '-receipt.json').exists():
                    raise ValueError('conflicting receipt and failure')
                failures.append({'runId': spec['runId'], 'result': 'failed', 'timeout': _read_json(fail_path)['timeout']})
            else:
                result = _validate_run(root, spec, manifest, recorded_root=catalog['recordedRoot'])
                check_receipt(root, spec, result['record'])
                records.append(result['record'])
        report = (verify(root, manifest, plan, recorded_root=catalog['recordedRoot']) if not failures else None)
        plans[plan] = {'correctness': 'pass' if not failures else 'incomplete',
                       'measurementValidity': 'valid' if not failures else 'partial',
                       'performanceComparison': 'not_assessed', 'validRuns': len(records),
                       'failedRuns': failures, 'report': report, 'runs': records if failures else []}
    return {'schemaVersion':'xuilab.evidence.audit/v1', 'indexSha256':index_sha,
            'integrity':'pass', 'evidenceId':catalog['evidenceId'], 'candidateId':catalog['candidateId'],
            'buildId':catalog['buildId'], 'sourceRevision':catalog['sourceRevision'],
            'relocation': {'recordedRoot':catalog['recordedRoot'], 'physicalRoot':str(root)}, 'plans':plans}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('pack'); p.add_argument('--repo', type=Path, default=Path('.'))
    p.add_argument('--catalog', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('check'); p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--expected-index-sha256'); p.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'pack':
            result = pack(args.repo, args.catalog, args.out)
        else:
            result = audit(args.bundle, args.expected_index_sha256)
            if args.out:
                output = args.out.absolute(); base = args.bundle.absolute()
                if output == base or base in output.parents:
                    raise ValueError('audit output must be outside immutable bundle')
                write_new(output, result)
            result = {k:v for k,v in result.items() if k != 'plans'} | {'plans':{
                k:{a:b for a,b in v.items() if a not in ('report','runs')} for k,v in result['plans'].items()}}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print('EVIDENCE FAILED: ' + str(exc), file=sys.stderr); return 1


if __name__ == '__main__':
    raise SystemExit(main())
