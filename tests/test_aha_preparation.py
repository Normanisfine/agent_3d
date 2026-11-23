"""Preparation handoff, early failures and shared-budget accounting."""
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from agen3d.multiagent.aha.contracts import Config, load
from agen3d.multiagent.aha.runtime import Runtime
from agen3d.multiagent.aha.reference import source_video
from agen3d.multiagent.aha import bootstrap, doctor, reference


def config(tmp_path, **updates):
    source = tmp_path / 'input.mp4'
    source.write_bytes(b'video')
    values = dict(aha_repo=str(tmp_path), blender='blender', python='python',
        preparation={'input': str(source)}, output=str(tmp_path / 'job'),
        supervisor={'backend': 'codex', 'call_reservation_usd': .1},
        worker={'backend': 'mock'}, judge={'backend': 'codex', 'call_reservation_usd': .1})
    values.update(updates)
    return Config(**values)


def test_dataset_resolution_never_uses_ground_truth(tmp_path):
    (tmp_path / 'ground_truth').mkdir()
    with pytest.raises(ValueError):
        source_video(tmp_path)
    video = tmp_path / 'reference/original_camera_rgb.mp4'
    video.parent.mkdir()
    video.write_bytes(b'rgb')
    assert source_video(tmp_path) == video
    assert source_video(video.parent) == video


def test_choose_walkthrough_from_an_ordinary_capture_directory(tmp_path):
    video = tmp_path / 'North studio.MOV'
    video.touch()
    assert source_video(tmp_path) == video
    (tmp_path / 'second.mp4').touch()
    with pytest.raises(ValueError, match='Multiple videos'):
        source_video(tmp_path)
    assert source_video(video) == video


@pytest.mark.parametrize('controller', ['auto', 'driven'])
def test_launch_room_from_cli(monkeypatch, tmp_path, controller):
    import sys
    from agen3d.multiagent.aha import cli as auto
    from agen3d.multiagent.aha_driven import cli as driven

    template = Path(__file__).resolve().parents[1] / 'configs/multiagent/aha.room.json'
    monkeypatch.chdir(tmp_path)
    video = tmp_path / 'studio.mp4'
    video.touch()
    received = []

    class Started(Exception):
        pass

    def start(config, **kwargs):
        received.append(config)
        raise Started

    if controller == 'auto':
        command, entry = 'run', auto
        monkeypatch.setattr('agen3d.multiagent.aha.runtime.Runtime', start)
    else:
        command, entry = 'init', driven
        monkeypatch.setattr(driven.Session, 'create', start)

    monkeypatch.setattr(sys, 'argv', ['aha', command, str(template),
                                     '--input', video.name, '--output', 'my-room'])
    with pytest.raises(Started):
        entry.main()
    assert source_video(received[0].preparation.input) == video
    assert Path(received[0].output) == tmp_path / 'my-room'


def test_raw_and_prepared_inputs_are_exclusive(tmp_path):
    with pytest.raises(ValueError, match='do not mix'):
        config(tmp_path, source_scene='scene.blend')
    with pytest.raises(ValueError, match='complete prepared'):
        config(tmp_path, preparation=None)
    with pytest.raises(ValueError):
        config(tmp_path, host_hourly_usd=-1)


def test_config_preserves_virtualenv_interpreter_symlinks(tmp_path):
    interpreter = tmp_path / 'venv/bin/python'
    interpreter.parent.mkdir(parents=True)
    interpreter.symlink_to('/usr/bin/python3')
    c = config(tmp_path, python='venv/bin/python', hunyuan=dict(
        python='venv/bin/python', repo='repo', checkpoint='model:hunyuan-shape', reservation_usd=.1))
    path = tmp_path / 'config.json'
    path.write_text(c.model_dump_json())
    loaded = load(path)
    assert loaded.python == str(interpreter)
    assert loaded.hunyuan.python == str(interpreter)


class Reviewer:
    def __init__(self, verdict='pass', omit=False):
        self.verdict, self.omit = verdict, omit

    def complete(self, spec, system, packet, paths, output):
        value = dict(candidate_revision=packet['candidate_revision'], verdict=self.verdict,
            severity='routine', observations=['reviewed'],
            defects=[] if self.verdict == 'pass' else ['bad floor alignment'],
            reviewed_images=packet['image_order'][:-1] if self.omit else packet['image_order'])
        return SimpleNamespace(text=json.dumps(value), actual_usd=.02, usage={})


