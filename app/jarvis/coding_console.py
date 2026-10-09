"""Bounded native coding activity with inspectable commands and real source diffs."""
import json
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText


class CodingConsole:
    def __init__(self, parent, code=None, command=None, stop=None):
        self.callbacks={'code':code,'command':command,'stop':stop}
        self.frame=tk.Frame(parent,bg='#111111');self.frame.pack(fill='both',expand=True)
        style=ttk.Style(parent)
        if 'JarvisCoding.field' not in style.element_names():style.element_create('JarvisCoding.field','from','clam','Treeview.field')
        style.layout('JarvisCoding.Treeview',[('JarvisCoding.field',{'sticky':'nswe','children':[
            ('Treeview.padding',{'sticky':'nswe','children':[('Treeview.treearea',{'sticky':'nswe'})]})]})])
        style.configure('JarvisCoding.Treeview',background='#181818',fieldbackground='#181818',foreground='#e9e9ef',rowheight=27,font=('Segoe UI',10))
        style.map('JarvisCoding.Treeview',background=[('selected','#303b55')],foreground=[('selected','#ffffff')])
        self.rows={};self.order=[];self.windows=[]
        self.summary=tk.StringVar(value='Jarvis coding · commands, edits and checks')
        tk.Label(self.frame,textvariable=self.summary,bg='#111111',fg='#c1c6d4',anchor='w').pack(fill='x')
        self.tree=ttk.Treeview(self.frame,columns=('state','seconds'),show='tree headings',height=5,style='JarvisCoding.Treeview')
        self.tree.heading('#0',text='Activity · select to expand');self.tree.heading('state',text='Result');self.tree.heading('seconds',text='Time')
        self.tree.column('#0',width=300);self.tree.column('state',width=80);self.tree.column('seconds',width=55)
        self.tree.pack(fill='both',expand=True)
        self.detail=ScrolledText(self.frame,height=7,bg='#1b1b1b',fg='#e9e9ef',insertbackground='white',font=('Consolas',10),wrap='word',state='disabled')
        self.detail.pack(fill='both',expand=True,pady=(4,0));self.detail.tag_configure('added',foreground='#83daa5');self.detail.tag_configure('removed',foreground='#ff9090')
        self.tree.bind('<<TreeviewSelect>>',self.expand)
        ttk.Button(self.frame,text='Open coding workspace',command=self.open).pack(anchor='e',pady=3)

    def notify(self, row):
        key=str(row.get('id',''))
        if not key:return
        if key not in self.rows:
            self.order.append(key);self.tree.insert('', 'end',iid=key)
        self.rows[key]=dict(row)
        self.tree.item(key,text=row.get('label','Activity'),values=(row.get('state',''),str(row.get('seconds',''))+'s' if 'seconds' in row else ''))
        self.tree.see(key)
        while len(self.order)>300:
            old=self.order.pop(0);self.rows.pop(old,None);self.tree.delete(old)
        edited={r.get('file') for r in self.rows.values() if r.get('file')}
        self.summary.set(f'Jarvis coding · {len(edited)} files changed · {len(self.order)} activities')
        if self.tree.selection()==(key,):self.expand()
        for window,console in list(self.windows):
            if window.winfo_exists():console.notify(row)
            else:self.windows.remove((window,console))

    def expand(self, _event=None):
        selected=self.tree.selection()
        if not selected:return
        row=self.rows[selected[0]]
        self.detail.configure(state='normal');self.detail.delete('1.0','end')
        self.detail.insert('end',row.get('label','')+'\n'+row.get('detail','')+'\n')
        if row.get('file'):self.detail.insert('end',f"{row['file']} +{row.get('added',0)} −{row.get('removed',0)}\n")
        for line in str(row.get('diff') or row.get('output','')).splitlines(keepends=True):
            self.detail.insert('end',line,'added' if line.startswith('+') else 'removed' if line.startswith('-') else '')
        if row.get('gpu'):self.detail.insert('end','\nGPU allocation: '+json.dumps(row['gpu']))
        self.detail.configure(state='disabled')

    def open(self):
        window=tk.Toplevel(self.frame);window.title('Jarvis coding workspace');window.geometry('1000x700')
        # Pack input controls before the expanding review, keeping them reachable.
        if any(self.callbacks.values()):
            controls=tk.Frame(window,bg='#111111');controls.pack(side='bottom',fill='x',padx=8,pady=8)
            goal=ttk.Entry(controls);goal.pack(fill='x',pady=4)
            row=tk.Frame(controls,bg='#111111');row.pack(fill='x')
            if self.callbacks['code']:ttk.Button(row,text='Code in chosen folder…',command=lambda:self.callbacks['code'](goal.get())).pack(side='left')
            if self.callbacks['stop']:ttk.Button(row,text='Stop task',command=self.callbacks['stop']).pack(side='right')
            shell=ttk.Entry(controls);shell.pack(fill='x',pady=4)
            if self.callbacks['command']:
                def run():
                    value=shell.get().strip()
                    if value:self.callbacks['command'](value);shell.delete(0,'end')
                shell.bind('<Return>',lambda _event:run())
                ttk.Button(controls,text='Run manual command · requires approval',command=run).pack(anchor='e')
        console=CodingConsole(window,**self.callbacks)
        for key in self.order:console.notify(self.rows[key])
        self.windows.append((window,console))
