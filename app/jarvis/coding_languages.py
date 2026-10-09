"""Bounded, first-party language guidance. No model commands are executed here."""
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

LANGUAGES = {
 'python': ('.py', 'Use existing dependencies or stdlib; a desktop GUI needs real callbacks and mainloop. Preserve imports/interfaces.', 'https://docs.python.org/3/'),
 'c': ('.c .h', 'Use C17, checked bounds/allocation and explicit ownership. C has no standard GUI; on Windows use Win32 or the requested installed toolkit. Supply complete build inputs.', 'https://learn.microsoft.com/en-us/cpp/c-language/'),
 'cpp': ('.cpp .cc .cxx .hpp .hh .hxx', 'Use C++17 RAII, standard containers, checked input and matching header declarations. Use Win32 or an installed requested GUI library; do not invent Qt/SDL availability.', 'https://learn.microsoft.com/en-us/cpp/cpp/'),
 'csharp': ('.cs .csproj .sln .resx', 'Respect installed .NET target/framework. WinForms requires a Windows target and UseWindowsForms in csproj, STAThread, Application.Run and wired events. WPF needs real XAML/code-behind bindings. Include project files.', 'https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/'),
 'java': ('.java', 'Public class name must match filename; preserve packages. Use Swing on the EDT with listeners and javax.swing.Timer; JavaFX needs declared dependencies. A JRE alone cannot compile: require JDK javac.', 'https://dev.java/learn/'),
 'javascript': ('.js .mjs .cjs', 'Match ESM/CommonJS to package.json and file extension. Wire events, validate input, update visible state. Avoid external CDN dependencies for offline projects.', 'https://developer.mozilla.org/en-US/docs/Web/JavaScript'),
 'typescript': ('.ts .tsx', 'Use real types, narrow nullable DOM values, preserve tsconfig/import conventions. Type-check in the selected project; do not silence errors with blanket any or ts-ignore.', 'https://www.typescriptlang.org/docs/'),
 'react': ('.jsx .tsx', 'Use components, state and real event handlers, stable list keys, immutable updates and cleaned-up effects/timers. Include working mount and declared local dependencies; JSX needs a build tool. Preserve existing Vite/Next conventions.', 'https://react.dev/learn'),
 'html': ('.html .htm .css', 'Build semantic responsive HTML/CSS with labels, keyboard controls and visible errors. For a single-file deliverable embed working CSS/JS, no placeholder controls or network assets.', 'https://developer.mozilla.org/en-US/docs/Web/HTML'),
 'go': ('.go .mod', 'Respect module/package paths, handle errors, defer cleanup, avoid data races. GUI needs a declared external toolkit; stdlib net/http serves browser UI.', 'https://go.dev/doc/'),
 'rust': ('.rs', 'Respect Cargo dependencies, ownership, Result handling and lifetimes. Native UI requires declared crates; never fabricate a stdlib GUI.', 'https://doc.rust-lang.org/book/'),
 'kotlin': ('.kt .kts', 'Match JVM/Android target and Gradle project. Use declared libraries, null safety and real event/state updates.', 'https://kotlinlang.org/docs/home.html'),
 'swift': ('.swift', 'Respect platform: SwiftUI needs an Apple SDK. Do not promise an iOS build on Windows; retain testable logic and declared target requirements.', 'https://www.swift.org/documentation/'),
 'php': ('.php', 'Validate input and escape HTML; use prepared database statements. Separate server handlers from client UI and declare server prerequisites.', 'https://www.php.net/manual/en/'),
 'ruby': ('.rb', 'Respect Gemfile dependencies and encoding; use explicit error handling and tests. GUI/framework requires installed gems.', 'https://www.ruby-lang.org/en/documentation/'),
 'sql': ('.sql', 'Use the existing SQL dialect, parameterized values and migrations preserving existing data. Never assume destructive operations are authorized.', 'https://www.sqlite.org/docs.html'),
}
EXTENSIONS = {ext for suffixes, _, _ in LANGUAGES.values() for ext in suffixes.split()} | {'.xaml', '.xml', '.gradle', '.svg'}
EXTENSION_PATTERN = '|'.join(re.escape(e[1:]) for e in sorted(EXTENSIONS))
LANGUAGE_PATTERN = r'(?:c\+\+|c#|csharp|c sharp|c|python|javascript|typescript|java|react|html|css|rust|go|kotlin|swift|php|ruby|sql)'


