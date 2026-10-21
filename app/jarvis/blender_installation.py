"""Read-only local installation discovery shared by runtime and setup CLI."""
import os
from pathlib import Path
import shutil


def executables(configured=None):
    candidates=[configured,shutil.which('blender'),r'D:\blender.exe']
    for variable in ('ProgramFiles','ProgramFiles(x86)','LOCALAPPDATA'):
        value=os.environ.get(variable)
        if not value:continue
        folder=Path(value)/'Blender Foundation'
        if folder.is_dir():candidates.extend(folder.glob('Blender*/blender.exe'))
    found=[];seen=set()
    for value in candidates:
        if not value:continue
        try:path=Path(value).resolve()
        except (OSError,ValueError):continue
        identity=str(path).casefold()
        if identity in seen or path.name.casefold()!='blender.exe' or not path.is_file():continue
        seen.add(identity);found.append(path)
    return found
