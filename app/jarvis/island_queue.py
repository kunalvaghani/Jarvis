"""Native queue controls backed by the same persistent task lifecycle."""
import json
import tkinter as tk
from tkinter import ttk


class QueueView:
    def __init__(self, parent, app):
        self.app, self.parent = app, parent
        # The real Island is compact. Keep routine decisions outside the scroll
        # body so a mapped but clipped queue cannot silently start their timer.
        self.decision_bar = ttk.Frame(parent)
        self.decision_bar.pack(fill='x',side='top')
        viewport = ttk.Frame(parent); viewport.pack(fill='both',expand=True)
        self.canvas = tk.Canvas(viewport,highlightthickness=0,borderwidth=0)
        scrollbar = ttk.Scrollbar(viewport,orient='vertical',command=self.canvas.yview)
        scrollbar.pack(side='right',fill='y');self.canvas.pack(side='left',fill='both',expand=True)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.body = ttk.Frame(self.canvas)
        self.body_window = self.canvas.create_window((0,0),window=self.body,anchor='nw',
            state='normal' if self.parent.winfo_ismapped() else 'hidden')
        # Tk canvas window items can retain their mapped flag under an unmapped
        # ancestor. Explicitly hide/show the item with the actual Queue surface.
        self.parent.bind('<Map>',lambda event:self.map_body(event,True),add='+')
        self.parent.bind('<Unmap>',lambda event:self.map_body(event,False),add='+')
        self.body.bind('<Configure>',lambda _event:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',self.resize_body)
        parent = self.body
        self.summary = tk.StringVar(value='Durable task queue')
        self.summary_label = ttk.Label(parent, textvariable=self.summary, wraplength=720)
        self.summary_label.pack(fill='x')
        bar = ttk.Frame(parent)
        bar.pack(fill='x')
        self.buttons(bar,[(caption,lambda a=action:self.control(a)) for caption,action in
            [('Pause queue','pause_queue'),('Resume queue','resume_queue'),('Stop all','cancel'),('Cancel waiting','cancel_pending')]]+
            [('Overnight',lambda:self.send('run the queue overnight')),('Day mode',lambda:self.send('day mode')),
             ('Report',lambda:self.send('open the morning report'))],lambda callback:callback())
        self.groups = ttk.Treeview(parent, columns=('project','progress','status'), show='headings', height=3)
        for key in ('project','progress','status'):
            self.groups.heading(key,text=key.title())
            self.groups.column(key,width=230)
        self.groups.pack(fill='x')
        group_bar = ttk.Frame(parent); group_bar.pack(fill='x')
        self.buttons(group_bar,[('Inspect group','inspect'),('Pause group','pause'),('Resume group','resume'),
                              ('Urgent group','urgent'),('Cancel pending branches','cancel pending')],self.group_action)
        self.tree = ttk.Treeview(parent, columns=('state','priority','lane','task'), show='headings', height=8)
        for key, width in [('state',145),('priority',60),('lane',70),('task',350)]:
            self.tree.heading(key, text=key.title())
            self.tree.column(key, width=width)
        self.tree.pack(fill='both', expand=True)
        controls = ttk.Frame(parent)
        controls.pack(fill='x')
        self.buttons(controls,[(label,lambda a=action:self.control(a,True)) for label,action in
            [('Pause','pause'),('Resume','resume'),('Cancel','cancel'),('Urgent','urgent'),('Earlier','earlier'),('Later','later'),('Review generated','review')]]+
            [('Inspect',self.inspect)],lambda callback:callback())
        workflow_bar = ttk.Frame(parent); workflow_bar.pack(fill='x')
        self.workflow_text = tk.StringVar()
        ttk.Label(workflow_bar,text='Owning workflow ID:').pack(side='left')
        ttk.Entry(workflow_bar,textvariable=self.workflow_text).pack(side='left',fill='x',expand=True)
        ttk.Button(workflow_bar,text='Move selected',command=self.move_selected).pack(side='left')
        ttk.Button(workflow_bar,text='Split selected',command=self.split_selected).pack(side='left')
        answer_bar = ttk.Frame(parent)
        answer_bar.pack(fill='x')
        self.answer_text = tk.StringVar()
        ttk.Label(answer_bar, text='Answer selected paused task:').pack(side='left')
        ttk.Entry(answer_bar, textvariable=self.answer_text).pack(side='left', fill='x', expand=True)
        ttk.Button(answer_bar, text='Submit answer', command=self.answer_selected).pack(side='left')
        self.detail = tk.Text(parent, height=7, wrap='word')
        self.detail.pack(fill='both', expand=True)
        self.last_decision = None

    def resize_body(self, event):
        self.canvas.itemconfigure(self.body_window,width=event.width)
        self.summary_label.configure(wraplength=max(100,event.width-20))

    def map_body(self, event, visible):
        if event.widget == self.parent and self.canvas.winfo_exists():
            self.canvas.itemconfigure(self.body_window,state='normal' if visible else 'hidden')

    @staticmethod
    def buttons(parent, choices, command):
        for index,(label,action) in enumerate(choices):
            ttk.Button(parent,text=label,command=lambda a=action:command(a)).grid(
                row=index//3,column=index%3,sticky='ew')
        for column in range(3):parent.columnconfigure(column,weight=1)

    def decision_visible(self):
        if not self.parent.winfo_ismapped() or not self.decision_bar.winfo_ismapped():return False
        x,y = self.parent.winfo_rootx(),self.parent.winfo_rooty()
        right,bottom = x+self.parent.winfo_width(),y+self.parent.winfo_height()
        todo = list(self.decision_bar.winfo_children())
        while todo:
            widget = todo.pop();children = widget.winfo_children();todo.extend(children)
            if not widget.winfo_ismapped():return False
            if not children:
                left,top = widget.winfo_rootx(),widget.winfo_rooty()
                if (left<x or top<y or left+widget.winfo_width()>right or top+widget.winfo_height()>bottom
                        or widget.winfo_width()<widget.winfo_reqwidth() or widget.winfo_height()<widget.winfo_reqheight()):return False
        return bool(self.decision_bar.winfo_children())

    def ingress(self):
        return getattr(self.app.actions, 'ingress', None)

    def send(self, text):
        from .commands import Command
        self.app.actions.submit(Command('task', text))

    def control(self, action, selected=False):
        ingress = self.ingress()
        if ingress is None:
            return
        chosen = self.tree.selection()
        if selected and not chosen:
            return
        try:
            ingress.scheduler.control(action, chosen[0] if selected else None)
        except ValueError as exc:
            self.app.report('warning', str(exc))
        self.tick()

    def inspect(self):
        ingress, selected = self.ingress(), self.tree.selection()
        if ingress is None:
            return
        if selected:
            row = ingress.store.get(selected[0])
            graph = ingress.scheduler.graph
            data = {**row, 'history': ingress.store.history(row['id']), 'decisions': ingress.decisions.rows(),
                'ownership':graph.node(row['id']), 'result':graph.result(row['id']),
                'requirements':graph.edges(row['id']), 'readiness':graph.evaluate(row['id']),
                'relationships':[r for r in graph.snapshot()['relationships'] if row['id'] in {r['source'],r['target']}]}
        else:
            data = {'last_report': ingress.store.setting('last_report'), 'decisions': ingress.decisions.rows()}
        self.detail.delete('1.0', 'end')
        self.detail.insert('end', json.dumps(data, ensure_ascii=False, indent=2))

    def group_action(self, action):
        ingress, selected = self.ingress(), self.groups.selection()
        if ingress is None or not selected:return
        try:
            if action == 'inspect':
                graph = ingress.scheduler.graph.snapshot()
                data = {'group':next(g for g in graph['groups'] if g['id']==selected[0]),
                        'graph_revision':graph['revision'],'edges':graph['edges'],'decisions':ingress.decisions.rows()}
                self.detail.delete('1.0','end'); self.detail.insert('end',json.dumps(data,ensure_ascii=False,indent=2))
            else:ingress.group_control(action,selected[0])
        except ValueError as exc:self.app.report('warning',str(exc))
        self.tick()

    def move_selected(self):
        ingress, selected = self.ingress(), self.tree.selection()
        if ingress is None or not selected:return
        try:
            with ingress.scheduler.lock:ingress.scheduler.graph.move(selected[0],self.workflow_text.get().strip())
        except ValueError as exc:self.app.report('warning',str(exc))
        self.tick()

    def split_selected(self):
        ingress, selected = self.ingress(), self.tree.selection()
        if ingress is None or not selected:return
        try:
            with ingress.scheduler.lock:self.workflow_text.set(ingress.scheduler.graph.split(selected[0]))
        except ValueError as exc:self.app.report('warning',str(exc))
        self.tick()

    def answer_selected(self):
        ingress, selected = self.ingress(), self.tree.selection()
        if ingress is None or not selected:return
        row = ingress.store.get(selected[0])
        if row['state'] != 'WAITING_USER' or not row['checkpoint'].get('clarification'):
            self.app.report('warning', 'Select a task with a saved clarification; inspect uncertain effects separately.')
            return
        answer = self.answer_text.get().strip()
        if not 0 < len(answer) <= 2000:
            self.app.report('warning', 'Enter a clarification answer of at most 2000 characters.')
            return
        self.send(f"answer task {row['number']}: {answer}")
        self.answer_text.set('')

    def choose(self, identity, index):
        ingress = self.ingress()
        changed, decision = ingress.decisions.choose(identity, index)
        if changed or decision['status'] != 'PENDING':
            ingress.apply_decision(decision)
        self.last_decision = None
        self.tick()

    def tick(self):
        ingress = self.ingress()
        if ingress is None:
            self.summary.set('Durable task queue disabled in configuration or UI verification mode')
            return
        snapshot = ingress.scheduler.snapshot()
        self.summary.set(f"{snapshot['total']} admitted · {snapshot['running']} running · {snapshot['queued']} waiting · {snapshot['counts']}\n"
                         f"Overnight: {snapshot['overnight']} · Resources: {snapshot['resources']} · Estimates have high uncertainty")
        selected = self.tree.selection()
        graph = snapshot['graph']
        visible_groups = [g for g in graph['groups'] if g['total']]
        group_ids = {g['id'] for g in visible_groups}
        for identity in self.groups.get_children():
            if identity not in group_ids:self.groups.delete(identity)
        group_by_task = {}
        for group in visible_groups:
            name = group['project'] or group['goal'][:45]
            for task in group['tasks']:group_by_task[task] = name
            values = (name,f"{group['completed']}/{group['total']} · {group['progress']:.0%}",
                      'PAUSED' if group['paused'] else str(group['counts']))
            if self.groups.exists(group['id']):self.groups.item(group['id'],values=values)
            else:self.groups.insert('','end',iid=group['id'],values=values)
        # Update rows in place to retain selection, scroll position and input focus.
        rows = snapshot['tasks']
        identities = {r['id'] for r in rows}
        for identity in self.tree.get_children():
            if identity not in identities:
                self.tree.delete(identity)
        for row in rows:
            values = (row['state'],row['spec'].get('priority',0),row['spec'].get('lane','intake'),
                      f"#{row['number']} [{group_by_task.get(row['id'],'intake')}] {row['command'].get('value') or row['command']['kind']}"
                      +(f" · waits for {len(graph['evaluations'][row['id']]['blockers'])} prerequisites"
                        if graph['evaluations'].get(row['id'],{}).get('blockers') else ''))
            if self.tree.exists(row['id']):
                self.tree.item(row['id'], values=values)
            else:
                self.tree.insert('', 'end', iid=row['id'], values=values)
        pending = next((d for d in ingress.decisions.rows() if d['status'] == 'PENDING'), None)
        key = pending['id'] if pending else None
        if key != self.last_decision:
            for widget in self.decision_bar.winfo_children():
                widget.destroy()
            self.last_decision = key
            if pending:
                ttk.Label(self.decision_bar, text=pending['question'],wraplength=420).pack(fill='x')
                options = ttk.Frame(self.decision_bar);options.pack(fill='x')
                for i, label in enumerate(pending['options']):
                    ttk.Button(options, text=label, command=lambda n=i,k=key:self.choose(k,n)).grid(row=i//2,column=i%2,sticky='ew')
                for column in range(2):options.columnconfigure(column,weight=1)
        if pending and self.decision_visible():
            ingress.decisions.presented(key)  # Timer starts only after the question is on screen.
