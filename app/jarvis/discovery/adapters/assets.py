"""Local-first asset identity, license hard gates and content-addressed cache.

No model download, script/macro execution, CAD import or inferred internals.
Reported metadata is supplied provenance, not independent engineering truth.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal
from pydantic import Field
from ..contracts import Source, StrictModel
from ...agent_context import scoped
from ...skill_memory import linked
from ...obsidian_memory import SENSITIVE

PERMITTED = frozenset({'CC0-1.0', 'CC-BY-4.0', 'MIT', 'BSD-3-Clause', 'Apache-2.0'})
FORMATS = frozenset({'.step', '.stp', '.stl', '.obj', '.glb', '.gltf', '.blend', '.fcstd', '.urdf', '.mjcf', '.json'})


class Identity(StrictModel):
    manufacturer: str = Field(min_length=1, max_length=120)
    model: str = Field(min_length=1, max_length=120)
    year: int | None = Field(default=None, ge=1800, le=2200)
    variant: str | None = Field(default=None, max_length=120)
    rule_set: str | None = Field(default=None, max_length=120)


class AssetCandidate(StrictModel):
    identity: Identity
    target: Identity
    representation: Literal['authoritative_cad', 'replica', 'concept', 'visual_only', 'comparable', 'unknown']
    relative_file: str = Field(min_length=1, max_length=500)
    source: Source
    license_confirmed: bool = False
    attribution: str | None = Field(default=None, max_length=1000)
    attribution_required: bool = False
    dimensions_checked: bool = False
    functional_separation_checked: bool = False
    suitable_size: bool = False


def assess(candidate: AssetCandidate):
    hard_rejects, gaps = [], []
    if not candidate.license_confirmed or candidate.source.license not in PERMITTED:
        hard_rejects.append('license is missing, unsupported or not confirmed for intended reuse')
    if not (candidate.source.author or '').strip() or not candidate.source.sha256 or not candidate.source.locator.strip():
        hard_rejects.append('required author or source file hash missing')
    needs_credit = candidate.attribution_required or candidate.source.license == 'CC-BY-4.0'
    if needs_credit and not (candidate.attribution or '').strip():
        hard_rejects.append('required attribution missing')
    extension = Path(candidate.relative_file).suffix.casefold()
    if extension not in FORMATS:
        hard_rejects.append('unsupported asset format')
    mismatches = []
    for field in ('manufacturer', 'model', 'year', 'variant', 'rule_set'):
        actual, requested = getattr(candidate.identity, field), getattr(candidate.target, field)
        if requested is not None:
            if isinstance(requested, str):
                equal = isinstance(actual, str) and actual.casefold().strip() == requested.casefold().strip()
            else:
                equal = actual == requested
            if not equal:
                mismatches.append(field)
    exact_claim = not mismatches and candidate.representation == 'authoritative_cad'
    if candidate.representation != 'authoritative_cad':
        gaps.append('source describes ' + candidate.representation + '; not exact engineering CAD')
    gaps.extend('identity mismatch: '+name for name in mismatches)
    if not candidate.dimensions_checked:
        gaps.append('dimensions have not been checked')
    if not candidate.functional_separation_checked:
        gaps.append('functional separation has not been checked')
    weights = {'identity': 20 if exact_claim else 0, 'provenance': 20 if not hard_rejects else 0,
               'dimensions': 20 if candidate.dimensions_checked else 0,
               'functional': 15 if candidate.functional_separation_checked else 0,
               'license': 10 if candidate.license_confirmed and candidate.source.license in PERMITTED else 0,
               'format': 10 if extension in FORMATS else 0, 'resources': 5 if candidate.suitable_size else 0}
    # Forbidden license/origin is a veto, never an attractive low score.
    state = ('REJECTED' if hard_rejects else 'FOUND_EXACT' if exact_claim else
             'FOUND_COMPARABLE' if candidate.representation == 'comparable' else 'FOUND_VISUAL_ONLY')
    return {'asset_state': state, 'hard_rejects': hard_rejects, 'gaps': gaps, 'weights': weights,
            'score': None if hard_rejects else sum(weights.values()),
            'substitution_requires_approval': not exact_claim and not hard_rejects,
            'identity_basis': 'supplied metadata, not independent engineering validation',
            'evidence_status': 'INSUFFICIENT_EVIDENCE',
            'justification': 'Metadata and declared reuse rights checked; no independent CAD, license or physics validation.'}


def local_bytes(root: Path, relative: str, limit=16_000_000):
    path = scoped(root, relative)
    if any(linked(p) or SENSITIVE.search(p.name) for p in (path, *path.parents) if p.is_relative_to(Path(root).resolve())):
        raise ValueError('linked or sensitive source path')
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError('regular file within byte budget required')
    with path.open('rb') as stream:
        body = stream.read(limit+1)
    if len(body) > limit:
        raise ValueError('source exceeded byte budget while reading')
    return body


def inspect_local(root: Path, candidate: AssetCandidate):
    result = assess(candidate)
    if result['hard_rejects']:
        return result  # Do not read rejected/unlicensed asset contents.
    body = local_bytes(root, candidate.relative_file)
    actual = hashlib.sha256(body).hexdigest()
    if actual != candidate.source.sha256:
        raise ValueError('asset file differs from supplied source hash')
    return {**result, 'file_sha256': actual, 'file_bytes': len(body), 'executed': False}


def cache_local(root: Path, candidate: AssetCandidate, *, memory):
    """Private Journal artifact cache. Never create an executable host asset cache."""
    result = inspect_local(root, candidate)
    if result['hard_rejects']:
        raise PermissionError('asset hard rejected; no cache created')
    body = local_bytes(root, candidate.relative_file, limit=500_000)
    if hashlib.sha256(body).hexdigest() != result['file_sha256']:
        raise ValueError('asset changed between inspection and caching')
    identity = 'asset-'+result['file_sha256']+'-'+hashlib.sha256(candidate.source.model_dump_json().encode()).hexdigest()[:12]
    existing = memory.get(identity)
    if existing is not None:
        return existing.locator
    source = memory.get(candidate.source.id, candidate.source.revision)
    if source is not None and source != candidate.source:
        raise ValueError('source revision already has different provenance')
    # Small binary assets are inert artifact payloads. Preserve source/license/lineage.
    import base64
    from datetime import datetime, timezone
    ref = memory.journal.put({'encoding': 'base64', 'sha256': result['file_sha256'],
                              'content': base64.b64encode(body).decode('ascii'),
                              'source': candidate.source.model_dump(mode='json'),
                              'attribution': candidate.attribution, 'lineage': 'original user-provided file',
                              'cached_at_utc': datetime.now(timezone.utc).isoformat()}, data_type='Report')
    from ..contracts import RunArtifact
    memory.put(candidate.source)
    memory.put(RunArtifact(id=identity, locator=ref, sha256=result['file_sha256'],
                           media_type='application/octet-stream', source_ids=(candidate.source.id,),
                           justification='Inert small asset cache; rights/provenance retained; no embedded code executed.'))
    return ref
