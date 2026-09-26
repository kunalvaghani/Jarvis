import unittest
from jarvis.task_graph import resource_dependencies, validate_dependencies
from jarvis.brain import validate_plan


def step(identifier=None, dependencies=None):
    result = {"action": "open", "value": "calculator", "expected": "Calculator visible"}
    if identifier is not None:
        result.update(id=identifier, dep=dependencies if dependencies is not None else [-1])
    return result


class TaskGraphTests(unittest.TestCase):
    def test_existing_and_ordered_plans_remain_sequential(self):
        steps = [step(), step()]
        self.assertEqual(validate_plan({"steps": steps}), steps)
        steps = [step(0), step(1, [0])]
        self.assertEqual(validate_plan({"steps": steps}), steps)

    def test_bad_graphs_are_rejected_before_dispatch(self):
        for steps in ([step(0, [1]), step(1, [0])], [step(0), step(0)],
                      [step(0, [0])], [step(0, [99])], [step(0, [-1, 2])],
                      [step(0, "0")], [step(True)], [step(0, [False])]):
            with self.subTest(steps=steps), self.assertRaises(ValueError):
                validate_plan({"steps": steps})

    def test_completed_prerequisites_require_verification_and_cannot_be_reused(self):
        validate_dependencies([step(1, [0])], [{"id": 0, "verified": True}])
        for completed in ([{"id": 0}], [{"id": 0, "verified": False}]):
            with self.assertRaises(ValueError):
                validate_dependencies([step(1, [0])], completed)
        with self.assertRaises(ValueError):
            validate_dependencies([step(0)], [{"id": 0, "verified": True}])

    def test_generated_references_are_detected_but_never_executed_as_targets(self):
        self.assertEqual(resource_dependencies({"value": "<GENERATED>-1 <GENERATED>-2 <GENERATED>-1"}), [1, 2])
        for value in ("<GENERATED>-1", "<GENERATED>-bad"):
            with self.assertRaises(ValueError):
                validate_plan({"steps": [{**step(), "value": value}]})
