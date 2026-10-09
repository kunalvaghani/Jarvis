"""Small, project-scoped coding tasks with checked model output and atomic writes."""
import ast
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile

from .projects import MARKERS, SKIP, has_project_marker
from .commands import normalize_spoken_code_request
from .code_context import related_context, bounded_references, apply_replacements, check_python_interfaces, save_change_review
from .agent_context import coding_context
from . import gui_contract
from .coding_languages import EXTENSIONS, LANGUAGE_PATTERN, context as language_context, check_source, evidence_label


SOURCE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".html", ".css", ".md", ".txt", ".yaml", ".yml", ".toml",
                     ".c", ".h", ".cpp", ".hpp", ".go", ".java", ".rs", ".sh", ".ps1", ".sql"}
SOURCE_EXTENSIONS |= EXTENSIONS
SOURCE_PATTERN = "|".join(re.escape(extension[1:]) for extension in sorted(SOURCE_EXTENSIONS))
CODING_PATTERN = "|".join(re.escape(extension[1:]) for extension in sorted(
    SOURCE_EXTENSIONS - {".txt", ".md", ".yaml", ".yml", ".toml"}))
SKIP_LOWER = {name.casefold() for name in SKIP}


def python_file_request(goal):
    """Recognize an underspecified Python coding request without inventing a goal."""
    if not (re.search(r"\b(?:create|make|write|build)\b", goal, re.I)
            and re.search(r"\bpython\s+(?:(?:source\s+)?file|code)\b", goal, re.I)
            and re.search(r"\bcode\b", goal, re.I)):
        return None
    explicit = re.search(r"\b([A-Za-z][\w-]{0,80}\.py)\b", goal, re.I)
    if explicit:
        return explicit[1]
    topic = re.search(r"\b(?:with|containing) (?:a |an )?([a-z][a-z0-9 -]{1,50}?) code\b", goal, re.I)
    if not topic:
        topic = re.search(r"\bcode for (?:a |an )?([a-z][a-z0-9 -]{1,50}?)(?=\s+(?:in|inside|to|please)\b|[.?!]|$)", goal, re.I)
    if not topic:
        raise ValueError("What should the Python file do? Name its purpose or filename, such as calculator.py.")
    name = re.sub(r"[^a-z0-9]+", "_", topic[1].casefold()).strip("_")
    if not name:
        raise ValueError("Name the Python file or describe what its code should do.")
    return name + ".py"


def named_folder_request(goal):
    def scope(value):
        path=Path(value)
        return str(path.parent) if path.suffix.lower() in SOURCE_EXTENSIONS and not path.is_dir() else value
    # A clarification prefix is authoritative, even when the original task
    # still contains an unavailable named/absolute destination.
    prefix = re.match(r"^(?:in|inside) (?:the )?folder (.+?),\s*", goal, re.I)
    if prefix:
        return scope(prefix[1].strip().strip('\"\''))
    quoted = re.search(r'\b(?:in|inside|to|open)(?: the)?(?: folder)?\s+["\']([a-z]:[\\/][^"\']+)["\']', goal, re.I)
    if quoted:
        return scope(quoted[1].strip())
    absolute = re.search(r'\b(?:in|inside|to)(?: the)?(?: folder)?\s+([a-z]:[\\/].+?)(?=\s+(?:and|with|containing)\b|$)', goal, re.I)
    if absolute:
        return scope(absolute[1].strip())
    # A named absolute source file also supplies its project scope.
    source = re.search(r'["\']([a-z]:[\\/][^"\']+\.(?:' + SOURCE_PATTERN + r'))["\']', goal, re.I)
    if not source:
        source = re.search(r'(?<!\w)([a-z]:[\\/].+?\.(?:' + SOURCE_PATTERN + r'))(?=\s|$)', goal, re.I)
    if source:
        return str(Path(source[1]).parent)
    opening = re.match(r"^open (?:the )?folder (.+?)(?:,|\s+(?:and|then)\s+)", goal, re.I)
    if opening:
        return opening[1].strip()
    # Prefer folder-first destinations before suffix syntax: otherwise
    # "to monitor my health in folder TestCodes" captures the app's purpose.
    first = re.search(r'\b(?:in|inside|to)\s+(?:the\s+)?(?:project\s+)?folder\s+(?:["\']([^"\']+)["\']|([a-z0-9][a-z0-9 _-]{0,70}?)(?=\s+(?:and|then|with|containing)\b|[,;.!?]|$))', goal, re.I)
    if first:
        name = (first[1] or first[2]).strip()
        return name if first[1] else re.sub(r'\s+(?:project\s+)?folder$', '', name, flags=re.I)
    match = re.search(r"\b(?:in|inside|to) (?:the )?([a-z0-9](?:(?!\b(?:in|inside|to)\b)[a-z0-9 _-]){0,70}?) (?:project )?folder\b", goal, re.I)
    if match:
        name = match[1].strip()
        return name + ' folder' if name.casefold() in {'this','current','selected','open'} else name
    return None


