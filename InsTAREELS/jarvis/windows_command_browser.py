"""Unique scoped DOM targets for the pinned Playwright reference recipes."""
from pathlib import Path


def perform(request, page):
    from .windows_commands import prepare, interpret
    from .toolkits import public_url
    prepared=prepare(request['ids'],request['bindings'])
    if any(r['type']!='WEB' for r,_ in prepared):raise ValueError('Only browser recipes are admitted here.')
    expected=[request.get('url','')]
    if not expected[0] or expected[0]!=page.url:
        raise ValueError('Inspect the owned browser first; its URL must match this request.')
    def guard(row):
        if page.is_closed() or page.url!=expected[0]:
            raise ValueError('Owned page closed or URL changed; no further input issued.')
    class ScopedLocator:
        def __init__(self,locator):self.locator=locator
        def __getattr__(self,name):
            if name=='first':
                # The sample .first cannot silently choose among multiple headings.
                self.unique(); return self
            method=getattr(self.locator,name)
            def call(*args,**kwargs):
                self.unique()
                if name in {'fill','press','select_option','check','uncheck','click'}:
                    if self.locator.evaluate("e => e.type==='password' || /password/i.test(e.getAttribute('autocomplete')||'')"):
                        raise ValueError('Password fields are excluded.')
                result=method(*args,**kwargs)
                expected[0]=page.url  # Accept navigation caused by this one explicit action only.
                return result
            return call
        def unique(self):
            if self.locator.count()!=1 or not self.locator.is_visible():
                raise ValueError('The requested DOM target must be unique and visible.')
    class ScopedPage:
        def __getattr__(self,name):
            method=getattr(page,name)
            def call(*args,**kwargs):
                if name=='goto':
                    public_url(args[0])
                    result=method(*args,wait_until='domcontentloaded',**kwargs)
                    expected[0]=page.url
                    return result
                if name=='screenshot':
                    path=Path(kwargs.get('path',''))
                    if not path.is_absolute() or path.exists():
                        raise ValueError('Screenshot needs an absolute, new output filename.')
                if name in {'get_by_role','get_by_label','get_by_placeholder','get_by_text'}:
                    kwargs['exact']=True
                result=method(*args,**kwargs)
                return ScopedLocator(result) if name.startswith('get_by_') or name=='locator' else result
            return call
    result=interpret(prepared,{'page':ScopedPage()},guard)
    result['url']=page.url
    return result
