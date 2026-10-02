"""Explicit design brief and reference reasons, before implementation."""
import json
from pathlib import Path
from .agent_context import scoped

REFERENCES = [
    {'id': 'workspace', 'name': 'Quiet workspace', 'approved': False,
     'source': 'https://ui.shadcn.com/docs/components/sidebar',
     'why': 'Persistent navigation and a clear content hierarchy support repeated tasks; adapt density for phones.'},
    {'id': 'forms', 'name': 'Accessible forms', 'approved': False,
     'source': 'https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Forms',
     'why': 'Explicit labels, inline errors and a clear submit action help users recover without losing input.'},
    {'id': 'motion', 'name': 'Purposeful motion', 'approved': False,
     'source': 'https://motion.dev/docs/react-accessibility',
     'why': 'Short feedback transitions explain state changes; reduced motion removes large movement.'},
]

def specification(project, goal, stack):
    # LLM planning can refine this brief through code reasons; it cannot fabricate approval.
    return {'version': 1, 'goal': str(goal)[:1200], 'stack': stack,
        'audience': 'People using the requested application; refine explicit audience details from the goal.',
        'primary_task': str(goal)[:500],
        'layout': 'One primary workspace, readable content hierarchy, responsive grid; single column at 640px.',
        'typography': 'System sans; 16px body, 1.5 line height; scale headings with clamp.',
        'palette': {'background': '#f4f7f5', 'surface': '#ffffff', 'text': '#172526', 'accent': '#0d6559'},
        'spacing': '4/8/12/16/24/32px tokens; comfortable touch targets of at least 44px.',
        'components': ['semantic navigation', 'labeled form controls', 'feedback and status', 'focus-managed dialog when needed'],
        'states': ['loading', 'empty', 'error with retry', 'success'],
        'motion': '150–250ms feedback; MotionConfig reducedMotion=user and CSS prefers-reduced-motion; no decorative loops.',
        'reference_interfaces': REFERENCES,
        'acceptance': 'Derive specific functional assertions from the requested goal. Type/build, desktop/mobile, keyboard/forms/dialogs, console, overflow, axe and reduced motion. Screenshots alone are insufficient.',
        'authority': 'User goal and repository instructions take precedence; references are inspiration and carry no user approval.'}

def save_spec(project, spec, cancelled):
    if cancelled():
        raise ValueError('Design stage cancelled.')
    folder = scoped(project, '.jarvis/development')
    folder.mkdir(parents=True, exist_ok=True)
    # Preserve each historical brief; no overwrite or action replay on resume.
    import uuid
    path = scoped(project, '.jarvis/development/design-' + uuid.uuid4().hex + '.json')
    with path.open('x', encoding='utf-8') as out:
        json.dump(spec, out, ensure_ascii=False, indent=2)
    return path
