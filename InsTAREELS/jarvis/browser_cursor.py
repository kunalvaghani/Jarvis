"""Disposable Jarvis pointer inside its owned page; CDP never moves the OS mouse."""
from uuid import uuid4


SHOW = """({token,box}) => {
 const e=document.createElement('div');
 e.dataset.jarvisCursor=token; e.setAttribute('aria-hidden','true');
 e.style.cssText='position:fixed;width:64px;height:60px;pointer-events:none;z-index:2147483647;contain:strict;';
 const x=Math.max(2,Math.min(innerWidth-2,box.x+box.width/2));
 const y=Math.max(2,Math.min(innerHeight-2,box.y+box.height/2));
 e.style.left=x+'px'; e.style.top=y+'px';
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
 svg.setAttribute('width','64');svg.setAttribute('height','60');svg.setAttribute('aria-hidden','true');
 const arrow=document.createElementNS('http://www.w3.org/2000/svg','path');
 arrow.setAttribute('d','M2 2 L2 32 L10 24 L17 40 L24 37 L17 20 L29 20 Z');
 arrow.setAttribute('fill','#00d2e1');arrow.setAttribute('stroke','#e6ffff');arrow.setAttribute('stroke-width','2');
 const label=document.createElementNS('http://www.w3.org/2000/svg','text');
 label.setAttribute('x','34');label.setAttribute('y','24');label.setAttribute('fill','#00e6f0');
 label.setAttribute('font-size','18');label.setAttribute('font-family','sans-serif');label.textContent='J';
 svg.append(arrow,label);e.appendChild(svg);
 document.documentElement.appendChild(e);
 e.animate([{transform:'translate(-100px,-70px)',opacity:0},{transform:'translate(0,0)',opacity:1}],{duration:180,fill:'forwards',easing:'ease-out'});
 setTimeout(()=>e.remove(),1200);
} """
REMOVE = "token => {for(const e of document.querySelectorAll('[data-jarvis-cursor]')) if(e.dataset.jarvisCursor===token)e.remove()}"


def click(target, page, **kwargs):
    """Pin one element, illustrate, dispatch once, clean up even on navigation/error."""
    element = target.element_handle(timeout=5000) if hasattr(target,'element_handle') else target
    if element is None: raise ValueError('The selected browser control disappeared; no click issued.')
    element.scroll_into_view_if_needed(timeout=5000)
    box = element.bounding_box()
    if not box: raise ValueError('The selected browser control has no visible bounds; no click issued.')
    token = uuid4().hex
    before = page.url
    try:
        page.evaluate(SHOW,{'token':token,'box':box})
        page.wait_for_timeout(240)
        if page.is_closed() or page.url!=before:
            raise ValueError('The page changed while Jarvis approached; no click issued.')
        return element.click(**kwargs)
    finally:
        try: page.evaluate(REMOVE,token)
        except Exception: pass  # A lost cleanup reply must never repeat the click.
