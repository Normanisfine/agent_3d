"""Read-only run audit, including receipts nested in parallel branch directories."""
import argparse
from collections import defaultdict
import json
from pathlib import Path


def audit(root):
    root = Path(root)
    calls = []
    for path in sorted(root.rglob('calls/*.json')):
        receipt = json.loads(path.read_text())
        usage = receipt.get('usage', {})
        hosted = usage.get('usage', {})
        calls.append({'path': str(path.relative_to(root)), 'model': receipt.get('model'),
                      'input_tokens': hosted.get('prompt_tokens'),
                      'output_tokens': hosted.get('completion_tokens'),
                      'actual_usd': hosted.get('cost'), 'response_characters': len(receipt.get('text', ''))})
    stages = defaultdict(lambda: {'count': 0, 'wall_seconds_sum': 0.})
    for row in json.loads((root/'stages.json').read_text()):
        stages[row['stage']]['count'] += 1
        stages[row['stage']]['wall_seconds_sum'] += row['wall_seconds']
    return {'source_run': str(root.resolve()), 'calls': calls, 'stages': dict(stages),
            'task_results': json.loads((root/'tasks.json').read_text()),
            'stopped': json.loads((root/'stopped.json').read_text()) if (root/'stopped.json').exists() else None,
            'limitations': 'Stage sums may overlap; not elapsed time. Missing usage/cost remains null. No visual quality score inferred.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.run)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)


if __name__ == '__main__':
    main()
