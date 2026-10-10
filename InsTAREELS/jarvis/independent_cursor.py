"""Jarvis's visible pointer (the cyan J) and its clicks.

The cue shows where Jarvis acts. Clicks use Jarvis's own touch pointer
(jarvis_pointer.py): a real tap that never uses your mouse buttons and returns
your pointer to where it was. Accessibility actions remain the fallback.
"""
import math
import threading
import time
from uuid import uuid4


class CursorCue:
    """Nonactivating, click-through Win32 cue, owned by the calling worker.

    A separate thread enforces expiry even if an accessibility provider blocks.
    Closing the worker also disposes the OS window. Cleanup cannot retry input.
    """
    def __init__(self, rect, owner=0):
        if (not isinstance(rect, (list, tuple)) or len(rect) != 4
                or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v)>1_000_000 for v in rect)
                or not 0 < rect[2]-rect[0] <= 20000 or not 0 < rect[3]-rect[1] <= 20000):
            raise ValueError('The Jarvis cursor needs current finite target bounds.')
        self.x, self.y = round((rect[0]+rect[2])/2), round((rect[1]+rect[3])/2)
        self.owner = owner
        self.arrived, self.finished, self.stop = threading.Event(), threading.Event(), threading.Event()
        self.error = None
        self.handle = None
        self.thread = None

    def __enter__(self):
        self.thread = threading.Thread(target=self._run, name='Jarvis cursor cue', daemon=True)
        self.thread.start()
        if not self.arrived.wait(.8) or self.error or self.finished.is_set():
            self.close()
            raise ValueError('Jarvis cursor could not prepare; no control action issued.')
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self.stop.set()
        if self.thread:
            try: self.thread.join(.35)
            except RuntimeError: pass  # Cleanup cannot change a dispatched action into a retry.

    def _run(self):
        name = 'JarvisCursor-' + uuid4().hex
        instance = brush = None
        registered = False
        try:
            import win32api
            import win32con
            import win32gui
            instance = win32api.GetModuleHandle(None)
            brush = win32gui.CreateSolidBrush(0)
            def paint(hwnd, message, wparam, lparam):
                if message == win32con.WM_NCHITTEST:
                    return win32con.HTTRANSPARENT
                if message == win32con.WM_MOUSEACTIVATE:
                    return win32con.MA_NOACTIVATE
                if message == win32con.WM_PAINT:
                    dc, ps = win32gui.BeginPaint(hwnd)
                    pen = fill = None
                    try:
                        win32gui.FillRect(dc, win32gui.GetClientRect(hwnd), brush)
                        pen = win32gui.CreatePen(win32con.PS_SOLID, 2, win32api.RGB(230,255,255))
                        fill = win32gui.CreateSolidBrush(win32api.RGB(0,210,225))
                        old_pen, old_fill = win32gui.SelectObject(dc,pen), win32gui.SelectObject(dc,fill)
                        if self.stop.is_set(): win32gui.Ellipse(dc,3,3,21,21)
                        win32gui.Polygon(dc,[(12,12),(12,42),(20,34),(27,50),(34,47),(27,30),(39,30)])
                        win32gui.SelectObject(dc,old_fill)
                        win32gui.SelectObject(dc,old_pen)
                        win32gui.SetBkMode(dc,win32con.TRANSPARENT)
                        win32gui.SetTextColor(dc,win32api.RGB(0,230,240))
                        win32gui.DrawText(dc,'J',-1,(43,12,72,40),win32con.DT_LEFT)
                    except Exception as exc:
                        self.error = type(exc).__name__
                    finally:
                        if pen: win32gui.DeleteObject(pen)
                        if fill: win32gui.DeleteObject(fill)
                        win32gui.EndPaint(hwnd,ps)
                    return 0
                return win32gui.DefWindowProc(hwnd,message,wparam,lparam)

            wc = win32gui.WNDCLASS()
            wc.hInstance, wc.lpszClassName, wc.lpfnWndProc = instance, name, paint
            win32gui.RegisterClass(wc); registered = True
            flags = (win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT |
                     win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_NOACTIVATE)
            self.handle = win32gui.CreateWindowEx(flags,name,'Jarvis cursor',win32con.WS_POPUP,
                self.x-112,self.y-82,76,60,self.owner,0,instance,None)
            win32gui.SetLayeredWindowAttributes(self.handle,0,255,win32con.LWA_COLORKEY)
            started = time.monotonic()
            # Absolute expiry is independent of the action callback and close().
            while time.monotonic()-started < .95:
                elapsed = time.monotonic()-started
                progress = min(1,elapsed/.18)
                easing = 1-(1-progress)**3
                x,y = self.x-12-round(100*(1-easing)), self.y-12-round(70*(1-easing))
                win32gui.SetWindowPos(self.handle,win32con.HWND_TOPMOST,x,y,76,60,
                    win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW)
                win32gui.InvalidateRect(self.handle,None,True)
                win32gui.UpdateWindow(self.handle)
                win32gui.PumpWaitingMessages()
                if progress >= 1: self.arrived.set()
                if self.stop.is_set() and elapsed >= .30: break
                time.sleep(.01)
        except Exception as exc:
            self.error = type(exc).__name__
            self.arrived.set()
        finally:
            try:
                if self.handle and win32gui.IsWindow(self.handle): win32gui.DestroyWindow(self.handle)
                if registered: win32gui.UnregisterClass(name,instance)
                if brush: win32gui.DeleteObject(brush)
            except Exception as exc:
                self.error = self.error or type(exc).__name__
            finally:
                self.handle = None
                self.finished.set()


