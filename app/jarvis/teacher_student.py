"""Compile verified teacher traces into parameterized reference procedures.

Templates are guidance, not executable authorization. Training export is a
separate, explicitly invoked offline operation; private records stay local.
"""
import hashlib
import json

FORBIDDEN = {'run_command', 'type_text', 'fill_text', 'delete_file', 'send', 'publish'}


def compile_procedure(task):
    routes = list(task.get('model_routes', []))
    for checkpoint in task.get('checkpoints', []):
        if checkpoint.get('stage') == 'model_route':
            try:
                routes.append(json.loads(checkpoint.get('evidence', '')))
            except (ValueError, TypeError):
                continue
    if not any(row.get('model') == 'qwen3.5:9b' for row in routes):
        return None
    checks = task.get('checkpoints', [])
    if (task.get('status') != 'completed' or task.get('failures')
            or not any(c.get('stage') == 'goal_verified' and c.get('evidence') for c in checks)):
        return None
    completed = (task.get('plan') or {}).get('completed', [])
    if not completed or len(completed) > 20:
        return None
    slots, bindings, steps = {}, {}, []
    for step in completed:
        action = step.get('action')
        if (step.get('verified') is not True or not isinstance(action, str)
                or action in FORBIDDEN or not step.get('expected')):
            return None
        arguments = {}
        for key in ('value', 'folder', 'content', 'find', 'platform', 'browser'):
            value = step.get(key, '')
            if not isinstance(value, str):
                return None
            if key == 'platform' and value not in {'', 'youtube', 'spotify'}:
                return None
            if key == 'browser' and value not in {'', 'chrome', 'edge', 'firefox'}:
                return None
            if key in {'platform', 'browser'} or not value:
                arguments[key] = value
            else:
                # Every target/content binding is supplied from the NEW request.
                # No old path, identifier, private text or approval survives.
                binding = (key, value)
                slot = bindings.setdefault(binding, key + '_' + str(len(bindings)+1))
                slots[slot] = {'type': 'string', 'source': 'current_request', 'field': key}
                arguments[key] = {'$slot': slot}
        steps.append({'action': action, 'arguments': arguments, 'verify': 'fresh independent readback of current requested result'})
    template = {'version': 1, 'teacher': 'qwen3.5:9b', 'slots': slots, 'steps': steps,
        'failure_conditions': ['changed prerequisites', 'unbound or ambiguous parameter', 'tool/schema unavailable',
                               'negative experience matches', 'uncertain earlier effect', 'independent verification failed'],
        'contract': 'Reference only; recheck tools, current scope, approval and preconditions; never replay uncertain effects.'}
    template['family'] = hashlib.sha256(json.dumps(template, sort_keys=True).encode()).hexdigest()[:20]
    return template


def readiness(procedures):
    """Idle metadata assessment only; never exports examples or starts training."""
    templates = [item['teacher_procedure'] for item in procedures.values()
                 if isinstance(item, dict) and isinstance(item.get('teacher_procedure'), dict)
                 and item.get('last_attempt') == 'verified']
    families = {item.get('family') for item in templates if item.get('family')}
    return {'teacher_procedures': len(templates), 'independent_families': len(families),
            'status': 'curation_and_consent_required' if len(families) >= 5 else 'more_verified_families_needed',
            'training_started': False, 'promotion_allowed': False}


def examples_from_task(task, relevant_context=None, *, privacy='private', private_authorized=False):
    """Explicit curated-export boundary; never called by the foreground runtime.

    Task verification is necessary, but human review is still required before
    these candidates enter the training pipeline. Never infer public provenance
    from a goal/model claim or copy an entire private context into a dataset.
    """
    if privacy not in {'public', 'private'} or (privacy == 'private' and private_authorized is not True):
        raise ValueError('Private teacher example export requires explicit authorization.')
    template = compile_procedure(task)
    routes = task.get('model_routes', [])
    if (template is None or not routes or any(not isinstance(r, dict) or r.get('model') != 'qwen3.5:9b' for r in routes)):
        raise ValueError('Export requires a wholly teacher-attributed verified trace.')
    context = relevant_context or {}
    if not isinstance(context, dict) or set(context) - {'tools', 'conditions'} or len(json.dumps(context)) > 8000:
        raise ValueError('Supply only bounded relevant tools and task conditions.')
    goal = task.get('goal')
    if not isinstance(goal, str) or not 1 <= len(goal) <= 2000:
        raise ValueError('A bounded original input is required.')
    from .native_tools import parameter_fields
    proof = [c.get('evidence') for c in task.get('checkpoints', []) if c.get('stage') == 'goal_verified' and c.get('evidence')]
    previous, examples = [], []
    for step in task['plan']['completed']:
        fields = parameter_fields(step['action'])
        arguments = {k: step[k] for k in fields if k in step}
        if not {'value', 'expected'} <= arguments.keys():
            raise ValueError('Teacher trace lacks complete native arguments.')
        examples.append({'input': json.dumps({'goal': goal, 'relevant_context': context, 'completed': previous}),
            'target': json.dumps({'name': step['action'], 'arguments': arguments}),
            'family': template['family'], 'teacher_model': 'qwen3.5:9b', 'privacy': privacy,
            'reviewed': False, 'verified': True,
            'verification': 'Whole-goal proof SHA256 '+hashlib.sha256(json.dumps(proof).encode()).hexdigest(),
            'source_task_id': task.get('task_id'), 'failure_conditions': template['failure_conditions']})
        previous = previous + [{k: step[k] for k in ('action', 'value', 'folder', 'result', 'verified') if k in step}]
    if any(len(row['input']) > 16000 or len(row['target']) > 16000 for row in examples):
        raise ValueError('Teacher context exceeds the curation budget; narrow it explicitly.')
    return examples


def curated_examples(rows, allow_private=False):
    """Caller supplies curated consent-marked examples, never a runtime auto-export."""
    seen, splits = set(), {'train': [], 'heldout': []}
    for row in rows:
        if (row.get('verified') is not True or row.get('reviewed') is not True
                or row.get('teacher_model') != 'qwen3.5:9b'
                or row.get('privacy') not in ({'public', 'private'} if allow_private else {'public'})):
            raise ValueError('Only reviewed, verified 9B examples with authorized privacy may train.')
        for field in ('input', 'target', 'family', 'verification'):
            if not isinstance(row.get(field), str) or not 1 <= len(row[field]) <= 16000:
                raise ValueError('Curated examples require bounded input, target, family and verification.')
        identity = hashlib.sha256((row['input']+'\n'+row['target']).encode()).hexdigest()
        if identity in seen:
            raise ValueError('Duplicate training example.')
        seen.add(identity)
        # Whole procedure families stay on one side. Variants cannot leak.
        split = 'heldout' if int(hashlib.sha256(row['family'].encode()).hexdigest()[:8], 16) % 5 == 0 else 'train'
        splits[split].append({**row, 'id': identity})
    if not all(splits.values()):
        raise ValueError('Curate more independent families: both train and heldout examples are required.')
    return splits
