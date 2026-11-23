"""Run the experimental controller with an existing AHA config and NEW output."""
import argparse
import json
from pathlib import Path
from agen3d.multiagent.aha.contracts import load
from ..pipeline.config import load_env
from .runtime import Runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--cuda', action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output must be a new directory')
    if args.env_file:
        load_env(args.env_file)
    config = load(args.config)
    config.output = str(args.output.resolve())
    # Text transport avoids the observed forced-schema decoding loops. Local
    # Recipe validation remains mandatory. Never silently modify input configs.
    config.worker = config.worker.model_copy(update={
        'response_mode': 'text', 'max_output_tokens': min(config.worker.max_output_tokens, 2400)})
    result = Runtime(config).run(cuda=args.cuda)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result.get('status') == 'layout_validated' else 1)


if __name__ == '__main__':
    main()
