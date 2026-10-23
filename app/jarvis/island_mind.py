"""The island's Mind view: the six-module cognitive architecture, live.

Nodes light up when their module worked in the last moment, dots flow along the pathways from active modules,
and clicking a node shows what it does in Jarvis, the code behind it, its pathways, latency and live contents.
"""
import math
import time
import tkinter as tk
from pathlib import Path

BG, CARD, TEXT, MUTED, ACCENT = '#000000', '#151515', '#eeeeee', '#909090', '#b4caff'
COLOURS = {'perception': '#7fd1ff', 'working_memory': '#b4caff', 'long_term_memory': '#c9a7ff',
           'reasoning': '#ffd27f', 'executive': '#8ff0b4', 'action': '#ff9f8f'}
# Grid positions (column, row) and the pathways between modules, as in the architecture diagram.
LAYOUT = {'perception': (0, 0), 'working_memory': (1, 0), 'reasoning': (2, 0),
          'action': (0, 1), 'executive': (1, 1), 'long_term_memory': (2, 1)}
EDGES = [('perception', 'working_memory', ''), ('working_memory', 'reasoning', ''),
         ('reasoning', 'long_term_memory', 'recall'), ('long_term_memory', 'reasoning', ''),
         ('reasoning', 'executive', ''), ('executive', 'action', ''),
         ('executive', 'long_term_memory', ''), ('action', 'long_term_memory', 'outcomes · consolidation'),
         ('action', 'perception', 'feedback')]
SHORT = {'perception': ('Perception', 'Vision · Speech · Sensing'), 'working_memory': ('Working Memory', 'Active context'),
         'long_term_memory': ('Long-Term Memory', 'Episodic · Procedural'), 'reasoning': ('Reasoning · World Model', 'Simulation · Inference'),
         'executive': ('Executive Control', 'Planning · Meta-learning'), 'action': ('Action / Tools', 'Actuators · Code · APIs')}


