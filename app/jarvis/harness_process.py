"""Windows ownership fence: closing/killing the worker reaps only its children."""
import os
import subprocess


class OwnedJob:
    def __init__(self, *, memory_bytes=None, cpu_seconds=None):
        self.handle = None
        import math
        if memory_bytes is not None and (type(memory_bytes) is not int or not 16*2**20<=memory_bytes<=4*2**30):
            raise ValueError('Owned process memory limit must be 16 MiB through 4 GiB.')
        if cpu_seconds is not None and (type(cpu_seconds) not in (int,float) or not math.isfinite(cpu_seconds) or not 1<=cpu_seconds<=120):
            raise ValueError('Owned process CPU limit must be 1 through 120 seconds.')
        if os.name != 'nt':
            if memory_bytes is not None or cpu_seconds is not None:
                raise ValueError('Resource-limited owned jobs require a qualified platform implementation.')
            return
        import ctypes
        from ctypes import wintypes as w
        class Basic(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                ('flags', w.DWORD), ('min_working', ctypes.c_size_t), ('max_working', ctypes.c_size_t),
                ('active_limit', w.DWORD), ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]
        class Extended(ctypes.Structure):
            _fields_ = [('basic', Basic), ('io', IO), ('process_memory', ctypes.c_size_t),
                ('job_memory', ctypes.c_size_t), ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = w.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        self.kernel.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.c_void_p]
        self.kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        self.kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        self.kernel.OpenProcess.restype = w.HANDLE
        self.kernel.CloseHandle.argtypes = [w.HANDLE]
        self.handle = self.kernel.CreateJobObjectW(None, None)
        self._extended_type = Extended
        limits = Extended()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if memory_bytes is not None:
            limits.basic.flags |= 0x100  # JOB_OBJECT_LIMIT_PROCESS_MEMORY (committed memory)
            limits.process_memory = memory_bytes
        if cpu_seconds is not None:
            limits.basic.flags |= 0x2  # JOB_OBJECT_LIMIT_PROCESS_TIME, 100 ns units
            limits.basic.process_time = int(cpu_seconds * 10_000_000)
        if not self.handle or not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.close()
            raise OSError('Could not establish Harness process ownership.')

    def attach(self, process):
        if self.handle is None:
            return
        child = self.kernel.OpenProcess(0x0100 | 0x0001, False, process.pid)
        try:
            if not child or not self.kernel.AssignProcessToJobObject(self.handle, child):
                process.terminate()
                process.wait(timeout=5)
                raise OSError('Could not attach the owned Harness process.')
        finally:
            if child:
                self.kernel.CloseHandle(child)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None

    def usage(self):
        """Observed peak committed bytes, not an estimate or working-set RSS."""
        if not self.handle:return {'peak_process_committed_bytes':None}
        import ctypes
        values=self._extended_type()
        if not self.kernel.QueryInformationJobObject(self.handle,9,ctypes.byref(values),ctypes.sizeof(values),None):
            raise OSError('Could not read owned Job Object resource evidence.')
        return {'peak_process_committed_bytes':int(values.peak_process)}


def hidden_spawn(job, spawn):
    def launch(*args, **kwargs):
        kwargs['creationflags'] = kwargs.get('creationflags', 0) | getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        process = spawn(*args, **kwargs)
        job.attach(process)
        return process
    return launch
