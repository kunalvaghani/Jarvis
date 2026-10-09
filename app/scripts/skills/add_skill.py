"""Create a local workflow guide without executing downloaded helpers."""
import argparse
from pathlib import Path
import re


def create(base, name, description, instructions):
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) or len(name) > 64:
        raise ValueError('Use a lowercase hyphenated name, at most 64 characters.')
    if not description.strip() or '\n' in description or '\r' in description or len(description) > 1024:
        raise ValueError('Provide a one-line description, at most 1024 characters.')
    base = Path(base)
    from jarvis.skill_memory import linked
    folder = base / 'custom-skills' / name
    if (base / 'skills' / name).exists():
        raise ValueError('A bundled guide already uses this name; choose another.')
    for p in (folder, folder.parent, base):
        if linked(p):
            raise ValueError('Custom guides must use regular local directories.')
    body = f'---\nname: {name}\ndescription: {description.strip()}\n---\n\n{instructions.strip()}\n\nUse current Jarvis tools and fresh observations. Verify completion and respect cancellation and required approvals.\n'
    if len(body.encode('utf-8')) > 8000:
        raise ValueError('Keep the complete guide within 8,000 bytes.')
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'SKILL.md'
    with path.open('x', encoding='utf-8') as output:
        output.write(body)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('name')
    parser.add_argument('--description', required=True)
    parser.add_argument('--instructions-file', type=Path)
    args = parser.parse_args()
    instructions = (args.instructions_file.read_text(encoding='utf-8') if args.instructions_file else
        '# Workflow\n\nEdit this section with your ordered steps, when to use them, and how Jarvis should verify the result.')
    path = create(Path(__file__).resolve().parents[2], args.name, args.description, instructions)
    print(f'Created {path}\nEdit the workflow; Jarvis reloads it during discovery. Refresh the Obsidian copy with refresh_skill_memory.py.')


if __name__ == '__main__':
    main()
