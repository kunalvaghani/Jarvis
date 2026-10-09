"""Pinned upstream guidance and resources: read-only at execution time."""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from .agent_context import scoped
from .hermes import REVISION


CONTRACT = ("Upstream Hermes reference guidance only. Use Jarvis's currently offered tools and current authorization. "
            "Map browser actions to browser_inspect/navigate/click/fill, web_extract to scrape_web, and file reads to read_file. "
            "terminal/execute_code require the existing explicit command approval; computer_use is not installed here. "
            "Do not invent upstream tool names, run bundled scripts, install dependencies, send messages, or use paid services automatically. "
            "Check prerequisites and fresh state; unsupported platforms are reference only. Verify the whole task.")


class HermesSkills:
    def __init__(self, base):
        self.base = Path(base)
        self.root = self.base / "integrations/hermes-agent"
        self.rows = []
        self.error = None
        try:
            manifest = self.base / "integrations/profiles/hermes/hermes-skills.json"
            if not manifest.is_file():
                self.error = "Hermes skill manifest missing; run scripts/skills/build_hermes_skill_catalog.py after Hermes setup."
                return
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if data.get("revision") != REVISION or data.get("version") != 1:
                raise ValueError("Hermes skill manifest revision does not match the pinned source.")
            for row in data["skills"]:
                if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", row["name"]):
                    raise ValueError("Invalid Hermes skill name.")
                scoped(self.root, row["directory"])
                self.rows.append(row)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.rows = []
            self.error = str(exc)

    def compatible(self, row):
        return not row.get("platforms") or "windows" in row["platforms"]

    def search(self, query=".", limit=20, include_unsupported=False):
        from .skill_memory import words
        tokens = words(query.replace('-', ' '))
        specific = tokens - {'search', 'find', 'open', 'use', 'create', 'make', 'check', 'help', 'skills', 'skill', 'available'}
        if specific:
            tokens = specific
        rows = [(3 * len(tokens & words(row['name'].replace('-', ' ')))
                 + 2 * len(tokens & words(row['description']))
                 + len(tokens & words(' '.join(row.get('tags', []))))
                 + (0.1 if row['source'] == 'skills' else 0), row)
                for row in self.rows if include_unsupported or self.compatible(row)]
        rows.sort(key=lambda pair: (-pair[0], pair[1]['name']))
        return [{k: row.get(k) for k in ('name', 'description', 'source', 'category', 'platforms', 'prerequisites', 'conditions')}
                | {"windows_supported": self.compatible(row), "requirements_verified": False}
                for score, row in rows if query == "." or score >= 1][:limit]

    def read_bytes(self, row, resource):
        entry = next((f for f in row['files'] if f['path'] == resource), None)
        if entry is None:
            raise ValueError("No indexed resource with that exact relative path.")
        path = scoped(self.root, row['directory'] + '/' + resource)
        from .skill_memory import linked
        if any(linked(p) for p in (path, *path.parents) if p.is_relative_to(self.root)):
            raise ValueError("Linked Hermes resources are unsupported.")
        raw = path.read_bytes()
        if len(raw) != entry['bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError("Hermes resource changed from the indexed pinned copy; preserve and review it before rebuilding the index.")
        return raw

    def read(self, name, resource="SKILL.md", limit=12000):
        row = next((r for r in self.rows if r['name'] == name), None)
        if row is None:
            raise ValueError("Unknown Hermes skill name.")
        if not self.compatible(row):
            raise ValueError("This upstream skill does not declare Windows support; see its reference copy in Obsidian.")
        raw = self.read_bytes(row, resource)
        if len(raw) > limit:
            raise ValueError("Full skill/resource exceeds the model context budget; inspect its complete Obsidian copy or choose a smaller supporting reference. No partial guide was loaded.")
        return {"name": name, "resource": resource, "guidance": raw.decode('utf-8-sig'),
                "contract": CONTRACT, "prerequisites": row.get('prerequisites'), "conditions": row.get('conditions'),
                "resources": [r['path'] for r in row['files'] if r['path'] != resource]}

    def context(self, goal):
        selected = []
        explicit = re.findall(r"(?:\$hermes:|/hermes-)([a-z0-9-]+)", goal)
        remaining = 12000 if explicit else 4000
        candidates = [{"name": name} for name in explicit[:2]] or self.search(goal, limit=2)
        for item in candidates:
            row = next((r for r in self.rows if r['name'] == item['name']), None)
            if row is None or not self.compatible(row):
                continue
            file = next(f for f in row['files'] if f['path'] == 'SKILL.md')
            if file['bytes'] <= remaining:
                data = self.read(row['name'], limit=remaining)
                remaining -= file['bytes']
                selected.append(data)
            else:
                selected.append({"name": row['name'], "description": row['description'],
                                 "notice": "Full body not loaded: exceeds remaining context budget. Use skill_read folder=@hermes with a supporting reference or inspect the complete Obsidian copy.",
                                 "resources": [r['path'] for r in row['files'] if r['path'] != 'SKILL.md'][:12]})
        return {"skills": selected, "contract": CONTRACT} if selected else {}

    def sync(self, path_for, cancelled):
        """Copy all reference files; no installation/import/execution of helpers."""
        links, count = [], 0
        for row in self.rows:
            if cancelled():
                return count
            directory = 'Jarvis Skills/Hermes/' + row['directory']
            for entry in row['files']:
                if cancelled():
                    return count
                raw = self.read_bytes(row, entry['path'])
                path = path_for(directory + '/' + entry['path'])
                if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']:
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile('wb', dir=path.parent, delete=False) as output:
                    temporary = Path(output.name)
                    output.write(raw)
                try:
                    os.replace(temporary, path)
                finally:
                    temporary.unlink(missing_ok=True)
            state = 'Windows guidance; prerequisites unverified' if self.compatible(row) else 'Reference only; platform unsupported on Windows'
            links.append(f"- [[{directory}/SKILL|{row['name']}]] — {row['description']} ({state}; {row['source']})")
            count += 1
        from .skill_memory import atomic
        if not cancelled():
            license_text = (self.base / 'integrations/profiles/hermes/HERMES-LICENSE').read_text(encoding='utf-8')
            atomic(path_for('Jarvis Skills/Hermes/UPSTREAM-LICENSE.txt'), license_text)
            atomic(path_for('Jarvis Hermes Skills.md'), '# Jarvis Hermes Skills\n\n[[Jarvis Brain]] · [[Jarvis Skills]]\n\n'
                   + f"Source: {REVISION}. {len(self.rows)} upstream reference skills.\n\n" + CONTRACT + '\n\n' + '\n'.join(links) + '\n')
        return count
