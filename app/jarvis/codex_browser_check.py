"""Owned local browser interaction check, executed by the validation worker."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit, unquote

from .codex_validation import source_path
from .harness_process import OwnedJob, hidden_spawn


def run(specification):
    import requests
    from playwright.sync_api import sync_playwright, expect
    data=json.loads(Path(specification).read_text(encoding='utf-8'));root=Path(data['root']);check=data['check']
    component=check.get('component') if check['kind']=='browser_component' else None
    frontend_entry=check['entry'] if component else check['path']
    job=OwnedJob();process=None;http=None;thread=None;errors=[];api=[];blocked=[]
    try:
        server=check.get('server')
        if server:
            with socket.socket() as port_socket:port_socket.bind(('127.0.0.1',0));port=port_socket.getsockname()[1]
            entry=source_path(root,server['path'])
            program=sys.executable if server['kind']=='python' else __import__('shutil').which('node')
            if not program:raise ValueError('Missing backend runtime toolchain.')
            env=dict(os.environ);env.update(PORT=str(port),JARVIS_PORT=str(port),JARVIS_DATA_DIR=str(root/'validation-data'))
            (root/'validation-data').mkdir(exist_ok=True)
            with (root/'server-check.log').open('w',encoding='utf-8') as output:
                process=hidden_spawn(job,subprocess.Popen)([program,str(entry),'--port',str(port),'--data-dir',str(root/'validation-data')],cwd=root,env=env,
                    stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT)
            ready=False;deadline=time.monotonic()+15;last_readiness='GET / not attempted'
            with requests.Session() as client:
                client.trust_env=False
                while time.monotonic()<deadline:
                    if process.poll() is not None:raise ValueError('Backend exited before readiness: '+(root/'server-check.log').read_text(encoding='utf-8')[-3000:])
                    try:
                        response=client.get(f'http://127.0.0.1:{port}/',timeout=.5,allow_redirects=False)
                        last_readiness='GET / returned HTTP '+str(response.status_code)
                        if response.status_code==200:
                            import psutil
                            owned={process.pid,*[p.pid for p in psutil.Process(process.pid).children(recursive=True)]}
                            owners={c.pid for c in psutil.net_connections(kind='tcp') if c.laddr and c.laddr.port==port and c.status=='LISTEN'}
                            if not owners or not owners<=owned:raise ValueError('Readiness port is not owned by the generated backend; no shared server reused.')
                            # A serial HTTP/1.1 server can hold this keep-alive
                            # socket and starve a browser's second connection.
                            # Probe only a read, retaining the first session.
                            with requests.Session() as independent:
                                independent.trust_env=False
                                try:
                                    peer=independent.get(f'http://127.0.0.1:{port}/',timeout=5,allow_redirects=False)
                                except requests.RequestException as error:
                                    raise ValueError('Backend cannot answer an independent GET / while its first connection remains open. '
                                        'Check HTTP/1.1 keep-alive with a single-threaded server; support concurrent connections or close responses. '
                                        'This is a backend connection-handling failure, not an instruction to increase browser timeouts. '
                                        +type(error).__name__) from error
                                if peer.status_code!=200:
                                    raise ValueError('Independent frontend read returned HTTP '+str(peer.status_code))
                            ready=True;break
                    except requests.RequestException as error:last_readiness='GET / failed: '+str(error)[:350]
                    time.sleep(.1)
            if not ready:raise ValueError('Backend '+server['path']+' did not serve its real frontend within 15 seconds. '
                +last_readiness+'; backend log: '+(root/'server-check.log').read_text(encoding='utf-8')[-2500:])
        else:
            class Quiet(SimpleHTTPRequestHandler):
                def log_message(self,*args):pass
            http=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(root)))
            port=http.server_port;thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='chrome',headless=True)
            try:
                page=browser.new_page(viewport={'width':390,'height':844})
                page.set_default_timeout(7000)
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.on('console',lambda message:errors.append('Console: '+message.text)
                    if message.type=='error' and urlsplit(message.location.get('url','')).path!='/favicon.ico' else None)
                def response_seen(response):
                    if response.status>=400 and urlsplit(response.url).path!='/favicon.ico':errors.append(str(response.status)+' '+response.url)
                    if response.request.resource_type in {'fetch','xhr'} and response.ok:api.append(response.url)
                page.on('response',response_seen)
                def route_request(route):
                    address=urlsplit(route.request.url)
                    if address.hostname=='127.0.0.1' and address.port==port:
                        name=unquote(address.path).lstrip('/')
                        if component and name in check.get('suppress_resources',[]):
                            route.fulfill(status=200,content_type='text/css' if Path(name).suffix.lower()=='.css' else 'application/javascript',body='')
                        else:route.continue_()
                    else:blocked.append(route.request.url);route.abort()
                page.route('**/*',route_request)
                # Backend readiness already requires GET /. Exercise that real
                # homepage, not only /index.html: a malformed root response can
                # advertise 200 while returning an error page or wrong UI.
                entry_route = '/' if server else '/' + frontend_entry
                response=page.goto(f'http://127.0.0.1:{port}'+entry_route,wait_until='networkidle')
                if not response or response.status!=200:raise ValueError('Frontend entry did not return HTTP 200.')
                if not page.locator('body').inner_text().strip():raise ValueError('Frontend rendered an empty body.')
                if component:
                    missing=[s for s in check['required_selectors'] if page.locator(s).count()==0]
                    if missing:raise ValueError('Markup lacks shared DOM selectors: '+json.dumps(missing))
                    if component=='markup':
                        empty_articles=page.locator('article').evaluate_all('(elements)=>elements.filter(e=>!e.innerText.trim()&&!e.querySelector("img[src],video[src],audio[src],svg")).length')
                        if empty_articles:raise ValueError('Empty semantic article/feature cards are unfinished content. Add meaningful visible card headings/descriptions or real media; aria-label alone does not fill a visible card.')
                        crossing=page.evaluate('''()=>document.querySelector('style,script:not([src])')!==null||[...document.querySelectorAll('*')].some(e=>[...e.attributes].some(a=>a.name==='style'||a.name.startsWith('on')))''')
                        if crossing:raise ValueError('Separate component ownership requires CSS/JS in external assigned files, without inline styles/scripts/event handlers.')
                        links=page.evaluate('''()=>[...document.querySelectorAll('script[src],link[rel="stylesheet"]')].map(e=>decodeURIComponent(new URL(e.src||e.href).pathname).slice(1))''')
                        missing=[name for name in check.get('suppress_resources',[]) if name not in links]
                        if missing:raise ValueError('Markup omits declared script/style links: '+json.dumps(missing))
                    if component=='logic':
                        scripts=page.evaluate('''()=>[...document.scripts].map(e=>e.src?decodeURIComponent(new URL(e.src).pathname).slice(1):'')''')
                        if check['path'] not in scripts:raise ValueError('Markup does not load the assigned JavaScript source.')
                    if component=='styles':
                        matched=page.evaluate('''(path)=>{let n=0;function inspect(rules){for(const r of rules){if(r.selectorText){try{if(document.querySelector(r.selectorText))n++}catch{}}else if(r.cssRules)inspect(r.cssRules)}}for(const s of document.styleSheets)if(s.href&&decodeURIComponent(new URL(s.href).pathname).slice(1)===path)inspect(s.cssRules);return n}''',check['path'])
                        if not matched:raise ValueError('Stylesheet has no actual CSS rules matching the real markup.')
                try:
                    for step in check['steps']:
                        action=step['action']
                        if action=='reload':page.reload(wait_until='networkidle');continue
                        target=page.locator(step['selector'])
                        if action=='click':target.click()
                        elif action=='fill':target.fill(step['value'])
                        elif action=='text':
                            expect(target).to_be_visible()
                            if target.evaluate('(element)=>["INPUT","TEXTAREA"].includes(element.tagName)'):
                                raise ValueError('Text assertion requires visible textContent, but '+step['selector']+
                                    ' is an input/textarea. Its value is not textContent. Repair the markup with a text-bearing element and have JavaScript update textContent. Preserve the registered check; this is not a loading/timing failure.')
                            expect(target).to_have_text(step['value'])
                        elif action=='value':
                            expect(target).to_be_visible();expect(target).to_have_value(step['value'])
                except Exception as error:
                    raise ValueError('Browser step failed: '+json.dumps(step)+'; '+str(error)[-2500:]
                        +'; observed runtime/HTTP errors: '+json.dumps(errors)[:2500]) from error
                if errors:raise ValueError('Browser/runtime errors: '+json.dumps(errors)[:3000])
                if blocked:raise ValueError('Required external requests blocked during local verification: '+json.dumps(blocked)[:1500])
                if not page.evaluate('document.documentElement.scrollWidth<=innerWidth+2'):raise ValueError('UI overflows the 390px viewport.')
                animation_results=[]
                for selector in check.get('animation_selectors',[]):
                    target=page.locator(selector).first
                    expect(target).to_be_visible()
                    before=target.evaluate('(el)=>el.getAnimations().map(a=>({time:a.currentTime,state:a.playState}))')
                    sample='(el)=>{const s=getComputedStyle(el);return JSON.stringify([s.transform,s.opacity,s.filter,s.color,s.backgroundColor,s.backgroundPosition,s.boxShadow,s.left,s.top,s.width,s.height,s.borderRadius])}'
                    style_before=target.evaluate(sample)
                    page.wait_for_timeout(250)
                    after=target.evaluate('(el)=>el.getAnimations().map(a=>({time:a.currentTime,state:a.playState}))')
                    if not any(a['state']=='running' and isinstance(a['time'],(int,float)) and i<len(before)
                               and isinstance(before[i]['time'],(int,float)) and a['time']>before[i]['time']
                               for i,a in enumerate(after)):
                        raise ValueError('No advancing rendered animation on '+selector)
                    if target.evaluate(sample)==style_before:
                        raise ValueError('Animation timeline advances without an observed visual style change on '+selector)
                    animation_results.append(selector)
                if server and not api:raise ValueError('No successful real frontend-to-backend fetch/XHR was observed; a static UI is insufficient.')
                page.screenshot(path=str(root/'browser-check.png'),full_page=True)
                page.set_viewport_size({'width':1280,'height':900});page.wait_for_timeout(150)
                if not page.evaluate('document.documentElement.scrollWidth<=innerWidth+2'):raise ValueError('UI overflows the 1280px viewport.')
                if errors:raise ValueError('Desktop resize runtime errors: '+json.dumps(errors)[:3000])
                page.screenshot(path=str(root/'browser-check-desktop.png'),full_page=True)
                for width in (320,768,1920):
                    page.set_viewport_size({'width':width,'height':900});page.wait_for_timeout(150)
                    if not page.evaluate('document.documentElement.scrollWidth<=innerWidth+2'):
                        raise ValueError('UI overflows the '+str(width)+'px viewport.')
                if errors:raise ValueError('Responsive resize runtime errors: '+json.dumps(errors)[:3000])
                print(json.dumps({'browser_passed':True,'entry_route':entry_route,'component':component,'steps':len(check['steps']),'runtime_errors':errors,'backend_requests':len(api),'mobile_width':390,'desktop_width':1280,'tested_widths':[320,390,768,1280,1920],'advancing_animations':animation_results}),flush=True)
            finally:browser.close()
    finally:
        job.close()
        if process and process.poll() is None:process.terminate();process.wait(timeout=10)
        if http:http.shutdown();http.server_close();thread.join(timeout=3)


if __name__=='__main__':run(sys.argv[1])
