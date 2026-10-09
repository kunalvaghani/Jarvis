"""Read only exposed Image bounds inside an unobscured native Spotify window."""
import base64
import io


def unobscured(gui, handle, rect):
    left,top,right,bottom = rect
    if gui.GetForegroundWindow()!=handle or not 8 <= right-left <= 192 or not 8 <= bottom-top <= 192:
        return False
    bounds = gui.GetWindowRect(handle)
    if not (bounds[0]<=left<right<=bounds[2] and bounds[1]<=top<bottom<=bounds[3]):
        return False
    return all(gui.GetAncestor(gui.WindowFromPoint(point),2)==handle for point in
               ((left+1,top+1),(right-2,top+1),(left+1,bottom-2),(right-2,bottom-2),((left+right)//2,(top+bottom)//2)))


def row_artwork(window, controls, handle):
    """Optional thumbnails are display evidence only, never action identity."""
    import win32gui
    from PIL import ImageGrab
    from .ui_controls import _category
    images = window.descendants(control_type='Image',cache_enable=True)[:120]
    result = {}
    for control in _category(controls,'track',window.window_text())[:12]:
        left,top,right,bottom = control['rect']
        for image in images:
            try:
                box = image.rectangle()
                rect = (box.left,box.top,box.right,box.bottom)
                if not image.is_visible() or not (left<=box.left<box.right<=right and top<=box.top<box.bottom<=bottom):
                    continue
                if not unobscured(win32gui,handle,rect):
                    continue
                capture = ImageGrab.grab(bbox=rect,all_screens=True)
                if not unobscured(win32gui,handle,rect):
                    continue
                capture.thumbnail((64,64))
                output = io.BytesIO()
                capture.convert('RGB').save(output,format='PNG')
                result[str(control['id'])] = base64.b64encode(output.getvalue()).decode('ascii')
                break
            except (OSError,RuntimeError,ValueError):
                continue
    return result
