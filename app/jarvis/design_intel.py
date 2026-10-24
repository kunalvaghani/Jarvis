"""PCIDE design intelligence: concrete design specifications, coherent component selection and a quality gate.

Style words become explicit tokens and restraint rules, so "futuristic" does not mean neon everywhere.
An existing project design system is reused and extended, never replaced. The quality gate combines
deterministic static checks with a real headless-browser render (Playwright, already installed for
Jarvis's browser checks). Screenshot comparison is advisory; it is never treated as proof of quality.
"""
import json
import re
import time
from pathlib import Path

from .code_intel import CodeCandidateRanker, ExternalCodeIntegrationGuard, iterate, project_facts, words

# Each direction: palette, typography, shape, motion and the anti-patterns it must avoid.
DIRECTIONS = {
    'futuristic': {'match': {'futuristic', 'hud', 'sci-fi', 'scifi', 'iron', 'jarvis', 'cyber', 'holographic', 'space'},
                   'palette': {'background': '#0b0f14', 'surface': '#121821', 'surface_raised': '#18212c', 'text': '#e6edf3',
                               'muted': '#8b98a5', 'accent': '#4cc9f0', 'accent_alt': '#f4a261', 'danger': '#ef476f', 'border': '#233142'},
                   'typography': {'body': 'Inter, Segoe UI, system-ui, sans-serif', 'numeric': 'JetBrains Mono, Cascadia Mono, ui-monospace, monospace',
                                  'scale': [12, 14, 16, 20, 24, 32], 'weights': [400, 500, 600]},
                   'radius': {'sm': 4, 'md': 8, 'lg': 12}, 'elevation': 'thin 1px borders and inner highlights instead of heavy shadows',
                   'motion': {'fast_ms': 120, 'base_ms': 200, 'slow_ms': 320, 'spring': {'stiffness': 320, 'damping': 30}},
                   'rules': ['one accent colour for interactive/active state, one secondary accent for warnings',
                             'monospace tabular numerals for live values', 'glow only on the focused/active element, never on every card',
                             'data first: charts and values have the strongest contrast']},
    'premium': {'match': {'premium', 'saas', 'professional', 'enterprise', 'clean', 'business', 'polished'},
                'palette': {'background': '#f7f7f8', 'surface': '#ffffff', 'surface_raised': '#ffffff', 'text': '#111827',
                            'muted': '#6b7280', 'accent': '#2f6fed', 'accent_alt': '#0f9d77', 'danger': '#d93025', 'border': '#e5e7eb'},
                'typography': {'body': 'Inter, Segoe UI, system-ui, sans-serif', 'numeric': 'Inter, system-ui, sans-serif',
                               'scale': [12, 14, 16, 18, 24, 30], 'weights': [400, 500, 600]},
                'radius': {'sm': 6, 'md': 10, 'lg': 14}, 'elevation': 'subtle two-step shadows; borders on dense surfaces',
                'motion': {'fast_ms': 120, 'base_ms': 180, 'slow_ms': 260, 'spring': {'stiffness': 400, 'damping': 34}},
                'rules': ['generous whitespace and a strict 8px grid', 'a single neutral palette with one brand accent',
                          'motion confirms actions; nothing loops']},
    'playful': {'match': {'playful', 'fun', 'colorful', 'colourful', 'friendly', 'cute', 'kids'},
                'palette': {'background': '#fffaf3', 'surface': '#ffffff', 'surface_raised': '#fff3e0', 'text': '#2b2a33',
                            'muted': '#6c6a7a', 'accent': '#ff7a59', 'accent_alt': '#3cb4ac', 'danger': '#e5484d', 'border': '#f1e4d1'},
                'typography': {'body': 'Nunito, Segoe UI, system-ui, sans-serif', 'numeric': 'Nunito, system-ui, sans-serif',
                               'scale': [13, 15, 17, 21, 27, 34], 'weights': [400, 600, 800]},
                'radius': {'sm': 10, 'md': 16, 'lg': 24}, 'elevation': 'soft coloured shadows',
                'motion': {'fast_ms': 140, 'base_ms': 240, 'slow_ms': 380, 'spring': {'stiffness': 260, 'damping': 18}},
                'rules': ['bouncy springs only on direct manipulation', 'two accent colours maximum']},
    'minimal': {'match': {'minimal', 'minimalist', 'simple', 'calm', 'quiet', 'neutral'},
                'palette': {'background': '#fafafa', 'surface': '#ffffff', 'surface_raised': '#ffffff', 'text': '#171717',
                            'muted': '#737373', 'accent': '#171717', 'accent_alt': '#525252', 'danger': '#b91c1c', 'border': '#e5e5e5'},
                'typography': {'body': 'system-ui, Segoe UI, sans-serif', 'numeric': 'system-ui, sans-serif',
                               'scale': [12, 14, 16, 18, 22, 28], 'weights': [400, 500]},
                'radius': {'sm': 4, 'md': 6, 'lg': 8}, 'elevation': 'borders only',
                'motion': {'fast_ms': 100, 'base_ms': 160, 'slow_ms': 220, 'spring': {'stiffness': 500, 'damping': 40}},
                'rules': ['typography and spacing carry the hierarchy', 'no decorative animation']},
}
AVOID = ['generic purple-blue gradient backgrounds', 'identical rounded cards for every element', 'glassmorphism on every surface',
         'random glowing buttons', 'placeholder-only interactions presented as finished', 'decorative animation without a purpose']
