"""Run only the explicitly identified Player, serially, with a frozen run plan."""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
import sys
import time

from verify_list_runs import _assert_no_reparse_components, _validate_run, verify


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
    write_new(manifest_path, manifest)
    binary_files = [player] + sorted((player.parent / (player.stem + '_Data') / 'Managed').glob('XUILab.*.dll'))
    hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in binary_files}
    write_new(root / f'{args.stamp}-{args.plan}-build-hashes.json', hashes)
    for spec in manifest['runs']:
        run_id = spec['runId']
        if (root / run_id).exists():
            raise RuntimeError('Refusing to overwrite ' + run_id)
        for path, expected in hashes.items():
            if hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest() != expected:
                raise RuntimeError('Build changed after plan freeze')
        log = root / (run_id + '-player.log')
        cmd = [str(player), '-screen-fullscreen', '0', '-screen-width', '960', '-screen-height', '540', '-force-d3d11',
               '-logFile', str(log), '--xuilab-run', '--xuilab-quit', '--xuilab-output-root', str(root),
               '--xuilab-run-id', run_id, '--xuilab-case', spec['caseId'], '--xuilab-series-id', args.stamp + '-' + args.plan,
               '--xuilab-run-index', str(spec['runIndex']), '--xuilab-repeat-count', str(spec['plannedRepeatCount']),
               '--xuilab-warmup-frames', str(spec['warmupFrames']), '--xuilab-measure-frames', str(spec['measureFrames']),
               '--xuilab-sample-capacity', str(spec['measureFrames']), '--xuilab-target-frame-rate', str(spec['targetFrameRate']),
               '--xuilab-vsync-count', '0', '--xuilab-candidate-id', args.candidate, '--xuilab-build-id', args.build,
               '--xuilab-source-revision', args.source]
        process = None
        started = time.monotonic()
        try:
            print('START ' + run_id, flush=True)
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            # Visible interactive Player is required: SW_HIDE produced black captures
            # and cannot establish a visible rendering benchmark on this machine.
            startup.wShowWindow = 1
            process = subprocess.Popen(cmd, startupinfo=startup, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            code = process.wait(timeout=args.timeout)
            if code != 0:
                raise RuntimeError(f'Player exit {code}; see {log.name}')
            result = _validate_run(root, spec, manifest)
            print('PASS ' + run_id + ' p95=' + str(result['record']['p95FrameIntervalMs']), flush=True)
            write_new(root / (run_id + '-receipt.json'), dict(runId=run_id, pid=process.pid, exitCode=code,
                      durationSeconds=time.monotonic()-started, completedUtc=dt.datetime.now(dt.timezone.utc).isoformat(),
                      artifactSetSha256=result['record']['artifactSetSha256']))
        except Exception as exc:
            timed_out = isinstance(exc, subprocess.TimeoutExpired)
            if process is not None and process.poll() is None:
                process.kill()  # Only the exact process created above.
                process.wait(timeout=15)
            failure = dict(runId=run_id, pid=process.pid if process else None, timeout=timed_out,
                           exitCode=process.returncode if process else None, reason=str(exc),
                           durationSeconds=time.monotonic()-started)
            write_new(root / (run_id + '-orchestration-failure.json'), failure)
            raise
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
