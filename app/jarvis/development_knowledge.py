"""Small first-party guides selected by stack; reference data, never permissions."""
import json
from pathlib import Path
import re

LIBRARY = Path(__file__).parent / 'assets/development-skills.json'

def detect_stack(project, goal=''):
    from .agent_context import scoped, bounded_text
    package = scoped(project, 'package.json')
    if package.is_file():
        data = json.loads(bounded_text(package, 16000))
        deps = {**data.get('dependencies', {}), **data.get('devDependencies', {})}
        for name, stack in [('expo', 'expo'), ('electron', 'electron'), ('next', 'next'), ('vite', 'vite')]:
            if name in deps:
                return stack
        return 'react' if 'react' in deps else 'node'
    # Never scaffold a different language inside an existing application.
    if any(scoped(project, p).exists() for p in ('pyproject.toml', 'Cargo.toml', 'go.mod', 'CMakeLists.txt', 'pom.xml', 'build.gradle')):
        return 'existing'
    text = goal.casefold()
    if any(p.suffix.lower() in {'.csproj', '.sln'} for p in list(Path(project).iterdir())[:200] if p.is_file()):
        return 'existing'
    if re.search(r'(?<!\w)(?:c\+\+|c#|c sharp|csharp|c|java|python|rust|go|kotlin|swift|php|ruby)(?!\w)', text):
        return 'existing'
    if re.search(r'\b(?:single.file|plain|vanilla|standalone)\b', text) and re.search(r'\b(?:html|javascript|css)\b', text):
        return 'node'
    if re.search(r'\b(expo|react native|android|ios|mobile app)\b', text):
        return 'expo'
    if re.search(r'\b(electron|desktop app|windows app)\b', text):
        return 'electron'
    if re.search(r'\b(next\.?js|server rendering|backend|server-side)\b', text):
        return 'next'
    if re.search(r'\b(react|website|dashboard|web app|landing page|frontend)\b', text):
        return 'vite'
    return 'unknown'

def catalog():
    return json.loads(LIBRARY.read_text(encoding='utf-8'))['skills']

def context(project, goal, target=None, budget=5500):
    stack = detect_stack(project, goal)
    extension = Path(target or '').suffix.lower()
    if extension == '.py' or stack == 'existing':
        return []
    if stack == 'unknown' and extension in {'.js','.jsx','.ts','.tsx','.css','.html'}:
        stack = 'vite' if extension in {'.jsx','.tsx'} else 'node'
    text = str(goal).casefold()
    selected, used = [], 0
    for row in catalog():
        if stack not in row['stacks']:
            continue
        if row['name'] == 'react-typescript' and stack == 'node' and extension not in {'.jsx','.tsx'} and 'react' not in text:
            continue
        if row['name'] == 'animation' and not re.search(r'animat|motion|transition|gsap', text):
            continue
        size = len(json.dumps(row, ensure_ascii=False))
        if used + size <= budget:
            selected.append(row)
            used += size
    return selected

def read(name):
    row = next((r for r in catalog() if r['name'] == name), None)
    if row is None:
        raise ValueError('Unknown built-in development skill.')
    return json.dumps(row, ensure_ascii=False)