def folder_matches_request(requested, project):
    if requested.casefold() in {'this folder','current folder','selected folder','open folder'}:
        return True
    if Path(requested).is_absolute():
        return Path(requested).resolve() == Path(project).resolve()
    return re.sub(r'[^a-z0-9]', '', requested.casefold()) == re.sub(r'[^a-z0-9]', '', Path(project).name.casefold())


def coding_folder(actions, goal, cancelled, prior=None):
    """Explicit path, then freshly observed open folder, then remembered scope."""
    requested = named_folder_request(goal)
    if requested:
        return actions._task_folder('the open folder' if requested == 'open folder' else requested, cancelled)
    try:
        return actions._task_folder('this folder', cancelled)
    except ValueError:
        if cancelled():
            raise ValueError('Coding cancelled before selecting a project.')
        if isinstance(prior, dict) and prior.get('project') and Path(prior['project']).is_dir():
            return prior['project']
        raise


def workspace_coding_request(goal):
    goal = normalize_spoken_code_request(goal)
    # Notes/data workflows remain file operations even when their subject is
    # called "project". A plain folder scope is not a code-generation request.
    if (re.search(r'\b[a-z][\w-]*\.(?:txt|csv)\b', goal, re.I)
            and not re.search(r"\b[a-z][\w-]*\.(?:" + CODING_PATTERN + r")\b", goal, re.I)
            and not re.search(r'\b(?:python|code|scripts?|programs?|apps?)\b', goal, re.I)
            and not requested_new_folder(goal)):
        return False
    return bool(re.search(r"\b(?:create|make|build|add|modify|edit|update|write|fix|refactor)\b", goal, re.I)
                and (re.search(r"\b(?:scripts?|programs?|apps?|projects?|games?|websites?|webpages?)\b", goal, re.I)
                     or re.search(r'(?<!\w)' + LANGUAGE_PATTERN + r'(?!\w)', goal, re.I)
                     or simple_folder_request(goal) or requested_new_folder(goal)
                     or (gui_contract.requested(goal) and re.fullmatch(r'(?:please )?(?:add|fix|update|modify|change)\s+(?:the |a )?(?:ui|gui)(?:\s+(?:to it|again|please))*[.!?]*', goal, re.I))
                     or re.search(r"\b[a-z][\w-]*\.(?:" + CODING_PATTERN + r")\b", goal, re.I)))


def explicit_coding_intent(goal):
    """Code/product intent survives words such as email or GitHub in a spec."""
    if not workspace_coding_request(goal):
        return False
    if re.match(r'(?:please )?(?:write|draft|create|make|update|edit|modify|add)\s+(?:a |an |the )?(?:email|tweet|pull request|github repository|jira issue|calendar event|slack message)\b',goal,re.I):
        return False
    return bool(re.search(r'(?<!\w)' + LANGUAGE_PATTERN + r'(?!\w)', goal, re.I)
                or re.search(r'\b[a-z][\w-]*\.(?:' + CODING_PATTERN + r')\b', goal, re.I)
                or re.search(r'\b(?:code|scripts?|programs?|ui|gui|components?)\b', goal, re.I)
                or re.search(r'\b(?:create|make|build|write)\b.*\b(?:games?|apps?|websites?|webpages?)\b', goal, re.I))


def simple_folder_request(goal):
    match = re.fullmatch(r"(?:create|make) (?:a |the )?folder (?:called |named )?([a-z0-9][a-z0-9 _-]{0,55})[.!]?", goal.strip(), re.I)
    return match[1].strip() if match and match[1].split()[0].casefold() not in {"and", "with", "in", "inside"} else None


def requested_new_folder(goal):
    match = re.search(r"\b(?:create|make|build) (?:a |the )?(?:folder (?:called |named )?|([a-z0-9_-]+) folder\b)", goal, re.I)
    if not match:
        return None
    if match[1]:
        name = match[1]
    else:
        after = goal[match.end():]
        named = re.match(r"([a-z0-9_-]+)", after.strip(), re.I)
        name = named[1] if named else None
    return name if name and name.casefold() not in {"and", "with", "in", "inside", "a", "the"} else None


def single_python_target(goal):
    """Infer only a clear single-script target; code still comes from the coder."""
    if requested_new_folder(goal) or re.search(r'\b(?:and then|scripts|programs|files)\b', goal, re.I):
        return None
    match = re.search(r'\b(?:create|make|write|build) (?:a |an |the )?python (?:script|program|file|code) (?:for |called |named )?(?:a |an )?([a-z][a-z0-9 _-]{0,45}?)(?=\s+(?:in|inside)\b|[.!?]|$)', goal, re.I)
    if not match or re.search(r'\b(?:and|with|then)\b', match[1], re.I):
        return None
    name = re.sub(r'[^a-z0-9]+', '_', match[1].casefold()).strip('_')
    return name + '.py' if name else None


