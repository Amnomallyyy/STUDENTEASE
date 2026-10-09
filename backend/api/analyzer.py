"""Analyzer routes: run the evidence check, read a report. Register with app.include_router(analyzer.router)."""
from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from backend.api.errors import HANDLED, http_error
from backend.schemas import ExtractedCV, Profile
from backend.schemas.analyzer import AnalyzerReport
from backend.services import session
from backend.services.cv_text import CVTextError
from backend.services.evidence import anomalies, linkedin, reconcile
from backend.services.evidence.github import GitHubError, GitHubEvidence, GitHubUserNotFound, get_github, skills_from_github

router = APIRouter(prefix="/analyzer", tags=["analyzer"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024

_reports: dict[str, AnalyzerReport] = {}
_latest_id: str | None = None


@router.post("/run", response_model=AnalyzerReport)
def run_analyzer(
    github_username: str | None = Form(default=None),
    linkedin_text: str | None = Form(default=None),
    linkedin_export: UploadFile | None = File(default=None),
) -> AnalyzerReport:
    """Compare the CV with GitHub and/or a LinkedIn export, store the report and update the profile."""
    global _latest_id
    profile = session.get_profile()
    if not profile.skills:
        raise HTTPException(status_code=409, detail="Upload a CV first.")

    username = (github_username or "").strip() or None
    export_text = _linkedin_text(linkedin_text, linkedin_export)
    if username is None and export_text is None:
        raise HTTPException(status_code=422, detail="Give a GitHub username or a LinkedIn export (text or file).")

    github_evidence = _fetch_github(username) if username else None
    linkedin_cv = _extract_linkedin(export_text) if export_text else None
    report = build_report(profile, github_evidence, linkedin_cv)

    _reports[report.report_id] = report
    _latest_id = report.report_id
    session.update_profile(anomalies=report.anomalies, integrity_score=report.integrity_score)
    return report


@router.get("/report", response_model=AnalyzerReport)
def get_report(report_id: str | None = Query(default=None)) -> AnalyzerReport:
    report = _reports.get(report_id or _latest_id or "")
    if report is None:
        raise HTTPException(status_code=404, detail="No analyzer report yet. Call POST /analyzer/run first.")
    return report


def build_report(profile: Profile, github: GitHubEvidence | None, linkedin_cv: ExtractedCV | None) -> AnalyzerReport:
    """Reconcile the sources, run the rules, add suggested fixes."""
    github_skills = skills_from_github(github) if github else []
    linkedin_skills = linkedin_cv.skills if linkedin_cv else []
    clusters = reconcile.reconcile(profile.skills, github_skills, linkedin_skills)
    found = anomalies.find_anomalies(profile.skills, profile.projects, profile.experience, github, linkedin_cv, clusters)
    found = anomalies.explain_fixes(found, _context(profile, github, linkedin_cv))

    sources = {"cv": len(profile.skills)}
    if github is not None:
        sources["github"] = len(github_skills)
    if linkedin_cv is not None:
        sources["linkedin"] = len(linkedin_skills)
    return AnalyzerReport(
        report_id=uuid4().hex,
        anomalies=found,
        integrity_score=anomalies.integrity_score(clusters, profile.skills),
        clusters=clusters,
        sources=sources,
        github_username=github.username if github else None,
    )


def _context(profile: Profile, github: GitHubEvidence | None, linkedin_cv: ExtractedCV | None) -> str:
    lines = [f"Target role: {profile.target_role or 'not set'}", "CV skills: " + ", ".join(s.name for s in profile.skills)]
    if profile.projects:
        lines.append("CV projects: " + ", ".join(p.name for p in profile.projects))
    if github is not None:
        repos = ", ".join(f"{r.name} ({', '.join(r.languages) or 'no code'}, {r.commit_count} commits)" for r in github.repos)
        lines.append(f"GitHub repos: {repos or 'none'}")
    if linkedin_cv is not None:
        lines.append("LinkedIn skills: " + ", ".join(s.name for s in linkedin_cv.skills))
    return "\n".join(lines)


def _linkedin_text(text: str | None, upload: UploadFile | None) -> str | None:
    if upload is not None and upload.filename:
        content = upload.file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="LinkedIn export is larger than 5 MB.")
        try:
            return linkedin.read_export(upload.filename, content)
        except CVTextError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return text.strip() if text and text.strip() else None


def _fetch_github(username: str) -> GitHubEvidence:
    try:
        return get_github(username)
    except GitHubUserNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GitHubError as exc:
        raise HTTPException(status_code=502, detail=f"GitHub error: {exc}") from exc


def _extract_linkedin(text: str) -> ExtractedCV:
    try:
        return linkedin.skills_from_linkedin(text)
    except HANDLED as exc:
        raise http_error(exc) from exc
