"""Owned exact-port3000 collision assertion, preserving any pre-existing listener."""
import json
from pathlib import Path
import socket
import sys
import tempfile
from contextlib import nullcontext
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis.development_tools import DevelopmentTools

def main():
    base=Path(__file__).resolve().parents[2];listener=socket.socket();owned=False
    try:
        try:listener.bind(('127.0.0.1',3000));listener.listen();owned=True
        except OSError:
            # Only accept a real existing listener, rather than assuming every
            # bind failure means a busy port. Read-only connect does not send data.
            with socket.create_connection(('127.0.0.1',3000),timeout=1):pass
        # Retain owned fixture files for readback; Windows can briefly retain
        # file handles after the owned child exits. Never erase unknown state.
        with nullcontext(tempfile.mkdtemp(prefix='module22-port-',dir=base/'.jarvis-runtime/jarvis-audit')) as tmp:
            root=Path(tmp);(root/'dist').mkdir();(root/'dist/index.html').write_text('<h1>Owned</h1>')
            tools=DevelopmentTools(base)
            try:
                url=tools.start_preview(root,'expo',lambda:False)
                assert int(url.rsplit(':',1)[1])!=3000 and tools.healthy()
                child=tools.preview['process'];tools.stop_preview();assert child.poll() is not None
                if owned:assert listener.getsockname()[1]==3000
                else:
                    with socket.create_connection(('127.0.0.1',3000),timeout=1):pass
            finally:tools.close()
        result={'case':'JRV-22-003','PASS':True,'port3000_occupied_by_owned_fixture':owned,
          'owned_preview_stopped':True,'unrelated_processes_killed':0,'scope':'Actual loopback exact-port collision, no HTTP/account data sent to pre-existing listener.'}
        (base/'artifacts/jarvis-audit/modules/22-web-development/port3000-proof.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result))
    finally:listener.close()

if __name__=='__main__':main()
