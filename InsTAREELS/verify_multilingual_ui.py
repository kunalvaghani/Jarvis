"""Real Qwen generation + interactive browser acceptance in owned fixture folders.

Authored contracts/tests are independent of generated implementations. No user
project is run. Run --generate, then --test; failed tests feed exact source and
errors back to the normal coder with --repair ID.
"""
import argparse
from datetime import datetime, timezone
from functools import partial
import hashlib
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import json
import os
import re
from pathlib import Path
import subprocess
import threading
import time
from types import SimpleNamespace

from jarvis.brain import BrainClient
from jarvis.coder import Coder

BASE = Path(__file__).resolve().parent
ROOT = BASE / 'examples/multilingual'
RECORD = BASE / 'artifacts/multilingual-ui-check.json'
DEPS = BASE / 'artifacts/development-dashboard/node_modules'

# Compact but real requirements; levels are relative to this nine-project suite.
CASES = [
 ('game-1-orbit', 'game', 1, 'index.html', 'Orbit Catch',
  'Create a standalone single-file HTML CSS JavaScript game with animated UI titled Orbit Catch. '
  'A Start button id=start starts play; a moving orb BUTTON id=target inside an arena gives one point per click. '
  'Show Score: N in id=score initially 0. Pause id=pause freezes play/motion and shows Paused in id=status; clicking it resumes. '
  'Reset id=reset sets score to zero and ready state. Start must enable scoring. Keep orb inside arena; keyboard Space on orb also scores. '
  'Use attractive dark space UI, animated stars, responsive layout and reduced motion.'),
 ('game-2-pairs', 'game', 2, 'index.html', 'Prism Pairs',
  'Create a standalone single-file HTML CSS JavaScript animated memory game titled Prism Pairs. '
  'Six card buttons ids=card0,card1,card2,card3,card4,card5 have pairs A,A,B,B,C,C in that fixed order. '
  'Initially face down. Clicking two matching cards permanently reveals them and increments Pairs: N in id=pairs initially 0. '
  'Mismatch flips back after 700ms and temporarily blocks extra clicks. After three pairs show You won in id=status. '
  'Restart id=reset restores all cards and Pairs: 0. Include 3D flip transitions, animated background, visible instructions, keyboard buttons, responsive UI.'),
 ('game-3-breakout', 'game', 3, 'index.html', 'Neon Breakout',
  'Create a complete standalone single-file HTML CSS JavaScript animated canvas game titled Neon Breakout. '
  'Canvas id=arena, Start id=start, Pause id=pause toggles Paused/Playing in id=status, Reset id=reset. '
  'Paddle arrow-key and pointer controls; bouncing ball, brick collision and score, three lives, loss/win states, increasing levels, colored particle bursts. '
  'Score: N id=score starts zero. Starting begins visible time-based motion, pause freezes ball, resume continues; reset shows Ready and score zero. '
  'Use requestAnimationFrame with delta time, no duplicate loops. Responsive neon UI, keyboard instructions and reduced-motion background. Ball must visibly travel upward from center on Start.'),
 ('app-1-focus', 'app', 1, 'index.html', 'Focus Flow',
  'Create a standalone single-file HTML CSS JavaScript animated focus timer app titled Focus Flow. '
  'Number input id=duration in seconds default 5 min 1 max 3600. Start id=start starts countdown; id=time displays remaining seconds as an integer. '
  'Pause id=pause freezes countdown, toggles resume. Reset id=reset stops timer and restores input duration. id=status shows Ready, Running, Paused or Complete. '
  'Reject invalid duration visibly. Show animated radial progress, dark lavender dashboard, task note input and responsive accessible UI; avoid duplicate timers.'),
 ('app-2-expenses', 'app', 2, 'index.html', 'Pocket Ledger',
  'Create a standalone single-file HTML CSS JavaScript animated expense tracker titled Pocket Ledger. '
  'Inputs id=description and id=amount; Add expense id=add. Empty description or amount <=0 shows validation error, no row. '
  'Rows in id=entries include description, amount, Delete button. Total: formatted amount id=total initially 0.00. '
  'Use localStorage to persist rows and restore on reload. Search id=search filters descriptions, show No results for no match. '
  'Category select, colored spending chart, animated entry transitions and always animated decorative graph, keyboard form submission, responsive clean teal UI.'),
 ('app-3-board', 'app', 3, 'App.tsx', 'Studio Board',
  'Create a complete React TypeScript App.tsx exporting default App with all CSS in a style tag, titled Studio Board. '
  'Animated responsive kanban board with Todo, Doing, Done columns. Input id=taskTitle and Add task button id=add. '
  'New task is Todo; each card has Move to Doing and then Move to Done buttons, plus Delete. '
  'Search input id=search filters tasks, empty results visible. id=summary shows Done: N. Persist tasks in localStorage with error handling. '
  'Include priority selection, editable task dialog, keyboard-accessible controls, real drag/drop column moves, animated counters/background, reduced motion. Empty title error. '
  'Use only react imports and no external assets; dependencies already installed. Keep complete source below 10000 characters.'),
 ('website-1-folio', 'website', 1, 'index.html', 'Aster Studio',
  'Create a complete standalone single-file HTML CSS JavaScript animated portfolio website titled Aster Studio. '
  'Polished editorial hero, floating animated gradient artwork, projects, about and contact sections. Nav links scroll to real sections. '
  'Projects filter buttons All, Web, Design with data-filter attributes; three cards id=projects children with data-category web,web,design. '
  'Contact form id=contact: inputs id=name,id=email,id=message, Send message button id=send; validate required email. '
  'Valid submission displays Thanks in id=status locally without pretending an email was sent. Responsive mobile nav, keyboard navigation, reduced motion.'),
 ('website-2-market', 'website', 2, 'index.html', 'Forma Market',
  'Create a complete standalone single-file HTML CSS JavaScript animated shop website titled Forma Market. '
  'Six product cards with real category filtering and search id=search. First product named Luna Lamp costs 29. '
  'Its Add to cart button id=addFirst adds quantity; cart id=cart lists items, Cart: N id=count and Total: NN.NN id=total. '
  'Cart has Remove buttons, checkout id=checkout opens dialog with required name/email, Confirm order shows local Demo order confirmed without network or payments. '
  'Checkout inputs ids=orderName,orderEmail; Confirm order button id=orderConfirm, result id=orderStatus. '
  'Persist cart across reload. Responsive polished warm editorial product UI, animated art and entry transitions, keyboard dialog close and reduced motion. No external assets.'),
 ('website-3-booking', 'website', 3, 'App.tsx', 'Atlas Escapes',
  'Create complete React TypeScript App.tsx exporting default App with all CSS in a style tag, titled Atlas Escapes. '
  'Animated travel booking website with six destination cards, search id=search, category filters, sorting and favorites. '
  'Category select id=categoryFilter, sort select id=sort, Favorites only toggle id=favoritesFilter, first favorite toggle id=favoriteFirst. '
  'First card destination Kyoto, Book button id=bookFirst opens accessible dialog. Input id=traveler, email id=email, date id=date, guests id=guests min1 max8; Confirm booking id=confirm. '
  'Invalid fields show visible errors; valid form closes dialog and shows Booking confirmed in id=status with destination/traveler and price. '
  'Booking history persists localStorage and appears on reload; Cancel buttons work. No real booking/network. Responsive layered hero, animated artwork, transitions and reduced motion. '
  'Only react imports, no external assets; source below 11000 characters.'),
]


