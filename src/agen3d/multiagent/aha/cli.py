"""Single AHA-backed construction entry point."""
import argparse
import json
from pathlib import Path

from ..resources import load_env
from ..store import save
from .contracts import load
from .doctor import check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['doctor', 'run', 'prepare-reference', 'capacity'])
    parser.add_argument('config', type=Path, nargs='?')
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--cuda', action='store_true')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--input', type=Path, help='Room video or capture directory for run or doctor')
    parser.add_argument('--video', type=Path)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--resume-preparation', action='store_true',
                        help='Reuse completed preparation after a blocked reference review; keep ledger/budget')
    args = parser.parse_args()
    if args.resume_preparation and args.command != 'run':
        parser.error('--resume-preparation is only valid with run')
    if args.input and (args.config is None or args.command not in ('run', 'doctor')):
        parser.error('--input requires run or doctor with a video preparation config')
    if args.env_file:
        load_env(args.env_file)
    if args.command == 'prepare-reference':
        if not args.output or bool(args.video) == bool(args.bundle):
            parser.error('prepare-reference needs --output and exactly one of --video/--bundle')
        from .reference import prepare
        result = prepare(args.output, video=args.video, bundle=args.bundle)
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result['ok'] else 1)
    config = load(args.config, room_input=args.input,
                  output=args.output if args.command == 'run' else None) if args.config else None
    if args.command == 'capacity':
        if config is None or not args.output:
            parser.error('capacity requires a config and --output NEW_DIRECTORY')
        from .scheduling import calibrate
        if args.output.exists():
            parser.error('capacity output must be new')
        print(json.dumps(calibrate(config, args.output), indent=2))
        return
    if args.command == 'run' and config is None:
        parser.error('run requires an AHA construction config')
    if args.command == 'run':
        from .runtime import Runtime
        result = Runtime(config, resume_preparation=args.resume_preparation).run(
            cuda=args.cuda)
    else:
        result = check(config, cuda=args.cuda)
    if args.report:
        save(args.report, result)
    print(json.dumps(result, indent=2))
    if result.get('required_ready') is False or result.get('status') not in (None, 'layout_validated'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
