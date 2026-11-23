"""Fixed shared-ngspice operation, imported ONLY by the existing Linux sandbox.

No dependencies beyond stdlib. C ABI follows Debian ngspice 44.2 sharedspice.h.
No supplied paths, model files, shell commands, background simulation or netlists.
"""
import ctypes as C
import hashlib
import math
import os
from pathlib import Path
import platform
import time
import faulthandler
import sys


def solve(supply_v: float, upper_ohm: float, lower_ohm: float):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64' or os.geteuid() == 0:
        raise RuntimeError('solver worker requires the reviewed Linux non-root sandbox')
    if not Path('/runner.py').is_file() or Path.cwd() != Path('/work'):
        raise RuntimeError('solver worker is not a host execution path')
    for v, lo, hi in ((supply_v, -100, 100), (upper_ohm, 1, 1e9), (lower_ohm, 1, 1e9)):
        if type(v) not in (int, float) or not math.isfinite(v) or not lo <= v <= hi:
            raise ValueError('finite SI scalar outside fixed-divider bounds')
    root = Path(__file__).resolve().parent
    # Native crashes must leave a stack, never an unexplained successful result.
    faulthandler.enable(file=sys.__stderr__)
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', HOME='/work', SPICE_SCRIPTS='/work')
    if any(Path(p).exists() for p in ('/work/spinit', '/work/.spiceinit', '/nonexistent/.spiceinit')):
        raise RuntimeError('initialization scripts are forbidden')
    # Fixed data-library paths, never resolved from an untrusted request.
    C.CDLL(str(root / 'libgomp1/usr/lib/x86_64-linux-gnu/libgomp.so.1.0.0'), mode=C.RTLD_GLOBAL)
    lib = C.CDLL(str(root / 'libngspice0/usr/lib/x86_64-linux-gnu/libngspice.so.0.0.12'))
    started = time.process_time()
    messages, exits = [], []
    text_cb = C.CFUNCTYPE(C.c_int, C.c_char_p, C.c_int, C.c_void_p)
    exit_cb = C.CFUNCTYPE(C.c_int, C.c_int, C.c_bool, C.c_bool, C.c_int, C.c_void_p)
    data_cb = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_int, C.c_int, C.c_void_p)
    init_cb = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_int, C.c_void_p)
    background_cb = C.CFUNCTYPE(C.c_int, C.c_bool, C.c_int, C.c_void_p)

    @text_cb
    def output(text, ident, user):
        if len(messages) < 64:
            messages.append((text or b'')[:500].decode('ascii', errors='replace'))
        return 0

    @text_cb
    def status(text, ident, user):
        return 0

    @exit_cb
    def exiting(code, immediate, requested, ident, user):
        exits.append(code)
        return 0

    @data_cb
    def data(values, count, ident, user):
        return 0

    @init_cb
    def initialized(values, ident, user):
        return 0

    @background_cb
    def background(running, ident, user):
        return 0

    # 44.2's pre-init no-spinit API calls cp_vset before callbacks exist and
    # segfaulted in this build. Instead use the empty private scratch directory
    # for scripts/HOME; no user init file is mounted into the container.
    lib.ngSpice_Init.argtypes = [text_cb, text_cb, exit_cb, data_cb, init_cb, background_cb, C.c_void_p]
    lib.ngSpice_Init.restype = C.c_int
    if lib.ngSpice_Init(output, status, exiting, data, initialized, background, None) != 0:
        raise RuntimeError('ngspice initialization failed')
    lib.ngSpice_Command.argtypes = [C.c_char_p]
    lib.ngSpice_Command.restype = C.c_int
    if lib.ngSpice_Command(b'version -f') != 0:
        raise RuntimeError('ngspice version check failed')
    if not any('ngspice-44.2' in m for m in messages):
        raise RuntimeError('ngspice version differs from reviewed pin')
    text = ('Jarvis ideal DC divider\n'
            f'V1 vin 0 DC {supply_v:.17g}\nR1 vin vout {upper_ohm:.17g}\n'
            f'R2 vout 0 {lower_ohm:.17g}\n.op\n.end\n')
    lines = [line.encode('ascii') for line in text.splitlines()]
    circuit = (C.c_char_p * (len(lines)+1))(*lines, None)
    lib.ngSpice_Circ.argtypes = [C.POINTER(C.c_char_p)]
    lib.ngSpice_Circ.restype = C.c_int
    if lib.ngSpice_Circ(circuit) != 0 or lib.ngSpice_Command(b'op') != 0 or exits:
        raise RuntimeError('ngspice did not complete the fixed DC operating point')

    class Vector(C.Structure):
        _fields_ = [('name', C.c_char_p), ('type', C.c_int), ('flags', C.c_short),
                    ('real', C.POINTER(C.c_double)), ('complex', C.c_void_p), ('length', C.c_int)]

    lib.ngGet_Vec_Info.argtypes = [C.c_char_p]
    lib.ngGet_Vec_Info.restype = C.POINTER(Vector)

    def scalar(name):
        pointer = lib.ngGet_Vec_Info(name)
        if not pointer or pointer.contents.length != 1 or not pointer.contents.real:
            raise ValueError('solver omitted a required real DC scalar')
        value = float(pointer.contents.real[0])
        if not math.isfinite(value):
            raise ValueError('solver returned a nonfinite result')
        return value

    return {'vectors': {'input_v': scalar(b'vin'), 'output_v': scalar(b'vout'),
                        'supply_current_a': scalar(b'v1#branch')},
            'solver': 'ngspice-shared', 'solver_version': '44.2',
            'netlist_sha256': hashlib.sha256(text.encode('ascii')).hexdigest(),
            'cpu_s': time.process_time()-started}
