"""Conservative task classification and admission; inference still uses gpu_scheduler."""
import ctypes
import os
import re
import time
from datetime import datetime, timedelta, timezone


class _SessionPrefix(ctypes.Structure):
    _fields_ = [('session_id',ctypes.c_uint32),('state',ctypes.c_int32),('flags',ctypes.c_int32)]


class _SessionDataPrefix(ctypes.Union):
    # The SDK union contains LARGE_INTEGER fields and has native 8-byte alignment.
    # Only its common prefix is read; user/domain names are never decoded.
    _fields_ = [('session',_SessionPrefix),('alignment',ctypes.c_uint64)]


class _SessionInfoPrefix(ctypes.Structure):
    _fields_ = [('level',ctypes.c_uint32),('data',_SessionDataPrefix)]


def session_unlocked():
    """WTS lock state, independent of a temporarily accessible input desktop."""
    if os.name != 'nt':return False
    buffer,size=ctypes.c_void_p(),ctypes.c_uint32()
    try:
        wts=ctypes.WinDLL('wtsapi32',use_last_error=True)
        query=wts.WTSQuerySessionInformationW
        query.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,
            ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(ctypes.c_uint32)]
        query.restype=ctypes.c_int
        free=wts.WTSFreeMemory;free.argtypes=[ctypes.c_void_p];free.restype=None
        try:
            # WTS_CURRENT_SERVER_HANDLE, WTS_CURRENT_SESSION, WTSSessionInfoEx.
            if not query(None,0xffffffff,25,ctypes.byref(buffer),ctypes.byref(size)) or not buffer.value:
                return False
            if size.value < ctypes.sizeof(_SessionInfoPrefix):return False
            info=ctypes.cast(buffer,ctypes.POINTER(_SessionInfoPrefix)).contents
            import sys
            version=sys.getwindowsversion()
            unlocked=0 if (version.major,version.minor)==(6,1) else 1
            return info.level==1 and info.data.session.state==0 and info.data.session.flags==unlocked
        finally:
            if buffer.value:free(buffer)
    except (OSError,AttributeError,ValueError):
        return False

READ_ONLY = {'jarvis_status', 'system_info', 'screen_info'}
CONTROL = {'queue_status', 'cancel_all', 'cancel_current', 'cancel_task', 'end_conversation',
           'stop_speaking', 'sleep', 'approval_answer', 'whatsapp_answer', 'island_choice', 'memory_choice'}


def queue_request(text):
    """Preserve scheduling syntax before ordinary command punctuation cleanup."""
    return bool(re.match(r'^(?:answer task \d+\s*:|link task\b|move task\b|add to workflow\b|(?:pause|resume|urgent|cancel pending) group\b|after that\b|after tasks? \d+\b|urgent\b|asap\b|make this urgent\b|add this to (?:the )?queue\b|queue this\b|queue these\b|in \d+ (?:seconds?|minutes?|hours?)\b|(?:do this|do|run this) after\b)', text.strip(), re.I)
                or re.search(r'\s+by \d{1,2}:\d{2}[.!]?$', text.strip(), re.I))


def classify(command, now=None):
    kind, text = command['kind'], command.get('value', '')
    explicit = bool(re.search(r'\b(?:urgent|asap|highest priority)\b', text, re.I))
    readonly = kind in READ_ONLY
    sensitive = kind in {'delete','delete_in_folder','run_command','whatsapp_send','whatsapp_reply','messenger_send','ability_approve','ability_enable','repo_forget','memory_forget'}
    spec = {'priority': 100 if explicit else 0, 'explicit_priority': explicit,
            'urgency': 10 if re.search(r'\b(?:soon|important)\b', text, re.I) else 0,
            'deadline': None, 'not_before': 0, 'dependencies': [],
            'lane': 'background' if kind == 'jarvis_status' else 'fast' if readonly else 'inference' if kind in {'task', 'code_task', 'ask'} else 'desktop',
            'locks': [] if readonly else ['legacy-actions', 'desktop', 'shared-planner'],
            'read_only': readonly, 'reversible': readonly, 'unattended': readonly,
            'approval': True if sensitive else False if readonly else 'execution-time tool policy', 'risk': 'sensitive' if sensitive else 'read-only' if readonly else 'tool-policy',
            'complexity': 'small' if readonly else 'unknown',
            'duration_seconds': 2 if readonly else 300, 'uncertainty': 'high',
            'resources': {'ram_mb': 32 if readonly else 512, 'gpu': not readonly,
                          'cpu': 1, 'network': not readonly, 'disk': 'unknown'},
            'tools': [kind], 'model': 'existing router' if not readonly else None,
            'splittable': False}
    return _project_step(spec) if kind == 'project_step' else _code_research(spec) if kind == 'code_research' else spec


