"""Project snapshots are artifacts in the existing scientific Journal facade."""
from __future__ import annotations

import hashlib
from .component_graph import Project
from ..contracts import RunArtifact, bounded_json


def save(memory, project: Project) -> str:
    body = bounded_json(project.model_dump(mode='json'))
    # Preflight all immutable entity conflicts before storing a snapshot pointer.
    records = [*project.components, *(b.parameter for b in project.parameters), project.scenario]
    for record in records:
        old = memory.get(record.id, record.revision)
        if old is not None and old != record:
            raise ValueError('entity revision already has different content')
    identity = 'project-snapshot:' + project.id
    old_snapshot = memory.get(identity, project.revision)
    if old_snapshot is not None:
        previous = memory.journal.get(old_snapshot.locator)
        if previous != body:
            raise ValueError('project revision is immutable')
        return old_snapshot.locator
    ref = memory.journal.put(body, data_type='Report')
    for record in records:
        memory.put(record)
    memory.put(RunArtifact(id=identity, revision=project.revision, locator=ref,
                           sha256=hashlib.sha256(body.encode()).hexdigest(), media_type='application/json',
                           evidence_status='MODEL_CONSISTENT',
                           justification='Validated assembly and explicit dependencies; not a solver result.'))
    return ref


def load(memory, project_id: str, revision: int | None = None) -> Project:
    record = memory.get('project-snapshot:'+project_id, revision)
    if not isinstance(record, RunArtifact):
        raise ValueError('project snapshot not found')
    body = memory.journal.get(record.locator)
    if not body or hashlib.sha256(body.encode()).hexdigest() != record.sha256:
        raise ValueError('project snapshot hash mismatch')
    return Project.model_validate_json(body)
