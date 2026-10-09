"""Claude Code source boundary validation; never grants shell permission."""
from pathlib import Path
import re


def gui_script_target(goal, path):
    names={name.casefold() for name in re.findall(r'(?<![\w.-])([a-z][\w.-]*\.py)(?![\w.-])',goal,re.I)}
    return names=={Path(path).name.casefold()}


def decide(root, tool, args):
    root=Path(root).resolve(strict=True)
    if tool not in {'Read','Write','Edit','Glob','Grep'}:
        raise ValueError('Only scoped file tools are enabled for this coding request.')
    raw=args.get('file_path') if tool in {'Read','Write','Edit'} else args.get('path',str(root))
    if not isinstance(raw,str) or not raw:
        raise ValueError('The tool requires an exact project path.')
    path=Path(raw)
    path=path if path.is_absolute() else root/path
    if not path.resolve().is_relative_to(root) or path.is_symlink():
        raise ValueError('The target must remain inside the selected project, without links.')
    relative=path.relative_to(root)
    if any(part.startswith('.') or part.lower() in {'node_modules','models','venv','build','dist','target'} for part in relative.parts):
        raise ValueError('Hidden files, configuration secrets and generated dependencies are outside the editable source scope.')
    if tool in {'Glob','Grep'}:
        pattern=args.get('pattern','')
        if tool=='Glob' and ('..' in str(pattern) or Path(str(pattern)).is_absolute()):
            raise ValueError('Glob patterns must remain project-relative.')
        return path,None
    from jarvis.coder import SOURCE_EXTENSIONS, check_content
    if path.suffix.lower() not in SOURCE_EXTENSIONS or len(relative.parts)>8:
        raise ValueError('Choose a supported source/configuration file inside this project.')
    if path.exists() and (not path.is_file() or path.stat().st_size>80000):
        raise ValueError('Target must be a bounded regular source file.')
    if tool=='Read': return path,None
    if tool=='Write':
        content=args.get('content')
    else:
        if not path.is_file(): raise ValueError('Read the existing file before editing it.')
        current=path.read_text(encoding='utf-8')
        old,new=args.get('old_string'),args.get('new_string')
        if not isinstance(old,str) or not old or not isinstance(new,str): raise ValueError('Edit requires exact old/new text.')
        count=current.count(old)
        if count!=1 and not (count>0 and args.get('replace_all') is True): raise ValueError('Edit text must match uniquely or explicitly replace all matches.')
        content=current.replace(old,new) if args.get('replace_all') else current.replace(old,new,1)
    check_content(path,content)
    return path,content
