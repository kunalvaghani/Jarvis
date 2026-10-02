"""Isolated real Chromium inspection of one owned loopback development preview."""
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROLES=['button','textbox','combobox','dialog','heading','link','checkbox','status','listitem','tab','main']
KEYS=['Tab','Shift+Tab','Enter','Escape','Space','ArrowDown','ArrowUp']
ATTRIBUTES=['data-motion','aria-expanded','aria-invalid','aria-pressed','open','value']

def test_plan_schema():
    """Constrain model proposals at decoding, then validate again at execution."""
    variants=[]
    for action in ('click','fill','select','press','assert_text','assert_count','assert_attribute'):
        props={'action':{'type':'string','enum':[action]}}
        required=['action']
        if action!='assert_text':
            props.update(role={'type':'string','enum':ROLES},name={'type':'string','maxLength':160})
            if action!='press':required.extend(['name','role'])
        if action!='click':
            props['value']=({'type':'string','enum':KEYS} if action=='press' else
                {'type':'integer','minimum':0,'maximum':1000} if action=='assert_count' else {'type':'string','maxLength':500})
            required.append('value')
        if action=='assert_attribute':
            props['attribute']={'type':'string','enum':ATTRIBUTES}
            required.append('attribute')
        variants.append({'type':'object','additionalProperties':False,'required':required,'properties':props})
    return {'type':'object','additionalProperties':False,'required':['tests'],'properties':{'tests':{
        'type':'array','minItems':3,'maxItems':10,'items':{'type':'object','additionalProperties':False,
        'required':['name','steps'],'properties':{'name':{'type':'string','maxLength':160},
        'steps':{'type':'array','minItems':1,'maxItems':12,'items':{'oneOf':variants}}}}}}}

def validate_tests(tests):
    if not isinstance(tests,list) or len(tests)>20:
        raise ValueError('Provide up to 20 functional scenarios.')
    allowed={'click','fill','select','press','assert_text','assert_count','assert_attribute'}
    assertions=0
    for test in tests:
        if not isinstance(test,dict) or not isinstance(test.get('name'),str) or not isinstance(test.get('steps'),list) or not 1<=len(test['steps'])<=12:
            raise ValueError('Each browser scenario needs a name and bounded steps.')
        for step in test['steps']:
            if not isinstance(step,dict) or step.get('action') not in allowed:
                raise ValueError('Unsupported browser verification action.')
            if step['action'].startswith('assert_'):
                assertions+=1
            if step.get('role','button') not in ROLES:
                raise ValueError('Unsupported semantic role.')
            if len(json.dumps(step))>1500:
                raise ValueError('Browser step oversized.')
            if step['action']=='press' and step.get('value') not in KEYS:
                raise ValueError('Unsupported browser key.')
    return assertions

def step(page,item):
    action=item['action']
    if action=='assert_text':
        from playwright.sync_api import expect
        expect(page.get_by_text(item['value'],exact=item.get('exact',True)).first).to_be_visible(timeout=5000)
        return
    if action=='press' and not item.get('name'):
        page.keyboard.press(item['value'])
        return
    locator=page.get_by_role(item.get('role','button'),name=item.get('name',''),exact=True)
    if action=='assert_count':
        from playwright.sync_api import expect
        expect(locator).to_have_count(int(item['value']),timeout=5000)
        return
    if locator.count()!=1:
        raise ValueError('Expected one control: '+str(item.get('name')))
    if action=='click': locator.click()
    elif action=='fill': locator.fill(str(item['value']))
    elif action=='select': locator.select_option(str(item['value']))
    elif action=='press': locator.press(item['value'])
    elif action=='assert_attribute':
        from playwright.sync_api import expect
        if item.get('attribute') not in {'data-motion','aria-expanded','aria-invalid','aria-pressed','open','value'}:
            raise ValueError('Unsupported assertion attribute.')
        expected=str(item['value'])
        if item['attribute']=='data-motion' and expected=='@motion-preference':
            expected='reduced' if page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches") else 'full'
        expect(locator).to_have_attribute(item['attribute'],expected)

