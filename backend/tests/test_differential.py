from backend.schemas import Job, Skill, SkillCategory
from backend.services import differential


def skill(name: str, weight: float = 1.0) -> Skill:
    return Skill(name=name, category=SkillCategory.tool, weight=weight)


def job(job_id: str, *skill_names: str) -> Job:
    return Job(
        id=job_id,
        company="Acme",
        title=f"Role {job_id}",
        city="Karachi",
        lat=24.86,
        lng=67.0,
        required_skills=[skill(n) for n in skill_names],
    )


def test_market_gaps_count_jobs_and_rank_by_weight_and_demand(fake_embed):
    jobs = [job("a", "SQL", "Python"), job("b", "SQL"), job("c", "Tableau"), job("d", "PostgreSQL")]
    missing = [skill("SQL", weight=2), skill("Tableau", weight=2), skill("Docker", weight=2)]

    gaps = differential.market_gaps(missing, jobs)

    # SQL is required by a and b by name and by d through PostgreSQL (cosine 0.9): 3 of 4 jobs.
    assert [(g.skill, g.jobs_requiring, g.jobs_total, g.priority) for g in gaps] == [
        ("SQL", 3, 4, 1.75),
        ("Tableau", 1, 4, 1.25),
        ("Docker", 0, 4, 1.0),
    ]


def test_market_gaps_without_jobs_uses_role_weight_only(fake_embed):
    gaps = differential.market_gaps([skill("SQL", weight=2)], [])

    assert (gaps[0].jobs_requiring, gaps[0].jobs_total, gaps[0].priority) == (0, 0, 1.0)
    assert fake_embed == []


def test_score_job_reports_matched_missing_and_distance(fake_embed):
    user = [skill("Python"), skill("PostgreSQL")]

    result = differential.score_job(user, job("x", "Python", "SQL", "Tableau"), distance_km=12.3456)

    assert result.id == "x"
    assert result.matched == ["Python", "SQL"]
    assert result.missing == ["Tableau"]
    assert result.match_pct == 66.7
    assert result.distance_km == 12.35