DARK_WORDS = {'dark', 'night', 'futuristic', 'hud', 'cyber'}
LIGHT_WORDS = {'light', 'bright', 'white'}


class VisualDesignResearchManager:
    """Requirement text and project facts -> one concrete, explicit design specification."""

    def specification(self, project, requirement, facts=None):
        facts = facts or project_facts(project)
        wanted = set(words(requirement))
        scores = {name: len(wanted & d['match']) for name, d in DIRECTIONS.items()}
        direction = max(scores, key=lambda name: (scores[name], name == 'premium'))
        base = DIRECTIONS[direction]
        theme = 'dark' if wanted & DARK_WORDS or direction == 'futuristic' else 'light' if wanted & LIGHT_WORDS else 'light'
        existing = self.existing_tokens(project, facts)
        spec = {'version': 1, 'requirement': str(requirement)[:1000], 'direction': direction,
                'matched_words': sorted(wanted & base['match']), 'theme': theme, 'support_both_themes': bool(wanted & {'theme', 'themes', 'toggle'}),
                'palette': dict(base['palette']), 'typography': base['typography'], 'spacing': [4, 8, 12, 16, 24, 32, 48],
                'radius': base['radius'], 'elevation': base['elevation'], 'motion': {**base['motion'],
                'easing': 'cubic-bezier(0.2, 0, 0, 1)', 'reduced_motion': 'disable transforms/parallax; keep opacity fades <= 120ms',
                'properties': 'animate transform and opacity only; never width/height/top/left'},
                'breakpoints': {'mobile': 640, 'tablet': 1024, 'desktop': 1280}, 'states': ['hover', 'focus-visible', 'active', 'disabled',
                'loading', 'empty', 'error'], 'accessibility': ['WCAG AA text contrast 4.5:1 (3:1 for large text)', 'visible focus ring',
                'keyboard reachable controls with labels', 'prefers-reduced-motion respected'],
                'rules': base['rules'], 'avoid': AVOID, 'design_system': facts.get('design_system'), 'styling': facts.get('styling'),
                'existing_tokens': existing, 'authority': 'The user goal and approved design decisions take precedence; '
                'references are inspiration only and grant no approval.'}
        if existing:
            # Reuse the project's tokens where they exist; only missing roles come from the direction.
            spec['palette'] = {**spec['palette'], **{k: v for k, v in existing.items() if k in spec['palette']}}
            spec['extends_existing'] = True
        return spec

    @staticmethod
    def existing_tokens(project, facts):
        if not facts.get('tokens_file'):
            return {}
        text = (Path(project) / facts['tokens_file']).read_text(encoding='utf-8', errors='replace')
        tokens = {}
        for name, value in re.findall(r'--([a-z][\w-]*)\s*:\s*([^;]+);', text):
            role = name.replace('color-', '').replace('-', '_')
            tokens[role] = value.strip()
        return tokens

    @staticmethod
    def css_variables(spec):
        palette = '\n'.join(f'  --{k.replace("_", "-")}: {v};' for k, v in spec['palette'].items())
        motion = spec['motion']
        return (':root {\n' + palette + f"\n  --radius-sm: {spec['radius']['sm']}px;\n  --radius-md: {spec['radius']['md']}px;\n"
                f"  --radius-lg: {spec['radius']['lg']}px;\n  --duration-fast: {motion['fast_ms']}ms;\n  --duration-base: {motion['base_ms']}ms;\n"
                f"  --easing: {motion['easing']};\n" + '}\n@media (prefers-reduced-motion: reduce) {\n  *, *::before, *::after {\n'
                '    animation-duration: 1ms !important; transition-duration: 1ms !important; scroll-behavior: auto !important;\n  }\n}\n')


