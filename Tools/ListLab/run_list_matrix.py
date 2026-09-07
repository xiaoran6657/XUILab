"""Run only the explicitly identified Player, serially, with a frozen run plan."""
import argparse
import hashlib
import json
import pathlib
import sys

from verify_list_runs import _assert_no_reparse_components, verify
from resume_list_plan import LOCK_SUFFIX, PlanLock, execute_plan


def write_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def make_plan(args):
    groups = ([(100, 'scroll', -1), (100, 'lifecycle', -1),
               (1000, 'scroll', -1), (1000, 'lifecycle', -1), (1000, 'scroll', 60)]
              if args.plan == 'matrix' else
              [(100, 'scroll', -1), (100, 'lifecycle', -1)] if args.plan == 'pilot' else
              [(300, 'scroll', -1), (10000, 'scroll', -1)])
    repeats = 5 if args.plan == 'matrix' else 1
    order = ['normal', 'virtual', 'virtual', 'normal', 'normal', 'virtual', 'virtual', 'normal', 'normal', 'virtual'] if repeats == 5 else ['normal', 'virtual']
    runs = []
    for count, profile, target in groups:
        indexes = {'normal': 0, 'virtual': 0}
        for backend in order:
            indexes[backend] += 1
            case = f'list-{backend}-{count}-{profile}'
            run_id = f'{args.stamp}-{args.plan}-{case}-{target}-r{indexes[backend]}'
            runs.append(dict(runId=run_id, caseId=case, targetFrameRate=target,
                             runIndex=indexes[backend], plannedRepeatCount=repeats, warmupFrames=300, measureFrames=1800))
    return dict(candidateId=args.candidate, buildId=args.build, sourceRevision=args.source, runs=runs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--player', type=pathlib.Path, required=True)
    parser.add_argument('--root', type=pathlib.Path, default=pathlib.Path('Artifacts'))
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--build', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--stamp', required=True)
    parser.add_argument('--plan', choices=['pilot', 'matrix', 'stress'], required=True)
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    if not args.stamp or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in args.stamp):
        parser.error('stamp must be one safe identifier')
    _assert_no_reparse_components(args.root, 'output root')
    _assert_no_reparse_components(args.player, 'player')
    player = args.player.resolve(strict=True)
    root = args.root.absolute()
    root.mkdir(parents=True, exist_ok=True)
    _assert_no_reparse_components(root, 'output root')
    manifest = make_plan(args)
    manifest_path = root / f'{args.stamp}-{args.plan}-manifest.json'
    # Share the same lock and durable child intents as the resume tool. Freeze
    # creates no Player; a resume that wins the subsequent lock can only execute
    # this exact frozen plan. Every writer then revalidates completed runs.
    lock = PlanLock(root / (manifest_path.name + LOCK_SUFFIX))
    lock.acquire()
    try:
        write_new(manifest_path, manifest)
        binary_files = [player] + sorted((player.parent / (player.stem + '_Data') / 'Managed').glob('XUILab.*.dll'))
        hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in binary_files}
        write_new(root / f'{args.stamp}-{args.plan}-build-hashes.json', hashes)
    finally:
        lock.release()
    execute_plan(root, manifest_path, player, plan=args.plan, timeout_seconds=args.timeout)
    report = verify(root, manifest, plan=args.plan)
    out = root / f'{args.stamp}-{args.plan}-verified.json'
    write_new(out, report)
    print('VERIFIED ' + str(out), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('FAILED: ' + str(error), file=sys.stderr)
        sys.exit(1)
