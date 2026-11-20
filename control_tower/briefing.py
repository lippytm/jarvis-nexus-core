"""Render a deterministic offline evidence-aware briefing excerpt."""
def project_summary(projects):
    """Never replace missing evidence with an assertion of production readiness."""
    allowed = {"verified", "in_progress", "planned", "blocked", "unknown"}
    lines = []
    for project in projects:
        status = project.get("status", "unknown")
        if status not in allowed:
            status = "unknown"
        evidence = project.get("evidence_url")
        if status == "verified" and not evidence:
            status = "unknown"
        name = project.get("name", "Unnamed project")
        lines.append(f"{name}: {status}" + (f" (evidence: {evidence})" if evidence else ""))
    return "\n".join(lines)
