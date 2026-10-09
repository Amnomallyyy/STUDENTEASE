"""Deterministic, explainable anomaly rules over the reconciled skill clusters.

    find_anomalies(profile_skills, projects, experience, github, linkedin, clusters) -> list[Anomaly]
    integrity_score(clusters, cv_skills) -> float | None   100 x share of CV skills backed by an external source
    explain_fixes(anomalies, context)    -> list[Anomaly]  fills suggested_fix (one LLM call, templated fallback)

Rules (each runs only when the source it needs was provided):
    unsupported_claim  CV skill with no GitHub and no LinkedIn evidence                        severity 2
    missed_strength    GitHub language with > 20 % of the code that the CV does not mention    severity 1
    weak_evidence      CV project whose repo has <= 1 commit or no README                      severity 2
    inconsistency      Same organisation on CV and LinkedIn, different title or years          severity 2
    overclaim          "expert"-style wording for a skill mentioned once with no evidence       severity 3
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from backend.llm_adapter import LLMError, complete_json
from backend.schemas import Anomaly, Experience, ExtractedCV, Project, Skill
from backend.schemas.analyzer import SkillCluster
from backend.services.evidence.github import GitHubEvidence, GitHubRepo
from backend.services.evidence.reconcile import cluster_for, has_external
from backend.services.normalize import canonical

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "anomaly_fix.md"
STRENGTH_SHARE = 0.20
YEARS_TOLERANCE = 0.5
_OVERCLAIM = re.compile(r"\b(expert|advanced|mastery|master)\b", re.IGNORECASE)


def find_anomalies(
    profile_skills: list[Skill],
    projects: list[Project],
    experience: list[Experience],
    github: GitHubEvidence | None,
    linkedin: ExtractedCV | None,
    clusters: list[SkillCluster],
) -> list[Anomaly]:
    found: list[Anomaly] = []
    if github is not None or linkedin is not None:
        overclaims = _overclaims(profile_skills, clusters, github, linkedin)
        found.extend(overclaims)
        flagged = {a.claim.lower() for a in overclaims}
        found.extend(_unsupported_claims(profile_skills, clusters, github, linkedin, skip=flagged))
    if github is not None:
        found.extend(_missed_strengths(github, clusters))
        found.extend(_weak_evidence(projects, github))
    if linkedin is not None:
        found.extend(_inconsistencies(experience, linkedin.experience))
    return sorted(found, key=lambda a: (-a.severity, a.kind, a.claim.lower()))


def integrity_score(clusters: list[SkillCluster], cv_skills: list[Skill]) -> float | None:
    """Share of CV skills with GitHub or LinkedIn backing, as a percentage. None when no external evidence exists."""
    if not cv_skills or not any(has_external(c) for c in clusters):
        return None
    backed = sum(1 for skill in cv_skills if (c := cluster_for(clusters, skill.name)) is not None and has_external(c))
    return round(100.0 * backed / len(cv_skills), 1)


# --------------------------------------------------------------------------- rules

def _sources_checked(github: GitHubEvidence | None, linkedin: ExtractedCV | None) -> str:
    parts = []
    if github is not None:
        parts.append(f"{len(github.repos)} GitHub repos")
    if linkedin is not None:
        parts.append("the LinkedIn export")
    return " or ".join(parts)


def _unsupported_claims(skills, clusters, github, linkedin, *, skip: set[str]) -> list[Anomaly]:
    out = []
    for skill in skills:
        cluster = cluster_for(clusters, skill.name)
        if skill.name.lower() in skip or (cluster is not None and has_external(cluster)):
            continue
        out.append(
            _anomaly(
                "unsupported_claim",
                skill.name,
                f"{skill.name} is on the CV but appears in none of {_sources_checked(github, linkedin)}.",
                severity=2,
            )
        )
    return out


def _missed_strengths(github: GitHubEvidence, clusters: list[SkillCluster]) -> list[Anomaly]:
    out = []
    for language, share in github.language_share.items():
        if share <= STRENGTH_SHARE:
            continue
        cluster = cluster_for(clusters, language)
        if cluster is not None and "cv" in cluster.sources:
            continue
        repos = [r.name for r in github.repos if language in r.languages]
        out.append(
            _anomaly(
                "missed_strength",
                canonical(language),
                f"{canonical(language)} is {round(100 * share)}% of the code in your GitHub repos "
                f"({', '.join(repos[:3])}) but is not on the CV.",
                severity=1,
            )
        )
    return out


def _weak_evidence(projects: list[Project], github: GitHubEvidence) -> list[Anomaly]:
    repos = {_slug(r.name): r for r in github.repos}
    out = []
    for project in projects:
        repo = repos.get(_slug(project.name))
        if repo is None or not _is_weak(repo):
            continue
        problems = []
        if repo.commit_count <= 1:
            problems.append(f"only {repo.commit_count} commit{'' if repo.commit_count == 1 else 's'}")
        if not repo.readme.strip():
            problems.append("no README")
        out.append(
            _anomaly(
                "weak_evidence",
                project.name,
                f"The GitHub repo {repo.name} for this project has {' and '.join(problems)}.",
                severity=2,
            )
        )
    return out


def _is_weak(repo: GitHubRepo) -> bool:
    return repo.commit_count <= 1 or not repo.readme.strip()


def _inconsistencies(cv: list[Experience], linkedin: list[Experience]) -> list[Anomaly]:
    by_org = {_slug(e.organisation): e for e in linkedin if e.organisation.strip()}
    out = []
    for item in cv:
        other = by_org.get(_slug(item.organisation)) if item.organisation.strip() else None
        if other is None:
            continue
        reasons = []
        if _title_key(item.title) != _title_key(other.title):
            reasons.append(f"the title is '{item.title}' on the CV and '{other.title}' on LinkedIn")
        if item.years is not None and other.years is not None and abs(item.years - other.years) > YEARS_TOLERANCE:
            reasons.append(f"the CV says {item.years:g} years and LinkedIn {other.years:g}")
        if reasons:
            out.append(
                _anomaly(
                    "inconsistency",
                    f"{item.title} at {item.organisation}",
                    f"For {item.organisation}, {' and '.join(reasons)}.",
                    severity=2,
                )
            )
    return out


def _overclaims(skills, clusters, github, linkedin) -> list[Anomaly]:
    out = []
    for skill in skills:
        quote = next((q for q in skill.evidence if _OVERCLAIM.search(q)), None)
        if quote is None:
            continue
        cluster = cluster_for(clusters, skill.name)
        if cluster is not None and (cluster.mention_count > 1 or has_external(cluster)):
            continue
        out.append(
            _anomaly(
                "overclaim",
                skill.name,
                f"The CV says \"{quote}\" but {skill.name} is mentioned only once and appears in none of "
                f"{_sources_checked(github, linkedin)}.",
                severity=3,
            )
        )
    return out


def _anomaly(kind: str, claim: str, evidence: str, *, severity: int) -> Anomaly:
    return Anomaly(id=f"{kind}:{_slug(claim)}", kind=kind, claim=claim, evidence=evidence, severity=severity)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _title_key(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", text.lower()).strip()


# --------------------------------------------------------------------------- suggested fixes

class AnomalyFix(BaseModel):
    id: str
    why_it_matters: str = Field(default="", description="One sentence, recruiter's view.")
    fix: str = Field(description="One concrete CV edit.")


class AnomalyFixes(BaseModel):
    fixes: list[AnomalyFix] = Field(default_factory=list)


def explain_fixes(anomalies: list[Anomaly], context: str) -> list[Anomaly]:
    """Fill `suggested_fix` on every anomaly with one LLM call; fall back to templates when it fails."""
    if not anomalies:
        return anomalies
    by_id: dict[str, AnomalyFix] = {}
    try:
        reply = complete_json(_prompt(anomalies, context), AnomalyFixes, max_tokens=1500)
        by_id = {fix.id: fix for fix in reply.fixes if fix.fix.strip()}
    except LLMError:
        pass  # the templated fixes below keep the demo working offline
    out = []
    for anomaly in anomalies:
        fix = by_id.get(anomaly.id)
        text = f"{fix.why_it_matters.strip()} {fix.fix.strip()}".strip() if fix else _template(anomaly)
        out.append(anomaly.model_copy(update={"suggested_fix": text}))
    return out


def _prompt(anomalies: list[Anomaly], context: str) -> str:
    items = [{"id": a.id, "kind": a.kind, "claim": a.claim, "evidence": a.evidence} for a in anomalies]
    safe_context = context.replace("</context>", "")[:6000]
    return (
        f"{_instructions()}\n\n<context>\n{safe_context}\n</context>\n\n"
        f"<anomalies>\n{json.dumps(items, indent=1)}\n</anomalies>"
    )


@lru_cache(maxsize=1)
def _instructions() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _template(anomaly: Anomaly) -> str:
    claim = anomaly.claim
    if anomaly.kind == "unsupported_claim":
        return (
            f"Recruiters check skills against public work, and nothing backs {claim}. "
            f"Add a project that shows {claim} or move it to a 'Currently learning' line."
        )
    if anomaly.kind == "missed_strength":
        repos = re.search(r"\(([^)]+)\)", anomaly.evidence)
        where = f" the {repos.group(1).split(',')[0].strip()} repo" if repos else " the matching repo"
        return f"{claim} is a real strength the CV hides. Add{where} under Projects and list {claim} in Skills."
    if anomaly.kind == "weak_evidence":
        return (
            f"A near-empty repo makes the '{claim}' project look unfinished. "
            "Add a README that explains what it does and push the working code before linking it."
        )
    if anomaly.kind == "inconsistency":
        return (
            "Mismatched job details between the CV and LinkedIn look careless. "
            f"Make the title and dates for '{claim}' identical on both."
        )
    if anomaly.kind == "overclaim":
        return (
            f"'Expert' wording for {claim} invites hard interview questions you may not want. "
            f"Change it to 'Familiar with {claim}' unless you can show expert-level work."
        )
    return f"Review the claim '{claim}' and make sure the CV can back it up."
