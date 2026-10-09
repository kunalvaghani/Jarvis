"""Trusted notebook/Nmap entry point inside the reviewed utility container."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import xml.etree.ElementTree as ET


def main():
    # Kernel subprocess diagnostics must not corrupt the JSON response protocol.
    descriptor=os.open(os.devnull,os.O_WRONLY)
    os.dup2(descriptor,2);os.close(descriptor)
    request=json.loads(sys.stdin.buffer.read(1000000))
    if os.geteuid()==0:raise ValueError('Utility container must be non-root.')
    operation=request['operation']
    if operation=='notebook':
        import nbformat
        from nbclient import NotebookClient
        notebook=nbformat.read('/input.ipynb',as_version=4)
        if len(notebook.cells)>30:raise ValueError('Notebook exceeds 30 cells.')
        NotebookClient(notebook,timeout=10,kernel_name='python3',allow_errors=False,resources={'metadata':{'path':'/work'}}).execute()
        for cell in notebook.cells:
            cell.pop('attachments',None);cell['metadata']={}
            for output in cell.get('outputs',[]):
                if output.get('data') is not None:output['data']={'text/plain':output['data'].get('text/plain','[rich output excluded]')}
                output.pop('metadata',None)
        notebook['metadata']={}
        return {'notebook':json.dumps(notebook),'executed_cells':sum(c.cell_type=='code' for c in notebook.cells)}
    if operation=='nmap':
        import ipaddress
        target=request['target'];ports=request['ports']
        if not 1<=len(ports)<=16 or any(type(p) is not int or not 1<=p<=65535 for p in ports):raise ValueError('Use 1–16 numeric ports.')
        server=None
        if request.get('_fixture'):
            import http.server,threading
            server=http.server.HTTPServer(('127.0.0.1',0),http.server.BaseHTTPRequestHandler)
            threading.Thread(target=server.serve_forever,daemon=True).start();ports=[server.server_port];target='127.0.0.1'
        else:
            network=ipaddress.ip_network(target,strict=False)
            if not network.is_private or network.num_addresses>16:raise ValueError('Only an explicitly approved private range of at most 16 addresses is supported.')
            if str(network)=='127.0.0.1/32':target=socket.gethostbyname('host.docker.internal')
        try:
            process=subprocess.run(['nmap','-sT','-Pn','-n','--max-retries','0','--host-timeout','5s','-p',','.join(map(str,ports)),'-oX','-',target],capture_output=True,timeout=12,check=True)
            tree=ET.fromstring(process.stdout)
            return {'hosts':[{'address':h.find('address').get('addr'),'ports':[{'port':int(p.get('portid')),'state':p.find('state').get('state')} for p in h.findall('ports/port')]} for h in tree.findall('host')],'engine':'Nmap TCP connect; no scripts or privilege escalation'}
        finally:
            if server:server.shutdown();server.server_close()
    raise ValueError('Unknown isolated utility operation.')


if __name__=='__main__':
    try:result={'ok':True,'value':main()}
    except Exception as error:result={'ok':False,'error_type':type(error).__name__,'error':str(error)[:500]}
    print(json.dumps(result))
