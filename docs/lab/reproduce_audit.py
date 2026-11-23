"""Read source declarations without starting Jarvis; optionally write public audit evidence.

From the repository root: app/.venv/Scripts/python.exe -B docs/lab/reproduce_audit.py --write
No private memory, credentials, live tool calls, model calls, or service startup.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
sys.dont_write_bytecode = True
sys.path.insert(0, str(APP))


def deny_effects(event, args):
    if event in {"socket.connect", "socket.connect_ex", "socket.bind", "socket.sendto",
                 "subprocess.Popen", "os.system", "os.startfile"}:
        raise PermissionError("Static Lab audit refuses network/process effects: " + event)


def version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def source_index():
    """Public definitions are review candidates, not automatically user-facing capabilities."""
    rows, errors = [], []
    for path in sorted((APP / "jarvis").rglob("*.py")):
        if "_vendor" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except (OSError, SyntaxError, UnicodeError) as exc:
            errors.append({"path": path.relative_to(ROOT).as_posix(), "error": type(exc).__name__})
            continue
        definitions = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
                row = {"name": node.name, "line": node.lineno, "kind": type(node).__name__}
                if isinstance(node, ast.ClassDef):
                    row["methods"] = [{"name": n.name, "line": n.lineno} for n in node.body
                                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                                      and not n.name.startswith("_")]
                else:
                    row["arguments"] = [a.arg for a in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)]
                definitions.append(row)
        rows.append({"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "definitions": definitions})
    return {"scope": "app/jarvis Python source excluding _vendor; public definitions are not capability claims",
            "modules": rows, "errors": errors}


def collect():
    from jarvis.neural.registry import Registry
    from jarvis.neural.graph import CapabilityGraph
    from jarvis.tools import SPECS
    from jarvis.execution_strategy import METHODS
    from jarvis.blender_host import catalog
    from jarvis.blender_installation import executables
    from jarvis import capabilities, flags
    import psutil

    registry = Registry().refresh()  # No Journal: never opens the production brain database.
    graph = CapabilityGraph.from_registry(registry)
    config = json.loads((APP / "config/config.json").read_text(encoding="utf-8"))
    routes = {name: {"pattern": row[0], "tools": list(row[1]), "skills": list(row[2])}
              for name, row in capabilities.ROUTES.items()}
    tools = [{"name": s.name, "backend": s.backend, "approval": s.approval,
              "description": s.description, "neuron": registry.by_tool(s.name).node_id if registry.by_tool(s.name) else None}
             for s in SPECS]
    blender = catalog()
    for row in blender:
        row["direct_neurons"] = [n.node_id for n in registry.nodes.values()
                                 if n.node_id == "tool." + row["tool"] + "@v1"
                                 or n.capability == "blender." + row["tool"]]
    skills = [{"path": p.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
              for folder in (APP / "skills", APP / "custom-skills") for p in sorted(folder.glob("*/SKILL.md"))]
    public = {
        "date_local": "2026-11-04 Asia/Calcutta",
        "scope": "Fresh source-derived metadata; registration is not runtime eligibility or live acceptance",
        "registry": registry.summary(), "synapses": len(graph.synapses),
        "tool_specs": len(tools), "methods": len(METHODS),
        "missing_tool_spec_neurons": [t["name"] for t in tools if t["neuron"] is None],
        "backend_counts": dict(sorted(Counter(t["backend"] for t in tools).items())),
        "flags": flags.summary(config), "bundled_or_custom_skills": len(skills),
        "blender_catalog_tools": len(blender),
        "blender_catalog_without_direct_neuron": sum(not row["direct_neurons"] for row in blender),
        "blender_executables": [str(p) for p in executables()],
        "python": platform.python_version(),
        "ram_total_bytes": psutil.virtual_memory().total,
        "ram_available_bytes": psutil.virtual_memory().available,
        "disk_free_bytes": shutil.disk_usage(ROOT).free,
        "path_executables": {n: shutil.which(n) for n in ("uv", "pixi", "conda", "wsl", "blender", "FreeCAD", "kicad-cli", "ngspice", "verilator")},
        "core_environment_packages": {n: version(n) for n in ("pytest", "pydantic", "rustworkx", "numpy", "scipy", "sympy", "pint", "mujoco", "pychrono", "pyvista", "optuna", "paper-qa", "cadquery", "cocotb")},
        "spec_sha256": hashlib.sha256((ROOT / "docs/specs/JARVIS_Universal_Discovery_Lab_v2.md").read_bytes()).hexdigest(),
    }
    return {"summary.json": public, "registry.json": graph.snapshot(), "tool_specs.json": tools,
            "intent_routes.json": routes, "blender_catalog.json": blender, "skills.json": skills,
            "source_index.json": source_index()}


def markdown_inventory(data):
    rows = ["# Neuron inventory", "", "2026-11-04 IST. Generated by [reproduce_audit.py](reproduce_audit.py).",
            "", "Source declarations, not live tests. `active` means registered; policy may still deny execution.",
            "Inputs/outputs are declared ports; generic Text ports do not establish a fully typed adapter.",
            "No per-neuron intent list or golden-test field exists in the current Neuron schema.",
            "Existing category matchers are retained in [intent_routes.json](evidence/intent_routes.json).",
            "No Lab neurons were added and no production memory was opened.", "",
            "| Neuron | Capability / entry point | Inputs → outputs | Requirements | Status / effect |",
            "|---|---|---|---|---|"]
    for n in data["registry.json"]["neurons"]:
        ports = lambda items: ", ".join(p["name"] + ":" + p["type"] for p in items) or "none"
        fields = [n["node_id"], n["capability"] + " / " + n["provider"],
                  ports(n["inputs"]) + " → " + ports(n["outputs"]), ", ".join(n["requirements"]) or "none declared",
                  n["status"] + " / " + n["side_effect_class"]]
        rows.append("| " + " | ".join(str(v).replace("|", "\\|").replace("\n", " ") for v in fields) + " |")
    rows += ["", "## Existing capabilities without direct neurons", "",
             "Every ToolSpec is covered in this snapshot. This is coverage of declared tools, not every capability in the repository.",
             "The separate Blender connector catalog has 203 tools with no individual neuron in this configured registry.",
             "Blender has seven existing aggregate/method/route/verifier neurons; its optional 203-tool MCP registration is absent.",
             "Activation is a separate approval gate; do not enable it to inflate coverage.",
             "See [the complete connector catalog](evidence/blender_catalog.json).", "",
             "[source_index.json](evidence/source_index.json) indexes all public definitions in app/jarvis except _vendor.",
             "Helpers, workers and implementation methods are not automatically executable capabilities. Review each candidate's",
             "callers, permissions and tests before deciding whether it needs a wrapper neuron. Exhaustive semantic coverage remains open.",
             "Other deferred candidates include repository-skill operations, individual loaded procedures, numerical libraries,",
             "background awareness/knowledge workers and connector operations exposed only through aggregate entry points.",
             "A source definition alone never grants execution permission."]
    return "\n".join(rows) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write sanitized evidence under docs/lab/evidence")
    args = parser.parse_args()
    sys.addaudithook(deny_effects)
    data = collect()
    if args.write:
        out = Path(__file__).resolve().parent / "evidence"
        out.mkdir(exist_ok=True)
        for name, body in data.items():
            (out / name).write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (out.parent / "NEURON_INVENTORY.md").write_text(markdown_inventory(data), encoding="utf-8")
    print(json.dumps(data["summary.json"], indent=2))


if __name__ == "__main__":
    main()
