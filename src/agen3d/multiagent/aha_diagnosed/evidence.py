"""Preflight all evidence before calls; bounded batches never drop required views."""
import hashlib
import json
from pathlib import Path
from ..aha.runtime import digest


POLICY_VERSION='aha-diagnosed-review-1'


def packets(task, request, instances, source_images, max_images=8):
    if max_images < 3:
        raise ValueError('At least three image slots required')
    if not request.get('candidate_revision'):
        raise ValueError('Missing candidate revision')
    result=[]
    for oid in task.object_ids:
        focus=request.get('object_views',{}).get(oid,[])
        if not focus or len(focus)!=len(set(focus)):
            raise ValueError('Missing or duplicate required focus views: '+oid)
        if any(key not in request['images'] for key in focus):
            raise ValueError('Required focus image missing: '+oid)
        images={key:request['images'][key] for key in focus}
        source_ids=instances[oid].source_image_ids
        for sid in source_ids:
            if sid not in source_images:
                raise ValueError('Declared source evidence missing: '+sid)
            images['original:'+sid]=source_images[sid]
        for path in images.values():
            if not Path(path).is_file() or Path(path).stat().st_size == 0:
                raise ValueError('Missing/empty evidence file: '+str(path))
        # Shared source and object-focus anchor give each shard some common
        # context. No required image is discarded, even for large packets.
        anchors=list(dict.fromkeys([focus[0],'original:'+source_ids[0]]))
        remaining=[key for key in images if key not in anchors]
        width=max_images-len(anchors)
        chunks=[remaining[i:i+width] for i in range(0,len(remaining),width)] or [[]]
        for number,chunk in enumerate(chunks):
            ids=list(dict.fromkeys(anchors+chunk))
            result.append({'object_id':oid,'batch':number,'images':{key:images[key] for key in ids},
                           'required_object_images':list(images), 'focus_images':focus})
    return result


def review_key(packet, images, model):
    payload={'policy':POLICY_VERSION,'packet':packet,'model':model.model_dump(),
             'images':{key:{'path':str(Path(path).resolve()),'sha256':digest(path)}
                       for key,path in images.items()}}
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
