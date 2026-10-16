"""Readback of the actual existing authored Vite build through its owned preview."""
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import build_opener,ProxyHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis.development_tools import DevelopmentTools

def main():
    base=Path(__file__).resolve().parents[2];root=base/'artifacts/projects/development-dashboard'
    expected=(root/'dist/index.html').read_bytes();tools=DevelopmentTools(base)
    try:
        url=tools.start_preview(root,'vite',lambda:False)
        with build_opener(ProxyHandler({})).open(url,timeout=3) as r:
            assert r.status==200;observed=r.read()
        assert observed==expected and b'/assets/' in observed
        process=tools.preview['process'];tools.stop_preview();assert process.poll() is not None
        result={'case':'JRV-22-001','PASS':True,'same_built_html_served':True,
            'html_sha256':hashlib.sha256(observed).hexdigest(),'owned_preview_stopped':True,
            'scope':'Actual authored installed Vite build→Vite preview→HTTP readback; separate minimal static fixture has DOM/axe/scenario assertions. No autonomous model or production acceptance.'}
        (base/'artifacts/jarvis-audit/modules/22-web-development/built-preview-proof.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result))
    finally:tools.close()

if __name__=='__main__':main()
