"""Named-control Gmail operations in the user's existing Chrome session.

No profile copying, password extraction, SMTP login or physical mouse movement.
"""
import os
from pathlib import Path
import re
import time

BRIDGE=None


def select_compose(drafts, identity=None):
    if identity is not None:
        matches=[draft for draft in drafts if list(draft.element_info.runtime_id)==identity]
    else:
        matches=[draft for draft in drafts if draft.rectangle().height()>=100]
        if not matches and len(drafts)==1:matches=drafts
    if len(matches)!=1:raise ValueError('Inspect one expanded Gmail draft or supply its exact observed identity; other drafts are preserved.')
    return matches[0]


def chrome_window(allow_absent=False):
    from pywinauto import Desktop
    import psutil
    candidates=[]
    for window in Desktop(backend='uia').windows():
        try:
            if window.is_visible() and psutil.Process(window.process_id()).name().casefold()=='chrome.exe':
                addresses=[]
                for toolbar in window.descendants(control_type='ToolBar'):
                    ancestor=toolbar.parent();inside_page=False
                    for _ in range(12):
                        if ancestor is None or ancestor.handle==window.handle and ancestor.element_info.control_type=='Window':break
                        if ancestor.element_info.control_type=='Document':inside_page=True;break
                        ancestor=ancestor.parent()
                    if not inside_page:addresses.extend(toolbar.descendants(control_type='Edit'))
                values=[]
                for address in addresses:
                    try:values.append(address.iface_value.CurrentValue)
                    except Exception:pass
                if sum(bool(re.match(r'^(?:https://)?mail\.google\.com(?:/|$)',value)) for value in values)==1:candidates.append(window)
        except (OSError,psutil.Error):continue
    if not candidates and allow_absent:return None
    if len(candidates)!=1:raise ValueError('Select one Gmail tab in your logged-in Chrome window, then try again. No cookies or credentials are copied.')
    return candidates[0]


def unique(window, names, roles):
    matches=[]
    for role in roles:
        for item in window.descendants(control_type=role):
            labels={item.window_text().strip().casefold(),str(item.element_info.name or '').strip().casefold(),str(item.element_info.automation_id or '').strip().casefold()}
            if item.is_visible() and item.is_enabled() and labels.intersection(n.casefold() for n in names):matches.append(item)
    if len(matches)!=1:raise ValueError('Gmail control must be uniquely visible: '+names[0])
    return matches[0]


def guard(window):
    import win32gui
    if win32gui.GetForegroundWindow()!=window.handle or not win32gui.IsWindow(window.handle):raise ValueError('Gmail lost focus; no further input issued.')
    current=chrome_window()
    if current.handle!=window.handle:raise ValueError('Gmail tab/window changed; no further input issued.')


def focus_host(window):
    import win32gui
    # Avoid Chrome UIA SetFocus on an already foreground host: its provider can
    # route focus to a compose title control and change the panel's state.
    if win32gui.GetForegroundWindow()!=window.handle:window.set_focus()
    guard(window)


def activate(window,element):
    from .independent_cursor import CursorCue
    rectangle=element.rectangle()
    # Resolve a supported pattern before dispatch. Never fall back after a
    # failed invocation, which could repeat an action with an uncertain result.
    from pywinauto.uia_defines import NoPatternInterfaceError
    try:method=element.iface_invoke.Invoke
    except NoPatternInterfaceError:
        from pywinauto.uia_defines import get_elem_interface
        interface=get_elem_interface(element.element_info.element,'LegacyIAccessible')
        if interface.CurrentDefaultAction!='Press':raise ValueError('Gmail button has no supported activation pattern.')
        def method():
            element.set_focus();guard(window)
            if not element.has_keyboard_focus():raise ValueError('Gmail button focus was not verified.')
            element.type_keys('{ENTER}',set_foreground=False)
    with CursorCue([rectangle.left,rectangle.top,rectangle.right,rectangle.bottom],window.handle):
        guard(window)
        method()


def set_value(window,element,text):
    guard(window)
    interface=element.iface_value
    if interface.CurrentIsReadOnly:raise ValueError('Gmail field is read-only.')
    interface.SetValue(text)
    if interface.CurrentValue!=text:raise ValueError('Gmail field readback failed; inspect before retrying.')


