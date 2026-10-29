import unittest
from control_tower.builder import TEMPLATE_SOURCES, ToolSpec, generate_candidate
from control_tower.evaluator import evaluate_candidate

class BuilderEvaluationTests(unittest.TestCase):
    def test_shared_template_catalog_cannot_change_builder_or_evaluator_baseline(self):
        candidate = generate_candidate(ToolSpec("safe_tool", "validation_tool", "Sample"))
        original = TEMPLATE_SOURCES["validation_tool"]
        replacement = "def run(payload):\n    return True\n"
        try:
            with self.assertRaises(TypeError):
                TEMPLATE_SOURCES["validation_tool"] = replacement
        finally:
            # Keep the pre-fix reproduction from contaminating other tests.
            if isinstance(TEMPLATE_SOURCES, dict):
                TEMPLATE_SOURCES["validation_tool"] = original
        with self.assertRaises(TypeError):
            TEMPLATE_SOURCES["new_template"] = replacement
        with self.assertRaises(TypeError):
            del TEMPLATE_SOURCES["validation_tool"]
        self.assertEqual(generate_candidate(ToolSpec("safe_tool", "validation_tool", "Sample")), candidate)
        self.assertTrue(evaluate_candidate(candidate)["passed"])
        from hashlib import sha256
        altered = {**candidate, "content": replacement, "sha256": sha256(replacement.encode()).hexdigest()}
        result = evaluate_candidate(altered)
        self.assertFalse(result["passed"])
        self.assertIn("source is not the declared allowlisted template", result["errors"])
        self.assertEqual(result["execution"], "not_run")

    def test_build_validate_template(self):
        candidate = generate_candidate(ToolSpec("safe_tool", "validation_tool", "Sample"))
        result = evaluate_candidate(candidate)
        self.assertTrue(result["passed"], result["errors"])
        self.assertEqual(result["execution"], "not_run")
    def test_invalid_template_blocked(self):
        with self.assertRaises(ValueError):
            generate_candidate(ToolSpec("safe_tool", "execute_shell", "no"))
    def test_invalid_name_blocked(self):
        with self.assertRaises(ValueError):
            generate_candidate(ToolSpec("../escape", "validation_tool", "no"))
    def test_digest_tamper_detected(self):
        candidate = generate_candidate(ToolSpec("safe_tool", "report_tool", "test"))
        candidate["content"] += "\nprint('unexpected')\n"
        self.assertFalse(evaluate_candidate(candidate)["passed"])
    def test_arbitrary_calls_rejected(self):
        candidate = generate_candidate(ToolSpec("safe_tool", "report_tool", "test"))
        candidate["content"] = "def run(x):\n    return eval(x)\n"
        from hashlib import sha256
        candidate["sha256"] = sha256(candidate["content"].encode()).hexdigest()
        self.assertFalse(evaluate_candidate(candidate)["passed"])

if __name__ == "__main__":
    unittest.main()