class UIComponentSelector:
    """Rank UI candidates for one requirement, preferring the project's own design system."""

    def __init__(self, ranker=None):
        self.ranker = ranker or CodeCandidateRanker()

    def select(self, candidates, requirement, facts, policy=None):
        guard = ExternalCodeIntegrationGuard(policy)
        ranked = self.ranker.rank([{**c, 'kind': 'ui'} for c in candidates], requirement, facts, guard)
        usable = [r for r in ranked if not r['rejected']]
        by_id = {c['id']: c for c in candidates}
        libraries = {}
        for row in usable:
            library = by_id[row['candidate']].get('design_system') or by_id[row['candidate']].get('repository') or 'local'
            libraries.setdefault(library, []).append(row['score'])
        primary = facts.get('design_system') or (max(libraries, key=lambda k: sum(libraries[k])) if libraries else None)
        for row in usable:
            library = by_id[row['candidate']].get('design_system') or by_id[row['candidate']].get('repository') or 'local'
            if primary and library not in {primary, 'local'}:
                row['score'] = round(row['score'] * .85, 4)  # One coherent system beats mixing unrelated libraries.
                row.setdefault('notes', []).append(f'different library than the primary {primary}')
        usable.sort(key=lambda r: -r['score'])
        return {'primary_library': primary, 'selected': usable[0] if usable else None, 'ranked': usable,
                'rejected': [r for r in ranked if r['rejected']]}


