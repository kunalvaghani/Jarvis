"""Capture ONLY an owned native QueueView with synthetic persisted state.

No screen capture, microphone, external tools, models or user task database access.
"""
import argparse
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import tkinter as tk
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis.commands import Command
from jarvis.task_ingress import TaskIngress
from jarvis.island_queue import QueueView


def capture(hwnd, path):
    user,gdi=ctypes.windll.user32,ctypes.windll.gdi32
    user.GetDC.restype=ctypes.c_void_p
    gdi.CreateCompatibleDC.argtypes=[ctypes.c_void_p];gdi.CreateCompatibleDC.restype=ctypes.c_void_p
    gdi.CreateDIBSection.restype=ctypes.c_void_p
    gdi.CreateDIBSection.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint,ctypes.POINTER(ctypes.c_void_p),ctypes.c_void_p,ctypes.c_uint]
    gdi.SelectObject.argtypes=[ctypes.c_void_p,ctypes.c_void_p];gdi.SelectObject.restype=ctypes.c_void_p
    user.PrintWindow.argtypes=[wintypes.HWND,ctypes.c_void_p,ctypes.c_uint]
    rect=wintypes.RECT();user.GetClientRect(hwnd,ctypes.byref(rect));w,h=rect.right,rect.bottom
    class Header(ctypes.Structure):
        _fields_=[('size',ctypes.c_uint),('width',ctypes.c_long),('height',ctypes.c_long),('planes',ctypes.c_ushort),
                  ('bits',ctypes.c_ushort),('compression',ctypes.c_uint),('image_size',ctypes.c_uint),('x',ctypes.c_long),
                  ('y',ctypes.c_long),('used',ctypes.c_uint),('important',ctypes.c_uint)]
    header=Header(40,w,-h,1,32,0,w*h*4,0,0,0,0)
    dc=user.GetDC(hwnd);memory=gdi.CreateCompatibleDC(dc);pixels=ctypes.c_void_p()
    bitmap=gdi.CreateDIBSection(dc,ctypes.byref(header),0,ctypes.byref(pixels),None,0)
    previous=gdi.SelectObject(memory,bitmap)
    try:
        if not user.PrintWindow(hwnd,memory,3):raise RuntimeError('Owned window rendering failed')
        rendered=Image.frombytes('RGB',(w,h),ctypes.string_at(pixels,w*h*4),'raw','BGRX')
        if len(rendered.getcolors(w*h) or []) < 3:raise RuntimeError('Owned preview is blank')
        rendered.save(path)
    finally:
        gdi.SelectObject(memory,previous)
        gdi.DeleteObject.argtypes=[ctypes.c_void_p];gdi.DeleteObject(bitmap)
        gdi.DeleteDC.argtypes=[ctypes.c_void_p];gdi.DeleteDC(memory)
        user.ReleaseDC.argtypes=[wintypes.HWND,ctypes.c_void_p];user.ReleaseDC(hwnd,dc)


def main(path):
    with tempfile.TemporaryDirectory(prefix='jarvis-queue-render-') as directory:
        base=Path(directory)
        actions=SimpleNamespace(base=base,generation=0,closed=threading.Event(),queue_lock=threading.Lock(),pending_tasks=[],report=lambda *_:None)
        ingress=TaskIngress(actions,base/'queue.sqlite3');actions.ingress=ingress
        ingress.scheduler.observe=lambda:{'ram_available_mb':16384,'cpu_percent':12,'battery_low':False,'desktop':True}
        root=tk.Tk();root.title('Jarvis Queue — synthetic fixture preview');root.geometry('1150x780+20+20')
        try:
            app=SimpleNamespace(actions=actions,report=actions.report)
            view=QueueView(root,app)
            rows=[]
            for i in range(10):
                token=threading.Event()
                rows.append(ingress.scheduler.put_nowait((0,Command('create',f'fixture-{i+1}.txt'),token)))
            for i in range(3):
                ingress.scheduler.get();ingress.scheduler.outcome('COMPLETED' if i<2 else 'FAILED','Synthetic receipt; no tool executed',{'fixture':True});ingress.scheduler.task_done()
            ingress.scheduler.control('pause',rows[3])
            ingress.store.transition(rows[4],'WAITING_APPROVAL','Synthetic approval gate; no request sent')
            ingress.scheduler.control('urgent',rows[5]);ingress.scheduler.get()
            ingress.store.setting('overnight',True)
            ingress.decisions.create(None,'Overnight scheduling preference',['Balanced priorities','Prefer coding'],confidence=.95,reversible=True,sensitive=False)
            view.tick();view.tree.selection_set(rows[5]);view.inspect()
            root.update_idletasks();root.update()
            user=ctypes.windll.user32
            hwnd=user.GetParent(root.winfo_id()) or root.winfo_id()
            path.parent.mkdir(parents=True,exist_ok=True)
            capture(hwnd,path)
            print('Owned native QueueView fixture captured: '+str(path))
        finally:
            root.destroy();ingress.close();ingress.store.db.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)
