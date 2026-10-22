"""Read-only dashboard view model; never treats missing metrics as zero."""
def build_dashboard(projects, metrics):
    allowed = {"verified", "planned", "blocked", "unknown", "in_progress"}
    results = []
    for project in projects:
        status = project.get("status", "unknown")
        evidence = project.get("evidence_url")
        if status not in allowed or (status == "verified" and not evidence):
            status = "unknown"
        results.append({"name": project.get("name", "unnamed"), "status": status, "evidence_url": evidence})
    fields = ("visits", "optins", "memberships", "referrals", "verified_commissions_usd", "cost_usd")
    result_metrics = {field: metrics.get(field, "unavailable") for field in fields}
    return {"projects": results, "metrics": result_metrics, "environment": "read_only_sandbox"}