def context(goal, target=None):
    text = str(goal).casefold()
    suffix = Path(target or '').suffix.lower()
    chosen = []
    for name, (extensions, guidance, source) in LANGUAGES.items():
        aliases = {'c': r'c(?![+#])', 'cpp': r'c\+\+|cpp', 'csharp': r'c#|csharp|c sharp'}.get(name, name)
        if suffix in extensions.split() or re.search(r'(?<!\w)(?:' + aliases + r')(?!\w)', text):
            chosen.append({'language': name, 'extensions': extensions.split(), 'guidance': guidance, 'source': source})
    return {'languages': chosen[:5], 'interface_contract': (
        'Honor the requested language and existing stack. A game/app/website must implement the requested behavior, '
        'not a console substitute or a UI mockup. Animated UI uses real time-based state, '
        'requestAnimationFrame or toolkit timers; stop/pause/reset must work. Prefer elapsed-time updates, '
        'responsive layout, keyboard access and reduced motion. Include error/empty states. '
        'Keep output complete and bounded. Syntax, compilation, visible rendering, interaction and animation '
        'are separate checks; claim only checks actually run. Missing toolchains are prerequisites, never success.')}


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.script_open = False
        self.parts = []
        self.scripts = []
    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.script_open = True
            attrs = dict(attrs)
            self.active = not attrs.get('src') and attrs.get('type', '').lower() in {'', 'module', 'text/javascript', 'application/javascript'}
            self.parts = []
    def handle_data(self, data):
        if self.active:
            self.parts.append(data)
    def handle_endtag(self, tag):
        if tag == 'script':
            if self.active:
                self.scripts.append(''.join(self.parts))
            self.active = False
            self.script_open = False


def check_source(path, content):
    """Parse only. Does not import, compile project hooks or run generated code."""
    suffix = Path(path).suffix.lower()
    if suffix in {'.csproj', '.xaml', '.xml', '.resx', '.svg'}:
        if '<!DOCTYPE' in content.upper() or '<!ENTITY' in content.upper():
            raise ValueError('External XML entities are unsupported.')
        try:
            ET.fromstring(content)
        except ET.ParseError as exc:
            raise ValueError('Generated XML is invalid: ' + str(exc)) from exc
    scripts = [content] if suffix in {'.js', '.mjs', '.cjs'} else []
    if suffix in {'.html', '.htm'}:
        parser = Scripts()
        parser.feed(content)
        parser.close()
        if parser.script_open:
            raise ValueError('Generated HTML contains an unclosed script; incomplete source was not accepted.')
        scripts = parser.scripts
    node = shutil.which('node')
    if node:
        for source in scripts:
            with tempfile.TemporaryDirectory(prefix='jarvis-syntax-') as folder:
                temporary = Path(folder) / ('source.cjs' if suffix == '.cjs' else 'source.mjs')
                temporary.write_text(source, encoding='utf-8')
                try:
                    result = subprocess.run([node, '--check', str(temporary)], capture_output=True, text=True,
                        timeout=10, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                except (OSError, subprocess.TimeoutExpired) as exc:
                    raise ValueError('JavaScript syntax checker unavailable: ' + str(exc)) from exc
                if result.returncode:
                    # Put the actual error first: a minified offending source
                    # line can otherwise consume the entire tool-feedback cap.
                    lines=result.stderr.splitlines()
                    errors=[line for line in lines if re.search(r'\b(?:SyntaxError|TypeError|ReferenceError|Error):',line)]
                    location=next((line for line in lines if re.search(r':\d+$',line.strip())), '')
                    detail='; '.join(errors+[location]) if errors else result.stderr[-600:]
                    raise ValueError('Generated JavaScript failed node --check: ' + detail[:600])


def evidence_label(path):
    suffix = Path(path).suffix.lower()
    if suffix in {'.py', '.json'}:
        return 'Syntax parsed; runtime behavior not tested'
    if suffix in {'.js', '.mjs', '.cjs', '.html', '.htm'} and shutil.which('node'):
        return 'JavaScript syntax parsed where present; UI/runtime behavior not tested'
    if suffix in {'.csproj', '.xml', '.xaml', '.resx', '.svg'}:
        return 'XML parsed; build/runtime behavior not tested'
    return 'Disk readback only; compiler and runtime checks required'
