"""Vision-route grounding benchmark: the full crop-then-ground pipeline against DOM ground truth.

D1 pages are rendered in headless Chrome; the page screenshot stands in for the screen capture, so
the benchmark needs no desktop and never photographs the user's screen. A case passes when the
point the route would click lies inside the element's DOM box. Results go to
results/vision-grounding.json.

    python benchmarks/vision_grounding.py [model ...]
"""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import statistics
import subprocess
import sys
import threading
import time

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from PIL import Image  # noqa: E402

from jarvis.control.coords import Rect, layout_from_rects  # noqa: E402
from jarvis.control.policy import Policy  # noqa: E402
from jarvis.control.routes.vision import OllamaGrounder, VisionExecutor  # noqa: E402
from jarvis.control.types import ControlError  # noqa: E402

VIEW = (1280, 800)
READ_BACK = '--no-read-back' not in sys.argv
PAGES = ('index', 'forms', 'modal', 'dynamic', 'scroll', 'files')
ELEMENTS = '''() => [...document.querySelectorAll('a,button,input,select,textarea,summary')].filter(e => {
  const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  return r.width > 4 && r.height > 4 && r.bottom > 0 && r.top < innerHeight && s.display != 'none' && s.visibility != 'hidden';
}).map(e => {
  // Clickable area = the control plus its own labels: clicking a <label> activates its control.
  const rects = [e.getBoundingClientRect(), ...[...(e.labels || [])].map(l => l.getBoundingClientRect())];
  const box = [Math.min(...rects.map(r => r.left)), Math.min(...rects.map(r => r.top)),
               Math.max(...rects.map(r => r.right)), Math.max(...rects.map(r => r.bottom))];
  let text = (e.innerText || e.value || e.getAttribute('aria-label') || '').trim(), name = '';
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.tagName) && e.labels && e.labels[0]) { text = e.labels[0].innerText.trim(); name = 'the ' + text + ' field'; }
  else if (e.tagName == 'A') name = 'the "' + text + '" link';
  else if (text) name = 'the "' + text + '" button';
  return {name: name.slice(0, 60), text: text.slice(0, 40), box}; }).filter(x => x.name.length > 6)'''
# Targets that are not on the page: the only safe outcome is a refusal, never a click.
ABSENT = [('forms', 'the "Delete account" button', 'Delete account'), ('index', 'the "Checkout" link', 'Checkout'),
          ('canvas', 'the yellow triangle', '')]
CANVAS = [('the red square', (40, 60, 100, 120)), ('the blue square', (170, 60, 230, 120)),
          ('the green square', (300, 60, 360, 120))]  # Shapes carry no label: no read-back.


def load_site():
    spec = importlib.util.spec_from_file_location('jarvis_d1_site', APP / 'benchmarks/sites/d1/server.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Site()


def cases():
    from playwright.sync_api import sync_playwright
    site = load_site()
    base, _ = site.start()
    rows = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome', headless=True)
            page = browser.new_page(viewport={'width': VIEW[0], 'height': VIEW[1]})
            for name in PAGES:
                page.goto(f'{base}/{name}.html')
                shot = page.screenshot()
                names = [e['name'] for e in page.evaluate(ELEMENTS)]
                for element in page.evaluate(ELEMENTS):
                    if names.count(element['name']) == 1:  # Ambiguous descriptions have no single right answer.
                        rows.append((name, shot, element['name'], tuple(element['box']), element['text']))
            page.goto(f'{base}/canvas.html')
            shot = page.screenshot()
            rows += [('canvas', shot, label, box, '') for label, box in CANVAS]
            shots = {row[0]: row[1] for row in rows}
            rows += [(page_name, shots[page_name], label, None, text) for page_name, label, text in ABSENT]
            browser.close()
    finally:
        site.stop()
    return rows


class VramPeak(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.peak, self.running = 0, True

    def run(self):
        while self.running:
            try:
                out = subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                                     capture_output=True, text=True, timeout=5).stdout
                self.peak = max(self.peak, int(out.split()[0]))
            except (OSError, ValueError, IndexError, subprocess.SubprocessError):
                pass
            time.sleep(.5)


def run(model, rows):
    image_for = {}

    def capture(region):
        return image_for['current'].crop((region.left, region.top, region.right, region.bottom))
    executor = VisionExecutor(Policy(), None, OllamaGrounder(model), capture=capture,
                              layout=lambda: layout_from_rects([('VIEW', (0, 0) + VIEW, 1.0)]),
                              window_at=lambda x, y: (1, 'chrome.exe', False))
    region = Rect(0, 0, *VIEW)
    image_for['current'] = Image.open(io.BytesIO(rows[0][1])).convert('RGB')
    try:
        executor.locate('the first link', region, 180)  # Load the model before timing.
    except ControlError:
        pass
    vram = VramPeak()
    vram.start()
    results = []
    for page, png, target, box, text in rows:
        image_for['current'] = Image.open(io.BytesIO(png)).convert('RGB')
        started = time.perf_counter()
        try:
            found = executor.locate(target, region, 180, label=text if READ_BACK else '')
            x, y = found.point.x, found.point.y
            hit = box is not None and box[0] - 1 <= x <= box[2] + 1 and box[1] - 1 <= y <= box[3] + 1
            outcome = 'hit' if hit else 'miss' if box is not None else 'false_click'
            detail = f'({x:.0f}, {y:.0f})'
        except ControlError as error:
            outcome, detail = ('correct_refusal' if box is None else error.category.value), str(error)[:80]
        ms = (time.perf_counter() - started) * 1000
        results.append({'page': page, 'target': target, 'box': box, 'outcome': outcome, 'detail': detail, 'ms': round(ms)})
        print(f'  {model:12} {page:8} {target[:40]:40} {outcome:16} {detail:14} {ms:6.0f} ms', flush=True)
    vram.running = False
    vram.join()
    latencies = sorted(r['ms'] for r in results)
    present = [r for r in results if r['box'] is not None]
    hits = sum(r['outcome'] == 'hit' for r in present)
    wrong = sum(r['outcome'] == 'miss' for r in present)
    absent = [r for r in results if r['box'] is None]
    return {'model': model, 'cases': len(present), 'hits': hits, 'wrong_clicks': wrong,
            'refused': len(present) - hits - wrong, 'accuracy': round(hits / len(present), 3),
            'absent_cases': len(absent), 'false_clicks_on_absent': sum(r['outcome'] == 'false_click' for r in absent),
            'p50_ms': round(statistics.median(latencies)), 'p95_ms': latencies[max(0, int(len(latencies) * .95) - 1)],
            'peak_vram_mib': vram.peak, 'results': results}


def main(models):
    rows = cases()
    print(f'{len(rows)} cases')
    summary = {'date': time.strftime('%Y-%m-%d'), 'pipeline': 'coarse 1280px + native crop, prefilled answer (no thinking), num_ctx 4096', 'label_read_back': READ_BACK,
               'ground_truth': 'DOM box of the control unioned with its own <label> boxes', 'viewport': VIEW,
               'runs': [run(model, rows) for model in models]}
    out = APP / 'benchmarks/results/vision-grounding.json'
    out.write_text(json.dumps(summary, indent=1), encoding='utf-8')
    for r in summary['runs']:
        print({k: v for k, v in r.items() if k != 'results'})


if __name__ == '__main__':
    main([a for a in sys.argv[1:] if not a.startswith('--')] or ['qwen3-vl:2b', 'qwen3-vl:4b'])
