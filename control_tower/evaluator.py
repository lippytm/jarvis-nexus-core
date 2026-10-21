"""Static independent-gate proxy for offline generated scaffold candidates."""
import ast
from hashlib import sha256

DISALLOWED = (ast.Import, ast.ImportFrom, ast.Call, ast.With, ast.AsyncWith,
              ast.Global, ast.Nonlocal)

def evaluate_candidate(candidate):
    content = candidate.get("content", "")
    errors = []
    if candidate.get("status") != "generated_not_executed":
        errors.append("candidate state mismatch")
    if sha256(content.encode("utf-8")).hexdigest() != candidate.get("sha256"):
        errors.append("digest mismatch")
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, DISALLOWED):
                errors.append("disallowed AST node")
    except SyntaxError:
        errors.append("syntax failure")
    return {"passed": not errors, "errors": errors, "execution": "not_run",
            "deployment": "not_deployed"}