def calculator_template(goal, name):
    if name.casefold() not in {"calculator.py", "basic_calculator.py"} or gui_contract.requested(goal) or re.search(r"\b(scientific|advanced)\b", goal, re.I):
        return None
    return (Path(__file__).parent / "templates" / "calculator.py").read_text(encoding="utf-8")


def test_calculator(path):
    for operation, first, second, expected in (("add", "5", "10", "15"),
                                                ("multiply", "6", "7", "42"),
                                                ("divide", "12", "4", "3")):
        result = subprocess.run([sys.executable, str(path), operation, first, second],
            cwd=path.parent, capture_output=True, text=True, timeout=5, check=False)
        if result.returncode or result.stdout.strip() != expected:
            raise ValueError(f"Calculator test failed for {operation}: {result.stderr.strip()[:300] or result.stdout.strip()[:300]}")
    zero = subprocess.run([sys.executable, str(path), "divide", "2", "0"],
        cwd=path.parent, capture_output=True, text=True, timeout=5, check=False)
    if zero.returncode == 0 or "zero" not in zero.stderr.casefold():
        raise ValueError("Calculator division by zero test failed.")


def create_python_from_goal(actions, client, goal, name, cancelled):
    """Create a visible draft first, fill it, then check the written program."""
    from .desktop_tasks import modify_text_file, write_new_file
    from .task_state import TaskState
    state = getattr(actions, "task_state", None)
    resumed = getattr(actions, "resume_source", None)
    from .clarification import TaskClarification
    try:
        folder = Path(coding_folder(actions, goal, cancelled, resumed)).resolve(strict=True)
    except ValueError as exc:
        if isinstance(exc, TaskClarification):
            raise
        raise TaskClarification("Which folder should I create the Python file in? Say a folder name or full path. " + str(exc), "folder") from exc
    if isinstance(state, TaskState):
        state.set_project(folder)
    if getattr(client, 'options', {}).get('coding_backend') in {'claude-code','codex','jarvis'}:
        return Coder(actions, client).run(folder, goal + ' Target source file: ' + name, cancelled, selected=True)
    requested_folder = named_folder_request(goal)
    if requested_folder and not folder_matches_request(requested_folder, folder):
        raise ValueError(f"The selected File Explorer folder is {folder.name}, not {requested_folder}. Open the requested folder first.")
    destination = folder / name
    marker = f"# Jarvis draft: {name}\n# Waiting for generated code.\n"
    from .code_stream import CodeDraft, owned_draft
    runtime_base = getattr(actions, 'base', None)
    runtime_base = runtime_base if isinstance(runtime_base, Path) else folder
    template = calculator_template(goal, name)
    if destination.is_symlink():
        raise ValueError("Jarvis will not edit a linked file.")
    if destination.exists():
        if not destination.is_file():
            raise ValueError(f"{name} is not a regular file.")
        existing = destination.read_text(encoding="utf-8")
        if template is not None and existing == template:
            test_calculator(destination)
            if isinstance(state, TaskState):
                state.checkpoint("goal_verified", source='calculator_functional_checks', evidence="Existing calculator matched requested template and four functional checks passed")
            return f"{destination} already has working calculator code; four functional checks passed."
        if existing != marker and not owned_draft(runtime_base, destination):
            raise ValueError(f"{name} already exists in {folder}; no file was overwritten.")
        actions.report("action", f"Resuming Jarvis draft {destination}")
    else:
        if cancelled():
            raise ValueError("Coding task cancelled before file creation.")
        write_new_file(folder, name, marker, cancelled)
        actions.report("action", f"Created draft {destination}")
    if isinstance(state, TaskState):
        state.checkpoint("observed_draft", target=destination, evidence="Jarvis draft read back; code generation can resume")
    actions.report("screen", f"Selected File Explorer folder: {folder}")
    actions.report("plan", f"Write Python code into {name}, then test it")
    step = {"path": name, "reason": "Implement the requested Python program in a new file"}
    stream = CodeDraft(runtime_base, destination, destination.read_bytes(), True, marker, cancelled, actions.report)
    content = template or generate_checked(client, cancelled, destination, goal=goal, project=folder.name,
        path=name, reason=step["reason"], current="", plan=[step], files=[], references={},
        _on_code=stream.write,
        **{**coding_context(folder, goal, name), "skill_project": str(folder)})
    from .progress import status
    status(actions.report, 'Validating code', destination)
    check_content(destination, content)
    if cancelled():
        raise ValueError(f"Coding task cancelled; draft remains at {destination}.")
    if isinstance(state, TaskState):
        state.checkpoint("action_attempted", action="modify_file", target=destination,
                         evidence="Generated draft replacement beginning; inspect disk after interruption")
    path = modify_text_file(folder, name, stream.expected.decode('utf-8'), content, cancelled)
    if not path or path.read_text(encoding="utf-8") != content:
        raise ValueError(f"The generated Python file could not be verified after writing; inspect {destination}.")
    if isinstance(state, TaskState):
        state.checkpoint("wrote_file", target=path, evidence="generated code replaced the draft")
        state.checkpoint("observed_file", target=path, evidence="generated content read back from disk")
    actions.report("action", f"Wrote code to {path}; testing")
    if template is not None:
        test_calculator(path)
    if isinstance(state, TaskState):
        state.checkpoint("goal_verified", source='disk_readback', evidence="Generated file read back; " +
            ("four calculator functional checks passed" if template is not None else "Python syntax checked; functional behavior not verified"))
    actions.last_created = (path, content)
    status(actions.report, 'File saved', path, file=str(path), preview=content[:1600], characters=len(content),
           outcome='Disk readback + calculator checks passed' if template is not None else 'Disk readback + Python syntax checked; behavior not tested')
    try:
        stream.complete()
    except (OSError, ValueError) as exc:
        actions.report('warning', 'Code was written; streaming metadata needs repair: ' + str(exc))
    return (f"Created and tested {path}: addition, multiplication, division, and division by zero passed."
            if template is not None else f"Created {path} with generated Python code; syntax checked.")


