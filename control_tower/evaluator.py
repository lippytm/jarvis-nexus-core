"""Static safety lint for *predefined* sandbox templates, not a secure execution sandbox."""
import ast
from hashlib import sha256

FORBIDDEN = (ast.Import, ast.ImportFrom, ast.With, ast.AsyncWith,
             ast.Global, ast.Nonlocal, ast.Lambda, ast.ClassDef)
ALLOWED_CALLS = {"isinstance", "len"}

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
            if isinstance(node, FORBIDDEN):
                errors.append("disallowed AST node")
            if isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_CALLS:
                    errors.append("disallowed call")
    except SyntaxError:
        errors.append("syntax failure")
    return {"passed": not errors, "errors": errors,
            "execution": "not_run", "deployment": "not_deployed"}
