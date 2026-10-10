"""Reviewed upstream execution primitives, adapted to Jarvis's existing worker.

Source revisions, licenses and modifications: integrations/execution-primitives/.
These are small ports/adaptations, not installations of the five agent frameworks.
All preparation is read-only. A prepared callback may be dispatched exactly once.
"""
from dataclasses import dataclass


class Unsupported(Exception):
    """No external input has been issued; another provider may prepare."""


@dataclass
class Prepared:
    call: object
    read: object = None
    expected: object = None
    before: object = None
    no_op: bool = False


def pattern(element, name):
    from pywinauto.uia_defines import NoPatternInterfaceError
    try:
        return getattr(element, 'iface_' + name)
    except NoPatternInterfaceError as exc:
        raise Unsupported('UIA ' + name + ' is unavailable') from exc


def selection(element, control, verb):
    role = control['role']
    if role == 'CheckBox':
        interface = pattern(element, 'toggle')
        before = int(interface.CurrentToggleState)
        no_op = verb == 'select' and before == 1
        expected = 1 if verb == 'select' else (0 if before == 1 else 1)
        return Prepared(interface.Toggle, lambda: int(interface.CurrentToggleState), expected, before, no_op)
    if role == 'ComboBox':
        interface = pattern(element, 'expand_collapse')
        before = int(interface.CurrentExpandCollapseState)
        return Prepared(interface.Expand, lambda: int(interface.CurrentExpandCollapseState), 1, before, before == 1)
    if role in {'TabItem', 'ListItem', 'DataItem', 'TreeItem', 'RadioButton'}:
        try:
            interface = pattern(element, 'selection_item')
        except Unsupported:
            return Prepared(pattern(element, 'invoke').Invoke)
        before = bool(interface.CurrentIsSelected)
        return Prepared(interface.Select, lambda: bool(interface.CurrentIsSelected), True, before, before)
    interface = pattern(element, 'invoke')
    return Prepared(interface.Invoke)


class UFO:
    """ControlReceiver.atomic_execution/set_edit_text pattern, without swallowed errors/replays."""
    name = 'ufo'

    def prepare(self, element, control, request, window):
        operation = request['operation']
        if operation == 'activate':
            # UFO's receiver invokes one explicitly selected wrapper method.
            # Resolve the pattern before calling; no coordinate guesses.
            return selection(element, control, request.get('verb', 'click'))
        if operation == 'fill_text':
            interface = pattern(element, 'value')
            before = interface.CurrentValue
            content = request['content']
            return Prepared(lambda: interface.SetValue(content), lambda: interface.CurrentValue,
                            content, before, before == content)
        if operation == 'open_menu':
            try:
                interface = pattern(element, 'expand_collapse')
            except Unsupported:
                interface = pattern(element, 'invoke')
                return Prepared(interface.Invoke)
            before = int(interface.CurrentExpandCollapseState)
            return Prepared(interface.Expand, lambda: int(interface.CurrentExpandCollapseState), 1, before, before == 1)
        if operation == 'shortcut':
            from .desktop_actions import SHORTCUTS, shortcut_key
            keys = SHORTCUTS[shortcut_key(request['value'])]
            # UFO ControlReceiver.keyboard_input uses application.type_keys.
            return Prepared(lambda: window.type_keys(keys, set_foreground=False, pause=.02))
        raise Unsupported('No reviewed UFO primitive for ' + operation)


_windows_patterns = None


def windows_patterns():
    global _windows_patterns
    if _windows_patterns is None:
        from . import upstream_windows_patterns as module
        _windows_patterns = module
    return _windows_patterns


