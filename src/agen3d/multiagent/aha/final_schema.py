"""Structured native final-review output; completeness is supplied by the reviewer."""
ASPECTS = ['inventory', 'placement', 'dimensions', 'orientation', 'relationships', 'uncertainty']


def obj(properties):
    return {'type':'object', 'properties':properties, 'required':list(properties), 'additionalProperties':False}


def strings(enum=None):
    item = {'type':'string'}
    if enum is not None:
        item['enum'] = list(enum)
    return {'type':'array', 'items':item}


def schema(request):
    text = {'type':'string'}
    row = obj({'observation':text, 'subjects':strings(),
               'aspect':{'type':'string','enum':ASPECTS}})
    return obj({
        'candidate_revision':{'type':'string','enum':[request['candidate_revision']]},
        'reviewer':text, 'verdict':{'type':'string','enum':['accepted','rejected']},
        'per_image_observations':obj({key:row for key in request['images']}),
        'object_focus_observations':obj({identity:obj({key:text for key in views})
                                        for identity,views in request.get('object_views',{}).items()}),
        'aspect_observations':obj({aspect:obj({'observation':text,'subjects':strings(),
                                             'views':strings(request['images'])}) for aspect in ASPECTS}),
        'scene_completeness':obj({'complete':{'type':'boolean'},'observation':text,
                                  'missing_elements':strings()}),
        'findings':{'type':'array','items':obj({'id':text,
            'severity':{'type':'string','enum':['blocking','nonblocking']},
            'affected_ids':strings(),'views':strings(request['images']),
            'observation':text,'resolution_needed':text})},
        'uncertainties':{'type':'array','items':obj({'observation':text,
            'impact':{'type':'string','enum':['blocking','nonblocking']}})},
        'unreviewed_areas':strings(),
    })


def normalize(raw, request):
    if raw['candidate_revision'] != request['candidate_revision']:
        raise ValueError('Final reviewer returned a stale revision')
    images = request['images']
    if set(raw['per_image_observations']) != set(images):
        raise ValueError('Final review requires a concrete observation for every image')
    complete = raw['scene_completeness']
    if raw['verdict'] == 'accepted' and (not complete['complete'] or complete['missing_elements']):
        raise ValueError('Incomplete room cannot be accepted by reviewing only existing objects')
    observations = [dict(aspect=row['aspect'], subjects=row['subjects'], views=[key],
                         observation=row['observation']) for key,row in raw['per_image_observations'].items()]
    if set(raw['aspect_observations']) != set(ASPECTS):
        raise ValueError('Final review omitted required aspects')
    observations += [dict(aspect=aspect, **row) for aspect,row in raw['aspect_observations'].items()]
    focused = raw['object_focus_observations']
    if set(focused) != set(request.get('object_views',{})):
        raise ValueError('Final review omitted object subjects')
    for identity,views in request.get('object_views',{}).items():
        if set(focused[identity]) != set(views):
            raise ValueError('Final review omitted object-focus evidence')
        observations += [dict(aspect='placement',subjects=[identity],views=[key],observation=value)
                         for key,value in focused[identity].items()]
    observations.append(dict(aspect='inventory',subjects=['scene_completeness'],views=list(images),
                             observation=complete['observation']))
    # No observations or verdicts are fabricated; only reviewer-authored fields are reshaped.
    return dict(schema_version=2,candidate_revision=raw['candidate_revision'],reviewer=raw['reviewer'],
                verdict=raw['verdict'],reviewed_views=list(images),observations=observations,
                findings=raw['findings'],uncertainties=raw['uncertainties'],unreviewed_areas=raw['unreviewed_areas'])
