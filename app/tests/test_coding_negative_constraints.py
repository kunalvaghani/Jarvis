"""A scientific/product request must not become coding solely from a prohibition."""
import pytest
from jarvis.coder import workspace_coding_request, explicit_coding_intent


@pytest.mark.parametrize('constraint', [
    'No arbitrary generated host scripts are authorized.',
    'Do not write Python scripts.',
    "Don't create a program.",
    'Never build an app.',
])
def test_negative_code_constraint_does_not_select_coder(constraint):
    goal = 'Research a mechanism and build an editable physical model. ' + constraint
    assert not workspace_coding_request(goal)
    assert not explicit_coding_intent(goal)


@pytest.mark.parametrize('goal', [
    'Write a Python program. Do not install packages.',
    'Do not install packages; write a Python program.',
    'Create a website. No paid services are allowed.',
    'Modify main.py to handle negative numbers. Never publish it.',
])
def test_positive_coding_request_survives_unrelated_constraint(goal):
    assert workspace_coding_request(goal)
    assert explicit_coding_intent(goal)