class WindowsMCP:
    """Use the actual vendored Windows-MCP UIA pattern wrappers."""
    name = 'windows-mcp'

    def prepare(self, element, control, request, window):
        module = windows_patterns()
        operation = request['operation']
        if operation == 'fill_text':
            interface = module.ValuePattern(pattern(element, 'value'))
            before, content = interface.Value, request['content']
            return Prepared(lambda: interface.SetValue(content, waitTime=0), lambda: interface.Value,
                            content, before, before == content)
        if operation in {'activate', 'open_menu'}:
            if operation == 'open_menu':
                try:
                    raw = pattern(element, 'expand_collapse')
                except Unsupported:
                    wrapped = module.InvokePattern(pattern(element, 'invoke'))
                    return Prepared(lambda: wrapped.Invoke(waitTime=0))
                wrapped = module.ExpandCollapsePattern(raw)
                before = int(raw.CurrentExpandCollapseState)
                return Prepared(lambda: wrapped.Expand(waitTime=0), lambda: int(raw.CurrentExpandCollapseState),
                                1, before, before == 1)
            base = selection(element, control, request.get('verb', 'click'))
            role = control['role']
            if role == 'ComboBox':
                wrapped = module.ExpandCollapsePattern(pattern(element, 'expand_collapse'))
                base.call = lambda: wrapped.Expand(waitTime=0)
            elif role == 'CheckBox':
                wrapped = module.TogglePattern(pattern(element, 'toggle'))
                base.call = lambda: wrapped.Toggle(waitTime=0)
            elif role in {'TabItem', 'ListItem', 'DataItem', 'TreeItem', 'RadioButton'}:
                if base.read:
                    wrapped = module.SelectionItemPattern(pattern(element, 'selection_item'))
                    base.call = lambda: wrapped.Select(waitTime=0)
                else:
                    wrapped = module.InvokePattern(pattern(element, 'invoke'))
                    base.call = lambda: wrapped.Invoke(waitTime=0)
            else:
                wrapped = module.InvokePattern(pattern(element, 'invoke'))
                base.call = lambda: wrapped.Invoke(waitTime=0)
            return base
        if operation == 'scroll':
            interface = pattern(element, 'scroll')
            wrapped = module.ScrollPattern(interface)
            before = (interface.CurrentHorizontalScrollPercent, interface.CurrentVerticalScrollPercent)
            horizontal, vertical = {'up': (2, 0), 'down': (2, 3), 'left': (0, 2), 'right': (3, 2)}[request['value']]
            axis = 1 if request['value'] in {'up', 'down'} else 0
            sign = 1 if request['value'] in {'down', 'right'} else -1
            if not 0 <= before[axis] <= 100:
                raise Unsupported('The scroll container exposes no usable native percentage')
            def moved():
                current = (interface.CurrentHorizontalScrollPercent, interface.CurrentVerticalScrollPercent)[axis]
                return 0 <= current <= 100 and (current - before[axis]) * sign > 0
            return Prepared(lambda: wrapped.Scroll(horizontal, vertical, waitTime=0),
                            moved, expected=True)
        raise Unsupported('No reviewed Windows-MCP primitive for ' + operation)


class CUA:
    """Python port of Cua Driver page_bookmark.rs set_value/invoke_element."""
    name = 'cua'

    def prepare(self, element, control, request, window):
        operation = request['operation']
        # Resolve directly from the admitted live UIA element, as in the Rust driver.
        from pywinauto.uia_defines import IUIA
        definitions = IUIA().UIA_dll
        raw = element.element_info.element
        def resolve(ident, interface):
            candidate = raw.GetCurrentPattern(ident)
            if not candidate:
                raise Unsupported('Cua port: missing current UIA pattern')
            return candidate.QueryInterface(interface)
        if operation == 'fill_text':
            value = resolve(10002, definitions.IUIAutomationValuePattern)
            if value.CurrentIsReadOnly:
                raise ValueError('The text field is read-only; no action taken.')
            before, content = value.CurrentValue, request['content']
            return Prepared(lambda: value.SetValue(content), lambda: value.CurrentValue,
                            content, before, before == content)
        if operation == 'activate' and control['role'] in {'Button', 'Hyperlink', 'MenuItem', 'SplitButton'}:
            invoke = resolve(10000, definitions.IUIAutomationInvokePattern)
            return Prepared(invoke.Invoke)
        raise Unsupported('No reviewed Cua Driver port for ' + operation)


