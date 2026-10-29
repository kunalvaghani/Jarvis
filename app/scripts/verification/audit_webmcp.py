"""Bounded WebMCP capability audit in an isolated, unauthenticated browser.

No package downloads, normal-profile access, tool execution or production flags.
The optional feature flag applies only to this owned ephemeral Chrome process.
"""
import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import time


DETECT = """() => {
 const describe = x => ({present:!!x, methods:Object.fromEntries(
  ['registerTool','unregisterTool','getTools','executeTool','listTools'].map(k=>[k,typeof x?.[k]]))});
 return {secureContext:isSecureContext, origin:location.origin,
  document:describe(document.modelContext), navigator:describe(navigator.modelContext),
  testing:describe(navigator.modelContextTesting)};
}"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experimental-flag', action='store_true')
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright, Page, Frame
    started = time.monotonic()
    record = {'date':datetime.now(timezone.utc).isoformat(), 'status':'FAIL',
              'playwright_version':version('playwright'),
              'native_page_webmcp':hasattr(Page,'webmcp'), 'native_frame_webmcp':hasattr(Frame,'webmcp'),
              'experimental_flag':args.experimental_flag, 'production_changes':False,
              'scope':'Ephemeral headless Chrome, no authenticated profile or application tool execution.'}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='chrome', headless=True, timeout=20000,
                args=['--enable-features=WebMCP'] if args.experimental_flag else [])
            try:
                record['browser_version'] = browser.version
                context = browser.new_context()
                page = context.new_page()
                # Loopback secure context supplied entirely by the local route;
                # no external website, credentials or server is involved.
                page.route('http://127.0.0.1:38417/**', lambda route: route.fulfill(
                    status=200, content_type='text/html', body='<!doctype html><title>Owned WebMCP capability audit</title>'))
                page.goto('http://127.0.0.1:38417/', wait_until='domcontentloaded', timeout=5000)
                record['interfaces'] = page.evaluate(DETECT)
                cdp = context.new_cdp_session(page)
                record['cdp_available'] = bool(cdp.send('Browser.getVersion').get('protocolVersion'))
                cdp.detach()
                record['status'] = 'OBSERVED'
            finally:
                browser.close()
    except Exception as error:
        record.update(error_type=type(error).__name__, error=str(error)[:1500])
    record['seconds'] = round(time.monotonic()-started,3)
    destination=Path(__file__).resolve().parents[2]/'.jarvis-runtime'/('webmcp-capability-flag.json' if args.experimental_flag else 'webmcp-capability-default.json')
    destination.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record))
    return 0 if record['status']=='OBSERVED' else 1


if __name__=='__main__':
    raise SystemExit(main())