class Actions:
    def __init__(self):
        self.base = BASE
    def report(self, kind, message):
        if kind in {'brain', 'warning'}:
            print(json.dumps({'event': kind, 'message': str(message)[:170]}), flush=True)


def receipt():
    return json.loads(RECORD.read_text()) if RECORD.exists() else {'date': datetime.now(timezone.utc).isoformat(),
        'scope': 'Actual local Jarvis/Qwen generated source; authored nine-project browser contracts; no user project or remote service executed.', 'projects': {}}


def save(data):
    RECORD.parent.mkdir(exist_ok=True)
    RECORD.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def generate(only=None, repair=False, model=None, gpu=0, backend=None):
    options = json.loads((BASE / 'config.json').read_text())['brain']
    if model:
        options = {**options, 'coder': model, 'coding_num_gpu': gpu}
    if backend:
        options={**options,'coding_backend':backend}
    client = BrainClient(BASE, options)
    data = receipt()
    try:
        for ident, kind, level, target, title, goal in CASES:
            if only and ident != only: continue
            project = ROOT / ident
            project.mkdir(parents=True, exist_ok=True)
            old = data['projects'].get(ident, {})
            if not repair and old.get('generated') and (project / target).exists(): continue
            if repair:
                goal = 'Fix ' + target + ' using file tools now. Observed failure: ' + old.get('error', '')[:180] + '. Read current file, preserve working features and control IDs. Original requirements: ' + goal
            goal += ' Keep source below 9000 characters. Use clear JavaScript with one statement per line, distinct DOM-element and state-variable names, complete braces and no repeated CSS rules.'
            # Single-target authored manifest exercises normal streamed generation,
            # syntax correction and guarded file writes without a second planner.
            started = time.monotonic()
            calls = []
            request = client.request
            def traced(op, cancelled, **kw):
                result = request(op, cancelled, **kw)
                calls.append({'operation': op, 'model': result.get('model_used'),
                    'exact_current_sha256': hashlib.sha256(kw.get('current', '').encode()).hexdigest(),
                    'validation_error': kw.get('validation_error', '')})
                return result
            client.request = traced
            try:
                if backend in {'claude-code','codex'}:
                    result=Coder(Actions(),client).run(project,'Target file: '+target+'. '+goal,selected=True)
                else:
                    result = Coder(Actions(), client)._run(project, goal[:1200], selected=True,
                        plan_override={'directories': [], 'files': [{'path': target, 'reason': goal}]})
                row = {'kind': kind, 'level': level, 'title': title, 'target': target, 'goal': goal,
                    'generated': True, 'generation_seconds': round(time.monotonic()-started, 3), 'calls': calls,
                    'backend':backend or 'direct-qwen','model':options.get('codex_model','jarvis-codex-qwen3.5:9b') if backend=='codex' else options.get('claude_code_model','jarvis-claude-qwen3.5:9b') if backend else options['coder'],
                    'source_sha256': hashlib.sha256((project/target).read_bytes()).hexdigest(), 'result': result}
                if old: row['history'] = old.get('history', []) + [{k:v for k,v in old.items() if k!='history'}]
                data['projects'][ident] = row
            except Exception as exc:
                data['projects'][ident] = {**old, 'generated': False, 'error': str(exc), 'calls': calls}
            finally:
                client.request = request
            save(data)
            print(json.dumps({'project': ident, 'generated': data['projects'][ident]['generated'], 'seconds': round(time.monotonic()-started, 1)}), flush=True)
    finally:
        client.close()


