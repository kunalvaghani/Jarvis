"""Independent verifiable rewards for AZR answers (Pillar D, Part C).

Rewards are computed only from the oracle: the deterministic simulation (deduction, abduction)
and sandboxed execution (induction). The reward code never imports or reads candidate training
outputs other than the answer text it scores. AZR's composite reward is used:
correct = 1, well-formatted but wrong = -0.5, format/safety failure = -1.
Induction also reports visible-only passes, so memorising the shown examples cannot score as
generalisation, and repeatability (every case is executed twice).
"""
from .azr_tasks import check_abduction, check_deduction, extract_code, screen_program

CORRECT, WRONG, MALFORMED = 1.0, -0.5, -1.0


def score_symbolic(task, answer):
    check = check_deduction(task, answer) if task['mode'] == 'deduction' else check_abduction(task, answer)
    reward = CORRECT if check['correct'] else WRONG if check['format_ok'] else MALFORMED
    return {**check, 'reward': reward}


def score_induction_batch(base, items, run_programs):
    """items: [(key, task, answer_text)] -> {key: result}; one sandbox run for the whole batch."""
    programs, results = [], {}
    for key, task, answer in items:
        source = extract_code(answer)
        try:
            screen_program(source)
        except (ValueError, SyntaxError) as exc:
            results[key] = {'format_ok': False, 'correct': False, 'reason': 'screen: ' + str(exc)[:80], 'reward': MALFORMED}
            continue
        programs.append({'id': key + ':visible', 'source': source, 'cases': task['visible']})
        programs.append({'id': key + ':hidden', 'source': source, 'cases': task['hidden']})
    if programs:
        rows = run_programs(base, programs)
        for key, task, _ in items:
            if key in results:
                continue
            visible, hidden = rows[key + ':visible'], rows[key + ':hidden']
            correct = bool(visible['passed'] and hidden['passed'])
            results[key] = {'format_ok': True, 'correct': correct, 'visible_passed': bool(visible['passed']),
                            'hidden_passed': bool(hidden['passed']),
                            'deterministic': bool(visible.get('deterministic') and hidden.get('deterministic')),
                            'error': visible.get('error') or hidden.get('error'),
                            'reason': 'generalizes' if correct else ('visible_only' if visible['passed'] else 'fails_visible'),
                            'reward': CORRECT if correct else WRONG}
    return results


def score_all(base, rows, run_programs):
    """rows: [{key, task, answer}] -> {key: result} for every mode."""
    results = {}
    induction = []
    for row in rows:
        if row['task']['mode'] == 'induction':
            induction.append((row['key'], row['task'], row['answer']))
        else:
            results[row['key']] = score_symbolic(row['task'], row['answer'])
    for start in range(0, len(induction), 40):
        results.update(score_induction_batch(base, induction[start:start + 40], run_programs))
    return results
