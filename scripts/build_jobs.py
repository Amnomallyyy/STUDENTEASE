"""Generate data/jobs.json: 210 synthetic job listings, 70 each in Karachi, Lahore and Islamabad.

    python scripts/build_jobs.py              deterministic offline build (what is committed)
    python scripts/build_jobs.py --check      print the demo statistics without writing
    python scripts/build_jobs.py --geocode    refresh the AREAS coordinates from Nominatim first
    python scripts/build_jobs.py --extract    derive required_skills with M1's LLM extractor instead

Every listing is placed in a named real area of its city (approximate coordinates in AREAS, plus up to
1 km of jitter), carries a fictional Pakistani-sounding company, `synthetic: true` and no source URL.
Titles are built from the roles in build_roles.py so the role name is visible in the title.

`required_skills` is derived from the role's skill list with a fixed seed (core -> weight 2,
preferred -> 1) and `requirements_text` mentions every one of those skills, so M1's extractor would
find the same names. `--extract` instead runs backend.services.extractor.extract_from_text on each
text, which needs an LLM API key; the committed file used the deterministic template because that is
reproducible offline and in CI. About 70 % of the analyst-type jobs in each city require SQL, which is
what makes the demo line "14 of 20 nearby jobs ask for SQL" true for Karachi.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_roles  # noqa: E402  (sibling script)

DATA_DIR = REPO_ROOT / "data"
SEED = 42
JOBS_PER_CITY = 70
JITTER_KM = 1.0
JOB_WEIGHTS = {"core": 2, "preferred": 1}
SQL_SHARE = 0.7  # of analyst-type jobs per city
ANALYST_ROLES = {"Data Analyst", "Business Intelligence Developer", "Business Analyst"}

CITIES: dict[str, tuple[float, float]] = {
    "Karachi": (24.8607, 67.0011),
    "Lahore": (31.5204, 74.3587),
    "Islamabad": (33.6844, 73.0479),
}

# Named areas with approximate real coordinates; `--geocode` refreshes them from Nominatim. The first
# BUSINESS_DISTRICTS entries of each city are its office districts, where analyst jobs cluster.
BUSINESS_DISTRICTS = 5
BUSINESS_DISTRICT_SHARE = 0.7
AREAS: dict[str, list[tuple[str, float, float]]] = {
    "Karachi": [
        ("I.I. Chundrigar Road", 24.8480, 67.0100),
        ("Saddar", 24.8600, 67.0250),
        ("Clifton", 24.8138, 67.0300),
        ("Shahrah-e-Faisal", 24.8600, 67.0650),
        ("DHA Phase 5", 24.8010, 67.0580),
        ("Bahadurabad", 24.8780, 67.0650),
        ("Gulshan-e-Iqbal", 24.9180, 67.0971),
        ("North Nazimabad", 24.9400, 67.0400),
        ("Gulistan-e-Johar", 24.9150, 67.1300),
        ("Korangi", 24.8300, 67.1300),
    ],
    "Lahore": [
        ("Gulberg", 31.5150, 74.3450),
        ("Mall Road", 31.5600, 74.3200),
        ("Garden Town", 31.5000, 74.3150),
        ("Model Town", 31.4800, 74.3250),
        ("Lahore Cantt", 31.5100, 74.3900),
        ("DHA Phase 5", 31.4700, 74.4100),
        ("Johar Town", 31.4700, 74.2700),
        ("Faisal Town", 31.4850, 74.3000),
        ("Allama Iqbal Town", 31.5100, 74.2800),
        ("Township", 31.4500, 74.3000),
        ("Bahria Town Lahore", 31.3700, 74.1900),
    ],
    "Islamabad": [
        ("Blue Area", 33.7150, 73.0750),
        ("F-7", 33.7200, 73.0550),
        ("G-9", 33.6900, 73.0300),
        ("F-10", 33.6950, 73.0130),
        ("I-8", 33.6680, 73.0750),
        ("G-11", 33.6700, 72.9850),
        ("E-11", 33.6960, 72.9780),
        ("Gulberg Greens", 33.6050, 73.1500),
        ("DHA Islamabad", 33.5300, 73.1600),
        ("Bahria Town Rawalpindi", 33.5200, 73.1100),
        ("Saddar Rawalpindi", 33.5970, 73.0500),
    ],
}

# Fictional employers; none of these is a real company.
COMPANIES = [
    "Indus Analytics (Pvt) Ltd", "Ravi Tech Labs", "Chenab Software House", "Margalla Digital",
    "Sindh Data Works", "Karakoram Cloud Systems", "Makran Logistics Tech", "Sutlej Fintech (Pvt) Ltd",
    "Hunza Innovations", "Thar Solutions (Pvt) Ltd", "Jhelum Systems", "Potohar Software",
    "Mehran Infotech", "Salt Range Networks", "Deosai AI Labs", "Khyber Codeworks",
    "Soan Valley Analytics", "Rohi Digital Services", "Cholistan Technologies",
    "Neelum Security Consultants", "Kirthar BPO Solutions", "Swat Mobile Studio",
    "Bolan Embedded Systems", "Chitral Design Studio", "Gwadar Port Technologies",
    "Tarbela Energy Software", "Ziarat Health Informatics", "Badshahi Media Group",
    "Shalimar E-Commerce (Pvt) Ltd", "Minar Learning Technologies", "Hingol Capital Advisors",
    "Kaghan Systems Integration", "Sukkur Barrage Software", "Multan Mango Tech",
    "Quetta Rock Networks", "Faisalabad Textile ERP Solutions",
]

# Roles per city; the counts sum to JOBS_PER_CITY.
ROLE_MIX: list[tuple[str, int]] = [
    ("Data Analyst", 16), ("Business Intelligence Developer", 3), ("Business Analyst", 3),
    ("Software Engineer", 4), ("Frontend Developer", 3), ("Backend Developer", 4),
    ("Full Stack Developer", 3), ("Data Scientist", 3), ("Data Engineer", 3),
    ("Machine Learning Engineer", 2), ("AI Engineer", 2), ("Mobile App Developer", 2),
    ("DevOps Engineer", 3), ("Cloud Engineer", 2), ("QA Engineer", 2), ("Cybersecurity Analyst", 2),
    ("Database Administrator", 1), ("Network Engineer", 1), ("IT Support Specialist", 2),
    ("Product Manager", 1), ("Project Manager", 1), ("UI/UX Designer", 2),
    ("Digital Marketing Specialist", 2), ("Technical Writer", 1), ("Financial Analyst", 1),
    ("Embedded Systems Engineer", 1),
]

TITLE_PATTERNS = [
    "Junior {role}", "Associate {role}", "{role}", "{role}", "Senior {role}", "{role} (Entry Level)",
    "Trainee {role}", "Graduate {role}",
]

# What the hire will do, by role, for the second sentence of requirements_text.
ROLE_TASKS = {
    "Data Analyst": "turn sales, operations and customer data into dashboards and reports that managers act on",
    "Data Scientist": "build predictive models and run experiments that guide product and pricing decisions",
    "Data Engineer": "design and maintain the pipelines that move data from source systems into our warehouse",
    "Machine Learning Engineer": "train, evaluate and deploy machine learning models into production services",
    "AI Engineer": "build LLM-powered features and integrate them into customer-facing products",
    "Business Analyst": "gather requirements from stakeholders and translate them into clear specifications",
    "Business Intelligence Developer": "model data and build the reports and dashboards used across the company",
    "Software Engineer": "design, build and maintain reliable software across our product line",
    "Frontend Developer": "build fast, accessible user interfaces for our web applications",
    "Backend Developer": "build and scale the APIs and services behind our products",
    "Full Stack Developer": "own features end to end, from the database to the browser",
    "Mobile App Developer": "ship and maintain our Android and iOS apps",
    "DevOps Engineer": "automate our build, deployment and monitoring so releases are safe and frequent",
    "Cloud Engineer": "design and operate our cloud infrastructure and keep it secure and cost-efficient",
    "QA Engineer": "design test plans and automate regression testing for our releases",
    "Cybersecurity Analyst": "monitor our systems, investigate alerts and harden our infrastructure",
    "Database Administrator": "keep our databases fast, backed up and available",
    "Network Engineer": "design, configure and troubleshoot our office and data-centre networks",
    "IT Support Specialist": "support staff with hardware, software, accounts and network issues",
    "Product Manager": "define the product roadmap and work with engineering and design to deliver it",
    "Project Manager": "plan and deliver client projects on time and within budget",
    "UI/UX Designer": "research user needs and design the interfaces of our web and mobile products",
    "Digital Marketing Specialist": "plan and run campaigns that grow our audience and leads",
    "Technical Writer": "write and maintain the developer documentation and user guides for our products",
    "Financial Analyst": "build financial models, forecasts and budgets for the leadership team",
    "Embedded Systems Engineer": "develop firmware for our sensor and controller products",
}

OPENERS = [
    "{company} is hiring a {title} for its {area} office in {city}.",
    "{company} ({area}, {city}) is looking for a {title}.",
    "We are {company}, based in {area}, {city}, and we need a {title}.",
    "{company} has an opening for a {title} at its {area} office in {city}.",
]
MUST_HAVES = [
    "Candidates must have hands-on experience with {skills}.",
    "You should be comfortable working with {skills}.",
    "Strong skills in {skills} are essential.",
    "The role requires solid experience with {skills}.",
]
NICE_TO_HAVES = [
    "Familiarity with {skills} is a plus.",
    "Experience with {skills} would be an advantage.",
    "Knowledge of {skills} is preferred but not required.",
]


# --------------------------------------------------------------------------- generation

def build_jobs(areas: dict[str, list[tuple[str, float, float]]] = AREAS) -> list[dict]:
    """Deterministic listing generation; the same seed always gives the same file."""
    rng = random.Random(SEED)
    roles = {role["name"]: role for role in build_roles.build_roles()}
    jobs: list[dict] = []
    for city, centre in CITIES.items():
        role_names = [name for name, count in ROLE_MIX for _ in range(count)]
        rng.shuffle(role_names)
        analyst_seen = 0
        for role_name in role_names:
            # Analyst jobs follow a fixed 7-in-10 pattern so each city lands on the share exactly;
            # other roles that list SQL ask for it with the same probability.
            force_sql = None
            if role_name in ANALYST_ROLES:
                force_sql = (analyst_seen % 10) < round(SQL_SHARE * 10)
                analyst_seen += 1
            elif any(s["name"] == "SQL" for s in roles[role_name]["skills"]):
                force_sql = rng.random() < SQL_SHARE
            area = _pick_area(rng, areas[city], business=role_name in ANALYST_ROLES)
            jobs.append(_job(rng, len(jobs) + 1, city, area, roles[role_name], force_sql))
    return jobs


def _pick_area(rng: random.Random, areas: list[tuple[str, float, float]], business: bool) -> tuple[str, float, float]:
    if business and rng.random() < BUSINESS_DISTRICT_SHARE:
        return rng.choice(areas[:BUSINESS_DISTRICTS])
    return rng.choice(areas)


def _job(rng: random.Random, number: int, city: str, area: tuple[str, float, float], role: dict,
         force_sql: bool | None) -> dict:
    area_name, lat, lng = area
    lat, lng = _jitter(rng, lat, lng)
    company = rng.choice(COMPANIES)
    title = rng.choice(TITLE_PATTERNS).format(role=role["name"])
    skills = _pick_skills(rng, role, force_sql)
    return {
        "id": f"j{number}",
        "company": company,
        "title": title,
        "city": city,
        "lat": round(lat, 5),
        "lng": round(lng, 5),
        "requirements_text": _describe(rng, company, title, role["name"], area_name, city, skills),
        "required_skills": [{"name": s["name"], "category": s["category"], "weight": JOB_WEIGHTS[s["requirement"]]}
                            for s in skills],
        "source_url": None,
        "synthetic": True,
    }


def _jitter(rng: random.Random, lat: float, lng: float, max_km: float = JITTER_KM) -> tuple[float, float]:
    """Move a point up to max_km in a random direction."""
    distance = max_km * math.sqrt(rng.random())  # sqrt keeps the points evenly spread over the disc
    angle = rng.uniform(0, 2 * math.pi)
    d_lat = distance * math.cos(angle) / 111.32
    d_lng = distance * math.sin(angle) / (111.32 * math.cos(math.radians(lat)))
    return lat + d_lat, lng + d_lng


def _pick_skills(rng: random.Random, role: dict, force_sql: bool | None) -> list[dict]:
    """5-10 of the role's skills, core ones first; force_sql pins SQL in or out for analyst jobs."""
    cores = [s for s in role["skills"] if s["requirement"] == "core"]
    prefs = [s for s in role["skills"] if s["requirement"] == "preferred"]
    n_core = min(len(cores), rng.randint(4, 7))
    n_pref = min(len(prefs), rng.randint(5, 10) - n_core)
    chosen_core = rng.sample(cores, n_core)
    chosen_pref = rng.sample(prefs, max(n_pref, 0))

    if force_sql is not None:
        sql = next((s for s in role["skills"] if s["name"] == "SQL"), None)
        has_sql = any(s["name"] == "SQL" for s in chosen_core + chosen_pref)
        if force_sql and sql is not None and not has_sql:
            chosen_core = [sql] + chosen_core[:-1] if sql in cores else chosen_core
            chosen_pref = chosen_pref if sql in cores else [sql] + chosen_pref[:-1]
        elif not force_sql and has_sql:
            chosen_core = [s for s in chosen_core if s["name"] != "SQL"]
            chosen_pref = [s for s in chosen_pref if s["name"] != "SQL"]
            spare = [s for s in cores if s["name"] != "SQL" and s not in chosen_core]
            if spare:
                chosen_core.append(rng.choice(spare))
    return sorted(chosen_core, key=lambda s: role["skills"].index(s)) + sorted(
        chosen_pref, key=lambda s: role["skills"].index(s)
    )