class MindView:
    def __init__(self, parent, app):
        self.app = app
        self.selected = 'reasoning'
        self.boxes = {}
        self.header = tk.Label(parent, text='Cognitive cycle · starting', bg=BG, fg=ACCENT, anchor='w',
                               font=('Segoe UI', 9, 'bold'))
        self.header.pack(fill='x')
        self.dag = tk.Label(parent,text='DAG · idle',bg=BG,fg=MUTED,anchor='w',justify='left',
                            wraplength=440,font=('Segoe UI',8))
        self.dag.pack(fill='x')
        self.dag_text = None
        # Cognitive awareness: operational state and controls, not a stream of internal thoughts.
        self.aware = tk.Label(parent, text='Awareness · off', bg=BG, fg=MUTED, anchor='w', justify='left',
                              wraplength=440, font=('Segoe UI', 8))
        self.aware.pack(fill='x')
        self.aware_text = None
        controls = tk.Frame(parent, bg=BG)
        controls.pack(fill='x')
        for label, value in (('Proactive on/off', 'toggle'), ('Focus', 'focus'), ('Pause exploring', 'exploration'),
                             ('Why?', 'why'), ("Don't suggest", 'feedback:reject_similar'), ('Clear observations', 'clear:all'),
                             ('Stop', 'stop')):
            tk.Button(controls, text=label, command=lambda v=value: self.awareness_control(v), bg=CARD, fg=TEXT,
                      activebackground='#2a2a2a', activeforeground=TEXT, relief='flat', font=('Segoe UI', 7),
                      padx=4, pady=1).pack(side='left', padx=(0, 3), pady=(1, 2))
        # Project collaboration: the active project's state from ProjectStore and the queue; voice remains primary.
        self.project = tk.Label(parent, text='Project · none', bg=BG, fg=MUTED, anchor='w', justify='left',
                                wraplength=440, font=('Segoe UI', 8))
        self.project.pack(fill='x')
        self.project_text = None
        actions_row = tk.Frame(parent, bg=BG)
        actions_row.pack(fill='x')
        for label, value in (('Next project', 'next'), ('Requirements', 'show the requirements'), ('Plan', 'show the plan'),
                             ("What's left", "what's left"), ('Blockers', 'what are the blockers'), ('Pause/Resume', 'toggle'),
                             ('Open folder', 'open')):
            tk.Button(actions_row, text=label, command=lambda v=value: self.project_control(v), bg=CARD, fg=TEXT,
                      activebackground='#2a2a2a', activeforeground=TEXT, relief='flat', font=('Segoe UI', 7),
                      padx=4, pady=1).pack(side='left', padx=(0, 3), pady=(1, 2))
        self.canvas = tk.Canvas(parent, bg=CARD, highlightthickness=0, height=220)
        self.canvas.pack(fill='x', pady=(2, 4))
        self.canvas.bind('<Button-1>', self.click)
        self.detail = tk.Label(parent, bg=CARD, fg=TEXT, anchor='nw', justify='left', font=('Segoe UI', 9),
                               padx=10, pady=8, wraplength=440)
        self.detail.pack(fill='both', expand=True)
        self.detail.bind('<Configure>', lambda e: self.detail.configure(wraplength=max(200, e.width - 20)))

    def cognition(self):
        return getattr(getattr(self.app, 'actions', None), 'cognition', None)

    def awareness(self):
        return getattr(getattr(self.app, 'actions', None), 'awareness', None)

    def awareness_control(self, value):
        engine = self.awareness()
        if engine is None or not engine.enabled:
            self.aware.configure(text='Awareness is off (config awareness.enabled)')
            return
        try:
            if value == 'toggle':
                reply = engine.control('off' if engine.proactive and not engine.stopped else 'resume')
            elif value == 'focus':
                reply = engine.control('focus:' + ('off' if engine.focus else 'on'))
            elif value == 'exploration':
                reply = engine.control('exploration:' + ('resume' if engine.curiosity.paused else 'pause'))
            elif value == 'why':
                reply = engine.status('why')
            else:
                reply = engine.control(value)
        except (ValueError, OSError) as exc:
            reply = 'Awareness control failed: ' + str(exc)[:120]
        self.detail.configure(text=reply)

    def projects(self):
        return getattr(getattr(self.app, 'actions', None), 'project_intel', None)

    def project_control(self, value):
        engine = self.projects()
        if engine is None or not engine.enabled:
            self.detail.configure(text='Project intelligence is off (config project_intelligence.enabled)')
            return
        from .commands import Command
        try:
            project = engine.store.active()
            if value == 'next':
                rows = engine.store.all()
                if not rows:
                    reply = 'No projects yet. Say "create a new project".'
                else:
                    index = next((i for i, p in enumerate(rows) if project and p['id'] == project['id']), -1)
                    engine.store.setting('active_project', rows[(index + 1) % len(rows)]['id'])
                    reply = 'Active project: ' + rows[(index + 1) % len(rows)]['name']
            elif value == 'open':
                if project and project.get('workspace') and Path(project['workspace']).is_dir():
                    import os
                    os.startfile(project['workspace'])  # Opens the project's own workspace in Explorer.
                    reply = 'Opened ' + project['workspace']
                else:
                    reply = 'The workspace has not been created yet.'
            else:
                text = ('resume the project' if project and project['status'] == 'paused' else 'pause the project') if value == 'toggle' else value
                reply = engine.handle(Command('project', text))
        except (ValueError, OSError) as exc:
            reply = 'Project control failed: ' + str(exc)[:160]
        self.detail.configure(text=reply)

    def refresh_project(self):
        engine = self.projects()
        snap = engine.snapshot() if engine is not None else {'enabled': False}
        if not snap.get('enabled'):
            text = 'Project · off (config project_intelligence.enabled)'
        elif not snap.get('project'):
            text = f"Project · none active ({snap.get('projects', 0)} saved)"
        else:
            done, total = snap['progress']
            parts = [f"Project · {snap['project']} · {snap['status']} · spec v{snap['version']} · {done}/{total} tasks done"]
            if snap['task']:
                parts.append(f"Now: {snap['milestone']} · {snap['task'][:70]}")
            if snap['question']:
                parts.append('Waiting for you: ' + snap['question'][:110])
            change = snap.get('last_change') or {}
            if change.get('op'):
                parts.append(f"Last change: {change['op']} {change.get('requirement', '')} {str(change.get('text') or change.get('to') or '')[:60]}".rstrip())
            results = snap.get('verification') or {}
            if results:
                parts.append('Checks: ' + ', '.join(f'{k} {v}' for k, v in list(results.items())[:6]))
            if snap['blockers']:
                parts.append(f"Blocked tasks: {snap['blockers']}")
            if snap['next']:
                parts.append(snap['next'])
            text = '\n'.join(parts)
        if text != self.project_text:
            self.project.configure(text=text)
            self.project_text = text

    def refresh_awareness(self):
        engine = self.awareness()
        if engine is None or not engine.enabled:
            text = 'Awareness · off (config awareness.enabled)'
        else:
            snap = engine.snapshot()
            mode = 'stopped' if snap['stopped'] else 'proactive' if snap['proactive'] else 'observe only'
            parts = [f"Awareness · {snap['status']} · {mode}" + (' · focus' if snap['focus'] else '') +
                     (' · exploring paused' if snap['exploration_paused'] else '')]
            if snap['goal']:
                parts.append('Goal: ' + snap['goal']['text'][:70])
            if snap['observation']:
                parts.append('Noticed: ' + snap['observation']['type'].replace('.', ' ') + ' · ' + str(snap['observation']['subject'])[:50])
            suggestion = snap['suggestion']
            if suggestion:
                parts.append(f"#{suggestion['number']} {suggestion['action'].replace('_', ' ')} · {suggestion['status']}"
                             + (' · automatic' if suggestion.get('automatic') else '') + ': ' + (suggestion.get('message') or suggestion['subject'])[:90])
            prediction = snap['prediction']
            if prediction:
                parts.append(f"Predicts: {prediction['consequence'][:70]} ({prediction['probability']:.0%}"
                             + ('' if prediction['calibrated'] else ', uncalibrated') + ')')
            if snap['warnings']:
                parts.append('Warnings: ' + ', '.join(snap['warnings']))
            text = '\n'.join(parts)
        if text != self.aware_text:
            self.aware.configure(text=text)
            self.aware_text = text

    def click(self, event):
        for name, (x1, y1, x2, y2) in self.boxes.items():
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.selected = name
                self.refresh()
                return

    def refresh(self):
        if getattr(self, 'aware', None) is not None:
            try:
                self.refresh_awareness()
            except Exception as exc:  # The awareness strip never breaks the Mind view.
                self.aware.configure(text='Awareness · unavailable (' + type(exc).__name__ + ')')
        if getattr(self, 'project', None) is not None:
            try:
                self.refresh_project()
            except Exception as exc:  # Nor does the project strip.
                self.project.configure(text='Project · unavailable (' + type(exc).__name__ + ')')
        cognition = self.cognition()
        if cognition is None or not cognition.enabled:
            self.header.configure(text='Cognitive loop is off (config cognition.enabled)')
            return
        if not cognition.lock.acquire(blocking=False):return
        try:snap = cognition.snapshot()
        finally:cognition.lock.release()
        state=getattr(getattr(self.app,'actions',None),'task_state',None)
        if state is not None:
            task=state.ui_snapshot()
            if task is not None:
                rows=task['steps']
                text=('DAG · '+task['status']+' · '+str(len(rows))+' nodes\n'+
                      ' · '.join(row['id']+': '+row['status'] for row in rows[:8])) if rows else 'DAG · '+task['status']
                adaptive = task.get('adaptive')
                if adaptive:
                    text = ('Task · ' + adaptive['state'] + ' · ' + str(adaptive['completed']) +
                            ' verified · ' + str(adaptive['remaining']) + ' remaining · ' +
                            str(adaptive['planning_cycles']) + ' planning calls')
                if text!=self.dag_text:
                    self.dag.configure(text=text)
                    self.dag_text=text
        self.header.configure(text=f"Cognitive cycle · {snap['cycle_hz']} Hz · {snap['cycles']} cycles · click a module for details")
        self.draw(snap)
        self.describe(snap)

    def draw(self, snap):
        c = self.canvas
        c.delete('all')
        width, height = max(300, c.winfo_width()), max(150, c.winfo_height())
        bw, bh = width * .29, height * .3
        centres = {name: (width * (.17 + .33 * col), height * (.2 + .46 * row)) for name, (col, row) in LAYOUT.items()}
        self.boxes = {name: (x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2) for name, (x, y) in centres.items()}
        modules, now = snap['modules'], time.time()
        for index, (source, target, caption) in enumerate(EDGES):
            (x1, y1), (x2, y2) = self.anchor(source, target), self.anchor(target, source)
            if source == 'long_term_memory' and target == 'reasoning':
                x1, x2 = x1 + 14, x2 + 14  # Two-way recall: a second, offset line.
            elif source == 'reasoning' and target == 'long_term_memory':
                x1, x2 = x1 - 14, x2 - 14
            if source == 'action' and target == 'long_term_memory':
                points = [x1, y1, (x1 + x2) / 2, height + 34, x2, y2]  # Below the executive.
            else:
                points = [x1, y1, x2, y2]
            live = modules[source]['active']
            c.create_line(*points, fill=COLOURS[source] if live else '#3a3a3a', width=2 if live else 1,
                          arrow='last', arrowshape=(8, 9, 3), smooth=len(points) > 4)
            if caption:
                mx, my = points[len(points) // 2 - 1 if len(points) > 4 else 0], points[len(points) // 2 if len(points) > 4 else 1]
                if len(points) == 4:
                    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                c.create_text(mx, my - 7 if len(points) == 4 else height - 8, text=caption, fill=MUTED, font=('Segoe UI', 7))
            if live:  # Data flowing along an active pathway.
                for k in range(3):
                    t = (now * .9 + k / 3 + index * .13) % 1
                    px, py = self.along(points, t)
                    c.create_oval(px - 2.5, py - 2.5, px + 2.5, py + 2.5, fill=COLOURS[source], outline='')
        for name, (x1, y1, x2, y2) in self.boxes.items():
            active, chosen = modules[name]['active'], name == self.selected
            glow = COLOURS[name]
            if active:
                pulse = 2 + math.sin(now * 8) * 1.5
                c.create_rectangle(x1 - pulse, y1 - pulse, x2 + pulse, y2 + pulse, outline=glow, width=1)
            c.create_rectangle(x1, y1, x2, y2, fill='#22252c' if active else '#1b1c21',
                               outline=glow if (active or chosen) else '#444', width=2 if chosen else 1)
            title, subtitle = SHORT[name]
            c.create_text((x1 + x2) / 2, y1 + bh * .34, text=title, fill=glow if active else TEXT, font=('Segoe UI', 8, 'bold'),
                          width=x2 - x1 - 6)
            c.create_text((x1 + x2) / 2, y1 + bh * .74, text=subtitle, fill=MUTED, font=('Segoe UI', 7), width=x2 - x1 - 6)

    def anchor(self, name, toward):
        x1, y1, x2, y2 = self.boxes[name]
        tx1, ty1, tx2, ty2 = self.boxes[toward]
        cx, cy, tx, ty = (x1 + x2) / 2, (y1 + y2) / 2, (tx1 + tx2) / 2, (ty1 + ty2) / 2
        if abs(cy - ty) < 5:
            return (x2, cy) if tx > cx else (x1, cy)
        if abs(cx - tx) < 5:
            return (cx, y2) if ty > cy else (cx, y1)
        return ((x2 if tx > cx else x1) - (12 if tx > cx else -12), y2 if ty > cy else y1)

    @staticmethod
    def along(points, t):
        if len(points) == 4:
            return points[0] + (points[2] - points[0]) * t, points[1] + (points[3] - points[1]) * t
        (ax, ay, bx, by, cx, cy) = points  # Quadratic curve through the control point.
        return ((1 - t) ** 2 * ax + 2 * (1 - t) * t * bx + t * t * cx, (1 - t) ** 2 * ay + 2 * (1 - t) * t * by + t * t * cy)

    def describe(self, snap):
        from .cognition import NODES
        name = self.selected
        title, subtitle, tier, description, code, pathways = NODES[name]
        module = snap['modules'][name]
        latency = f"{module['latency_ms']} ms" if module['latency_ms'] else 'not measured yet'
        last = f"{module['last_s']} s ago" if module['last_s'] is not None else 'not yet'
        lines = [f"{title}  ·  {subtitle}  ·  {tier}", description, '', f"Mechanism: {code}", f"Pathways: {pathways}",
                 f"Latency: {latency}  ·  last active {last}  ·  {module['events']} events"]
        live = self.live(name, snap)
        if live:
            lines += ['', live]
        self.detail.configure(text='\n'.join(lines))

    @staticmethod
    def live(name, snap):
        wm = snap['working_memory']
        if name == 'working_memory':
            parts = [f"Goal: {wm['goal'][:90]}" if wm.get('goal') else 'Goal: none',
                     f"Task: {wm['active_task'][:70]}" if wm.get('active_task') else '',
                     f"Waiting on: {wm['pending'][:70]}" if wm.get('pending') else '']
            parts += ['• ' + a for a in wm.get('attention', [])[:3]]
            return '\n'.join(p for p in parts if p)
        if name == 'perception':
            return '\n'.join('• ' + a for a in wm.get('attention', [])[:4]) or 'Nothing perceived yet.'
        if name == 'reasoning' and snap['last_prediction']:
            p = snap['last_prediction']
            return (f"Last prediction: {p['kind']} — {p['effect']}; {'reversible' if p['reversible'] else 'not reversible'}; "
                    f"~{p['expected_seconds']} s; success {round(p['success_chance'] * 100)}%"
                    + (f"; unsure: {p['uncertain'][0]}" if p['uncertain'] else ''))
        if name == 'executive' and snap['last_outcome']:
            o = snap['last_outcome']
            return f"Last outcome: {o['kind']} {'worked' if o['ok'] else 'failed'} in {o['seconds']} s (surprise {o['surprise']})"
        if name == 'long_term_memory':
            rows = [f"{k}: {v['attempts']} runs, {round(v['success'] * 100)}% ok" for k, v in list(snap['procedures'].items())[:3]]
            rows += ['Lesson: ' + lesson[17:][:90] for lesson in snap['lessons'][-2:]]
            return '\n'.join(rows) or 'No procedures recorded yet.'
        if name == 'action':
            return f"Last action: {wm['last_action'][:90]}" if wm.get('last_action') else 'No action yet this session.'
        return ''
