"""Subprocess adapter to the local AHA checkout; does not fork its acceptance policy."""
import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    request = json.loads(Path(sys.argv[1]).read_text())
    sys.path.insert(0, str(Path(request['aha_repo']) / 'src'))
    from aha3d.workflow import layout_gate
    from aha3d.io import write
    spec = layout_gate.normalize_spec(request['spec'])
    directory = Path(request['evidence_dir'])
    action = request['action']
    if action == 'preflight':
        result = layout_gate._technical_inputs(spec)
    elif action == 'prepare':
        tools = Path(request['aha_repo']) / 'tools/layout_inspection'
        def render(spec, output):
            command = [request['blender'], '-b', spec['source_scene'], '--disable-autoexec',
                       '-t', '2', '--python-exit-code', '1', '--python',
                       str(tools / 'render_blender.py'), '--']
            for name in ('reference', 'cameras', 'inputs', 'config'):
                command += ['--' + name, spec[name]]
            command += ['--out', str(output)]
            subprocess.run(command, check=True)
            return output
        from aha3d.workflow.object_review import generate
        def objects(spec, output):
            generate(spec, output, blender=request['blender'], python=sys.executable,
                     tools_root=tools, threads=2)
        layout_gate.prepare(spec, directory, runner=render, object_runner=objects)
        result = layout_gate.review_request(spec, directory)
    elif action == 'review':
        from aha3d.workflow.review_contract import run_reviewer
        review_request = layout_gate.review_request(spec, directory)
        # Native AHA gate retains an honest codex_exec_images receipt. Qwen is advisory.
        os.environ['AGEN3D_JUDGE_MODEL'] = request['judge'].get('model') or ''
        os.environ['AGEN3D_JUDGE_EFFORT'] = request['judge'].get('reasoning_effort') or ''
        os.environ['AGEN3D_JUDGE_AUDIT_DIR'] = str(directory / 'review-transport')
        try:
            run_reviewer(review_request, directory / 'visual-review.json',
                         executable=str(Path(__file__).with_name('codex_gate.py')))
        except (ValueError, subprocess.CalledProcessError) as exc:
            write(request['result'], {'verdict': 'invalid_review', 'error': str(exc)})
            return
        visual = json.loads((directory / 'visual-review.json').read_text())
        evidence = json.loads((directory / 'evidence.json').read_text())
        layout_gate.record_review(spec, directory, reviewer=visual['reviewer'],
            notes='Independent source-bound final layout review via AHA native contract.',
            verdict=visual['verdict'], expected_views=evidence['expected_views'], visual_review=visual)
        result = {'verdict': visual['verdict'], 'visual_review': visual}
        if visual['verdict'] == 'accepted':
            result['gate'] = layout_gate.require_current(spec, directory)
    elif action == 'require_current':
        result = layout_gate.require_current(spec, directory)
    else:
        raise ValueError('Unknown AHA bridge action')
    write(request['result'], result)


if __name__ == '__main__':
    main()
