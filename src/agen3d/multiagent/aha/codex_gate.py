#!/usr/bin/env python3
"""Native image-review transport with structured whole-room coverage and retained raw output."""
import json
import os
from pathlib import Path
import subprocess
import sys

from final_schema import schema, normalize


def main():
    args = sys.argv[1:]
    if not args or args[0] != 'exec':
        raise SystemExit('Expected Codex exec transport')
    prompt = sys.stdin.read()
    request = json.loads(prompt.split('Request: ', 1)[1])
    destination = Path(args[args.index('--output-last-message') + 1])
    audit = Path(os.environ['AGEN3D_JUDGE_AUDIT_DIR'])
    audit.mkdir(parents=True, exist_ok=False)
    schema_path = audit / 'schema.json'
    schema_path.write_text(json.dumps(schema(request)))
    raw_path = audit / 'raw-response.json'
    args[args.index('--output-last-message') + 1] = str(raw_path)
    cmd = ['codex', 'exec', '--ignore-user-config', '--disable', 'shell_tool',
           '--disable', 'unified_exec', '--disable', 'multi_agent', '--disable', 'multi_agent_v2',
           '-c', 'web_search="disabled"', '--output-schema', str(schema_path)]
    if os.environ.get('AGEN3D_JUDGE_MODEL'):
        cmd += ['--model', os.environ['AGEN3D_JUDGE_MODEL']]
    if os.environ.get('AGEN3D_JUDGE_EFFORT'):
        cmd += ['-c', 'model_reasoning_effort="' + os.environ['AGEN3D_JUDGE_EFFORT'] + '"']
    # The upstream request's image order and native attachments remain unchanged.
    prompt = ('Review the attached images against the JSON output schema. Produce concrete observations '
              'for EACH per_image_observations key, all object_focus_observations keys, and every aspect. '
              'Assess the COMPLETE observed room, not only the objects that happen to be modeled. '
              'Missing walls, furniture or other salient visible elements block acceptance. '
              'Object-focus images are candidate contours over source RGB or approximate reference '
              'backgrounds; background holes do not demonstrate holes in candidate geometry. '
              'Use model-only views to distinguish authored geometry from reference geometry. '
              'Accepted requires scene_completeness.complete=true, no missing_elements, no findings, '
              'no unreviewed_areas, and only nonblocking uncertainties. Otherwise reject. '
              'Keep factual caveats; never erase a blocker to satisfy the schema. Request: '
              + json.dumps(request, sort_keys=True))
    result = subprocess.run(cmd + args[1:], input=prompt, text=True, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)
    raw = json.loads(raw_path.read_text())
    final = normalize(raw, request)
    (audit / 'normalized-review.json').write_text(json.dumps(final, indent=2))
    destination.write_text(json.dumps(final))


if __name__ == '__main__':
    main()
