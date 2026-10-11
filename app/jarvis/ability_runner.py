"""Runs one learned ability in its own Python process (see repo_abilities.py).

Standalone on purpose: standard library only and no Jarvis imports, because it runs with the ability's own
interpreter (`python -I -B ability_runner.py request.json`). Jarvis never imports generated or repository code.

Before the ability loads, an audit hook refuses:
* new processes (subprocess, os.system, os.startfile, CreateProcess, os.kill);
* writing, deleting, renaming or creating folders outside the run folder and the ability's own home folder;
* reading files outside Python, the ability, its home, the run folder and Windows' own folders (fonts, DLLs);
* registry writes;
* network connections, unless the ability was approved for network use.

These are guard rails against mistakes in generated code, not a security boundary: native extensions can step
around audit hooks. That is why abilities that install third-party packages, run repository code or use the
network need the user's approval first, and why generated code is statically checked before it ever runs.
"""
import importlib.util
import json
import os
import sys
import time
import traceback

PROCESS_EVENTS = {"subprocess.Popen", "os.system", "os.exec", "os.spawn", "os.posix_spawn", "os.startfile",
                  "_winapi.CreateProcess", "os.kill", "os.fork", "os.forkpty", "pty.spawn"}
NETWORK_EVENTS = {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "socket.sendto", "socket.bind"}
PATH_EVENTS = {"os.remove": (0,), "os.rmdir": (0,), "os.rename": (0, 1), "shutil.rmtree": (0,), "os.mkdir": (0,),
               "os.chmod": (0,), "os.truncate": (0,), "os.link": (0, 1), "os.symlink": (0, 1), "os.utime": (0,),
               "shutil.copyfile": (1,), "shutil.move": (0, 1), "shutil.copytree": (1,)}
WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC


class Refused(PermissionError):
    pass


def real(path):
    if isinstance(path, int):
        return None
    try:
        path = os.fspath(path)
    except TypeError:
        return None
    if isinstance(path, bytes):
        path = path.decode("utf-8", "replace")
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def inside(path, roots):
    return path is not None and any(path == root or path.startswith(root.rstrip("\\/") + os.sep) for root in roots)


def guard(writable, readable, network):
    writable = [real(p) for p in writable]
    readable = [real(p) for p in readable] + writable

    def hook(event, args):
        if event in PROCESS_EVENTS:
            raise Refused("Learned abilities may not start other programs (" + event + ").")
        if event in NETWORK_EVENTS and not network:
            raise Refused("This ability was not approved for network use.")
        if event.startswith("winreg.") and any(word in event for word in ("Create", "Delete", "Set", "Save", "Load")):
            raise Refused("Learned abilities may not change the Windows registry.")
        if event == "open" and args:
            path = real(args[0])
            if path is None:
                return
            mode = args[1] if len(args) > 1 else None
            flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
            writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or bool(flags & WRITE_FLAGS)
            if writing and not inside(path, writable):
                raise Refused("Learned abilities may only write inside their run folder: " + str(args[0])[:200])
            if not writing and not inside(path, readable):
                raise Refused("Learned abilities may only read their inputs and their own files: " + str(args[0])[:200])
        elif event in PATH_EVENTS:
            for index in PATH_EVENTS[event]:
                if index < len(args) and not inside(real(args[index]), writable):
                    raise Refused("Learned abilities may only change files inside their run folder (" + event + ").")

    sys.addaudithook(hook)


def main(request_path):
    with open(request_path, encoding="utf-8") as handle:
        request = json.load(handle)
    work = os.path.realpath(request["workdir"])
    output = os.path.join(work, "result.json")
    started = time.time()

    def finish(data):
        data["seconds"] = round(time.time() - started, 2)
        with open(output, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)

    ability_dir = request["ability_dir"]
    windows = os.environ.get("SYSTEMROOT") or os.environ.get("WINDIR") or "C:\\Windows"
    python_dirs = {sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix, os.path.dirname(sys.executable)}
    readable = [ability_dir, windows] + sorted(python_dirs) + list(request.get("readable", []))
    writable = [work] + list(request.get("writable", []))
    for folder in writable:
        os.makedirs(folder, exist_ok=True)
    repo = request.get("repo_dir") or ""
    sys.path[:0] = [ability_dir] + ([os.path.join(repo, sub) for sub in ("src", "lib") if os.path.isdir(os.path.join(repo, sub))]
                                    + [repo] if repo else [])
    os.chdir(work)
    guard(writable, readable, bool(request.get("network")))
    try:
        spec = importlib.util.spec_from_file_location("jarvis_learned_ability", os.path.join(ability_dir, "ability.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if request.get("mode") == "test":
            inputs = module.sample_inputs(work)
            if not isinstance(inputs, dict):
                raise TypeError("sample_inputs() must return a dict of inputs.")
        else:
            inputs = request.get("inputs") or {}
        result = module.run(inputs, work)
        if isinstance(result, str):
            result = {"text": result}
        if not isinstance(result, dict):
            raise TypeError("run() must return a dict with 'text' and/or 'files'.")
        text = result.get("text") or ""
        if not isinstance(text, str):
            text = json.dumps(text, ensure_ascii=False, default=str)
        files = []
        for item in result.get("files") or []:
            path = real(os.path.join(work, os.fspath(item)))
            if not inside(path, [real(work)]) or not os.path.isfile(path):
                raise ValueError("run() returned a file that is missing or outside the run folder: " + str(item)[:200])
            files.append(os.path.relpath(path, real(work)))
        if not text.strip() and not files:
            raise ValueError("run() returned no text and no files.")
        finish({"ok": True, "text": text[:6000], "files": files[:20],
                "inputs": json.loads(json.dumps(inputs, default=str))})
    except BaseException as exc:  # Report everything (including SystemExit) to Jarvis instead of crashing silently.
        finish({"ok": False, "error": (type(exc).__name__ + ": " + str(exc))[:600],
                "trace": traceback.format_exc()[-3000:]})


if __name__ == "__main__":
    main(sys.argv[1])
