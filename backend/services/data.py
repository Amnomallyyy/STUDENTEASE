"""Loaders for the committed datasets owned by M5: data/roles.json, data/jobs.json, data/resources.json.

Formats are described in docs/data_formats.md. Paths can be overridden with ROLES_PATH, JOBS_PATH and
RESOURCES_PATH. Files are read once and cached; call reload_data() after they change.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.schemas import Job, Resource, Role

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class DataError(RuntimeError):
    """A dataset file is present but unusable (bad JSON or wrong shape)."""


class DataMissing(DataError):
    """A dataset file has not been created yet."""


class RoleNotFound(LookupError):
    pass


class JobNotFound(LookupError):
    pass


def _read(env_var: str, filename: str) -> tuple[str, Any]:
    path = Path(os.getenv(env_var, str(DATA_DIR / filename)))
    if not path.is_file():
        raise DataMissing(f"{path.name} not found at {path}")
    try:
        return path.name, json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataError(f"{path.name} is not valid JSON: {exc}") from exc


def _validate_list(model, items: Any, name: str) -> list:
    if not isinstance(items, list):
        raise DataError(f"{name} must be a JSON list")
    try:
        return [model.model_validate(item) for item in items]
    except ValidationError as exc:
        raise DataError(f"{name} is malformed: {exc}") from exc


@lru_cache(maxsize=1)
def _roles() -> tuple[Role, ...]:
    name, raw = _read("ROLES_PATH", "roles.json")
    return tuple(_validate_list(Role, raw, name))


@lru_cache(maxsize=1)
def _jobs() -> tuple[Job, ...]:
    name, raw = _read("JOBS_PATH", "jobs.json")
    return tuple(_validate_list(Job, raw, name))


@lru_cache(maxsize=1)
def _resources() -> dict[str, tuple[Resource, ...]]:
    name, raw = _read("RESOURCES_PATH", "resources.json")
    if not isinstance(raw, dict):
        raise DataError(f"{name} must be a JSON object of skill -> list of resources")
    return {skill.strip().lower(): tuple(_validate_list(Resource, items, name)) for skill, items in raw.items()}


def load_roles() -> list[Role]:
    return list(_roles())


def load_jobs() -> list[Job]:
    return list(_jobs())


def load_resources() -> dict[str, list[Resource]]:
    """Whitelisted learning links, keyed by lower-case skill name."""
    return {skill: list(items) for skill, items in _resources().items()}


def find_role(name: str) -> Role:
    key = name.strip().lower()
    roles = load_roles()
    for role in roles:
        if key in (role.id.lower(), role.name.lower()):
            return role
    raise RoleNotFound(f"Unknown role '{name}'. Available: {', '.join(r.name for r in roles)}")


def find_job(job_id: str) -> Job:
    for job in load_jobs():
        if job.id == job_id:
            return job
    raise JobNotFound(f"Unknown job id '{job_id}'")


def reload_data() -> None:
    _roles.cache_clear()
    _jobs.cache_clear()
    _resources.cache_clear()