class OpenComputerUse:
    """Port of native_actions.go uiaPreferredClick and set_value dispatch."""
    name = 'open-computer-use'

    def prepare(self, element, control, request, window):
        operation = request['operation']
        if operation == 'fill_text':
            value = pattern(element, 'value')
            before, content = value.CurrentValue, request['content']
            return Prepared(lambda: value.SetValue(content), lambda: value.CurrentValue,
                            content, before, before == content)
        if operation == 'activate':
            if control['role'] in {'CheckBox', 'ComboBox', 'RadioButton', 'TabItem', 'ListItem', 'DataItem', 'TreeItem'}:
                return selection(element, control, request.get('verb', 'click'))
            # Upstream's preferred accessibility click resolves Invoke, SelectionItem,
            # Toggle BEFORE dispatch. Never chain after an invocation exception.
            for name, method in [('invoke', 'Invoke'), ('selection_item', 'Select'), ('toggle', 'Toggle')]:
                try:
                    interface = pattern(element, name)
                except Unsupported:
                    continue
                return Prepared(getattr(interface, method))
        raise Unsupported('No reviewed Open Computer Use primitive for ' + operation)


class AgentS:
    """Accessible selection adaptation; physical WindowsACI centre clicks are excluded.

    Jarvis's independent cursor cannot dispatch through the shared mouse.
    Missing patterns therefore remain an unsupported preparation, before input.
    """
    name = 'agent-s'

    def prepare(self, element, control, request, window):
        if request['operation'] != 'activate' or control['role'] not in {'Button', 'Hyperlink', 'MenuItem', 'SplitButton', 'TabItem', 'ListItem', 'DataItem', 'TreeItem'}:
            raise Unsupported('Agent-S activation is limited to explicit accessible actions')
        return selection(element,control,request.get('verb','click'))


class JarvisPointer:
    """A real click with Jarvis's own touch pointer at the control's centre (first choice).

    Admitted only when the centre point hit-tests to this exact control in this
    window, so the tap cannot land on something else. Toggle/selection state is
    read back when the control exposes it. If the point is covered, off-screen or
    too small, preparation fails before input and the accessibility providers follow.
    """
    name = 'jarvis-pointer'
    ROLES = {'Button', 'Hyperlink', 'MenuItem', 'SplitButton', 'CheckBox', 'RadioButton', 'TabItem', 'ListItem',
             'DataItem', 'TreeItem', 'ComboBox', 'Image', 'Text', 'Group', 'Custom', 'Pane'}

    def prepare(self, element, control, request, window):
        from .jarvis_pointer import enabled, tap
        if request['operation'] not in {'activate', 'open_menu'} or not enabled():
            raise Unsupported('Physical pointer not requested for ' + request['operation'])
        if control.get('password') or control.get('role') not in self.ROLES:
            raise Unsupported('Jarvis pointer is not used for this control type')
        if not type(element).__module__.startswith('pywinauto'):
            raise Unsupported('Not a live accessible control')
        try:
            import win32gui
            from pywinauto import Desktop
            rect = element.rectangle()
            if rect.width() < 4 or rect.height() < 4:
                raise Unsupported('Control is too small to tap safely')
            x, y = (rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2
            if win32gui.GetAncestor(win32gui.WindowFromPoint((x, y)), 2) != window.handle:
                raise Unsupported('Another window covers the control')
            target = list(element.element_info.runtime_id)
            hit = Desktop(backend='uia').from_point(x, y)
            for _ in range(8):  # The point may land on a child (an icon or label inside the button).
                if hit is None or list(hit.element_info.runtime_id) == target:
                    break
                hit = hit.parent()
            if hit is None or list(hit.element_info.runtime_id) != target:
                raise Unsupported('The control centre belongs to a different element')
        except Unsupported:
            raise
        except Exception as exc:
            raise Unsupported('Jarvis pointer could not admit this control: ' + type(exc).__name__) from exc
        try:
            state = selection(element, control, request.get('verb', 'click'))
        except Unsupported:
            state = Prepared(None)
        return Prepared(lambda: tap(x, y), state.read, state.expected, state.before, state.no_op)


PROVIDERS = (JarvisPointer, UFO, WindowsMCP, CUA, OpenComputerUse, AgentS)
PRIORITY = tuple(provider.name for provider in PROVIDERS)