def at_point(x,y,hwnd):
    """Resolve a fresh accessible action at a grounded point; never synthesize mouse input."""
    from pywinauto import Desktop
    from .execution_adapters import selection, Unsupported
    import win32gui
    import win32process
    pid = win32process.GetWindowThreadProcessId(hwnd)[1]
    element = Desktop(backend='uia').from_point(x,y)
    candidate = None
    for _ in range(4):
        if not element: break
        info = element.element_info
        top=element.top_level_parent()
        if not top.handle or win32gui.GetAncestor(top.handle,2)!=hwnd: break
        rect = element.rectangle()
        if not (rect.left<=x<rect.right and rect.top<=y<rect.bottom): break
        if info.control_type=='Edit' and not getattr(info,'is_password',False):
            from .execution_adapters import Prepared
            action=Prepared(info.element.SetFocus)
            candidate=(element,action,list(info.runtime_id),[rect.left,rect.top,rect.right,rect.bottom],info.control_type,info.name)
            break
        if info.control_type in {'Button','Hyperlink','MenuItem','SplitButton','CheckBox','RadioButton','TabItem','ListItem','TreeItem','ComboBox'}:
            try:
                action = selection(element,{'role':info.control_type},'click')
            except Unsupported:
                pass
            else:
                candidate = (element,action,list(info.runtime_id),[rect.left,rect.top,rect.right,rect.bottom],info.control_type,info.name)
                break
        element = element.parent()
    if candidate is None:
        return physical_point(x, y, hwnd, pid)
    element,action,identity,bounds,role,name = candidate
    def guard():
        rect = element.rectangle()
        hit = win32gui.WindowFromPoint((x,y))
        if (not win32gui.IsWindow(hwnd) or win32gui.GetForegroundWindow()!=hwnd
                or win32process.GetWindowThreadProcessId(hwnd)[1]!=pid
                or win32gui.GetAncestor(hit,2)!=hwnd
                or list(element.element_info.runtime_id)!=identity
                or element.element_info.control_type!=role or element.element_info.name!=name
                or getattr(element.element_info,'is_password',False)
                or [rect.left,rect.top,rect.right,rect.bottom]!=bounds
                or not element.is_visible() or not element.is_enabled()):
            raise ValueError('The accessible target changed; no control action issued.')
    guard()
    return action,bounds,guard


def physical_point(x, y, hwnd, pid):
    """A grounded point with no accessible control: a real tap with Jarvis's own pointer."""
    from .jarvis_pointer import enabled, tap
    from .execution_adapters import Prepared
    import win32gui
    import win32process
    if not enabled():
        raise ValueError('This target has no accessible control and physical clicks are turned off (cursor.physical_clicks).')
    def guard():
        hit = win32gui.WindowFromPoint((x, y))
        if (not win32gui.IsWindow(hwnd) or win32gui.GetForegroundWindow() != hwnd
                or win32process.GetWindowThreadProcessId(hwnd)[1] != pid or win32gui.GetAncestor(hit, 2) != hwnd):
            raise ValueError('The target window changed or is covered; no click was sent.')
    guard()
    return Prepared(lambda: tap(x, y)), [x - 12, y - 12, x + 12, y + 12], guard


def activate_point(x,y,hwnd):
    action,bounds,guard = at_point(x,y,hwnd)
    if action.no_op: return None
    with CursorCue(bounds,hwnd):
        guard()
        return action.call()
