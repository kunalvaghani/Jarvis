# Fresh evaluation of actual trained Qwen weights

Completed 2026-09-27. [Individual results and exact inputs](results.json).
The selected local adapter generated 100 new Python JSON-CLI programs on CUDA
BF16, without retained teacher-source reuse, experience recall or execution
feedback. Each prompt contained two example cases; the third was withheld.

31/100 projects passed all three cases. 95 programs executed 285 small cases,
of which 112 passed. Five outputs were rejected before execution, leaving 15
planned small cases unexecuted. 24/86 training projects and 7/14 validation
projects passed. The validation projects had previously guided checkpoint
selection, so they are not an untouched final test set.

All ten larger cases executed the newly generated programs. Only edit distance
passed, for 1/10. Large inputs were never in the inference prompts. Both small
and larger results are retained even when they fail. Each project directory
contains the response, generated source and verification evidence.

These are distinct CLI tasks from the existing curriculum, not 100 complete
multi-file applications. The source policy and subprocess deadlines are not an
OS security sandbox. The score does not justify promoting this 0.5B candidate
over Jarvis's configured 4B coder.

See [training and exact resume](../../docs/qwen-weight-training.md) and
[exported model evidence](../qwen-jarvis-trained-20260927/results.json).
