"""Install Jarvis-owned skill notes into the configured Obsidian vault."""
import json
from datetime import datetime, timezone
from pathlib import Path
from jarvis.obsidian_memory import ObsidianMemory
from jarvis.skill_memory import SkillMemory


def main():
    base = Path(__file__).resolve().parent
    config = json.loads((base / "config.json").read_text(encoding="utf-8"))
    memory = ObsidianMemory(base, config.get("memory"))
    if not memory.enabled:
        raise ValueError("Obsidian memory is disabled.")
    skills = SkillMemory(memory)
    skills.sync()
    # Refresh tool metadata without falsely presenting the project/app scan as new.
    from jarvis.memory_index import write_tools_note, tool_entries, DIRECT_OPERATIONS
    write_tools_note(memory.vault, {'generated_at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                                   'tools': tool_entries(), 'operations': DIRECT_OPERATIONS})
    if skills.error:
        raise ValueError(skills.error)
    if skills.upstream_error:
        raise ValueError(skills.upstream_error)
    print(json.dumps({"installed_skills": len(skills.catalog), "verified_procedures": len(skills.procedures),
                      "hermes_reference_skills": len(skills.upstream.rows) if skills.upstream else 0,
                      "custom_skills": sum(s['origin'] == 'Custom' for s in skills.catalog),
                      "obsidian_personal_skills": sum(s['origin'] == 'Personal' for s in skills.catalog),
                      "runtime_tools": len(tool_entries()),
                      "guide_errors": skills.skill_errors,
                      "vault_connected": (memory.vault / "Jarvis Skills.md").is_file()}))


if __name__ == "__main__":
    main()
