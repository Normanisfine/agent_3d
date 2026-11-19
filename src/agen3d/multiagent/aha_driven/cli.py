"""One explicit operation per invocation; the supervising agent chooses the next."""
import argparse
import json
from pathlib import Path

from ..aha.contracts import Plan, Proposal, Review, Work, load
from ..pipeline.config import load_env
from .session import Session, read


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('init')
    p.add_argument('config', type=Path)
    p.add_argument('--output', type=Path, required=True, help='New, separate comparison directory')
    p.add_argument('--cuda', action='store_true')
    for name in ('status', 'packet', 'propose', 'build', 'review', 'commit', 'final-review', 'capacity', 'wave', 'merge', 'export'):
        p = commands.add_parser(name)
        p.add_argument('session', type=Path)
        if name == 'wave':
            p.add_argument('--plan', type=Path, required=True)
        if name == 'merge':
            p.add_argument('--branch', required=True)
        if name in ('packet', 'build'):
            p.add_argument('--task', type=Path, required=True)
        if name == 'packet':
            p.add_argument('--images', nargs='+', required=True, help='Registered source image IDs')
            p.add_argument('--assets', nargs='*', default=[], help='Only relevant registered asset IDs')
        if name == 'propose':
            p.add_argument('--packet', type=Path, required=True)
        if name == 'build':
            p.add_argument('--proposal', type=Path, required=True)
        if name in ('review', 'commit'):
            p.add_argument('--candidate', required=True)
        if name == 'review':
            p.add_argument('--review', type=Path, help='External agent review; omit to call a worker')
        if name in ('propose', 'review'):
            p.add_argument('--strong', action='store_true')
    args = parser.parse_args()
    if args.env_file:
        load_env(args.env_file)
    if args.command == 'init':
        config = load(args.config)
        config.output = str(args.output.resolve())
        session = Session.create(config, cuda=args.cuda)
    else:
        session = Session.open(args.session)
    try:
        name = args.command
        if name in ('init', 'status'):
            result = session.summary()
        elif name == 'capacity':
            result = session.calibrate_capacity()
        elif name == 'export':
            from ..aha.artifacts import export_output
            result = export_output(session)
        elif name == 'wave':
            result = session.build_wave(Plan.model_validate(read(args.plan)))
        elif name == 'merge':
            result = session.merge(args.branch)
        elif name == 'packet':
            result = {'packet': str(session.packet(Work.model_validate(read(args.task)),
                                                   args.images, args.assets))}
        elif name == 'propose':
            result = {'proposal': str(session.propose(args.packet, strong=args.strong))}
        elif name == 'build':
            result = session.build(Work.model_validate(read(args.task)),
                                   Proposal.model_validate(read(args.proposal)))
        elif name == 'review':
            result = session.review(args.candidate,
                Review.model_validate(read(args.review)) if args.review else None, strong=args.strong)
        elif name == 'commit':
            result = session.commit(args.candidate)
        else:
            result = session.final_review()
        session.ledger.event('driven_operation', {'command': name, 'revision': session.revision})
    except Exception as exc:
        session.ledger.event('driven_operation_failed', {'command': args.command,
                             'error': f'{type(exc).__name__}: {exc}'})
        raise
    finally:
        session.close()
    print(json.dumps(result, indent=2))
    if any(r.get('status') == 'failed' for r in result.get('results', {}).values()) or result.get('verdict') == 'repair' or result.get('layout_status') in ('needs_repair', 'blocked_review'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