def build_react(project):
    # Uses already installed, pinned local tooling, not model shell commands.
    entry = project / 'entry.tsx'
    entry.write_text('import React from "react"; import {createRoot} from "react-dom/client"; import App from "./App"; createRoot(document.getElementById("root")!).render(<App/>);\n')
    builder = BASE / '.jarvis-runtime/multilingual-build.mjs'
    aliases=[{'find':'react/jsx-runtime','replacement':str(DEPS/'react/jsx-runtime.js')},
        {'find':'react-dom/client','replacement':str(DEPS/'react-dom/client.js')},
        {'find':'react','replacement':str(DEPS/'react/index.js')}]
    builder.write_text('import {build} from '+json.dumps((DEPS/'vite/dist/node/index.js').as_uri())+'; import path from "node:path";\n'
        'await build({root:path.dirname(process.argv[2]),configFile:false,publicDir:false,define:{"process.env.NODE_ENV":"\\\"production\\\""},resolve:{alias:'+json.dumps(aliases)+'},'
        'build:{outDir:path.dirname(process.argv[3]),emptyOutDir:false,lib:{entry:process.argv[2],name:"JarvisExample",formats:["iife"],fileName:()=>"bundle.js"}}});\n')
    result = subprocess.run(['node', str(builder), str(entry), str(project/'bundle.js')], capture_output=True, text=True, timeout=45,
        env={**os.environ,'NO_COLOR':'1','FORCE_COLOR':'0'})
    if result.returncode:
        diagnostic=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',result.stderr)
        raise ValueError('React build failed: '+diagnostic[-2000:])
    # Full project-local TypeScript check against actual installed React types.
    config = {'compilerOptions': {'target': 'ES2022', 'lib': ['ES2022','DOM'], 'jsx': 'react-jsx',
        'module': 'ESNext', 'moduleResolution': 'bundler', 'strict': True, 'noEmit': True, 'skipLibCheck': True,
        'allowSyntheticDefaultImports': True,
        'paths': {'react': [str(DEPS/'@types/react')], 'react/*': [str(DEPS/'@types/react/*')], 'react-dom/*': [str(DEPS/'@types/react-dom/*')]}},
        'include': ['App.tsx','entry.tsx']}
    (project/'tsconfig.json').write_text(json.dumps(config))
    result = subprocess.run(['node',str(DEPS/'typescript/bin/tsc'),'-p',str(project/'tsconfig.json')], capture_output=True,text=True,timeout=45)
    if result.returncode: raise ValueError('TypeScript check failed: '+result.stdout[-2000:])
    (project/'index.html').write_text('<!doctype html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Jarvis React example</title></head><body><div id="root"></div><script src="bundle.js"></script></body></html>')


