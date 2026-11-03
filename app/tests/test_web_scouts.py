"""Web scouts (jarvis/control/web/scouts.py): a long page reaches the planner as a map plus its best parts."""
from jarvis.control.web.scouts import brief, condensed, segment


def page(rows: int = 60) -> str:
    lines = ['title "Inbox (12) - Mail"', '  banner', '    combobox "Search mail" [ref_1]', '    button "Settings" [ref_2]',
             '  navigation "Labels"', '    link "Inbox 12 unread" [ref_3]', '    link "Drafts" [ref_4]',
             '    link "Sent" [ref_5]']
    lines += ['  tabpanel "Primary"']
    for n in range(rows):
        lines.append(f'    row "unread, Sender {n} , Subject number {n} , 1 Nov , ' + 'snippet text ' * 30 + '"')
        lines += [f'      checkbox "" [ref_{100 + 6 * n}]'] + [f'      gridcell "cell {n}-{k} ' + 'x' * 40 + f'" [ref_{101 + 6 * n + k}]'
                                                             for k in range(5)]
    lines += ['  complementary "Side panel"', '    button "Calendar" [ref_9]']
    return '\n'.join(lines)


def test_short_pages_are_unchanged():
    text = 'title "Example"\n  heading "Example Domain"\n  link "More" [ref_1]'
    assert brief('what is the heading?', text) == text


def test_list_questions_see_every_row_and_the_count():
    out = brief('tell me the subject of the newest email in my inbox', page(50))  # a Gmail page holds 50
    assert len(out) <= 9000
    assert '50 items' in out.split('\n')[2]  # the map's first line: the list, with its count
    assert sum(1 for line in out.split('\n') if line.lstrip().startswith('row "')) == 50
    assert 'Subject number 0' in out and 'Subject number 49' in out


def test_a_cut_list_says_how_many_rows_are_missing():
    out = brief('how many emails are there?', page(80))
    shown = sum(1 for line in out.split('\n') if line.lstrip().startswith('row "'))
    assert shown < 80 and f'{80 - shown} more items not shown: this part has 80 items in all' in out


def test_navigation_goals_keep_the_matching_link():
    out = brief('open the Drafts folder', page())
    assert 'link "Drafts" [ref_4]' in out


def test_dialogs_come_first():
    text = page() + '\n  dialog "Discard draft?"\n    button "Discard" [ref_7]\n    button "Cancel" [ref_8]'
    out = brief('tell me the newest subject', text)
    assert out.split('\n')[2].strip().startswith('1. [*] dialog')


def test_condensed_list_keeps_one_ref_per_row():
    part = next(p for p in segment(page(10).split('\n'), 4000) if p.role == 'tabpanel')
    short = condensed(part)
    rows = [line for line in short if line.lstrip().startswith('row "')]
    assert len(rows) == 10 and all('[ref_' in line for line in rows)


def test_tie_break_is_only_a_hint():
    calls = []

    def pick(goal, tied):
        calls.append(len(tied))
        return None  # no clear margin: the deterministic order stands
    assert brief('zzz', page(), tie_break=pick) == brief('zzz', page())