def _describe(rng: random.Random, company: str, title: str, role_name: str, area: str, city: str,
              skills: list[dict]) -> str:
    """2-4 natural sentences that name every required skill."""
    cores = [s["name"] for s in skills if s["requirement"] == "core"]
    prefs = [s["name"] for s in skills if s["requirement"] == "preferred"]
    sentences = [
        rng.choice(OPENERS).format(company=company, title=title, area=area, city=city),
        f"You will {ROLE_TASKS[role_name]}.",
        rng.choice(MUST_HAVES).format(skills=_join(cores or prefs)),
    ]
    if cores and prefs:
        sentences.append(rng.choice(NICE_TO_HAVES).format(skills=_join(prefs)))
    return " ".join(sentences)


def _join(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


# --------------------------------------------------------------------------- optional modes

def refresh_areas() -> dict[str, list[tuple[str, float, float]]]:
    """Re-geocode every area with Nominatim; keeps the table value when a lookup finds nothing."""
    from geocode import geocode

    refreshed: dict[str, list[tuple[str, float, float]]] = {}
    for city, areas in AREAS.items():
        refreshed[city] = []
        for name, lat, lng in areas:
            query = f"{name}, Pakistan" if "Rawalpindi" in name or city in name else f"{name}, {city}, Pakistan"
            found = geocode(query)
            if found is None:
                print(f"no result for {query!r}; keeping ({lat}, {lng})", file=sys.stderr)
                found = (lat, lng)
            refreshed[city].append((name, round(found[0], 4), round(found[1], 4)))
            print(f"{query}: {refreshed[city][-1][1]}, {refreshed[city][-1][2]}")
    return refreshed


def extract_skills(jobs: list[dict]) -> None:
    """Replace required_skills with what M1's LLM extractor finds in requirements_text (needs an API key)."""
    from backend.services.extractor import extract_from_text

    weights = {
        role["name"]: {s["name"]: JOB_WEIGHTS[s["requirement"]] for s in role["skills"]}
        for role in build_roles.build_roles()
    }
    for job in jobs:
        role_name = next(name for name, _ in ROLE_MIX if name in job["title"])
        extracted = extract_from_text(job["requirements_text"])
        job["required_skills"] = [
            {"name": s.name, "category": s.category.value, "weight": weights[role_name].get(s.name, 1)}
            for s in extracted.skills
        ]


# --------------------------------------------------------------------------- checks

def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    d_lat, d_lng = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def stats(jobs: list[dict]) -> dict[str, object]:
    """The numbers the demo depends on."""
    out: dict[str, object] = {"total": len(jobs)}
    for city, (lat, lng) in CITIES.items():
        mine = [j for j in jobs if j["city"] == city]
        analysts = [j for j in mine if any(r in j["title"] for r in ANALYST_ROLES)]
        with_sql = [j for j in analysts if any(s["name"] == "SQL" for s in j["required_skills"])]
        nearest = sorted(mine, key=lambda j: haversine_km(lat, lng, j["lat"], j["lng"]))[:20]
        out[city] = {
            "jobs": len(mine),
            "data_analyst_titles": sum("Data Analyst" in j["title"] for j in mine),
            "analyst_jobs_with_sql": f"{len(with_sql)}/{len(analysts)}",
            "within_25km": sum(haversine_km(lat, lng, j["lat"], j["lng"]) <= 25 for j in mine),
            "max_km_from_centre": round(max(haversine_km(lat, lng, j["lat"], j["lng"]) for j in mine), 1),
            "nearest_20_with_sql": sum(any(s["name"] == "SQL" for s in j["required_skills"]) for j in nearest),
        }
    return out


def problems(jobs: list[dict]) -> list[str]:
    found = []
    if len({j["id"] for j in jobs}) != len(jobs):
        found.append("duplicate job ids")
    for city, (lat, lng) in CITIES.items():
        mine = [j for j in jobs if j["city"] == city]
        if sum("Data Analyst" in j["title"] for j in mine) < 15:
            found.append(f"{city}: fewer than 15 Data Analyst titles")
        if any(haversine_km(lat, lng, j["lat"], j["lng"]) > 30 for j in mine):
            found.append(f"{city}: a job is more than 30 km from the centre")
    k_lat, k_lng = CITIES["Karachi"]
    if sum(haversine_km(k_lat, k_lng, j["lat"], j["lng"]) <= 25 for j in jobs) < 20:
        found.append("fewer than 20 jobs within 25 km of Karachi centre")
    for job in jobs:
        if not 5 <= len(job["required_skills"]) <= 10:
            found.append(f"{job['id']}: {len(job['required_skills'])} required skills")
        text = job["requirements_text"].lower()
        for skill in job["required_skills"]:
            if skill["name"].lower() not in text:
                found.append(f"{job['id']}: requirements_text does not mention {skill['name']}")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="print statistics; write nothing")
    parser.add_argument("--geocode", action="store_true", help="refresh area coordinates from Nominatim first")
    parser.add_argument("--extract", action="store_true", help="derive required_skills with the LLM extractor")
    parser.add_argument("--out", type=Path, default=DATA_DIR / "jobs.json", help="output file")
    args = parser.parse_args(argv)

    areas = refresh_areas() if args.geocode else AREAS
    jobs = build_jobs(areas)
    if args.extract:
        extract_skills(jobs)
    print(json.dumps(stats(jobs), indent=2))
    issues = problems(jobs)
    for issue in issues:
        print(f"PROBLEM: {issue}", file=sys.stderr)
    if issues:
        return 1
    if args.check:
        return 0
    build_roles.write_json(args.out, jobs)
    print(f"wrote {len(jobs)} jobs to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