def project_files(project, limit=160):
    found = []
    for folder, directories, files in os.walk(project, followlinks=False):
        directories[:] = sorted((d for d in directories if d.casefold() not in SKIP_LOWER and not d.startswith(".")
                                 and not (Path(folder) / d).is_symlink()), key=lambda d: (
            d.casefold() in {'integrations', 'vendor', 'artifacts', 'third_party'},
            d.casefold() not in {'src', 'app', 'jarvis', 'lib'}, d.casefold()))
        for name in sorted(files):
            path = Path(folder) / name
            if not name.startswith(".") and path.suffix.lower() in SOURCE_EXTENSIONS and not path.is_symlink():
                found.append(path.relative_to(project).as_posix())
                if len(found) >= limit:
                    return found
    return found


def relative_parts(name, directory=False):
    if not isinstance(name, str) or len(name) > 180 or "\\" in name or ":" in name:
        raise ValueError("Coding plan named an invalid relative path.")
    relative = PurePosixPath(name)
    if (relative.is_absolute() or not relative.parts or any(part in {"", ".", ".."} or part.startswith(".")
            or part.casefold() in SKIP_LOWER for part in relative.parts) or len(relative.parts) > 4
            or (not directory and relative.suffix.lower() not in SOURCE_EXTENSIONS)):
        raise ValueError("Coding plan named an unsupported project path.")
    return relative


def strip_project_prefix(name, project):
    if not isinstance(name, str):
        return name
    parts = PurePosixPath(name).parts
    if len(parts) > 1 and parts[0].casefold() == project.name.casefold():
        return PurePosixPath(*parts[1:]).as_posix()
    return name


def target_path(project, name, planned_dirs=()):
    relative = relative_parts(name)
    path = project.joinpath(*relative.parts)
    if path.is_symlink() or path.resolve().parent != path.parent.resolve() or not path.resolve().is_relative_to(project):
        raise ValueError("Coding plan points outside the project.")
    if not path.parent.is_dir() and path.parent not in planned_dirs:
        raise ValueError("A new file needs an existing or planned folder.")
    return path


def draft_content(path):
    message = f"Jarvis draft: {path.name}. Waiting for generated code."
    extension = path.suffix.lower()
    if extension == ".json":
        return json.dumps({"_jarvis_draft": message}) + "\n"
    if extension in {".js", ".jsx", ".ts", ".tsx", ".css"}:
        return f"/* {message} */\n"
    if extension == ".html":
        return f"<!-- {message} -->\n"
    return f"# {message}\n"


def check_content(path, content):
    if not isinstance(content, str) or not content.strip() or len(content) > 20000 or "\x00" in content:
        raise ValueError("The coding model returned empty or oversized file content.")
    try:
        content.encode('utf-8')
    except UnicodeEncodeError as exc:
        raise ValueError('Generated source contains invalid Unicode; use valid UTF-8 characters.') from exc
    try:
        if path.suffix.lower() == ".py":
            ast.parse(content, filename=str(path))
        elif path.suffix.lower() == ".json":
            json.loads(content)
    except (SyntaxError, ValueError, MemoryError, RecursionError) as exc:
        raise ValueError(f"Generated {path.name} failed syntax validation: {exc}") from exc
    check_source(path, content)


def comment_markdown_preamble(content):
    """Turn an obvious generated README header before Python code into comments."""
    if not isinstance(content, str):
        return content
    lines = content.splitlines(keepends=True)
    anchor = next((i for i, line in enumerate(lines) if re.match(
        r"^(?:from\s+\S+\s+import\s+|import\s+|def\s+|async\s+def\s+|class\s+|@|if\s+__name__|[A-Za-z_]\w*\s*=)", line)), None)
    if anchor is None or anchor > 40 or not any(
            line.lstrip().startswith(("##", "```")) for line in lines[:anchor]):
        return content
    return "".join((line if not line.strip() or line.lstrip().startswith("#") else "# " + line)
                   for line in lines[:anchor]) + "".join(lines[anchor:])