def compose_windows(window):
    return [item for item in window.descendants(control_type='Window')
            if item.is_visible() and (item.window_text().strip().casefold()=='new message' or item.window_text().strip().casefold().startswith('compose: '))]


def expand_compose(window,compose):
    # Gmail can remember a collapsed compose state. Expand the existing draft;
    # never click Compose again after dispatching creation.
    if compose.rectangle().height()<100:
        activate(window,unique(compose,['Maximise','Maximize'],['Button']))
        time.sleep(.3)


def perform(request):
    operation=request['operation']
    if operation=='send':raise ValueError('Gmail sending is not enabled. Prepare a draft for review; nothing sent.')
    if operation=='open':
        window=chrome_window(allow_absent=True)
        if window is None:return {'create_tab_needed':True,'opened_existing_profile':False,'sent':False}
        # UIA Window.restore() can act on Gmail's focused compose dialog in
        # Chrome and collapse it. Only restore a minimized native host window.
        import win32gui
        import win32con
        if win32gui.IsIconic(window.handle):
            win32gui.ShowWindow(window.handle,win32con.SW_RESTORE)
        focus_host(window)
        return {'create_tab_needed':False,'opened_existing_profile':True,'reused_existing_gmail_window':True,'sent':False}
    if operation=='prepare':
        from pywinauto import Desktop
        import psutil
        windows=[w for w in Desktop(backend='uia').windows() if w.is_visible() and 'gmail' in w.window_text().casefold() and psutil.Process(w.process_id()).name().casefold()=='chrome.exe']
        if len(windows)!=1:raise ValueError('Choose one existing Gmail Chrome window.')
        window=windows[0];window.restore();window.set_focus()
        # Focus the native address bar for observation only; no text or submission.
        window.type_keys('^l');time.sleep(.2)
        return {'address_observation_prepared':True,'input_text_sent':False}
    if operation=='diagnose':
        from pywinauto import Desktop
        import psutil
        rows=[]
        for candidate in Desktop(backend='uia').windows():
            try:
                if candidate.is_visible() and psutil.Process(candidate.process_id()).name().casefold()=='chrome.exe':
                    edits=[e for e in candidate.descendants() if e.is_visible() and re.search(r'address|omnibox',e.window_text(),re.I)]
                    from collections import Counter
                    descendants=candidate.descendants()
                    known={'subject','subjectbox','message body','to recipients','recipients','to','search mail'}
                    rows.append({'address_fields':[e.window_text() for e in edits if 'address' in e.window_text().casefold()],'gmail_in_title':'gmail' in candidate.window_text().casefold(),'roles':dict(Counter(e.element_info.control_type for e in descendants)),'focused_roles':[e.element_info.control_type for e in descendants if e.has_keyboard_focus()],
                        'compose_field_labels':[{k:v for k,v in {'name':str(e.element_info.name),'id':str(e.element_info.automation_id),'role':e.element_info.control_type}.items()} for e in descendants if e.element_info.control_type in {'Edit','Document'} and (str(e.element_info.name).casefold() in known or str(e.element_info.automation_id).casefold() in known)]})
            except (OSError,psutil.Error):pass
        return {'chrome_windows':rows}
    window=chrome_window()
    global BRIDGE
    base=Path(__file__).resolve().parent.parent
    if (base/'.jarvis-runtime/gmail-extension/connection.json').exists():
        from .gmail_bridge import configured
        if BRIDGE is None:BRIDGE=configured(base)
        focus_host(window)
        if operation in {'draft','resume_draft'}:
            from .independent_cursor import CursorCue
            # Native bounds illustrate the operation; extension DOM identity
            # determines the actual target. No shared mouse input is issued.
            if operation=='draft':target=unique(window,['Compose'],['Button','Hyperlink'])
            else:target=select_compose(compose_windows(window))
            r=target.rectangle()
            with CursorCue([r.left,r.top,r.right,r.bottom],window.handle):
                guard(window)
                return BRIDGE.call(request)
        return BRIDGE.call(request)
    if operation=='inspect':
        compose=unique(window,['Compose'],['Button','Hyperlink'])
        return {'gmail_in_existing_chrome':True,'compose_available':True,'credentials_copied':False,
                'draft_runtime_ids':[list(w.element_info.runtime_id) for w in compose_windows(window)]}
    if operation=='verify_draft':
        drafts=compose_windows(window)
        compose=select_compose(drafts,request.get('draft_runtime_id'))
        subject=unique(compose,['Subject','Subjectbox'],['Edit'])
        message=unique(compose,['Message Body','Message body'],['Edit','Document'])
        to_field=unique(compose,['To recipients','Recipients','To'],['Edit'])
        return {'draft_created':True,'subject_verified':subject.iface_value.CurrentValue==request['subject'],
                'body_verified':message.iface_value.CurrentValue==request['body'],'sent':False,
                'recipient_set':bool(to_field.iface_value.CurrentValue) or any('@' in i.window_text() for i in compose.descendants(control_type='Button'))}
    if operation not in {'draft','resume_draft','send'}:raise ValueError('Use Gmail inspect, draft or send.')
    window.set_focus();guard(window)
    title=request['subject'];body=request['body'];recipient=request.get('to','')
    if len(title)>200 or len(body)>10000 or (recipient and not re.fullmatch(r'[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+',recipient)):raise ValueError('Invalid Gmail draft fields.')
    if request.get('attachments'):raise ValueError('Attachment upload is not validated; no draft is created or sent.')
    # Refuse to reuse or overwrite an existing compose window.
    drafts=compose_windows(window)
    if operation=='resume_draft':
        if recipient or not request.get('draft_runtime_id'):
            raise ValueError('Resuming requires the inspected unique draft identity and no recipient.')
        compose=select_compose(drafts,request['draft_runtime_id'])
    else:
        if drafts or any(item.is_visible() and item.window_text().casefold() in {'subject','subjectbox'} for item in window.descendants(control_type='Edit')):
            raise ValueError('A compose draft is already open. Inspect/save it before creating another; no automatic duplicate draft.')
        activate(window,unique(window,['Compose'],['Button','Hyperlink']));time.sleep(.3)
        drafts=compose_windows(window)
        if len(drafts)!=1:raise ValueError('Draft creation outcome uncertain; inspect before repeating.')
    if operation!='resume_draft':compose=drafts[0]
    expand_compose(window,compose)
    subject=unique(compose,['Subject','Subjectbox'],['Edit'])
    message=unique(compose,['Message Body','Message body'],['Edit','Document'])
    if operation=='resume_draft':
        if subject.iface_value.CurrentValue!=request.get('expected_subject') or message.iface_value.CurrentValue!=request.get('expected_body'):
            raise ValueError('Draft content changed; no overwrite issued.')
        to_field=unique(compose,['To recipients','Recipients','To'],['Edit'])
        if to_field.iface_value.CurrentValue or any('@' in i.window_text() for i in compose.descendants(control_type='Button')):
            raise ValueError('Draft has recipients; no input issued.')
    set_value(window,subject,title)
    set_value(window,message,body)
    if recipient:set_value(window,unique(compose,['To recipients','Recipients','To'],['Edit']),recipient)
    if operation in {'draft','resume_draft'}:return {'draft_created':True,'existing_draft_resumed':operation=='resume_draft','subject_verified':True,'body_verified':True,'sent':False,'recipient_set':bool(recipient)}
    if not recipient:raise ValueError('Sending requires an exact recipient; draft retained.')
    activate(window,unique(window,['Send','Send ‪(Ctrl-Enter)‬','Send (Ctrl-Enter)'],['Button']))
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        guard(window)
        if any(item.window_text().strip()=='Message sent' for item in window.descendants(control_type='Text')):
            return {'send_ui_confirmed':True,'recipient_delivery_verified':False,'no_automatic_retry':True}
        time.sleep(.1)
    raise ValueError('Send outcome uncertain; inspect Gmail Sent manually before repeating. No automatic retry.')


def serve():
    import json,sys
    try:
        for line in sys.stdin:
            row=json.loads(line)
            if row['request'].get('operation')=='shutdown':return
            try:response={'id':row['id'],'result':perform(row['request'])}
            except Exception as error:response={'id':row['id'],'error':type(error).__name__+': '+str(error)}
            print(json.dumps(response),flush=True)
    finally:
        if BRIDGE is not None:BRIDGE.close()


if __name__=='__main__':serve()