def interactions(page, ident):
    def click(selector): page.locator(selector).click()
    def fill(selector, value): page.locator(selector).fill(value)
    def contains(selector, value):
        from playwright.sync_api import expect
        expect(page.locator(selector)).to_contain_text(value)
    if ident == 'game-1-orbit':
        click('#start')
        assert page.locator('#target').evaluate('(e)=>e.tagName')=='BUTTON'
        for _ in range(2):
            page.locator('#target').focus(); page.keyboard.press('Space')
        contains('#score','2')
        click('#pause'); contains('#status','Paused')
        a=page.locator('#target').bounding_box();page.wait_for_timeout(250)
        assert a==page.locator('#target').bounding_box(),'Pause does not freeze target motion'
        page.locator('#target').focus();page.keyboard.press('Space');contains('#score','2')
        click('#pause');page.locator('#target').focus();page.keyboard.press('Space');contains('#score','3')
        assert page.locator('#target').evaluate('(e)=>{const t=e.getBoundingClientRect(),p=e.parentElement.getBoundingClientRect();return t.left>=p.left&&t.top>=p.top&&t.right<=p.right+1&&t.bottom<=p.bottom+1}'),'Orb travels outside its arena'
        click('#reset'); contains('#score','0')
    elif ident == 'game-2-pairs':
        for n in range(6):
            assert page.locator('#card'+str(n)).evaluate('(e)=>e.tagName')=='BUTTON','Cards need real keyboard-accessible buttons'
            click('#card'+str(n))
            if n%2:contains('#pairs',str((n+1)//2))
        contains('#pairs','3'); contains('#status','You won'); click('#reset'); contains('#pairs','0')
        click('#card0'); click('#card2'); page.wait_for_timeout(900); contains('#pairs','0')
    elif ident == 'game-3-breakout':
        click('#start'); contains('#status','Playing'); page.wait_for_timeout(500)
        a=page.locator('canvas').screenshot(); page.wait_for_timeout(450); b=page.locator('canvas').screenshot()
        assert a!=b, 'Canvas does not animate during play'
        page.keyboard.press('ArrowRight'); click('#pause'); contains('#status','Paused')
        a=page.locator('canvas').screenshot(); page.wait_for_timeout(350); assert a==page.locator('canvas').screenshot(), 'Pause does not freeze canvas'
        click('#pause'); contains('#status','Playing'); click('#reset'); contains('#score','0'); contains('#status','Ready')
    elif ident == 'app-1-focus':
        assert page.locator('#duration').input_value()=='5'
        fill('#duration','0');click('#start');contains('#status','Ready')
        assert page.locator('#error').is_visible(), 'Invalid duration lacks visible feedback'
        fill('#duration','3'); click('#start'); page.wait_for_timeout(1150); contains('#time','2')
        click('#pause'); contains('#status','Paused'); a=page.locator('#time').inner_text(); page.wait_for_timeout(1100); assert a==page.locator('#time').inner_text()
        click('#pause'); page.wait_for_timeout(2400); contains('#status','Complete'); click('#reset'); contains('#time','3')
        fill('#duration','6');click('#reset');contains('#time','6');contains('#status','Ready')
    elif ident == 'app-2-expenses':
        click('#add'); assert page.locator('#entries').inner_text().strip()==''
        assert 'valid' in page.locator('body').inner_text().lower() or 'required' in page.locator('body').inner_text().lower(), 'No visible validation error'
        fill('#description','Tea'); fill('#amount','12.50'); click('#add'); contains('#entries','Tea'); contains('#total','12.50')
        page.reload(); contains('#entries','Tea'); fill('#search','missing'); contains('body','No results'); fill('#search','')
        page.locator('#entries').get_by_role('button', name='Delete', exact=True).first.click(); contains('#total','0.00')
    elif ident == 'app-3-board':
        if not page.locator('#taskTitle').count() or not page.locator('#taskTitle').is_visible():
            click('#add'); fill('#taskTitle','Ship UI'); page.get_by_role('button',name='Save',exact=True).click()
        else:
            fill('#taskTitle','Ship UI'); click('#add')
        contains('body','Ship UI')
        page.get_by_role('button',name='Edit',exact=True).first.click()
        fill('#taskTitle','Ship polished UI')
        page.locator('select').last.select_option('high')
        page.get_by_role('button',name='Save',exact=True).click();contains('body','Ship polished UI')
        page.get_by_role('button',name='Move to Doing',exact=True).first.click()
        page.get_by_role('button',name='Move to Done',exact=True).first.click(); contains('#summary','1')
        page.reload(); contains('body','Ship polished UI'); fill('#search','missing'); contains('body','No results'); fill('#search','')
        card=page.locator('[draggable="true"]').filter(has_text='Ship polished UI').first
        assert card.count(),'Task cards do not support drag/drop'
        todo=page.get_by_role('heading',name=__import__('re').compile('^todo',__import__('re').I)).locator('..')
        card.drag_to(todo);contains('#summary','0')
        page.get_by_role('button',name='Delete',exact=True).first.click(); contains('#summary','0')
    elif ident == 'website-1-folio':
        for link in page.locator('nav a[href^="#"]').all():
            fragment=link.get_attribute('href')
            assert fragment and len(fragment)>1 and page.locator(fragment).count(), 'Navigation target missing'
            link.click();page.wait_for_timeout(500)
            assert page.evaluate('location.hash')==fragment,'Navigation does not reach its section'
        click('[data-filter="design"]'); assert page.locator('#projects [data-category="web"]:visible').count()==0,'Design filter still shows web projects'
        click('[data-filter="all"]'); assert page.locator('#projects [data-category]:visible').count()==3,'All filter must restore three projects'
        click('#send');assert 'Thanks' not in page.locator('#status').inner_text(), 'Empty form falsely confirms submission'
        fill('#name','Ada'); fill('#email','ada@example.test'); fill('#message','Hello'); click('#send'); contains('#status','Thanks')
    elif ident == 'website-2-market':
        assert page.locator('#productList article:visible').count()==6,'Shop must have six products'
        page.locator('#catContainer').get_by_role('button',name='lighting',exact=True).click()
        assert page.locator('#productList article:visible').count()==1,'Category filter did not restrict products'
        contains('#productList','Luna Lamp')
        page.locator('#catContainer').get_by_role('button',name='All',exact=True).click()
        fill('#search','missing');contains('#productList','No results')
        fill('#search','Luna');assert page.locator('#productList article:visible').count()==1
        fill('#search','')
        click('#addFirst'); contains('#count','1'); contains('#total','29.00'); page.reload(); contains('#cart','Luna Lamp')
        click('#addFirst'); contains('#count','2'); contains('#total','58.00')
        page.locator('#cart').get_by_role('button',name='Remove',exact=True).first.click(); contains('#count','0')
        click('#addFirst');click('#checkout')
        click('#orderConfirm');assert 'Demo order confirmed' not in page.locator('#orderStatus').inner_text(), 'Empty checkout accepted'
        assert page.locator('#orderError').is_visible() and page.locator('#orderError').inner_text(),'Missing checkout validation feedback'
        page.keyboard.press('Escape');assert not page.locator('#orderDialog').is_visible(),'Escape does not dismiss checkout'
        click('#checkout')
        fill('#orderName','Ada');fill('#orderEmail','ada@example.test');click('#orderConfirm');contains('#orderStatus','Demo order confirmed')
    elif ident == 'website-3-booking':
        click('#favoriteFirst');page.reload();click('#favoritesFilter')
        assert page.get_by_role('button',name=re.compile(r'^Book\b')).count()==1,'Favorites filter does not restrict destinations'
        click('#favoritesFilter')
        assert page.get_by_role('button',name=re.compile(r'^Book\b')).count()==6
        category=page.locator('#categoryFilter')
        options=category.locator('option').evaluate_all('(items)=>items.map(e=>e.value)')
        assert len(options)>1,'Category filter lacks choices'
        category.select_option(options[1]);assert page.get_by_role('button',name=re.compile(r'^Book\b')).count()<6
        category.select_option(options[0])
        sorting=page.locator('#sort');values=sorting.locator('option').evaluate_all('(items)=>items.map(e=>e.value)')
        assert len(values)>1,'Sorting lacks choices'
        def prices():
            return [int(re.search(r'\$([\d,]+)',text).group(1).replace(',','')) for text in page.get_by_text('Starting from $',exact=False).all_inner_texts()]
        sorting.select_option(label='Price: Low to High');assert prices()==sorted(prices()),'Price ascending sort is incorrect'
        sorting.select_option(label='Price: High to Low');assert prices()==sorted(prices(),reverse=True),'Price descending sort is incorrect'
        sorting.select_option(values[0])
        click('#bookFirst');page.keyboard.press('Escape');assert not page.get_by_role('dialog').count(),'Escape does not close booking'
        click('#bookFirst');page.get_by_role('dialog').get_by_role('button',name='Cancel',exact=True).click();assert not page.get_by_role('dialog').count(),'Cancel does not close booking'
        click('#bookFirst');click('#confirm')
        assert 'Booking confirmed' not in page.locator('#status').inner_text(),'Empty booking accepted'
        assert page.locator('input:invalid').count() or re.search(r'valid|required|enter',page.locator('body').inner_text(),re.I),'Invalid booking lacks visible feedback'
        fill('#traveler','Ada'); fill('#email','ada@example.test'); fill('#date','2027-01-10'); fill('#guests','9');click('#confirm')
        assert 'Booking confirmed' not in page.locator('#status').inner_text(),'Out-of-range guest count accepted'
        fill('#guests','2'); click('#confirm'); contains('#status','Booking confirmed')
        page.reload(); contains('body','Ada'); fill('#search','missing'); contains('body','No results'); fill('#search','')
        page.get_by_role('button',name='Cancel',exact=True).first.click(); assert 'Ada' not in page.locator('body').inner_text()


def test(only=None):
    from playwright.sync_api import sync_playwright
    data=receipt()
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self,*args): pass
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(ROOT)))
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,channel='chrome')
            try:
                for ident, kind, level, target, title, goal in CASES:
                    if only and ident!=only: continue
                    row=data['projects'].setdefault(ident,{})
                    if not row.get('generated'): continue
                    context=browser.new_context(viewport={'width':1280,'height':850})
                    from urllib.parse import urlparse
                    context.route('**/*',lambda route:route.continue_() if urlparse(route.request.url).hostname in {'127.0.0.1','localhost'} else route.abort())
                    page=context.new_page(); errors=[]; page.on('pageerror',lambda e:errors.append(e.stack or str(e)))
                    try:
                        if target.endswith('.tsx'): build_react(ROOT/ident)
                        url=f'http://127.0.0.1:{server.server_port}/{ident}/'
                        page.goto(url); page.get_by_role('heading',name=title,exact=True).wait_for(timeout=10000)
                        interactions(page,ident)
                        assert not errors, 'Browser runtime errors: '+str(errors)
                        page.reload(); page.wait_for_timeout(300)
                        page.evaluate("window.scrollTo({top:0,left:0,behavior:'instant'})")
                        page.wait_for_timeout(100)
                        # Capture a real running CSS/Web Animation on the page.
                        animations=page.evaluate('document.getAnimations().filter(a=>a.playState==="running").map(a=>a.currentTime)')
                        page.wait_for_timeout(200)
                        later=page.evaluate('document.getAnimations().filter(a=>a.playState==="running").map(a=>a.currentTime)')
                        assert animations and later and animations!=later, 'No active time-changing UI animation'
                        shots=BASE/'artifacts/multilingual-ui'; shots.mkdir(exist_ok=True)
                        page.screenshot(path=str(shots/(ident+'.png')),full_page=True)
                        page.set_viewport_size({'width':390,'height':844}); page.wait_for_timeout(300)
                        page.evaluate("window.scrollTo({top:0,left:0,behavior:'instant'})")
                        page.wait_for_timeout(100)
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2'), 'Mobile horizontal overflow'
                        page.screenshot(path=str(shots/(ident+'-mobile.png')),full_page=True)
                        page.emulate_media(reduced_motion='reduce'); page.wait_for_timeout(200)
                        assert page.get_by_role('heading',name=title,exact=True).is_visible()
                        row.update(passed=True, error='', animations_observed=len(animations), browser_errors=errors,
                            checked=['real controls and outcomes','reload persistence where requested','time-changing animation','390px layout','reduced-motion rendering'],
                            tested_date=datetime.now(timezone.utc).isoformat())
                        row['verifier_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
                    except Exception as exc:
                        failure=('Browser runtime errors: '+str(errors)+'\n' if errors else '')+(str(exc) or type(exc).__name__)
                        row.update(passed=False,error=failure[:2000],browser_errors=errors)
                    finally: context.close()
                    checks=BASE/'artifacts/multilingual-ui-browser';checks.mkdir(exist_ok=True)
                    row['tested_source_sha256']=hashlib.sha256((ROOT/ident/target).read_bytes()).hexdigest()
                    (checks/(ident+'.json')).write_text(json.dumps(row,indent=2)+'\n',encoding='utf-8')
                    save(data); print(json.dumps({'project':ident,'passed':row.get('passed'),'error':row.get('error','')[:220]}),flush=True)
            finally: browser.close()
    finally: server.shutdown(); server.server_close(); thread.join(timeout=3)
    data['passed']=all(data['projects'].get(c[0],{}).get('passed') for c in CASES)
    save(data)
    return data['passed']


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--generate',action='store_true'); parser.add_argument('--test',action='store_true'); parser.add_argument('--only'); parser.add_argument('--repair'); parser.add_argument('--model'); parser.add_argument('--gpu',type=int,default=0); parser.add_argument('--backend')
    args=parser.parse_args()
    if args.generate or args.repair: generate(args.repair or args.only,bool(args.repair),args.model,args.gpu,args.backend)
    if args.test:
        passed=test(args.only)
        if args.only:passed=receipt()['projects'].get(args.only,{}).get('passed',False)
        raise SystemExit(0 if passed else 1)
