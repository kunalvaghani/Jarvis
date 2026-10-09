"""Owned accessible native window for real control activation tests."""
from pathlib import Path
import sys
import win32api
import win32con
import win32gui
import pythoncom
pythoncom.CoInitialize()

name,output=sys.argv[1:]
def handle(hwnd,message,wparam,lparam):
    if message==win32con.WM_COMMAND and (wparam&0xffff)==101:
        Path(output).write_text('activated',encoding='utf-8')
        return 0
    if message==win32con.WM_DESTROY:
        win32gui.PostQuitMessage(0)
        return 0
    return win32gui.DefWindowProc(hwnd,message,wparam,lparam)
wc=win32gui.WNDCLASS();wc.hInstance=win32api.GetModuleHandle(None);wc.lpszClassName=name;wc.lpfnWndProc=handle
win32gui.RegisterClass(wc)
hwnd=win32gui.CreateWindow(name,name,win32con.WS_OVERLAPPEDWINDOW|win32con.WS_VISIBLE,100,100,400,220,0,0,wc.hInstance,None)
win32gui.CreateWindow('BUTTON','Verify fixture',win32con.WS_CHILD|win32con.WS_VISIBLE|win32con.WS_TABSTOP,30,30,180,40,hwnd,101,wc.hInstance,None)
try:win32gui.SetForegroundWindow(hwnd)
except win32gui.error:pass  # Let the user focus the owned window; never force it.
Path(output+'.ready').write_text('ready',encoding='utf-8')
win32gui.PumpMessages()