def generate_checked(client, cancelled, file_path, **request):
    from .coding_lessons import recall, LESSONS, check_learned_imports
    learned_lessons = []
    request['language_context'] = language_context(request.get('goal', ''), file_path)
    options = getattr(client, 'options', getattr(getattr(client, 'brain', None), 'options', {}))
    trained = (isinstance(options, dict) and options.get('trained_coder_checkpoint') and file_path.suffix.lower() == '.py')
    if file_path.suffix.lower() == '.py' and gui_contract.requested(request.get('goal', '')):
        request['gui_requirements'] = gui_contract.instructions(request['goal'])
        request['use_configured_coder'] = True
        trained = False
    if trained:
        request.pop('coding_lessons', None)
    elif file_path.suffix.lower() == '.py' and isinstance(getattr(client, 'base', None), Path):
        learned_lessons = recall(client.base, request.get('goal', ''), limit=len(LESSONS))
        request.setdefault('coding_lessons', learned_lessons[:5])
    previous, validation_error = "", ""
    for attempt in range(3):
        if cancelled():
            raise ValueError("Coding task cancelled.")
        result = client.request("code_edit", cancelled, **request,
            previous=previous, validation_error=validation_error)
        content = result.get("content") if isinstance(result, dict) else None
        try:
            if isinstance(result, dict) and result.get("replacements"):
                if content:
                    raise ValueError("Return targeted replacements or full content, not both.")
                content = apply_replacements(request.get("current", ""), result["replacements"])
            check_content(file_path, content)
            if file_path.suffix.lower() == '.py':
                check_learned_imports(content, learned_lessons)
                gui_contract.check(content, request.get('goal', ''))
            if file_path.suffix.lower() == ".py" and request.get("current"):
                check_python_interfaces(request["current"], content, request.get("goal", ""))
            return content
        except ValueError as exc:
            if file_path.suffix.lower() == ".py":
                commented = comment_markdown_preamble(content)
                if commented != content:
                    try:
                        check_content(file_path, commented)
                        check_learned_imports(commented, learned_lessons)
                        gui_contract.check(commented, request.get('goal', ''))
                        if request.get("current"):
                            check_python_interfaces(request["current"], commented, request.get("goal", ""))
                        return commented
                    except ValueError:
                        pass
            if attempt == 2:
                raise
            validation_error = str(exc)[:600]
            previous = content[:4000] if isinstance(content, str) else ""
    raise ValueError("The coding model could not generate valid code.")


