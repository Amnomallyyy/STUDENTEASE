"""External evidence for the CV analyzer: GitHub (official REST API), LinkedIn (the user's own export),
cross-source reconciliation and the anomaly rules.

    github.get_github(username)              -> GitHubEvidence (demo cache first, then the API)
    linkedin.skills_from_linkedin(text)      -> ExtractedCV with sources=["linkedin"]
    reconcile.reconcile(cv, github, linkedin) -> list[SkillCluster]
    anomalies.find_anomalies(...)            -> list[Anomaly]
"""
