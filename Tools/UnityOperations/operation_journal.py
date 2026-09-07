"""Durable, fail-closed MCP build/test bookkeeping. Never invokes Unity."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from datetime import datetime, timezone


class JournalError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe(path):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise JournalError(f'link/reparse forbidden: {part}')
    return path


def local(root, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative:
        raise JournalError('expected repository-relative slash path')
    path = safe(root / relative)
    if not path.is_relative_to(root) or '..' in Path(relative).parts or Path(relative).is_absolute():
        raise JournalError('path escapes root')
    return path


def read(path):
    try:
        return json.loads(safe(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise JournalError(f'unreadable record {path}: {exc}') from exc


def write_once(path, value):
    """O_EXCL is the interprocess claim. A torn record remains blocking."""
    safe(path)
    try:
        with path.open('xb') as stream:
            stream.write(canonical(value) + b'\n')
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise JournalError(f'already recorded; inspect, never resend: {path.name}') from exc


def timestamp(value):
    require(isinstance(value, str), 'timestamp must be UTC ISO 8601')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise JournalError('invalid timestamp') from exc
    require(parsed.utcoffset() == timezone.utc.utcoffset(parsed), 'timestamp must have UTC offset')
    return parsed


def now():
    return datetime.now(timezone.utc).isoformat()


def require(value, message):
    if not value:
        raise JournalError(message)


class Journal:
    def __init__(self, root, store=None):
        self.root = safe(root)
        self.store = safe(store or self.root / 'Artifacts/unity-operations')

    def validate_request(self, request):
        require(isinstance(request, dict), 'request must be an object')
        require(request.get('schema') == 'xuilab.unity-operation/v1', 'unknown request schema')
        require(request.get('kind') in ('build', 'test'), 'only single build/test jobs supported')
        for field in ('task', 'candidate', 'attempt', 'instance', 'operator'):
            require(isinstance(request.get(field), str) and request[field].strip(), f'missing {field}')
        require(request.get('project') == 'XUILab', 'project must be XUILab relative to repository')
        require(request.get('editor') == '2022.3.45f1c1', 'wrong Editor')
        require(isinstance(request.get('parameters'), dict) and request['parameters'], 'missing frozen parameters')
        require(isinstance(request.get('inputs'), dict) and request['inputs'], 'missing input hashes')
        for name, expected in request['inputs'].items():
            local(self.root, name)
            require(isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected), 'invalid SHA-256')
        required = ('playing', 'paused', 'compiling', 'importing', 'tests_running', 'build_running', 'prefab_stage', 'dirty_scene')
        pre = request.get('before', {})
        require(all(pre.get(key) is False for key in required), 'unsafe or unknown preflight')
        require(isinstance(request.get('restore_expected'), dict) and request['restore_expected'], 'missing restoration contract')
        artifacts = request.get('artifacts')
        require(isinstance(artifacts, list) and len(artifacts) == len(set(artifacts)), 'invalid artifact list')
        for name in artifacts:
            local(self.root, name)
        if request['kind'] == 'build':
            require(artifacts and request['parameters'].get('output_path') == artifacts[0], 'first artifact must match output_path')
            require(request['parameters'].get('platform'), 'missing build platform')
        else:
            require(request['parameters'].get('mode') in ('EditMode', 'PlayMode'), 'missing test mode')

    def inputs_match(self, request):
        return all(local(self.root, name).is_file() and digest(local(self.root, name)) == expected
                   for name, expected in request['inputs'].items())

    def prepare(self, request):
        self.validate_request(request)
        # Volatile operator/instance/preflight do not generate a fresh dispatch identity.
        frozen = {k: v for k, v in request.items() if k not in ('before', 'instance', 'operator')}
        identity = hashlib.sha256(canonical(frozen)).hexdigest()
        directory = safe(self.store / identity)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / 'request.json'
        if not path.exists():
            try:
                write_once(path, request)
            except JournalError:
                if not path.exists():
                    raise
        existing = read(path)
        require({k: v for k, v in existing.items() if k not in ('before', 'instance', 'operator')} == frozen, 'request collision')
        return identity

    def directory(self, identity):
        require(isinstance(identity, str) and re.fullmatch('[0-9a-f]{64}', identity), 'invalid operation ID')
        return safe(self.store / identity)

    def request(self, identity):
        request = read(self.directory(identity) / 'request.json')
        self.validate_request(request)
        frozen = {k: v for k, v in request.items() if k not in ('before', 'instance', 'operator')}
        require(hashlib.sha256(canonical(frozen)).hexdigest() == identity, 'request identity mismatch')
        return request

    def claim(self, identity):
        request = self.request(identity)
        require(self.inputs_match(request), 'frozen inputs drifted or missing')
        require(not any(local(self.root, name).exists() for name in request['artifacts']), 'output already exists; reconcile or use new dedicated output')
        write_once(self.directory(identity) / 'claim.json', {'at': now(), 'operation': identity})
        return {'action': 'dispatch_once', 'operation': identity}

    def envelope(self, identity, evidence):
        request = self.request(identity)
        require(isinstance(evidence, dict), 'evidence must be an object')
        require(evidence.get('operation') == identity, 'wrong operation')
        require(evidence.get('project_root') == str(self.root / 'XUILab'), 'wrong project root')
        require(evidence.get('candidate') == request['candidate'], 'wrong candidate')
        require(evidence.get('instance') == request['instance'], 'instance changed; reconcile manually')
        timestamp(evidence.get('observed_at'))
        raw = evidence.get('response')
        require(isinstance(raw, dict) and raw.get('success') is True and isinstance(raw.get('data'), dict), 'unsupported/error response; reconcile')
        return request, raw['data']

    def receipt(self, identity, evidence):
        read(self.directory(identity) / 'claim.json')
        _, data = self.envelope(identity, evidence)
        require(isinstance(data.get('job_id'), str) and data['job_id'], 'missing job ID')
        write_once(self.directory(identity) / 'receipt.json', evidence)

    def terminal(self, identity, evidence, validate_only=False):
        request, data = self.envelope(identity, evidence)
        receipt = read(self.directory(identity) / 'receipt.json')
        _, received = self.envelope(identity, receipt)
        require(data.get('job_id') == received['job_id'], 'wrong job ID')
        require(timestamp(evidence['observed_at']) >= timestamp(receipt['observed_at']), 'terminal predates receipt')
        require(self.inputs_match(request), 'inputs changed; cannot bind result to candidate')
        status = data.get('result' if request['kind'] == 'build' else 'status')
        require(status in ('succeeded', 'failed', 'cancelled', 'skipped'), 'no supported terminal state')
        passed = False
        if request['kind'] == 'build':
            require(data.get('platform') == request['parameters']['platform'], 'wrong build platform')
            output = data.get('output_path')
            require(output in (request['artifacts'][0], str(local(self.root, request['artifacts'][0]))), 'wrong build output')
            passed = status == 'succeeded' and type(data.get('errors')) is int and data['errors'] == 0
            if passed:
                require(timestamp(data.get('completed_at')) <= timestamp(evidence['observed_at']), 'completion after observation')
        else:
            require(data.get('mode') == request['parameters']['mode'], 'wrong test mode')
            summary = (data.get('result') or {}).get('summary', {})
            counts = [summary.get(key) for key in ('total', 'passed', 'failed', 'skipped')]
            passed = (status == 'succeeded' and summary.get('resultState') == 'Passed' and all(type(x) is int and x >= 0 for x in counts)
                      and counts[0] > 0 and counts[1] == counts[0] and counts[2:] == [0, 0]
                      and type(data.get('finished_unix_ms')) is int and data['finished_unix_ms'] > 0)
        hashes = {}
        if passed:
            for name in request['artifacts']:
                path = local(self.root, name)
                require(path.is_file() and path.stat().st_size > 0, f'missing/empty artifact: {name}')
                hashes[name] = digest(path)
        record = {'evidence': evidence, 'outcome': 'pass' if passed else 'fail', 'artifacts': hashes}
        if not validate_only:
            write_once(self.directory(identity) / 'terminal.json', record)
        return record

    def restore(self, identity, evidence, validate_only=False):
        request = self.request(identity)
        terminal = read(self.directory(identity) / 'terminal.json')
        require(isinstance(evidence, dict), 'restoration must be an object')
        require(evidence.get('operation') == identity and evidence.get('project_root') == str(self.root / 'XUILab'), 'wrong restoration identity')
        require(timestamp(evidence.get('observed_at')) > timestamp(terminal['evidence']['observed_at']), 'restore must be observed after terminal (UTC ISO timestamp)')
        observed = evidence.get('state', {})
        require(all(observed.get(k) == v for k, v in request['restore_expected'].items()), 'restoration mismatch')
        require(all(observed.get(k) is False for k in ('compiling', 'importing', 'tests_running', 'build_running')), 'operations not idle')
        require(isinstance(evidence.get('raw'), dict) and evidence['raw'], 'missing raw restoration observations')
        if not validate_only:
            write_once(self.directory(identity) / 'restore.json', evidence)

    def inspect(self, identity):
        request = self.request(identity)
        directory = self.directory(identity)
        result = {'operation': identity, 'task': request['task'], 'candidate': request['candidate'], 'outcome': 'not_run', 'restoration': 'not_run'}
        # Parse every existing record; torn files block rather than silently disappear.
        records = {name: read(directory / f'{name}.json') for name in ('claim', 'receipt', 'terminal', 'restore') if (directory / f'{name}.json').exists()}
        keys = list(records)
        require(keys == ['claim', 'receipt', 'terminal', 'restore'][:len(keys)], 'record sequence incomplete')
        if 'claim' in records:
            require(records['claim'].get('operation') == identity, 'claim identity mismatch')
        if 'receipt' in records:
            _, received = self.envelope(identity, records['receipt'])
            require(isinstance(received.get('job_id'), str) and received['job_id'], 'missing job ID')
        if 'claim' not in records:
            result['action'] = 'claim_after_live_preflight' if self.inputs_match(request) else 'reconcile_input_drift'
        elif 'receipt' not in records:
            result['action'] = 'reconcile_lost_receipt_do_not_resend'
        elif 'terminal' not in records:
            result.update(action='poll_existing_job', job_id=records['receipt']['response']['data']['job_id'])
        else:
            terminal = records['terminal']
            intact = all(local(self.root, p).is_file() and digest(local(self.root, p)) == h for p, h in terminal['artifacts'].items())
            if intact and self.inputs_match(request):
                require(self.terminal(identity, terminal['evidence'], validate_only=True) == terminal, 'terminal record inconsistent')
            else:
                intact = False
            if 'restore' in records:
                self.restore(identity, records['restore'], validate_only=True)
            result['outcome'] = terminal['outcome'] if intact else 'fail'
            result['action'] = 'verify_restoration' if 'restore' not in records else 'closed_do_not_resend'
            result['restoration'] = 'pass' if 'restore' in records else 'not_run'
            result['artifacts_intact'] = intact
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--store', type=Path)
    parser.add_argument('action', choices=('prepare', 'claim', 'receipt', 'terminal', 'restore', 'inspect'))
    parser.add_argument('--operation')
    parser.add_argument('--file', type=Path)
    args = parser.parse_args()
    try:
        journal = Journal(args.root, args.store)
        if args.action == 'prepare':
            require(args.file, '--file required')
            result = {'operation': journal.prepare(read(args.file))}
        else:
            require(args.operation, '--operation required')
            if args.action in ('claim', 'inspect'):
                result = getattr(journal, args.action)(args.operation)
            else:
                require(args.file, '--file required')
                getattr(journal, args.action)(args.operation, read(args.file))
                result = journal.inspect(args.operation)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (JournalError, OSError, KeyError, TypeError, AttributeError) as exc:
        print(json.dumps({'error': str(exc), 'action': 'reconcile_do_not_resend'}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
