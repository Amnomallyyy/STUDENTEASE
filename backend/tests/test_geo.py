import pytest

from backend.schemas import Job
from backend.services.geo import haversine_km, nearby_jobs


def job_at(job_id: str, lat: float, lng: float = 67.0) -> Job:
    return Job(id=job_id, company="Acme", title="Analyst", city="Karachi", lat=lat, lng=lng)


def test_one_degree_of_latitude_is_about_111_km():
    assert haversine_km(0, 0, 1, 0) == pytest.approx(111.19, abs=0.1)


def test_same_point_is_zero():
    assert haversine_km(24.86, 67.0, 24.86, 67.0) == 0


def test_nearby_jobs_filters_by_radius_and_sorts_closest_first():
    jobs = [job_at("far", 25.86), job_at("near", 24.96), job_at("here", 24.86)]

    pairs = nearby_jobs(jobs, (24.86, 67.0), radius_km=50)

    assert [job.id for job, _ in pairs] == ["here", "near"]
    assert pairs[0][1] == 0
    assert pairs[1][1] == pytest.approx(11.1, abs=0.2)


def test_without_a_location_every_job_is_returned_at_distance_zero():
    jobs = [job_at("a", 10.0), job_at("b", 50.0)]

    assert nearby_jobs(jobs, None, radius_km=5) == [(jobs[0], 0.0), (jobs[1], 0.0)]


def test_limit_caps_the_result():
    jobs = [job_at(str(i), 24.86 + i * 0.01) for i in range(5)]

    assert len(nearby_jobs(jobs, (24.86, 67.0), radius_km=100, limit=2)) == 2