class Coder:
    def __init__(self, actions, client):
        self.actions, self.client = actions, client

    def run(self, project, goal, cancelled=lambda: False, selected=False):
        from .development_projects import requested
        from .task_graph import MAX_TASK_GOAL_CHARS
        backend=getattr(self.client, 'options', {}).get('coding_backend')
        cli=backend in {'claude-code','codex','jarvis'}
        root = Path(project).resolve(strict=True)
        if not root.is_dir() or root.parent == root or not isinstance(goal, str) or not goal.strip() or len(goal)>(MAX_TASK_GOAL_CHARS if cli else 1200):
            raise ValueError('Name an individual project and a bounded development goal.')
        if not selected and not (has_project_marker(root) or root.parent.name.casefold() == 'phython project'):
            raise ValueError('Choose an individual project folder with a project marker.')
        folder_name = named_folder_request(goal)
        if selected and folder_name and not folder_matches_request(folder_name, root):
            raise ValueError('The selected folder does not match the requested coding folder.')
        if cli and not simple_folder_request(goal):
            if backend=='jarvis':
                from .codex_workload import run as workload_run
                from .native_coding import run as native_run
                return workload_run(self,root,goal,cancelled,executor=native_run,backend='Jarvis')
            if backend=='codex':
                if getattr(self.client,'options',{}).get('codex_workload_enabled',False):
                    from .codex_workload import run as workload_run
                    return workload_run(self,root,goal,cancelled)
                from .codex_code import run as codex_run
                return codex_run(self, root, goal, cancelled)
            from .claude_code import run as claude_run
            return claude_run(self, root, goal, cancelled)
        if requested(root, goal):
            from .development import run
            return run(self, root, goal, cancelled, selected)
        return self._run(root, goal, cancelled, selected)

    def _run(self, project, goal, cancelled=lambda: False, selected=False,
             plan_override=None, staged=False, development_context=None):
        from .task_state import TaskState
        state = getattr(self.actions, "task_state", None)
        def checkpoint(stage, **details):
            if isinstance(state, TaskState):
                state.checkpoint(stage, **details)
        goal = normalize_spoken_code_request(goal)
        current_task = state.snapshot() if isinstance(state, TaskState) else None
        prior = (state.previous(current_task["goal"], current_task["kind"]) if current_task and
                 current_task.get("kind") in {"task", "code_task"} else None)
        project = Path(project).resolve(strict=True)
        if not project.is_dir() or not goal.strip() or len(goal) > 1200:
            raise ValueError("Name a project and a specific coding goal.")
        if project.parent == project or (not selected and not (has_project_marker(project)
                or project.parent.name.casefold() == "phython project")):
            raise ValueError("Choose an individual project folder with a project marker; Jarvis will not code in a drive or parent folder.")
        requested_folder = named_folder_request(goal)
        if selected and requested_folder and not folder_matches_request(requested_folder, project):
            raise ValueError(f"The selected File Explorer folder is {project.name}, not {requested_folder}.")
        files = project_files(project)
        if isinstance(state, TaskState):
            state.set_project(project)
            from .experience_memory import observe_conditions
            state.set_conditions(observe_conditions(self.actions, project=project))
        checkpoint("inspecting_project", target=project, evidence=f"{len(files)} source files found")
        self.actions.report("screen", f"Open File Explorer folder: {project}; files: "
                            + (", ".join(files[:30]) if files else "no source files"))
        self.actions.report("brain", f"Inspecting {project.name} for coding task")
        simple_folder = simple_folder_request(goal)
        named_files = {match.group(0).casefold() for match in re.finditer(
            r"\b[a-z][\w-]{0,80}\.(?:" + SOURCE_PATTERN + r")\b", goal, re.I)}
        explicit_paths = {match.group(0).replace("\\", "/").casefold() for match in re.finditer(
            r"\b(?:[a-z0-9_-]+[/\\]){1,3}[a-z][\w-]{0,80}\.(?:" + SOURCE_PATTERN + r")\b", goal, re.I)}
        edit_request = bool(re.search(r"\b(?:modify|edit|update|fix|refactor|change|add)\b", goal, re.I))
        existing_named = [name for name in files if Path(name).name.casefold() in named_files]
        if explicit_paths:
            existing_named = [name for name in existing_named if name.casefold() in explicit_paths
                              or not any(Path(explicit).name.casefold() == Path(name).name.casefold() for explicit in explicit_paths)]
        if edit_request and not named_files and gui_contract.requested(goal):
            candidates = [name for name in files if name.lower().endswith('.py')]
            # A follow-up may use the last checked coding target only in this same project.
            history = state.data.get('history', []) if isinstance(state, TaskState) else []
            remembered = []
            for task in reversed(history):
                if task.get('project') != str(project):
                    continue
                for point in task.get('checkpoints', []):
                    if point.get('stage') in {'wrote_file', 'observed_file', 'generated_file'}:
                        target = Path(point.get('target', ''))
                        if target.is_absolute() and target.is_relative_to(project):
                            relative = target.relative_to(project).as_posix()
                            if relative in candidates and relative not in remembered:
                                remembered.append(relative)
                if remembered:
                    break
            chosen = remembered if len(remembered) == 1 else candidates
            if len(chosen) != 1:
                from .clarification import TaskClarification
                raise TaskClarification('Which Python script should get the UI? ' + ', '.join(candidates[:20]), 'file')
            existing_named = chosen
            named_files = {Path(chosen[0]).name.casefold()}
        if not staged and edit_request and len(named_files) == 1 and not existing_named:
            raise ValueError(f"{next(iter(named_files))} is not in the open folder {project.name}. "
                             "Available source files: " + (", ".join(files[:30]) if files else "none"))
        if not staged and edit_request and len(named_files) == 1 and len(existing_named) > 1:
            raise ValueError("That filename appears in multiple subfolders of " + project.name + ": "
                             + ", ".join(existing_named))
        direct_edit = len(named_files) == 1 and len(existing_named) == 1 and edit_request
        direct_new = single_python_target(goal) if not edit_request else None
        from .code_stream import CodeDraft, owned_draft
        runtime_base = getattr(self.actions, 'base', None)
        runtime_base = runtime_base if isinstance(runtime_base, Path) else project
        if direct_new and (project / direct_new).exists() and not owned_draft(runtime_base, project / direct_new) and (project / direct_new).read_text(encoding='utf-8').replace('\r\n', '\n') != draft_content(project / direct_new):
            raise ValueError(f'{direct_new} already exists; ask to edit it instead of creating it again. No existing code was overwritten.')
        context = related_context(project, files, goal, existing_named)
        runtime_context = coding_context(project, goal, files=files)
        runtime_context["skill_project"] = str(project)
        runtime_context.update(development_context or {})
        if plan_override is not None:
            plan = plan_override
        else:
            plan = ({"directories": [simple_folder], "files": []} if simple_folder else
                    {"directories": [], "files": [{"path": existing_named[0], "reason": goal[:160]}]}
                    if direct_edit else
                    {'directories': [], 'files': [{'path': direct_new, 'reason': goal[:160]}]}
                    if direct_new else
                    self.client.request("code_plan", cancelled, goal=goal, project=project.name, files=files,
                                        prior_task=prior, references=context, **runtime_context))
        if isinstance(plan, dict) and isinstance(plan.get("directories", []), list) and isinstance(plan.get("files"), list):
            plan = {**plan, "directories": [strip_project_prefix(name, project) for name in plan.get("directories", [])],
                "files": [{**step, "path": strip_project_prefix(step.get("path"), project)} if isinstance(step, dict) else step
                          for step in plan["files"]]}
        self.actions.report("plan", json.dumps(plan, ensure_ascii=False)[:1000])
        checkpoint("coding_plan", evidence="; ".join(step.get("path", "") for step in plan.get("files", []) if isinstance(step, dict)))
        steps = plan.get("files") if isinstance(plan, dict) else None
        directories = plan.get("directories", []) if isinstance(plan, dict) else None
        if (not isinstance(steps, list) or not isinstance(directories, list)
                or not 1 <= len(steps) + len(directories) <= (15 if staged else 6)
                or len(steps) > 3 or len(directories) > (12 if staged else 3)):
            raise ValueError("Coding plan must name up to three files and three folders.")
        planned_dirs = []
        for name in directories:
            relative = relative_parts(name, directory=True)
            folder = project.joinpath(*relative.parts)
            if folder in planned_dirs:
                raise ValueError("Coding plan repeated a folder.")
            if folder.is_symlink() or not folder.resolve().is_relative_to(project) or (folder.exists() and not folder.is_dir()):
                raise ValueError("Coding plan named an unsafe folder.")
            planned_dirs.append(folder)
        planned_dirs.sort(key=lambda path: len(path.relative_to(project).parts))
        required_folder = requested_new_folder(goal)
        if required_folder and not (project / required_folder).is_dir() and not any(
                folder.name.casefold() == required_folder.casefold() for folder in planned_dirs):
            raise ValueError(f"The coding plan omitted the requested {required_folder} folder.")
        for folder in planned_dirs:
            if not folder.parent.is_dir() and folder.parent not in planned_dirs:
                raise ValueError("A nested folder needs an existing or planned parent folder.")
        prepared = []
        seen = set()
        sources = []
        for step in steps:
            if cancelled():
                raise ValueError("Coding task cancelled.")
            if not isinstance(step, dict) or not isinstance(step.get("path"), str) or not isinstance(step.get("reason"), str):
                raise ValueError("Coding plan contains an invalid file step.")
            path = target_path(project, step["path"], planned_dirs)
            if path in seen:
                raise ValueError("Coding plan repeated a file.")
            seen.add(path)
            limit = 80000 if owned_draft(runtime_base, path) else 14000
            if path.exists() and (not path.is_file() or path.stat().st_size > limit):
                raise ValueError(f"{path.name} is not a small text file that Jarvis can safely edit.")
            original = path.read_bytes() if path.exists() else None
            try:
                current = original.decode("utf-8") if original is not None else ""
            except UnicodeDecodeError as exc:
                raise ValueError(f"{path.name} is not UTF-8 text.") from exc
            if current.replace("\r\n", "\n") == draft_content(path) or owned_draft(runtime_base, path):
                current = ""  # Resume a draft created by Jarvis on an earlier attempt.
            sources.append((step, path, original, current))
        selected_names = {path.name.casefold() for _, path, _, _ in sources}
        if not staged and not named_files <= selected_names:
            raise ValueError("The coding plan omitted a file you named: " + ", ".join(sorted(named_files - selected_names)))
        # Resolve all target guidance before creating any folders or draft files.
        target_contexts = {step['path']: {**coding_context(project, goal, step['path'], files), **(development_context or {}), "skill_project": str(project)}
                           for step, _, _, _ in sources}
        created_dirs = []
        for folder in planned_dirs:
            if cancelled():
                raise ValueError("Coding task cancelled before creating folders.")
            if not folder.exists():
                folder.mkdir()
                if folder.is_symlink() or not folder.is_dir():
                    raise ValueError(f"Could not observe the created folder {folder}.")
                created_dirs.append(folder.relative_to(project).as_posix())
                checkpoint("created_folder", target=folder)
                checkpoint("observed_folder", target=folder, evidence="folder exists")
                self.actions.report("action", f"Created folder {folder}")
        refreshed = []
        generated_context = []
        streams = []
        context = {**context, **{item["path"]: text for item, _, _, text in sources}}
        for step, path, original, current in sources:
            if original is None:
                if cancelled():
                    raise ValueError("Coding task cancelled; created folders remain.")
                with path.open("x", encoding="utf-8") as output:
                    output.write(draft_content(path))
                original = path.read_bytes()
                if path.read_text(encoding="utf-8") != draft_content(path):
                    raise ValueError(f"Could not observe the new draft {path}.")
                self.actions.report("action", f"Created draft {path}")
                checkpoint("created_draft", target=path)
                checkpoint("observed_draft", target=path, evidence="draft read back from disk")
            refreshed.append((step, path, original, current))
        sources = refreshed
        if not sources:
            return "Created folders in " + str(project) + ": " + ", ".join(created_dirs or ["already existed"])
        for step, path, original, current in sources:
            if cancelled():
                raise ValueError("Coding task cancelled.")
            self.actions.report("plan", f"{step['path']}: {step['reason'][:160]}")
            model_options = getattr(self.client, 'options', {})
            model_name = model_options.get('coder', model_options.get('planner', 'Local coder')) if isinstance(model_options, dict) else 'Local coder'
            self.actions.report('brain', str(model_name) + ' is generating ' + step['path'] + '; local inference may take several minutes. Stop remains available.')
            stream = CodeDraft(runtime_base, path, original, not current, draft_content(path), cancelled, self.actions.report)
            streams.append(stream)
            references = bounded_references(context, step["path"], generated_context)
            content = generate_checked(self.client, cancelled, path, goal=goal,
                       project=project.name, path=step["path"], reason=step["reason"], current=current,
                       _on_code=stream.write,
                       plan=steps, files=files[:100], references=references, prior_task=prior,
                       **target_contexts[step['path']])
            from .progress import status
            status(self.actions.report, 'Validating code', path)
            check_content(path, content)
            if stream.new_file:
                original = stream.expected
            generated_context.append((step["path"], content))
            checkpoint("generated_file", target=path, evidence="syntax checked where applicable")
            if current and len(current) > 1000 and len(content) < len(current) * .6 \
                    and not any(word in goal.casefold() for word in ("rewrite", "replace entire", "simplify", "remove most")):
                raise ValueError(f"Generated {path.name} removed too much existing code; no files were written.")
            if current == content:
                continue
            prepared.append((path, original, content))
        if not prepared:
            for stream in streams:
                try:
                    stream.complete()
                except (OSError, ValueError) as exc:
                    self.actions.report('warning', 'Streaming metadata needs repair: ' + str(exc))
            return ("Created folders: " + ", ".join(created_dirs) if created_dirs
                    else "The coding model proposed no file changes.")
        if cancelled():
            raise ValueError("Coding task cancelled before any files changed.")
        # Generate and validate every file before touching the project. Then guard against
        # intervening edits and write each file using a same-folder atomic replacement.
        for path, original, _ in prepared:
            if (path.read_bytes() if path.exists() else None) != original:
                raise ValueError(f"{path.name} changed while Jarvis was planning; no files were written.")
        if isinstance(state, TaskState):
            review = save_change_review(project, prepared, state.base)
            checkpoint("coding_review", target=review, evidence="original bytes and proposed diff preserved before file replacement")
            self.actions.report("coding_review", "Saved coding backup and proposed changes: " + str(review))
        written = []
        for path, original, content in prepared:
            if cancelled():
                break
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=path.parent,
                        prefix=".jarvis-code-", delete=False) as output:
                    temporary = Path(output.name)
                    output.write(content)
                if original is None:
                    os.link(temporary, path)  # Fails if another process created the new file.
                    temporary.unlink()
                else:
                    if not path.exists() or path.read_bytes() != original:
                        raise ValueError(f"{path.name} changed while Jarvis was writing it.")
                    checkpoint("action_attempted", action="modify_file", target=path,
                               evidence="Atomic replacement beginning; inspect fresh disk state after interruption")
                    os.replace(temporary, path)
                temporary = None
                with path.open("r", encoding="utf-8", newline="") as observed:
                    actual = observed.read()
                if actual != content:
                    raise ValueError(f"The updated file {path.name} did not match the generated content.")
                written.append(path.relative_to(project).as_posix())
                checkpoint("wrote_file", target=path, evidence="atomic write completed")
                checkpoint("observed_file", target=path, evidence="updated content read back from disk")
                status(self.actions.report, 'File saved', path, file=str(path), preview=content[:1600], characters=len(content),
                       outcome=evidence_label(path))
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        if len(written) != len(prepared):
            return "Coding task stopped after changing: " + ", ".join(written)
        self.actions.report("brain", "Changed " + ", ".join(written))
        for stream in streams:
            try:
                stream.complete()
            except (OSError, ValueError) as exc:
                self.actions.report('warning', 'Code was written; streaming metadata needs repair: ' + str(exc))
        checkpoint("development_batch_saved" if staged else "goal_verified", source='disk_readback', evidence="All proposed file changes read back from disk; Python/JSON syntax checked where applicable. Functional behavior is not verified.")
        made = ("Created folders " + ", ".join(created_dirs) + "; ") if created_dirs else ""
        ui_checked = ' Requested Python GUI structure checked; runtime behavior still needs testing.' if gui_contract.requested(goal) and any(path.suffix.lower() == '.py' for path, _, _ in prepared) else ''
        return f"Updated {project.name}: " + made + ", ".join(written) + ". Language syntax parsed where supported." + ui_checked + " Build and test the project to verify its behavior."