def contrast(foreground, background):
    def luminance(hex_colour):
        value = hex_colour.lstrip('#')
        if len(value) == 3:
            value = ''.join(c * 2 for c in value)
        r, g, b = (int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
        lin = [c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4 for c in (r, g, b)]
        return .2126 * lin[0] + .7152 * lin[1] + .0722 * lin[2]
    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return round((light + .05) / (dark + .05), 2)


STATIC_CHECKS = [
    ('reduced_motion', 'animations without a prefers-reduced-motion path',
     lambda text: bool(re.search(r'@keyframes|animation:|transition:|motion\.|animate\(', text)) and
     not re.search(r'prefers-reduced-motion|useReducedMotion|reducedMotion', text)),
    ('layout_animation', 'animating layout properties (width/height/top/left) instead of transform/opacity',
     lambda text: bool(re.search(r'transition:\s*[^;]*\b(?:width|height|top|left|margin)\b|@keyframes[^}]*\{[^}]*\b(?:width|height|top|left):', text, re.S))),
    ('infinite_animation', 'continuously running animations',
     lambda text: len(re.findall(r'animation:[^;]*\binfinite\b|repeat:\s*Infinity', text)) > 2),
    ('focus_removed', 'focus outline removed without a focus-visible replacement',
     lambda text: bool(re.search(r'outline:\s*(?:none|0)', text)) and ':focus-visible' not in text),
    ('placeholder', 'placeholder content presented as finished',
     lambda text: bool(re.search(r'lorem ipsum|TODO:? implement|coming soon|onClick=\{\(\)\s*=>\s*\{\s*\}\}', text, re.I))),
    ('unlabelled_icon_button', 'icon-only buttons without accessible labels',
     lambda text: bool(re.search(r'<button(?![^>]*aria-label)[^>]*>\s*<(?:svg|img|i)\b', text, re.I))),
    ('console_left', 'console.log left in UI source', lambda text: len(re.findall(r'console\.log\(', text)) > 3),
]


class DesignQualityGate:
    """Static checks + a real render. Each finding names its check and evidence; nothing claims 'professional'."""

    def __init__(self, base, playwright=True):
        self.base = Path(base)
        self.playwright = playwright

    def static(self, project, spec=None):
        project = Path(project)
        findings, colours = [], set()
        for path in iterate(project, 1500):
            if path.suffix not in {'.css', '.scss', '.html', '.jsx', '.tsx', '.js', '.ts', '.vue', '.svelte'} or path.stat().st_size > 400_000:
                continue
            text = path.read_text(encoding='utf-8', errors='replace')
            relative = path.relative_to(project).as_posix()
            for key, label, check in STATIC_CHECKS:
                if check(text):
                    findings.append({'check': key, 'severity': 'warning', 'file': relative, 'detail': label})
            colours |= {c.casefold() for c in re.findall(r'#[0-9a-fA-F]{6}\b', text) if not re.search(r'--[\w-]+\s*:\s*' + re.escape(c), text)}
        if len(colours) > 14:
            findings.append({'check': 'palette', 'severity': 'warning', 'file': '*',
                             'detail': f'{len(colours)} hard-coded colours outside design tokens'})
        if spec:
            palette = spec['palette']
            for fg, bg in (('text', 'background'), ('text', 'surface'), ('muted', 'surface')):
                if palette.get(fg, '').startswith('#') and palette.get(bg, '').startswith('#'):
                    ratio = contrast(palette[fg], palette[bg])
                    if ratio < 4.5:
                        findings.append({'check': 'token_contrast', 'severity': 'error', 'file': 'design tokens',
                                         'detail': f'{fg} on {bg} contrast {ratio}:1 is below 4.5:1'})
        return findings

    def render(self, entry, out, baseline=None, viewports=None):
        """Load the entry in Chromium; collect console errors, overflow, focus, contrast, motion and screenshots."""
        if not self.playwright:
            return {'status': 'NOT_RUN', 'reason': 'browser checks disabled'}
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {'status': 'BLOCKED', 'reason': 'Playwright is not installed'}
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        viewports = viewports or {'desktop': (1440, 900), 'tablet': (834, 1112), 'mobile': (390, 844)}
        report = {'status': 'PASS', 'entry': str(entry), 'viewports': {}, 'console_errors': [], 'failed_requests': [], 'findings': []}
        url = entry if str(entry).startswith(('http://', 'https://')) else Path(entry).resolve().as_uri()
        try:
            with sync_playwright() as play:
                try:
                    browser = play.chromium.launch(channel='chrome', headless=True)  # Same browser as Jarvis's existing checks.
                except Exception:
                    browser = play.chromium.launch(headless=True)
                try:
                    for name, (width, height) in viewports.items():
                        for scheme in (('light', 'dark') if name == 'desktop' else ('light',)):
                            context = browser.new_context(viewport={'width': width, 'height': height}, color_scheme=scheme)
                            page = context.new_page()
                            page.on('console', lambda message: report['console_errors'].append(message.text[:300]) if message.type == 'error' else None)
                            page.on('pageerror', lambda error: report['console_errors'].append(str(error)[:300]))
                            page.on('requestfailed', lambda request: report['failed_requests'].append(request.url[:200]))
                            started = time.perf_counter()
                            page.goto(url, wait_until='load', timeout=20000)
                            page.wait_for_timeout(400)
                            metrics = page.evaluate(PAGE_PROBE)
                            metrics['load_ms'] = round((time.perf_counter() - started) * 1000, 1)
                            shot = out / f'{name}-{scheme}.png'
                            page.screenshot(path=str(shot), full_page=True)
                            metrics['screenshot'] = shot.name
                            if name == 'desktop' and scheme == 'light':
                                metrics['keyboard'] = keyboard_probe(page)
                                reduced = browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce')
                                motion_page = reduced.new_page()
                                motion_page.goto(url, wait_until='load', timeout=20000)
                                metrics['reduced_motion'] = motion_page.evaluate(MOTION_PROBE)
                                reduced.close()
                            report['viewports'][f'{name}-{scheme}'] = metrics
                            context.close()
                finally:
                    browser.close()
        except Exception as exc:  # A missing browser binary or broken page is reported, never hidden.
            return {'status': 'BLOCKED', 'reason': type(exc).__name__ + ': ' + str(exc)[:300]}
        for key, metrics in report['viewports'].items():
            if metrics['horizontal_overflow']:
                report['findings'].append({'check': 'overflow', 'severity': 'error', 'viewport': key,
                                           'detail': f"page is {metrics['scroll_width']}px wide in a {metrics['viewport_width']}px viewport"})
            for item in metrics['low_contrast'][:5]:
                report['findings'].append({'check': 'contrast', 'severity': 'error', 'viewport': key, 'detail': item})
            for item in metrics['clipped'][:5]:
                report['findings'].append({'check': 'clipped', 'severity': 'warning', 'viewport': key, 'detail': item})
            for item in metrics['unlabelled'][:5]:
                report['findings'].append({'check': 'label', 'severity': 'error', 'viewport': key, 'detail': item})
            keyboard = metrics.get('keyboard')
            if keyboard is not None and keyboard['focusable'] and not keyboard['visible_focus']:
                report['findings'].append({'check': 'focus', 'severity': 'error', 'viewport': key,
                                           'detail': 'tabbing reached controls but no visible focus indicator was detected'})
            motion = metrics.get('reduced_motion')
            if motion and motion['running_animations'] > 0:
                report['findings'].append({'check': 'reduced_motion', 'severity': 'error', 'viewport': key,
                                           'detail': f"{motion['running_animations']} animations keep running with reduced motion requested"})
        for message in report['console_errors'][:10]:
            report['findings'].append({'check': 'console', 'severity': 'error', 'detail': message})
        for request in report['failed_requests'][:10]:
            report['findings'].append({'check': 'resource', 'severity': 'error', 'detail': 'failed to load ' + request})
        if baseline:
            report['baseline'] = compare(Path(baseline), out)
        report['status'] = 'FAIL' if any(f['severity'] == 'error' for f in report['findings']) else 'PASS'
        (out / 'visual-qa.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        return report

    def evaluate(self, project, entry=None, spec=None, baseline=None, out=None):
        static = self.static(project, spec)
        render = self.render(entry, out or (Path(project) / '.jarvis' / 'visual-qa'), baseline) if entry else \
            {'status': 'NOT_RUN', 'reason': 'no renderable entry point (HTML file or local URL) was identified'}
        defects = [f for f in static + render.get('findings', []) if f['severity'] == 'error']
        return {'static': static, 'render': render, 'defects': defects,
                'status': 'FAIL' if defects else ('PASS' if render['status'] == 'PASS' else 'PARTIAL'),
                'note': 'Deterministic layout, accessibility, console and motion checks plus screenshots; '
                        'visual similarity and model critique are advisory and were not used as proof.'}


PAGE_PROBE = r'''() => {
  const doc = document.documentElement;
  const parse = c => { const m = c.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?/); return m ? [ +m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4] ] : null; };
  const lum = ([r, g, b]) => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const background = el => { while (el) { const c = parse(getComputedStyle(el).backgroundColor); if (c && c[3] > 0.5) return c; el = el.parentElement; } return [255, 255, 255, 1]; };
  const lowContrast = [], clipped = [], unlabelled = [];
  for (const el of Array.from(document.querySelectorAll('body *')).slice(0, 2500)) {
    const style = getComputedStyle(el); const rect = el.getBoundingClientRect();
    if (style.visibility === 'hidden' || style.display === 'none' || rect.width === 0 || rect.height === 0) continue;
    const text = Array.from(el.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join(' ');
    if (text) {
      const fg = parse(style.color), bg = background(el);
      if (fg) { const a = lum(fg), b = lum(bg); const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
        const large = parseFloat(style.fontSize) >= 24 || (parseFloat(style.fontSize) >= 18.66 && parseInt(style.fontWeight) >= 700);
        if (ratio < (large ? 3 : 4.5)) lowContrast.push(`"${text.slice(0, 40)}" ${ratio.toFixed(2)}:1`); }
      if (el.scrollWidth > el.clientWidth + 2 && ['hidden', 'clip'].includes(style.overflowX) && style.textOverflow !== 'ellipsis') clipped.push(`"${text.slice(0, 40)}" is cut off`);
    }
    if (['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName) || el.getAttribute('role') === 'button') {
      const name = (el.getAttribute('aria-label') || el.getAttribute('title') || el.innerText || el.value || el.getAttribute('placeholder') || '').trim();
      const labelled = el.id && document.querySelector(`label[for="${el.id}"]`);
      if (!name && !labelled) unlabelled.push(`${el.tagName.toLowerCase()} without an accessible name`);
    }
  }
  return { viewport_width: window.innerWidth, scroll_width: doc.scrollWidth, horizontal_overflow: doc.scrollWidth > window.innerWidth + 1,
           low_contrast: lowContrast.slice(0, 20), clipped: clipped.slice(0, 20), unlabelled: unlabelled.slice(0, 20),
           interactive: document.querySelectorAll('button, a[href], input, select, textarea, [tabindex]').length,
           layout_shift: (performance.getEntriesByType('layout-shift') || []).reduce((s, e) => s + (e.hadRecentInput ? 0 : e.value), 0) };
}'''

MOTION_PROBE = r'''() => ({ running_animations: document.getAnimations ? document.getAnimations().filter(a => a.playState === 'running' && a.effect && a.effect.getTiming().iterations === Infinity).length : 0 })'''


def keyboard_probe(page, presses=6):
    focusable, visible = 0, False
    for _ in range(presses):
        page.keyboard.press('Tab')
        state = page.evaluate('''() => { const el = document.activeElement; if (!el || el === document.body) return null;
            const s = getComputedStyle(el); return { outline: s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0,
            shadow: s.boxShadow !== 'none', visible: el.matches(':focus-visible') }; }''')
        if state:
            focusable += 1
            visible = visible or state['outline'] or state['shadow']
    return {'focusable': focusable, 'visible_focus': visible}


def compare(baseline, current):
    """Advisory pixel difference against an accepted baseline folder; rendering varies by machine."""
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return {'status': 'NOT_RUN', 'reason': 'Pillow unavailable'}
    rows = {}
    for shot in sorted(Path(current).glob('*.png')):
        reference = Path(baseline) / shot.name
        if not reference.is_file():
            rows[shot.name] = 'no baseline'
            continue
        with Image.open(reference) as a, Image.open(shot) as b:
            if a.size != b.size:
                rows[shot.name] = f'size changed {a.size} -> {b.size}'
                continue
            diff = ImageChops.difference(a.convert('RGB'), b.convert('RGB'))
            changed = sum(1 for pixel in diff.getdata() if max(pixel) > 24)
            rows[shot.name] = round(changed / (a.size[0] * a.size[1]), 4)
    return {'status': 'ADVISORY', 'changed_fraction': rows}
