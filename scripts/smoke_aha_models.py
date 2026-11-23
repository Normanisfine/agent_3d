"""One bounded image+JSON transport call per model, not a reconstruction benchmark."""
import argparse
import json
import time
from pathlib import Path

from PIL import Image, ImageDraw
from agen3d.multiagent.contracts import ModelSpec
from agen3d.multiagent.resources import load_env
from agen3d.multiagent.providers import Provider
from agen3d.multiagent.store import Ledger, save


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--env-file', type=Path)
    args = p.parse_args()
    if args.env_file:
        load_env(args.env_file)
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    im = Image.new('RGB', (128, 128), 'white')
    ImageDraw.Draw(im).rectangle((32,32,96,96), fill='red')
    im.save(out/'fixture.png')
    models = {
        'qwen': ModelSpec(backend='openrouter', model='qwen/qwen3-vl-30b-a3b-instruct',
                          provider='DeepInfra', max_output_tokens=128, call_reservation_usd=.03),
        'codex': ModelSpec(backend='codex', model='gpt-6-astra', reasoning_effort='medium',
                           max_output_tokens=128, call_reservation_usd=.25),
    }
    ledger = Ledger(out/'ledger.sqlite', .5)
    results = {}
    for name, model in models.items():
        key = ledger.reserve(name, model.call_reservation_usd)
        reply = None
        started = time.monotonic()
        try:
            reply = Provider().complete(model, 'Inspect the image. Return ONLY JSON: {"color": "...", "shape": "..."}.',
                {'task': {'role': 'critic'}, 'instruction': 'Name the central colored shape.'},
                [out/'fixture.png'], out)
            value = json.loads(reply.text)
            ok = value.get('color', '').lower() == 'red' and value.get('shape', '').lower() in {'square', 'rectangle'}
            results[name] = {'ok': ok, 'response': value, 'usage': reply.usage}
        except Exception as exc:
            results[name] = {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
        finally:
            ledger.settle(key, reply.actual_usd if reply else None,
                          {'wall_seconds': time.monotonic()-started, 'usage': reply.usage if reply else {}})
        save(out/'report.json', {'models': results, 'cost': ledger.summary(),
             'scope': 'Image transport, authentication and simple JSON only; not reconstruction quality.'})
        print(json.dumps({'model': name, 'ok': results[name]['ok']}), flush=True)


if __name__ == '__main__':
    main()
