"""Display snapshots of real pending choices, bound to their original authority."""
import hashlib
import json
import re
import time


def snapshot(actions, now=None):
    now = time.monotonic() if now is None else now
    from .whatsapp import snapshot as whatsapp_snapshot
    waiting = whatsapp_snapshot(actions)
    if waiting:
        return waiting  # A paused WhatsApp step (contact choice, message preview, incoming call).
    knowledge = getattr(actions, 'knowledge', None)
    if knowledge is not None and getattr(knowledge, 'pending_memory', None):
        card = knowledge.choice_snapshot()
        if card:
            return card
    groups = [('open', actions.pending_open, 45), ('project', actions.projects.pending, 180),
              ('control', actions.ui_controls.pending if actions.ui_controls else None, 45),
              ('task', actions.pending_question, 180)]
    for kind, pending, lifetime in groups:
        if not pending or not pending.get('choices') or now-pending['time'] > lifetime:
            continue
        choices = pending['choices']
        labels = [str(c.value) if kind=='open' else str(c.name) if kind=='project'
                  else str(c['name']) if kind=='control' else str(c) for c in choices]
        identity = {'kind': kind, 'time': pending['time'], 'generation': actions.generation,
                    'handle': pending.get('handle'), 'signature': pending.get('signature'),
                    'verb': pending.get('verb'), 'labels': labels}
        token = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        images = pending.get('thumbnails', {})
        return {'token': token, 'kind': kind, 'expires': pending['time']+lifetime,
                'question': pending.get('question', 'Choose an option or say its name / number.'),
                'options': [{'label': label[:500], 'image': images.get(str(c.get('id')), '') if kind=='control' else ''}
                            for label,c in zip(labels,choices)]}
    return None


def resolve(actions, token, index):
    from .commands import Command
    current = snapshot(actions)
    if not current or current['token'] != token or not 0 <= index < len(current['options']):
        raise ValueError('Those choices changed or expired. Repeat the request for a fresh list.')
    if current['kind'] == 'memory':
        return Command('memory_choice', str(index), token)
    if current['kind']=='open':
        selected = actions.pending_open['choices'][index]
        actions.pending_open = None
        actions.report('question','')
        return selected
    if current['kind']=='project':
        selected = actions.projects.pending['choices'][index]
        actions.projects.pending = None
        actions.report('question','')
        return Command('open_project',str(selected))
    if current['kind']=='control':
        return Command('island_control_choice',str(index),token)
    return actions._resolve_reply(Command('choose_control',str(index+1)),task_pending=actions.pending_question)


def navigation(text):
    text = str(text).strip().casefold().rstrip('.!?')
    match = re.fullmatch(r'(pause|resume|restart|stop) (?:the )?game',text)
    if match:
        return ('Games','@'+match[1])
    aliases = {'flappy': 'Flappy', 'flappy bird': 'Flappy', 'snake':'Snake', '2048':'2048',
               'tic tac toe':'Tic Tac Toe', 'tic-tac-toe':'Tic Tac Toe', 'memory':'Memory', 'memory pairs':'Memory'}
    match = re.fullmatch(r'(?:play|open|show|start)(?: the)? (.+?)(?: game)?(?: (?:in|on) (?:the )?island)?',text)
    if match and match[1] in aliases:
        return ('Games',aliases[match[1]])
    match = re.fullmatch(r'(?:show|open) (?:the )?(games|music|choices|overview|history|settings)(?: (?:in|on) (?:the )?island)?',text)
    return (match[1].title(),'') if match else None


def task_answer(state, text):
    """Answer local work questions from recorded state, without inventing a day plan."""
    text = str(text).strip().casefold().replace('’', "'").rstrip('?.!')
    daily = re.fullmatch(r"(?:what(?:'s| is)|show)(?: me)? my goals?(?: for)? today", text)
    work = text in {'what task was i working on', 'what was i working on', 'what am i working on',
                    'what are you doing', 'what are you doing currently', 'what file are you working on', 'show current task'}
    if not daily and not work:
        return None
    current = state.snapshot() if state is not None else None
    if daily:
        from datetime import datetime
        if current and current.get('started_at'):
            try:
                today = datetime.fromisoformat(current['started_at']).astimezone().date() == datetime.now().date()
            except ValueError:
                today = False
            if today:
                return "Today's recorded task: " + current['goal'] + '\nStatus: ' + current['status'] + '.\nNo separate daily goal list is connected.'
        return 'No daily goal is recorded for today. Tell me a goal or start a task to track it here.'
    if text in {'what task was i working on', 'what was i working on', 'what am i working on',
                'what are you doing', 'what are you doing currently', 'what file are you working on', 'show current task'}:
        if not current:
            return 'No task has been recorded yet.'
        points = current.get('checkpoints', [])
        target = next((p['target'] for p in reversed(points) if p.get('target')), current.get('project'))
        return ('Recorded task: ' + current['goal'] + '\nStatus: ' + current['status'] +
                ' · ' + current.get('stage','') + ('\nLast recorded target: '+target if target else '') +
                ('\n'+current['result'] if current.get('result') else ''))
    return None
