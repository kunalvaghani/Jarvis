"""Conservative source checks for explicitly requested Python graphical interfaces.

These are structural checks, not a claim that arbitrary user code ran successfully.
"""
import ast
import re


def requested(goal):
    # A complaint such as "there was no UI; add UI again" is a positive request.
    positive = re.search(r'\b(?:add|implement|build|create|make)\s+(?:(?:a|the|working|graphical)\s+)*(?:ui|gui|user interface)\b', goal, re.I)
    if re.search(r'\b(?:do not|don.t|never)\s+(?:add|create|implement)\s+(?:a |the )?(?:ui|gui)\b', goal, re.I):
        return False
    if not positive and re.search(r'\b(?:no|without|remove|delete)\s+(?:the\s+)?(?:ui|gui|graphical interface)\b', goal, re.I):
        return False
    if re.search(r'\b(?:terminal|console|command.line|text)\s+(?:ui|interface)\b', goal, re.I):
        return False
    return bool(re.search(r'\b(?:ui|gui|graphical|tkinter|pyside\w*|pyqt\w*|wxpython|kivy|user interface)\b', goal, re.I))


def instructions(goal):
    if not requested(goal):
        return ''
    return ('The user requests a working graphical UI, not a console-only program or placeholder. '
            'Edit the supplied current source and preserve its calculations and unrelated interfaces. '
            'Use the existing or explicitly requested GUI framework; if none is specified, use standard-library Tkinter/ttk. '
            'Provide a reachable launch entry point, visible laid-out controls, inputs appropriate to the task, '
            'and real event callbacks connected to existing functionality with visible results/errors. '
            'Running this script normally must open the UI and enter its event loop. Return the complete updated source.')


def check(content, goal, sources=None, entry_module='__entry__'):
    if not requested(goal):
        return
    trees={module:ast.parse(text) for module,text in (sources or {}).items()}
    trees[entry_module]=ast.parse(content)
    aliases_by_module={}
    definitions={}
    for module,tree in trees.items():
        aliases=aliases_by_module[module]={}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for item in node.names:
                    aliases[item.asname or item.name.split('.')[0]] = item.name if item.asname else item.name.split('.')[0]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported='.'.join(module.split('.')[:-node.level]+[node.module]) if node.level else node.module
                for item in node.names:
                    aliases[item.asname or item.name] = imported + '.' + item.name
                    if item.name == '*' and imported == 'tkinter':
                        for widget in ('Tk', 'Toplevel', 'Button', 'Entry', 'Text', 'Label', 'Scale', 'Checkbutton', 'Spinbox'):
                            aliases.setdefault(widget, 'tkinter.' + widget)
        definitions.update({module+'.'+node.name:(node,module) for node in tree.body
                            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))})

    def name(node,module):
        if isinstance(node, ast.Name):
            return aliases_by_module[module].get(node.id,module+'.'+node.id if module+'.'+node.id in definitions else node.id)
        if isinstance(node, ast.Attribute):
            return name(node.value,module) + '.' + node.attr
        return ''

    # Ignore never-called function/class placeholders and literal dead branches.
    reachable, seen = [], set()
    imported_modules={entry_module}
    def statements(module):
        return [(node,module) for node in trees[module].body if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]
    pending=statements(entry_module)
    while pending:
        node,module = pending.pop()
        if isinstance(node, ast.If) and isinstance(node.test, ast.Constant) and not node.test.value:
            pending.extend((child,module) for child in node.orelse)
            continue
        reachable.append((node,module))
        imports=[]
        if isinstance(node,ast.Import):imports=[a.name for a in node.names]
        elif isinstance(node,ast.ImportFrom) and node.module:
            imports=['.'.join(module.split('.')[:-node.level]+[node.module]) if node.level else node.module]
        for imported in imports:
            if imported in trees and imported not in imported_modules:
                imported_modules.add(imported);pending.extend(statements(imported))
        if isinstance(node, ast.Call):
            target = name(node.func,module)
            if target in definitions and target not in seen:
                seen.add(target)
                definition,owner=definitions[target]
                pending.extend((child,owner) for child in definition.body)
        pending.extend((child,module) for child in ast.iter_child_nodes(node))
    calls = [(node,module) for node,module in reachable if isinstance(node, ast.Call)]
    called = [name(node.func,module) for node,module in calls]
    gui_imports = any(value.startswith(('tkinter', 'PySide', 'PyQt', 'wx', 'kivy', 'streamlit', 'gradio'))
                      for module in imported_modules for value in aliases_by_module[module].values())
    launch = any(value.endswith(('.Tk', '.QApplication', '.App', '.Blocks', '.Interface')) for value in called)
    launch = launch or any(target in called and any(name(base,module).endswith(('.Tk', '.App', '.QApplication'))
                           for base in node.bases) for target,(node,module) in definitions.items() if isinstance(node, ast.ClassDef))
    loop = any(value.endswith(('.mainloop', '.exec', '.exec_', '.MainLoop', '.run', '.launch')) for value in called)
    widgets = any(value.rsplit('.', 1)[-1] in {'Button', 'Entry', 'Text', 'Scale', 'Checkbutton', 'Combobox',
                  'QPushButton', 'QLineEdit', 'QTextEdit', 'TextCtrl', 'TextInput', 'Textbox', 'Slider'} for value in called)
    binding = any((node.func.attr in {'connect', 'bind', 'Bind', 'click'} if isinstance(node.func, ast.Attribute) else False)
                  or any(k.arg == 'command' and not isinstance(k.value, ast.Constant)
                         and not (isinstance(k.value, ast.Lambda) and isinstance(k.value.body, ast.Constant))
                         for k in node.keywords)
                  for node,module in calls)
    layout = any(value.endswith(('.pack', '.grid', '.place', '.show', '.addWidget', '.setLayout', '.SetSizer')) for value in called)
    binding = binding or any(isinstance(node, ast.Assign) and not isinstance(node.value, ast.Constant)
                             and any(isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant)
                                     and target.slice.value == 'command' for target in node.targets) for node,module in reachable)
    # Streamlit uses a rerun model rather than an explicit desktop event loop.
    if any(value.startswith('streamlit.') for value in called):
        launch = loop = True
        layout = True
        widgets = any(value.endswith(('.button', '.text_input', '.number_input', '.selectbox')) for value in called)
        binding = any(isinstance(node, ast.If) and any(isinstance(child, ast.Call)
                      and name(child.func,module).endswith('.button') for child in ast.walk(node.test)) for node,module in reachable)
    if not (gui_imports and launch and loop and widgets and binding and layout):
        missing = [label for label, okay in (('GUI imports', gui_imports), ('reachable window/app launch', launch),
                   ('event loop', loop), ('interactive controls', widgets), ('connected callbacks', binding), ('visible layout', layout)) if not okay]
        raise ValueError('Requested graphical UI is missing: ' + ', '.join(missing) +
                         '. Preserve current source and implement a working UI, not console code or launch_ui(): pass.')
