"""Run diagnosis-led AHA in a fresh directory using an existing AHA config."""
import argparse
import json
from pathlib import Path
from agen3d.multiagent.aha.contracts import load
from ..pipeline.config import load_env
from .runtime import Runtime


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--env-file',type=Path)
    parser.add_argument('--cuda',action='store_true')
    parser.add_argument('--max-review-images',type=int,default=8,choices=range(3,17))
    parser.add_argument('--cheap-triage',action='store_true',help='Experimental: cheap rejection screening; passes require strong review')
    args=parser.parse_args()
    if args.output.exists():parser.error('Output must be a new directory')
    if args.env_file:load_env(args.env_file)
    config=load(args.config)
    config.output=str(args.output.resolve())
    if args.cheap_triage:
        config.worker=config.worker.model_copy(update={'response_mode':'text',
            'max_output_tokens':min(config.worker.max_output_tokens,2400)})
    runtime=Runtime(config,max_review_images=args.max_review_images,cheap_triage=args.cheap_triage)
    result=runtime.run(cuda=args.cuda)
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['status']=='layout_validated' else 1)


if __name__=='__main__':main()