def inspect(request):
    from playwright.sync_api import sync_playwright
    from .agent_context import scoped
    project=Path(request['project']).resolve(strict=True)
    output=Path(request['output']).resolve(strict=True)
    if not output.is_relative_to(scoped(project,'.jarvis/development')):
        raise ValueError('Evidence must stay inside this project.')
    url=request['url']
    parsed=urlsplit(url)
    if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or parsed.username or parsed.password or not parsed.port:
        raise ValueError('Only loopback development URLs allowed.')
    tests=request.get('tests',[])
    assertions=validate_tests(tests)
    interactions=sum(s['action'] in {'click','fill','select','press'} for t in tests for s in t['steps'])
    axe=scoped(project,'node_modules/axe-core/axe.min.js')
    if not axe.is_file():
        raise ValueError('Project-local axe-core is missing; accessibility evidence cannot be omitted.')
    result={'source':'playwright_chromium','url':url,'functional_assertions':assertions,'functional_interactions':interactions,'views':[],
            'screenshots_are_functional_proof':False,'native_platform_verified':False}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        try:
            for label,width,height,reduce in [('desktop',1440,1000,False),('mobile',390,844,False),('reduced-motion',1440,1000,True)]:
                context=browser.new_context(viewport={'width':width,'height':height},reduced_motion='reduce' if reduce else 'no-preference',accept_downloads=False)
                # Isolate cookies/storage; block external requests and navigation.
                def route(r):
                    p=urlsplit(r.request.url)
                    if p.scheme in {'data','blob'} or (p.scheme=='http' and p.hostname=='127.0.0.1' and p.port==parsed.port): r.continue_()
                    else: r.abort()
                context.route('**/*',route)
                page=context.new_page()
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)[:500]))
                page.on('console',lambda message:errors.append(message.text[:500]) if message.type=='error' else None)
                page.goto(url,wait_until='networkidle',timeout=20000)
                page.wait_for_timeout(350)
                observation=page.locator('body').aria_snapshot()[:16000]
                screenshot=output/(label+'.png')
                page.screenshot(path=str(screenshot),full_page=True)
                overflow=page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
                page.keyboard.press('Tab')
                keyboard=page.evaluate('document.activeElement !== document.body && document.activeElement !== document.documentElement')
                scenarios=[]
                for test in tests:
                    page.goto(url,wait_until='networkidle',timeout=20000)
                    try:
                        for item in test['steps']: step(page,item)
                        scenarios.append({'name':test['name'],'passed':True})
                    except Exception as exc:
                        scenarios.append({'name':test['name'],'passed':False,'error':str(exc)[:1200]})
                page.goto(url,wait_until='networkidle')
                page.add_script_tag(path=str(axe))
                accessibility=page.evaluate("async () => { const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}); return r.violations.map(v=>({id:v.id,impact:v.impact,description:v.description,nodes:v.nodes.map(n=>n.target)})); }")
                motion=page.evaluate("() => ({preference:matchMedia('(prefers-reduced-motion: reduce)').matches, activeTransformAnimations:document.getAnimations().filter(a=>a.effect && a.effect.getKeyframes().some(f=>f.transform && f.transform!=='none') && Number(a.effect.getTiming().duration)>100).length})")
                result['views'].append({'name':label,'viewport':[width,height],'screenshot':str(screenshot),
                    'observation':observation,
                    'horizontal_overflow':overflow,'keyboard_focus':keyboard,'console_errors':list(dict.fromkeys(errors)),
                    'accessibility_violations':accessibility,'motion':motion,'scenarios':scenarios,
                    'headings':page.get_by_role('heading').all_text_contents()[:20]})
                context.close()
        finally:
            browser.close()
    result['checks_passed']=all(not v['horizontal_overflow'] and v['keyboard_focus'] and not v['console_errors']
        and not v['accessibility_violations'] and all(s['passed'] for s in v['scenarios'])
        and (v['name']!='reduced-motion' or (v['motion']['preference'] and not v['motion']['activeTransformAnimations'])) for v in result['views'])
    result['goal_verified']=result['checks_passed'] and assertions>=3 and interactions>=1 and bool(tests)
    (output/'browser.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    data=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    result=inspect(data)
    print(json.dumps({'checks_passed':result['checks_passed'],'goal_verified':result['goal_verified']}))
