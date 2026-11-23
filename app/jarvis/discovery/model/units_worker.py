"""Owned, bounded JSON protocol, run by the dedicated Pint interpreter with -I."""
import json
import math
import sys
import time
import re

STARTED = time.process_time()


def deny_network_and_children(event, args):
    if event in ('socket.connect', 'socket.sendto', 'socket.bind', 'subprocess.Popen', 'os.system', 'os.startfile'):
        raise PermissionError('owned unit worker denies network and child execution')


sys.addaudithook(deny_network_and_children)


def main():
    import pint
    raw = sys.stdin.buffer.read(4097)
    if len(raw) > 4096:
        raise ValueError('unit request exceeds byte budget')
    request = json.loads(raw)
    if set(request) != {'value', 'unit', 'target'}:
        raise ValueError('unknown unit request fields')
    if type(request['value']) not in (float, int) or not math.isfinite(request['value']):
        raise ValueError('unit conversion requires a finite scalar')
    for field in ('unit', 'target'):
        if not isinstance(request[field], str) or not 1 <= len(request[field]) <= 80:
            raise ValueError('bounded unit name required')
        term = r'(?:[A-Za-z_][A-Za-z0-9_]*|1)(?:\s*(?:\*\*|\^)\s*[+-]?\d{1,2})?'
        if not re.fullmatch(term + r'(?:\s*[*/]\s*' + term + r')*', request[field].strip()):
            raise ValueError('unsupported unit expression')
    registry = pint.UnitRegistry()
    result = registry.Quantity(request['value'], request['unit']).to(request['target'])
    if not math.isfinite(float(result.magnitude)):
        raise ValueError('non-finite conversion result')
    print(json.dumps({'value': float(result.magnitude), 'unit': str(result.units), 'pint': pint.__version__,
                      'cpu_s': time.process_time() - STARTED}, allow_nan=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Do not reflect arbitrary input, local paths or environment details.
        print(json.dumps({'error': type(exc).__name__}))
        sys.exit(1)
