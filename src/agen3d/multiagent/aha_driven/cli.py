"""One explicit operation per invocation; the supervising agent chooses the next."""
import argparse
import json
from pathlib import Path

from ..aha.contracts import Plan, Proposal, Review, Work, load
from ..resources import load_env
from .session import Session, read
from .inventory import InventoryPlan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('init')
    p.add_argument('config', type=Path)
    p.add_argument('--input', type=Path, help='Room video or capture directory')
    p.add_argument('--output', type=Path, required=True, help='New session directory')
    p.add_argument('--cuda', action='store_true')
    p.add_argument('--inventory', type=Path, help='Boxer inventory.json with adjacent inventory_crops/')
    for name in ('status', 'inventory-plan', 'packet', 'propose', 'build', 'review', 'commit', 'final-review', 'capacity', 'wave', 'merge', 'export'):
        p = commands.add_parser(name)
        p.add_argument('session', type=Path)
        if name in ('wave', 'inventory-plan'):
            p.add_argument('--plan', type=Path, required=name == 'inventory-plan')
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
        config = load(args.config, room_input=args.input, output=args.output)
        session = Session.create(config, cuda=args.cuda, inventory_path=args.inventory)
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
        elif name == 'inventory-plan':
            result = session.register_inventory_plan(InventoryPlan.model_validate(read(args.plan)))
        elif name == 'wave':
            if args.plan:
                data = read(args.plan)
                if session.boxer is not None and 'omissions' in data:
                    plan = InventoryPlan.model_validate(data)
                    if plan != session.boxer.plan:
                        raise ValueError('Register this inventory-plan before running its wave')
                else:
                    plan = Plan.model_validate(data)
            elif session.boxer is not None and session.boxer.plan is not None:
                plan = session.boxer.plan
            else:
                parser.error('wave requires --plan or a registered inventory-plan')
            result = session.build_wave(plan)
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
