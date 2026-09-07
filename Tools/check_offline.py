"""Single read-only entry for PM, acceptance mapping and optional List evidence checks."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--bundle',type=Path)
    parser.add_argument('--expected-index-sha256')
    args=parser.parse_args()
    result={'python':sys.version.split()[0], 'dependencies':'stdlib only; Python >=3.11',
            'unity':'not_run', 'player':'not_run', 'evidence':'not_run'}
    if sys.version_info < (3,11):
        print('Python >=3.11 required',file=sys.stderr); return 1
    commands={name:[sys.executable,'-B',str(args.root/'Tools/ProjectManagement'/script),'--root',str(args.root)] for name,script in (('pm','check_pm.py'),('acceptance','check_acceptance.py'))}
    if args.bundle:
        commands['evidence']=[sys.executable,'-B',str(args.root/'Tools/ListLab/evidence_bundle.py'),'check','--bundle',str(args.bundle)]
        if args.expected_index_sha256: commands['evidence']+=['--expected-index-sha256',args.expected_index_sha256]
    elif args.expected_index_sha256:
        parser.error('--expected-index-sha256 requires --bundle')
    success=True
    for name,command in commands.items():
        run=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace')
        result[name]={'exitCode':run.returncode,'stdout':run.stdout,'stderr':run.stderr}
        success &= run.returncode==0
    result['result']='fail' if not success else 'pass' if args.bundle else 'partial (evidence not_run)'
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if success else 1


if __name__=='__main__': raise SystemExit(main())
