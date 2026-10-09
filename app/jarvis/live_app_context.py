"""Volatile window identity and observed UIA controls; never executable targets."""
import os
import threading
import time


def window_info(handle):
    import win32api
    import win32gui
    import win32process
    if not handle or not win32gui.IsWindow(handle):
        return None
    try:
        pid=win32process.GetWindowThreadProcessId(handle)[1]
        title=win32gui.GetWindowText(handle)[:200]
        window_class=win32gui.GetClassName(handle)
    except Exception:
        return None  # It may disappear between the initial check and metadata.
    if pid==os.getpid():
        return None
    started=None
    executable=''
    try:
        process=win32api.OpenProcess(0x0410,False,pid)
        try:
            executable=win32process.GetModuleFileNameEx(process,0)
            started=str(win32process.GetProcessTimes(process)['CreationTime'])
        finally:
            process.Close()
    except Exception:
        pass
    return {'handle':int(handle),'pid':pid,'process_started':started,'executable':executable,
            'title':title,
            'window_class':window_class,
            'visible':bool(win32gui.IsWindowVisible(handle))}


def foreground_window():
    import win32gui
    return win32gui.GetForegroundWindow()


class LiveAppContext:
    def __init__(self,probe=window_info,clock=time.monotonic,foreground=foreground_window):
        self.probe,self.clock=probe,clock
        self.foreground=foreground
        self.lock=threading.RLock()
        self.windows={}
        self.current=None

    @staticmethod
    def identity(row):
        return (row['handle'],row['pid'],row.get('process_started'),row.get('window_class'))

    def observe_window(self,handle):
        with self.lock:
            info=self.probe(handle)
            if not info or not info.get('title') or info.get('window_class') in {'Progman','WorkerW','Shell_TrayWnd'}:
                return
            previous=self.windows.get(handle)
            unchanged=bool(previous and self.identity(previous)==self.identity(info) and previous['title']==info['title'])
            self.windows[handle]={**info,'status':'open',
                'controls':previous.get('controls',[]) if unchanged else [],
                'observed_at':previous.get('observed_at') if unchanged else None}
            self.current=handle
            while len(self.windows)>8:
                self.windows.pop(next(iter(self.windows)))

    def record_controls(self,handle,snapshot):
        with self.lock:
            self.observe_window(handle)
            row=self.windows.get(handle)
            if not row or snapshot.get('title')!=row['title']:
                return
            # Do not retain field values, coordinates or executable runtime IDs.
            row['controls']=[{key:control[key][:120] if isinstance(control[key],str) else control[key]
                for key in ('name','role','context','selected','toggle_state') if key in control}
                for control in snapshot.get('controls',[]) if not control.get('password')][:40]
            row['observed_at']=self.clock()

    def snapshot(self):
        with self.lock:
            self.observe_window(self.foreground())
            rows=[]
            for old in self.windows.values():
                fresh=self.probe(old['handle'])
                state='closed' if fresh is None else 'replaced' if self.identity(fresh)!=self.identity(old) else 'open'
                controls=old['controls'] if state=='open' and fresh['title']==old['title'] and fresh['visible'] else []
                rows.append({**old,**(fresh if state=='open' else {}),'status':state,'controls':controls,
                    'controls_age_seconds':round(self.clock()-old['observed_at'],2) if controls and old['observed_at'] is not None else None})
            return {'current':next((row for row in rows if row['handle']==self.current),None),
                'recent_windows':[{key:row[key] for key in ('handle','pid','title','status','visible')} for row in rows],
                'notice':'Window status is checked now. Controls are observed reference; re-enumerate and validate before any input. Closed or replaced windows are not action targets.'}

    def refresh(self,ui,cancelled=lambda:False):
        if cancelled():
            return self.snapshot()
        try:
            handle=ui._handle()
            self.observe_window(handle)
            snapshot=ui.runner({'operation':'list','handle':handle,'owner_pid':os.getpid()},cancelled)
            if not cancelled():
                self.record_controls(handle,snapshot)
        except (ValueError,RuntimeError,OSError):
            # A failed accessibility read cannot make old buttons current.
            with self.lock:
                if self.current in self.windows:
                    self.windows[self.current]['controls']=[]
                    self.windows[self.current]['observed_at']=None
        return self.snapshot()
