"""One-shot native Office automation worker (main .venv, pywin32).

Opens a host-prepared temporary copy in a *new*, hidden Excel or Word instance
(DispatchEx), edits it through the application's own object model, saves it with
the application itself (so features openpyxl/python-docx cannot round-trip, such
as macros and charts, are preserved by Office) and quits. The owned process ID
is written to the host's PID file before any edit so a timed-out instance can be
stopped without touching the user's own Office windows.
"""
import json
import re
import sys
import uuid

LIMIT = 1_000_000
CELL = re.compile(r'[A-Z]{1,3}[1-9][0-9]{0,6}')


def _owned_pid(application, kind):
    import win32gui
    import win32process
    if kind == 'excel':
        handle = application.Hwnd
    else:
        caption = 'Jarvis-owned-' + uuid.uuid4().hex
        application.Caption = caption
        handle = win32gui.FindWindow('OpusApp', caption)
    if not handle:
        raise RuntimeError('Owned Office window was not found.')
    return win32process.GetWindowThreadProcessId(handle)[1]


def excel_write(application, request):
    book = application.Workbooks.Open(request['path'], UpdateLinks=0, ReadOnly=False)
    try:
        sheet = book.Worksheets(request['sheet'])
        for coordinate, value in request['cells'].items():
            if not CELL.fullmatch(coordinate):
                raise ValueError('Cells must be A1-style coordinates.')
            cell = sheet.Range(coordinate)
            if isinstance(value, str) and value.startswith('='):
                cell.Formula = value
            else:
                cell.Value = value
        application.Calculate()
        result = {coordinate: sheet.Range(coordinate).Value for coordinate in request['cells']}
        book.Save()
        return {'written': sorted(request['cells']), 'calculated': result}
    finally:
        book.Close(SaveChanges=False)


def word_write(application, request):
    document = application.Documents.Open(request['path'], ConfirmConversions=False, ReadOnly=False,
                                          AddToRecentFiles=False, Visible=False)
    try:
        for edit in request['edits']:
            if edit['kind'] == 'append_paragraph':
                document.Content.InsertParagraphAfter()
                document.Paragraphs(document.Paragraphs.Count).Range.Text = edit['text']
            elif edit['kind'] == 'replace_text':
                find = document.Content.Find
                find.ClearFormatting()
                find.Replacement.ClearFormatting()
                # Late-bound COM ignores named Execute arguments, so set properties explicitly.
                find.Text, find.Replacement.Text = edit['find'], edit['replace']
                find.Forward, find.Wrap, find.MatchCase = True, 0, True  # wdFindStop; exact case
                find.MatchWholeWord = find.MatchWildcards = False
                # Positional Execute: 11th argument Replace=wdReplaceAll (2).
                if not find.Execute(edit['find'], True, False, False, False, False, True, 0, False,
                                    edit['replace'], 2):
                    raise ValueError('Text not found; no change made.')
            else:
                raise ValueError('Unsupported Word edit.')
        document.Save()
        return {'edits': len(request['edits'])}
    finally:
        document.Close(SaveChanges=False)


def main():
    application = None
    try:
        raw = sys.stdin.buffer.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError('Office request exceeds 1 MB.')
        request = json.loads(raw)
        kind = request['application']
        if kind not in {'excel', 'word'}:
            raise ValueError('Unsupported Office application.')
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        application = win32com.client.DispatchEx('Excel.Application' if kind == 'excel' else 'Word.Application')
        application.Visible = False
        application.DisplayAlerts = False if kind == 'excel' else 0
        if kind == 'excel':
            application.AskToUpdateLinks = False
            application.EnableEvents = False  # Workbook event macros never run during automation.
            application.AutomationSecurity = 3  # msoAutomationSecurityForceDisable: macros preserved, not executed.
        else:
            application.AutomationSecurity = 3
        with open(request['pid_file'], 'w', encoding='ascii') as handle:
            handle.write(str(_owned_pid(application, kind)))
        value = (excel_write if kind == 'excel' else word_write)(application, request)
        text = json.dumps({'ok': True, 'value': value}, default=str, allow_nan=False)
    except Exception as error:
        text = json.dumps({'ok': False, 'error_type': type(error).__name__, 'error': str(error)[:500]})
    finally:
        if application is not None:
            try:
                application.Quit()
            except Exception:  # The host stops the owned PID if Quit did not complete.
                pass
    sys.stdout.write(text)


if __name__ == '__main__':
    main()