def install_fake_preparation(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(doctor, 'check', lambda *a, **k: {'required_ready': True})
    def prepare(output, **kwargs):
        calls.append(kwargs)
        Path(output).mkdir()
        return {'ok': True}
    monkeypatch.setattr(reference, 'prepare', prepare)
    def boot(c, ref, output, video):
        output.mkdir()
        scene, spec, image = output/'seed.blend', output/'layout.json', output/'source.png'
        for p in (scene, spec, image):
            p.write_bytes(b'test')
        return dict(source_scene=str(scene), layout_spec=str(spec), source_images={'s': str(image)},
                    review_images={'source': str(image), 'overlay': str(image)},
                    revision='r', alignment={}, binding={str(image): bootstrap.file_revision(image)})
    monkeypatch.setattr(bootstrap, 'bootstrap', boot)
    return calls


def test_preparation_and_review_share_job_ledger_and_continue(monkeypatch, tmp_path):
    calls = install_fake_preparation(monkeypatch, tmp_path)
    runtime = Runtime(config(tmp_path, host_hourly_usd=2), provider=Reviewer())
    def construction():
        assert runtime.c.preparation is None
        assert Path(runtime.c.source_scene).is_file()
        raise RuntimeError('construction reached')
    runtime.initialize_construction = construction
    result = runtime.run()
    assert len(calls) == 1
    assert result['status'] == 'blocked_construction'
    assert result['error'].endswith('construction reached')
    charges = {r['label']: r for r in result['cost']['charges']}
    assert charges['reference_review']['actual'] == .02
    for name in ('reference_preparation', 'construction_bootstrap'):
        row = charges[name]
        assert row['actual'] == pytest.approx(row['detail']['billed_host_seconds'] * 2 / 3600)
    assert result['wall_seconds'] >= sum(s['wall_seconds'] for s in result['stages'])
    # The resolved config remains independently loadable as a prepared-input job.
    assert load(runtime.output/'construction-config.json').preparation is None


def test_failed_preparation_is_reported_and_unknown_cost_retained(monkeypatch, tmp_path):
    install_fake_preparation(monkeypatch, tmp_path)
    def fail(*args, **kwargs):
        raise TimeoutError('Pi3X timed out')
    monkeypatch.setattr(reference, 'prepare', fail)
    result = Runtime(config(tmp_path), provider=Reviewer()).run()
    assert result['status'] == 'blocked_preparation' and result['scene'] is None
    row = next(r for r in result['cost']['charges'] if r['label'] == 'reference_preparation')
    assert row['actual'] is None and row['state'] == 'unknown' and row['reserved'] == .5
    assert row['detail']['status'] == 'failed' and row['detail']['wall_seconds'] > 0
    assert (tmp_path/'job/report.json').is_file()
    assert not (tmp_path/'job/construction-config.json').exists()


@pytest.mark.parametrize('verdict,omit', [('repair', False), ('pass', True)])
def test_reference_rejection_or_missing_coverage_blocks_construction(monkeypatch, tmp_path, verdict, omit):
    install_fake_preparation(monkeypatch, tmp_path)
    result = Runtime(config(tmp_path), provider=Reviewer(verdict, omit)).run()
    assert result['status'] == 'blocked_preparation'
    assert any(r['label'] == 'reference_review' for r in result['cost']['charges'])
    assert not (tmp_path/'job/construction-config.json').exists()


def test_budget_refuses_preparation_before_gpu_launch(monkeypatch, tmp_path):
    calls = install_fake_preparation(monkeypatch, tmp_path)
    c = config(tmp_path)
    c.codex_budget_exempt = False
    c.local_compute_budget_exempt = False
    c.preparation.reservation_usd = 4
    result = Runtime(c, provider=Reviewer()).run()
    assert result['status'] == 'incomplete_budget'
    assert calls == []
    assert not any(r['label'] == 'reference_preparation' for r in result['cost']['charges'])


def test_bootstrap_native_spec_and_source_evidence(monkeypatch, tmp_path):
    ref = tmp_path/'reference'
    (ref/'source_views').mkdir(parents=True)
    bundle = ref/'pi3x'
    bundle.mkdir()
    frames = [0, 15, 31]
    cameras = {'processed_size_wh': [8, 8], 'frames': [
        {'source_frame': f, 'c2w': np.eye(4).tolist(), 'intrinsics': np.eye(3).tolist()}
        for f in frames]}
    (ref/'cameras.json').write_text(json.dumps(cameras))
    np.savez(ref/'layers.npz', vertices=np.array([[0,0,0], [2,3,4]]),
             geometry_valid=[True,True], layer=[0,0])
    for p in (ref/'manifest.json', bundle/'inputs.json', bundle/'inputs.npz'):
        p.write_bytes(b'fixture')
    (ref/'source_views/reference_views.json').write_text(json.dumps({'source_frame_indices':frames}))
    for f in frames:
        for suffix in ('source','reference','overlay'):
            (ref/f'source_views/source_{f:06d}_{suffix}.png').write_bytes(b'image')
    (ref/'reference_build.json').write_text(json.dumps(dict(cameras=str(ref/'cameras.json'),
        mesh=str(ref/'layers.npz'), bundle=str(bundle),
        source_views=str(ref/'source_views/reference_views.json'))))
    def seed(c, folder, script, request):
        assert json.loads(request.read_text()) == cameras
        (folder/'seed.blend').write_bytes(b'empty authored scene')
    monkeypatch.setattr(bootstrap, 'execute', seed)
    c = config(tmp_path)
    generated = bootstrap.bootstrap(c, ref, tmp_path/'bootstrap', Path(c.preparation.input))
    assert len(generated['source_images']) == 3 and len(generated['review_images']) == 9
    cfg = json.loads((tmp_path/'bootstrap/inspection.json').read_text())
    assert cfg['source_frames'] == frames
    assert cfg['model_to_world'] == np.eye(4).tolist()
    assert set(cfg['views']) == {'top','front','side'}
    restored = bootstrap.handoff(ref, tmp_path/'bootstrap', restore=True)
    assert restored['revision'] == generated['revision']
    (tmp_path/'bootstrap/seed.blend').write_bytes(b'changed scene')
    assert bootstrap.handoff(ref, tmp_path/'bootstrap', restore=True)['revision'] != generated['revision']


def test_semantic_subprocess_can_import_uninstalled_sam3(monkeypatch, tmp_path):
    import os
    import subprocess
    import sys
    project = tmp_path/'project'
    sam = project/'external/sam3/sam3'
    sam.mkdir(parents=True)
    (sam/'__init__.py').write_text('')
    (sam/'model_builder.py').write_text('def build_sam3_image_model(): pass\n')
    aha = project/'external/aha-3d'
    module = aha/'tools/layout_inspection'
    module.mkdir(parents=True)
    (module/'semantic.py').write_text('from sam3.model_builder import build_sam3_image_model\n')
    monkeypatch.setattr(reference, 'PROJECT', project)
    monkeypatch.setenv('PYTHONPATH', 'src')
    env = reference.environment(aha)
    assert all(Path(p).is_absolute() for p in env['PYTHONPATH'].split(os.pathsep))
    assert env['HF_HUB_OFFLINE'] == '1'
    result = subprocess.run([sys.executable, '-m', 'tools.layout_inspection.semantic'],
                            cwd=aha, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('always_invalid', [False, True])
def test_contradictory_reference_review_gets_one_paid_retry(tmp_path, always_invalid):
    from agen3d.multiagent.aha.contracts import ReferenceReview
    from pydantic import ValidationError
    image = tmp_path/'source.png'
    image.write_bytes(b'image')
    class Contradictory:
        calls = 0
        def complete(self, spec, system, packet, paths, output):
            self.calls += 1
            if self.calls == 2:
                assert 'previous_invalid_response' in packet
                assert len(paths) == 1
            value = dict(candidate_revision='r', verdict='pass', severity='routine',
                observations=['reviewed'], reviewed_images=['source'],
                defects=['bad alignment'] if self.calls == 1 or always_invalid else [],
                limitations=[] if self.calls == 1 or always_invalid else ['uncalibrated scale'])
            return SimpleNamespace(text=json.dumps(value), actual_usd=.02, usage={})
    provider = Contradictory()
    runtime = Runtime(config(tmp_path), provider=provider)
    if always_invalid:
        with pytest.raises(ValidationError):
            runtime.call('reference_review', ReferenceReview, {'candidate_revision': 'r'}, {'source':str(image)}, strong=True)
    else:
        review = runtime.call('reference_review', ReferenceReview, {'candidate_revision': 'r'}, {'source':str(image)}, strong=True)
        assert review.defects == [] and review.limitations == ['uncalibrated scale']
    assert provider.calls == 2
    assert runtime.ledger.summary()['known_actual_usd'] == .04
    assert len(list((runtime.output/'calls').glob('*.json'))) == 2
    runtime._job_lock.close()


def test_resume_keeps_budget_costs_and_elapsed_without_repreparing(monkeypatch, tmp_path):
    calls = install_fake_preparation(monkeypatch, tmp_path)
    c = config(tmp_path)
    first = Runtime(c, provider=Reviewer('repair'))
    previous = first.run()
    old = json.loads((first.output/'report.json').read_text())
    def restored(*args, **kwargs):
        folder = first.output/'bootstrap'
        image = folder/'source.png'
        return dict(source_scene=str(folder/'seed.blend'),layout_spec=str(folder/'layout.json'),
            source_images={'s':str(image)}, review_images={'source':str(image),'overlay':str(image)},
            revision='r',alignment={},binding={str(image):bootstrap.file_revision(image)})
    monkeypatch.setattr(bootstrap, 'handoff', restored)
    resumed = Runtime(c, provider=Reviewer(), resume_preparation=True)
    def stop():
        raise RuntimeError('construction reached')
    resumed.initialize_construction = stop
    result = resumed.run()
    assert len(calls) == 1
    assert result['status'] == 'blocked_construction'
    assert result['wall_seconds'] > previous['wall_seconds']
    assert result['cost']['known_actual_usd'] == .04
    assert sum(r['label']=='reference_preparation' for r in result['cost']['charges']) == 1
    assert sum(r['label']=='reference_review' for r in result['cost']['charges']) == 2
    archived = next((first.output/'history').glob('*/report.json'))
    assert json.loads(archived.read_text()) == old


def test_resume_rejects_changed_budget(monkeypatch, tmp_path):
    install_fake_preparation(monkeypatch, tmp_path)
    c = config(tmp_path)
    Runtime(c, provider=Reviewer('repair')).run()
    c.budget_usd = 10
    with pytest.raises(ValueError, match='unchanged'):
        Runtime(c, resume_preparation=True)