def _project_step(spec):
    # Workspace creation writes only new or Jarvis-generated files; acceptance checks read.
    spec.update(lane='inference', locks=['legacy-actions', 'shared-planner'], reversible=True, unattended=True,
                approval=False, risk='new-files-only', complexity='small', duration_seconds=5,
                resources={'ram_mb': 64, 'gpu': False, 'cpu': 1, 'network': False, 'disk': 'small'}, model=None)
    return spec


def _code_research(spec):
    # Reads public sources into Jarvis's own cache; never touches project files or the desktop.
    spec.update(lane='research', locks=['code-research'], read_only=True, reversible=True, unattended=True, approval=False,
                risk='read-only', complexity='small', duration_seconds=60,
                resources={'ram_mb': 128, 'gpu': False, 'cpu': 1, 'network': True, 'disk': 'small'}, model=None)
    return spec


def score(row, now):
    spec = row['spec']
    age = max(0, now-row['created']) / 30  # Unbounded aging prevents permanent starvation.
    deadline = spec.get('deadline')
    slack = deadline-now-spec.get('duration_seconds', 300) if deadline else None
    deadline_score = 1000+min(1000, max(0, -slack)/60) if slack is not None and slack < 300 else 0
    return spec.get('priority', 0)*10 + spec.get('urgency', 0) + age + deadline_score + 10/(1+spec.get('duration_seconds', 300))


def modifiers(text, now=None):
    """Only explicit supported syntax is stripped. Ambiguous dates remain instructions."""
    now = time.time() if now is None else now
    spec = {}
    urgent = re.match(r'^(?:make this urgent[:,]?\s+|urgent[:,]?\s+|asap[:,]?\s+)', text, re.I)
    if urgent:
        spec.update(priority=100, explicit_priority=True)
        text = text[urgent.end():]
    text = re.sub(r'^(?:add this to (?:the )?queue|queue this)[:,]?\s+', '', text, flags=re.I)
    previous = re.match(r'^(?:do this|do|run this) after (?:the )?previous task[:,]?\s+', text, re.I)
    if previous:
        spec['after_previous'] = True
        text = text[previous.end():]
    scheduled = re.match(r'^in (\d{1,4}) (seconds?|minutes?|hours?)[:,]?\s+(.+)$', text, re.I | re.S)
    if scheduled:
        scale = 3600 if scheduled[2].lower().startswith('hour') else 60 if scheduled[2].lower().startswith('minute') else 1
        spec['not_before'], text = now+int(scheduled[1])*scale, scheduled[3]
    deadline = re.search(r'\s+by (\d{1,2}):(\d{2})[.!]?$', text, re.I)
    if deadline:
        hour, minute = int(deadline[1]), int(deadline[2])
        if hour > 23 or minute > 59:
            raise ValueError('Invalid deadline; use local 24-hour HH:MM')
        date = datetime.fromtimestamp(now, timezone.utc).astimezone().replace(hour=hour, minute=minute, second=0, microsecond=0)
        if date.timestamp() <= now:
            date += timedelta(days=1)
        spec['deadline'], text = date.timestamp(), text[:deadline.start()]
    return text.strip(), spec


def desktop_available():
    if not session_unlocked():
        return False
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.OpenInputDesktop.restype = ctypes.c_void_p
    handle = user.OpenInputDesktop(0, False, 0x0100)
    if not handle:
        return False
    user.CloseDesktop.argtypes = [ctypes.c_void_p]
    user.CloseDesktop(handle)
    return True


def resources():
    try:
        import psutil
        battery = psutil.sensors_battery()
        return {'ram_available_mb': psutil.virtual_memory().available/1048576,
                'cpu_percent': psutil.cpu_percent(),
                'battery_low': bool(battery and not battery.power_plugged and battery.percent < 20),
                'desktop': desktop_available()}
    except (ImportError, OSError):
        return {'ram_available_mb': 0, 'cpu_percent': 100, 'battery_low': True, 'desktop': False}
