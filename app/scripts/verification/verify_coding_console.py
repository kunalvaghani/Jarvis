"""Exercise real Tk activity selection/expansion and capture only the owned window."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tkinter as tk

from jarvis.coding_console import CodingConsole

BASE=Path(__file__).resolve().parents[2]


def main():
    root=tk.Tk();root.title('Jarvis coding workspace · owned verification');root.geometry('1000x700+20+20')
    console=CodingConsole(root)
    result={'date':datetime.now(timezone.utc).isoformat(),'passed':False,'scope':'Actual Tk coding console using actual isolated-fixture activity; no microphone or other applications controlled.'}
    try:
        live=json.loads((BASE/'artifacts/reports/native-coding-live-check.json').read_text())
        worker=live['workload_receipt']['workers'][0]
        candidates=[]
        for path in (BASE/'.jarvis-runtime/native-code').glob('*/activity.jsonl'):
            rows=[json.loads(line) for line in path.read_text().splitlines()]
            if any(row.get('label')=='Created main.py' and row.get('state')=='completed' for row in rows):candidates.append((path.stat().st_mtime,path,rows))
        _,path,rows=max(candidates)
        for row in rows:console.notify(row)
        root.update()
        edited=next(row for row in rows if row.get('file')=='main.py' and row.get('state')=='completed')
        console.tree.selection_set(edited['id']);console.tree.event_generate('<<TreeviewSelect>>');root.update()
        text=console.detail.get('1.0','end')
        assert 'main.py' in text and '+' in text and 'def add' in text,text
        console.open();root.update();assert len(console.windows)==1
        mirror=console.windows[0][1];assert mirror.rows==console.rows
        for window,_ in console.windows:window.withdraw()
        root.after(600,root.quit);root.mainloop()
        # PrintWindow captures our owned HWND, never the desktop. This is
        # an actual widget capture, not a fabricated sample or upstream image.
        import ctypes
        from ctypes import wintypes
        import win32gui,win32ui
        from PIL import Image
        hwnd=win32gui.GetParent(root.winfo_id());dc=win32gui.GetWindowDC(hwnd);src=win32ui.CreateDCFromHandle(dc)
        dest=src.CreateCompatibleDC();bitmap=win32ui.CreateBitmap();left,top,right,bottom=win32gui.GetWindowRect(hwnd)
        width,height=right-left,bottom-top;bitmap.CreateCompatibleBitmap(src,width,height);dest.SelectObject(bitmap)
        user=ctypes.WinDLL('user32');user.PrintWindow.argtypes=[wintypes.HWND,wintypes.HDC,wintypes.UINT];user.PrintWindow.restype=wintypes.BOOL
        try:
            assert user.PrintWindow(hwnd,dest.GetSafeHdc(),2),'Owned window capture failed'
            image=Image.frombuffer('RGB',(width,height),bitmap.GetBitmapBits(True),'raw','BGRX',0,1)
            assert len(image.getcolors(width*height) or [])>20,'Capture is empty'
            white=sum(count for count,color in image.getcolors(width*height) if all(value>245 for value in color))
            assert white<width*height*.2,'The native controls were not rendered in the capture'
            target=BASE/'artifacts/media/native-coding-console.png';image.save(target)
        finally:
            win32gui.DeleteObject(bitmap.GetHandle());dest.DeleteDC();src.DeleteDC();win32gui.ReleaseDC(hwnd,dc)
        result.update(passed=True,activity_rows=len(console.order),expanded_file='main.py',mirror_checked=True,image='artifacts/media/native-coding-console.png')
    except Exception as exc:result.update(error_type=type(exc).__name__,error=str(exc)[:2000])
    finally:root.destroy()
    (BASE/'artifacts/reports/native-coding-console-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2));return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
