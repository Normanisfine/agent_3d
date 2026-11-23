"""Exact evidence binding and deterministic receipt reuse, never fuzzy acceptance."""
import json
from pathlib import Path

import pytest

from agen3d.multiagent.aha.contracts import ReferenceReview
from agen3d.multiagent.aha.reviews import bind
from agen3d.multiagent.aha.runtime import Runtime, file_revision
from agen3d.multiagent.store import Ledger, save


def review(ids, revision='r'):
    return ReferenceReview(candidate_revision=revision, verdict='pass', severity='routine',
                           observations=['reviewed'], defects=[], reviewed_images=ids,
                           limitations=['predicted scale'])


def test_exact_filenames_are_bound_without_dropping_evidence():
    images = {'source': '/data/source.png', 'alignment_000': '/data/000000_floor_support.png'}
    result, aliases = bind(review(['source', '000000_floor_support.png']), 'r', images)
    assert result.reviewed_images == ['source', 'alignment_000']
    assert aliases == {'000000_floor_support.png': 'alignment_000'}
    assert result.limitations == ['predicted scale']


@pytest.mark.parametrize('ids,revision,images', [
    (['a'], 'wrong', {'a':'/a.png'}),
    (['a'], 'r', {'a':'/a.png','b':'/b.png'}),
    (['a','a.png'], 'r', {'a':'/a.png','b':'/b.png'}),
    (['same.png'], 'r', {'a':'/x/same.png','b':'/y/same.png'}),
    (['almost.png'], 'r', {'a':'/actual.png'}),
])
def test_incomplete_ambiguous_duplicate_or_stale_reviews_fail(ids, revision, images):
    with pytest.raises(ValueError):
        bind(review(ids, revision), 'r', images)


def cached_runtime(tmp_path):
    r = Runtime.__new__(Runtime)
    r.output = tmp_path
    r.ledger = Ledger(tmp_path/'ledger.sqlite',5)
    image = tmp_path/'support.png'
    image.write_bytes(b'original')
    images = {'alignment_000': str(image)}
    key = r.ledger.reserve('reference_review',.25)
    r.ledger.settle(key,None,{})
    save(tmp_path/'calls'/f'{key}.json', {'text':review(['support.png']).model_dump_json(),
                                       'images':{k:file_revision(v) for k,v in images.items()}})
    return r, {'revision':'r','review_images':images}, key


def test_cached_latest_review_reuses_exact_delivery_with_no_new_charge(tmp_path):
    r, generated, key = cached_runtime(tmp_path)
    result = r.cached_reference_review(generated)
    assert result.reviewed_images == ['alignment_000']
    assert len(r.ledger.summary()['charges']) == 1
    receipt = json.loads((tmp_path/'reference-review-reuse.json').read_text())
    assert receipt['call_id'] == key
    assert receipt['image_aliases'] == {'support.png':'alignment_000'}


def test_cached_review_rejects_changed_images_or_revision(tmp_path):
    r, generated, _ = cached_runtime(tmp_path)
    assert r.cached_reference_review({**generated,'revision':'new'}) is None
    Path(generated['review_images']['alignment_000']).write_bytes(b'changed')
    assert r.cached_reference_review(generated) is None


def test_never_revive_old_pass_over_latest_invalid_or_rejected_review(tmp_path):
    r, generated, _ = cached_runtime(tmp_path)
    key = r.ledger.reserve('reference_review',.25)
    r.ledger.settle(key,None,{})
    # A charged call with no response is also not an invitation to reuse an older pass.
    assert r.cached_reference_review(generated) is None
    rejected = review(['support.png']).model_copy(update={'verdict':'repair','defects':['bad floor']})
    save(tmp_path/'calls'/f'{key}.json', {'text':rejected.model_dump_json(),
        'images':{k:file_revision(v) for k,v in generated['review_images'].items()}})
    assert r.cached_reference_review(generated) is None
