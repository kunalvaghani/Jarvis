"""Optional official release watcher, driven by the existing idle scheduler.

Public metadata is untrusted reference data. No code, model, dependency, shell,
credential or private project text is ever sent, installed or executed here.
"""
from datetime import datetime, timezone
from importlib import metadata
import json
import math
import re
import time

SOURCES = {
    'ollama': ('ollama/ollama', None),
    'llama_cpp': ('ggml-org/llama.cpp', None),
    'mcp': ('modelcontextprotocol/python-sdk', 'mcp'),
    'transformers': ('huggingface/transformers', 'transformers'),
    'vscode': ('microsoft/vscode', None),
}


class TechnologyWatch:
    def __init__(self, base, options=None, clock=time.time):
        from .agent_context import scoped, bounded_text
        options = {} if options is None else options
        if not isinstance(options, dict) or set(options) - {'enabled', 'sources', 'interval_seconds'}:
            raise ValueError('Invalid technology_watch settings.')
        self.enabled = options.get('enabled', False)
        self.sources = options.get('sources', ['ollama', 'mcp'])
        self.interval = options.get('interval_seconds', 86400)
        if (type(self.enabled) is not bool or not isinstance(self.sources, list)
                or not self.sources or len(self.sources) > len(SOURCES)
                or any(not isinstance(s, str) or s not in SOURCES for s in self.sources)
                or len(set(self.sources)) != len(self.sources)
                or type(self.interval) not in (int, float) or not math.isfinite(self.interval)
                or not 3600 <= self.interval <= 604800):
            raise ValueError('Technology watch needs known sources and an interval of 1 hour to 7 days.')
        self.base, self.clock = base, clock
        self.state = {}
        self.findings = []
        self.status = 'disabled' if not self.enabled else 'idle'
        if self.enabled:
            try:
                data = json.loads(bounded_text(scoped(base, '.jarvis-runtime/technology-watch.json'), 32768))
                if isinstance(data, dict) and data.get('version') == 1 and isinstance(data.get('sources'), dict):
                    for name in self.sources:
                        row = data['sources'].get(name)
                        if (isinstance(row, dict) and type(row.get('checked_at')) in (int, float)
                                and math.isfinite(row['checked_at']) and 0 <= row['checked_at'] <= clock()
                                and isinstance(row.get('release'), str) and len(row['release']) <= 128):
                            self.state[name] = {'checked_at': row['checked_at'], 'release': row['release']}
                    for row in data.get('findings', [])[-20:] if isinstance(data.get('findings'), list) else []:
                        if (isinstance(row, dict) and row.get('source') in self.sources
                                and isinstance(row.get('release'), str)
                                and re.fullmatch(r'[A-Za-z0-9_.+-]{1,128}', row['release'])
                                and isinstance(row.get('published_at'), str) and len(row['published_at']) <= 40):
                            datetime.fromisoformat(row['published_at'].replace('Z', '+00:00'))
                            source_repo = SOURCES[row['source']][0]
                            self.findings.append({'source': row['source'], 'release': row['release'],
                                                  'published_at': row['published_at'],
                                                  'url': 'https://github.com/' + source_repo + '/releases/tag/' + row['release']})
            except (OSError, ValueError, RecursionError):
                pass

    @staticmethod
    def fetch(repo, cancelled):
        """One bounded unauthenticated GET; redirects refused, no shared session."""
        import requests
        if repo not in {value[0] for value in SOURCES.values()}:
            raise ValueError('Unknown official release source.')
        if cancelled():
            return None
        deadline = time.monotonic() + 5
        # Environment credentials/proxies are not inherited by this public client.
        with requests.Session() as session:
            session.trust_env = False
            with session.get('https://api.github.com/repos/' + repo + '/releases/latest',
                             headers={'Accept': 'application/vnd.github+json'}, timeout=(2, 2),
                             allow_redirects=False, stream=True) as response:
                if response.status_code != 200:
                    raise ValueError('Official release endpoint unavailable.')
                data = bytearray()
                # Byte-sized chunks keep a trickling server from hiding inside a
                # large buffered read past cancellation/the whole-fetch deadline.
                for chunk in response.iter_content(1):
                    if cancelled():
                        return None
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Release fetch exceeded its time budget.')
                    data.extend(chunk)
                    if len(data) > 262144:
                        raise ValueError('Release metadata exceeded its byte budget.')
                return json.loads(data)

    def tick(self, cancelled=lambda: False, fetch=None):
        """Check one due source. First observation seeds quietly; changes notify.

        A failed read is checkpointed for backoff. Cancellation leaves the source
        due, without a partial result. Foreground cancels between network chunks;
        an in-progress socket read is bounded by its two-second timeout.
        """
        if not self.enabled or cancelled():
            return None
        now = self.clock()
        name = next((s for s in self.sources if now - self.state.get(s, {}).get('checked_at', -self.interval) >= self.interval), None)
        if name is None:
            return None
        repo, package = SOURCES[name]
        prior = self.state.get(name, {}).get('release', '')
        release, finding = prior, None
        try:
            data = (fetch or self.fetch)(repo, cancelled)
            if cancelled() or data is None:
                return None
            if not isinstance(data, dict) or data.get('draft') is not False or data.get('prerelease') is not False:
                raise ValueError('Expected one stable release record.')
            tag, published = data.get('tag_name'), data.get('published_at')
            if (not isinstance(tag, str) or not re.fullmatch(r'[A-Za-z0-9_.+-]{1,128}', tag)
                    or not isinstance(published, str) or len(published) > 40):
                raise ValueError('Malformed release identity or date.')
            datetime.fromisoformat(published.replace('Z', '+00:00'))
            release = tag
            installed = None
            if package:
                try:
                    installed = metadata.version(package)
                except metadata.PackageNotFoundError:
                    pass
            if prior and prior != tag:
                finding = {'source': name, 'release': tag, 'published_at': published,
                           'url': 'https://github.com/' + repo + '/releases/tag/' + tag,
                           'installed_package_version': installed,
                           'compatibility': 'not_tested', 'trust': 'untrusted_reference',
                           'next_action': 'Review release notes against active project and hardware; test in isolation before approval.'}
            self.status = 'current'
        except Exception:
            self.status = 'deferred'  # No response bodies, credentials or private context in status.
        if cancelled():
            return None
        from .agent_context import scoped
        from .skill_memory import atomic
        pending = {**self.state, name: {'checked_at': now, 'release': release}}
        findings = self.findings
        if finding:
            findings = (findings + [{k: finding[k] for k in ('source', 'release', 'published_at', 'url')}])[-20:]
        try:
            atomic(scoped(self.base, '.jarvis-runtime/technology-watch.json'),
                   json.dumps({'version': 1, 'sources': pending, 'findings': findings}, indent=2) + '\n')
        except (OSError, ValueError):
            self.status = 'storage_unavailable'
            return None
        self.state = pending
        self.findings = findings
        return finding
