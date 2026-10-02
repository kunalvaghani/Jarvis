"""Index pinned upstream skills without importing or executing their scripts."""
import hashlib
import json
from pathlib import Path
import subprocess
import yaml
from jarvis.hermes import REVISION


def build(base):
    base = Path(base)
    root = base / "integrations/hermes-agent"
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).strip()
    if revision != REVISION:
        raise ValueError("Skill source must match Jarvis's pinned Hermes revision.")
    rows = []
    for source in ("skills", "optional-skills"):
        for path in sorted((root / source).rglob("SKILL.md")):
            if path.is_symlink() or any(p.is_symlink() for p in path.parents if p.is_relative_to(root)):
                raise ValueError("Linked skill sources are unsupported.")
            raw = path.read_bytes()
            metadata = yaml.safe_load(raw.decode("utf-8").split("---", 2)[1])
            files = []
            for resource in sorted(path.parent.rglob("*")):
                if not resource.is_file() or any(p.startswith('.') for p in resource.relative_to(path.parent).parts):
                    continue
                if resource.is_symlink():
                    raise ValueError("Linked skill resources are unsupported.")
                content = resource.read_bytes()
                files.append({"path": resource.relative_to(path.parent).as_posix(), "bytes": len(content),
                              "sha256": hashlib.sha256(content).hexdigest()})
            hermes = (metadata.get("metadata") or {}).get("hermes") or {}
            rows.append({"name": metadata["name"], "description": metadata.get("description", ""),
                         "category": path.parent.parent.name, "source": source,
                         "directory": path.parent.relative_to(root).as_posix(),
                         "platforms": metadata.get("platforms", []), "tags": hermes.get("tags", []),
                         "license": metadata.get("license", "See upstream license"),
                         "prerequisites": metadata.get("prerequisites", {}),
                         "environment": metadata.get("required_environment_variables", []),
                         "conditions": {k: v for k, v in hermes.items() if k.startswith(('requires_', 'fallback_'))},
                         "files": files})
    if len({r['name'] for r in rows}) != len(rows):
        raise ValueError("Duplicate upstream skill names.")
    result = {"version": 1, "revision": revision, "upstream": "https://github.com/NousResearch/hermes-agent",
              "skills": rows}
    (base / "integrations/hermes-skills.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"skills": len(rows), "bundled": sum(r['source'] == 'skills' for r in rows),
            "optional": sum(r['source'] == 'optional-skills' for r in rows),
            "windows_supported": sum(not r['platforms'] or 'windows' in r['platforms'] for r in rows)}


if __name__ == "__main__":
    print(json.dumps(build(Path(__file__).resolve().parent)))
