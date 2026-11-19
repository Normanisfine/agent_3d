"""Bind review claims to exact delivered images, allowing only unique filename aliases."""
from pathlib import Path


def bind(review, revision, images):
    if review.candidate_revision != revision:
        raise ValueError('Review candidate_revision differs from the supplied revision')
    aliases = {}
    for identity, path in images.items():
        aliases.setdefault(Path(path).name, []).append(identity)
    canonical, substitutions = [], {}
    for value in review.reviewed_images:
        if value in images:
            identity = value
        else:
            matches = aliases.get(value, [])
            if len(matches) != 1:
                raise ValueError(f'Unknown or ambiguous review image: {value}')
            identity = matches[0]
            substitutions[value] = identity
        canonical.append(identity)
    if len(canonical) != len(set(canonical)):
        raise ValueError('Review repeats an image instead of covering distinct evidence')
    missing = sorted(set(images) - set(canonical))
    if missing:
        raise ValueError('Review omitted image IDs: ' + ', '.join(missing))
    return review.model_copy(update={'reviewed_images': canonical}), substitutions
