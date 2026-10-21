import unittest
from control_tower.builder import ToolSpec, generate_candidate
from control_tower.evaluator import evaluate_candidate

class BuilderEvaluationTests(unittest.TestCase):
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
