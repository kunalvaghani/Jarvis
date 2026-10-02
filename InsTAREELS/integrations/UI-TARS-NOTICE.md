# UI-TARS component attribution

Copyright (c) 2025 Bytedance Ltd. and/or its affiliates. Apache-2.0; the complete [license](UI-TARS-LICENSE) is included.

Jarvis includes the unchanged `parse_action` function from [UI-TARS/codes/ui_tars/action_parser.py](https://github.com/bytedance/UI-TARS/blob/582f3a7ea5d285ee8ed9e2e84048d1ab01453c49/codes/ui_tars/action_parser.py), reviewed at revision `582f3a7ea5d285ee8ed9e2e84048d1ab01453c49` on 2026-10-02. [The extracted module](../jarvis/_vendor/ui_tars_action_parser.py) adds attribution/provenance comments and imports only `ast`. Other upstream functions, especially the generated PyAutoGUI code executor, are excluded.

Jarvis supplies its own typed local-model adapter, AST allowlist, Windows input worker, fresh-state guards, cancellation, native-first routing, Save workflow and outcome checks. These are Jarvis changes, not upstream UI-TARS functionality. The local model is Qwen3-VL, not UI-TARS weights. The UI-TARS Desktop application and Agent S runtime are not installed.

The [integration review](../docs/visual-interaction.md) records the evaluated alternatives, pinned revisions and verification limits. A component checksum records the reviewed source with LF line endings; it is a provenance/readiness check, not a security guarantee.
