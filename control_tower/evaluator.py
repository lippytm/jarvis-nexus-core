"""Static safety lint for *predefined* sandbox templates, not a secure execution sandbox."""
import ast
from hashlib import sha256
from control_tower.builder import TEMPLATE_SOURCES

FORBIDDEN = (ast.Import, ast.ImportFrom, ast.With, ast.AsyncWith,
             ast.Global, ast.Nonlocal, ast.Lambda, ast.ClassDef)
ALLOWED_CALLS = {"isinstance", "len"}

def evaluate_candidate(candidate):
    base = {"execution": "not_run", "deployment": "not_deployed",
            "review_scope": "exact_template_and_static_checks", "independent_security_audit": False}
    if not isinstance(candidate, dict) or not isinstance(candidate.get("content"), str):
        return {**base, "passed": False, "errors": ["candidate content must be text"]}
    content = candidate["content"]
    errors = []
    if len(content) > 10000:
        return {**base, "passed": False, "errors": ["candidate source limit exceeded"]}
    if candidate.get("status") != "generated_not_executed":
        errors.append("candidate state mismatch")
    try:
        if sha256(content.encode("utf-8")).hexdigest() != candidate.get("sha256"):
            errors.append("digest mismatch")
    except UnicodeError:
        errors.append("source must be valid UTF-8")
    template = candidate.get("template")
    if not isinstance(template, str) or TEMPLATE_SOURCES.get(template) != content:
        errors.append("source is not the declared allowlisted template")
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, FORBIDDEN):
                errors.append("disallowed AST node")
            if isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_CALLS:
                    errors.append("disallowed call")
    except (SyntaxError, ValueError, RecursionError):
        errors.append("syntax failure")
    return {**base, "passed": not errors, "errors": errors}
