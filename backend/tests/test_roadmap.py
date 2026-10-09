import pytest

from backend.llm_adapter import LLMError
from backend.schemas import Job, MarketGap, Resource, Roadmap, RoadmapTask, RoadmapWeek
from backend.services import roadmap as roadmap_service

GAPS = [
    MarketGap(skill="SQL", jobs_requiring=3, jobs_total=4, priority=1.75),
    MarketGap(skill="Tableau", jobs_requiring=1, jobs_total=4, priority=1.25),
    MarketGap(skill="Docker", jobs_requiring=0, jobs_total=4, priority=1.0),
]
RESOURCES = {
    "sql": [Resource(title="SQL Basics", url="https://example.org/sql", hours=6)],
    "tableau": [Resource(title="Tableau Intro", url="https://example.org/tableau", hours=5)],
}
PINNED = Job(id="j1", company="Acme", title="BI Analyst", city="Karachi", lat=24.86, lng=67.0)


def fake_llm(monkeypatch, draft: Roadmap | Exception):
    def fake(prompt, schema, **kwargs):
        if isinstance(draft, Exception):
            raise draft
        return draft

    monkeypatch.setattr(roadmap_service, "complete_json", fake)


def test_reprioritise_boosts_pinned_skills_and_adds_unknown_ones():
    ordered = roadmap_service.reprioritise(GAPS, ["Docker", "Git"])

    assert [(g.skill, g.priority) for g in ordered] == [
        ("Docker", 2.0),
        ("SQL", 1.75),
        ("Tableau", 1.25),
        ("Git", 1.0),
    ]


def test_fallback_gives_one_skill_per_week_with_whitelisted_links():
    plan = roadmap_service.fallback_roadmap(GAPS, RESOURCES, pinned_job_id="j1")

    assert plan.pinned_job_id == "j1"
    assert [w.week for w in plan.weeks] == [1, 2, 3]
    first = plan.weeks[0].tasks[0]
    assert (first.title, first.resource_url, first.hours) == ("SQL Basics", "https://example.org/sql", 6)
    last = plan.weeks[2].tasks[0]
    assert (last.title, last.resource_url, last.hours) == ("Learn Docker fundamentals", None, 4.0)


def test_fallback_never_makes_more_than_four_weeks():
    many = [MarketGap(skill=f"S{i}", jobs_requiring=0, jobs_total=0, priority=1.0) for i in range(8)]

    plan = roadmap_service.fallback_roadmap(many, {})

    assert len(plan.weeks) == 4
    assert sum(len(w.tasks) for w in plan.weeks) == 8


def test_llm_plan_is_cleaned_against_the_whitelist(monkeypatch):
    draft = Roadmap(
        weeks=[
            RoadmapWeek(
                week=1,
                focus="SQL",
                tasks=[
                    RoadmapTask(title="Do the course", skill="SQL", resource_url="https://example.org/sql"),
                    RoadmapTask(title="Invented link", skill="SQL", resource_url="https://evil.example/x", done=True),
                ],
            )
        ]
    )
    fake_llm(monkeypatch, draft)

    plan = roadmap_service.build_roadmap(GAPS, RESOURCES, role="Data Analyst", pinned_job=PINNED, pinned_missing=["SQL"])

    tasks = plan.weeks[0].tasks
    assert tasks[0].resource_url == "https://example.org/sql"
    assert tasks[1].resource_url is None
    assert tasks[1].done is False
    assert plan.pinned_job_id == "j1"


@pytest.mark.parametrize(
    "draft",
    [LLMError("provider down"), Roadmap(weeks=[RoadmapWeek(week=1, focus="x", tasks=[])])],
    ids=["llm-error", "no-tasks"],
)
def test_unusable_llm_output_falls_back_to_the_deterministic_plan(monkeypatch, draft):
    fake_llm(monkeypatch, draft)

    plan = roadmap_service.build_roadmap(GAPS, RESOURCES, role="Data Analyst")

    assert [w.week for w in plan.weeks] == [1, 2, 3]


def test_no_gaps_means_no_llm_call(monkeypatch):
    fake_llm(monkeypatch, AssertionError("LLM must not be called without gaps"))

    plan = roadmap_service.build_roadmap([], RESOURCES, role="Data Analyst")

    assert plan.weeks == []
