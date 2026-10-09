import unittest
from jarvis.model_selection import installed_model


class ModelSelectionTests(unittest.TestCase):
    def test_claude_backend_requires_local_alias_without_cloud_model(self):
        from jarvis.model_selection import required_models
        config={'brain':{'enabled':True,'coding_backend':'claude-code','planner':'qwen3.5:9b','coder':'qwen3.5:9b'},
            'context_selector':{'enabled':False},'command_cleanup':{'enabled':False}}
        names=required_models(config)
        self.assertIn('jarvis-claude-qwen3.5:9b',names)
        self.assertFalse(any('sonnet' in name or 'opus' in name for name in names))
    def test_preferred_model_wins_when_download_finishes(self):
        self.assertEqual(installed_model("qwen3.5:4b", {"qwen3.5:4b", "qwen3:4b"}), "qwen3.5:4b")

    def test_missing_preferred_uses_installed_compatible_model(self):
        self.assertEqual(installed_model("qwen3.5:4b", {"qwen3:4b"}), "qwen3:4b")
        self.assertEqual(installed_model("qwen3-vl:4b", {"qwen3-vl:2b"}, vision=True), "qwen3-vl:2b")
        with self.assertRaises(ValueError):
            installed_model("qwen3-vl:4b", {"qwen3:4b"}, vision=True)

    def test_disabled_fallback_does_not_silently_change_model(self):
        with self.assertRaises(ValueError):
            installed_model("qwen3.5:4b", {"qwen3:4b"}, allow_fallback=False)
