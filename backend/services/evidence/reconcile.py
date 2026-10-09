"""Cross-source skill reconciliation: the same skill from the CV, GitHub and LinkedIn becomes one cluster.

    reconcile(cv, github, linkedin) -> list[SkillCluster]
    cluster_for(clusters, name)     -> SkillCluster | None   lookup by any member spelling

Skills are grouped by canonical name first (alias table), then clusters whose names embed within
matcher.MATCH_THRESHOLD cosine of each other are merged, so "Jupyter" and "Jupyter Notebook" count as
one skill even without an alias entry.
"""
from __future__ import annotations

from backend.schemas import Skill
from backend.schemas.analyzer import SkillCluster
from backend.services import matcher
from backend.services.normalize import canonical

EXTERNAL_SOURCES = ("github", "linkedin")


def reconcile(cv: list[Skill], github: list[Skill], linkedin: list[Skill]) -> list[SkillCluster]:
    """Merge the three skill lists into clusters; CV clusters come first and keep the CV spelling."""
    clusters = _by_canonical_name(cv, github, linkedin)
    return _merge_similar(clusters)


def cluster_for(clusters: list[SkillCluster], name: str) -> SkillCluster | None:
    """The cluster that holds `name` under any of its spellings."""
    wanted = {name.strip().lower(), canonical(name).lower()}
    for cluster in clusters:
        spellings = {cluster.name.lower(), *(m.lower() for m in cluster.members), *(canonical(m).lower() for m in cluster.members)}
        if wanted & spellings:
            return cluster
    return None


def has_external(cluster: SkillCluster) -> bool:
    return any(source in EXTERNAL_SOURCES for source in cluster.sources)


def _by_canonical_name(*groups: list[Skill]) -> list[SkillCluster]:
    clusters: dict[str, SkillCluster] = {}
    for group in groups:
        for skill in group:
            name = canonical(skill.name)
            key = name.lower()
            mentions = max(1, len(skill.evidence))
            cluster = clusters.get(key)
            if cluster is None:
                clusters[key] = SkillCluster(
                    name=name, sources=list(skill.sources or ["cv"]), members=[skill.name.strip()], mention_count=mentions
                )
                continue
            if skill.name.strip() not in cluster.members:
                cluster.members.append(skill.name.strip())
            for source in skill.sources or ["cv"]:
                if source not in cluster.sources:
                    cluster.sources.append(source)
            cluster.mention_count += mentions
    return list(clusters.values())


def _merge_similar(clusters: list[SkillCluster]) -> list[SkillCluster]:
    """Fold each cluster into an earlier one whose name is a near-synonym by embedding.

    Two clusters that both come from the CV are never merged: the CV lists them as distinct skills,
    and collapsing them would silently change the integrity score's denominator.
    """
    if len(clusters) < 2:
        return clusters
    vectors = dict(zip([c.name for c in clusters], matcher.embed_cached([c.name for c in clusters])))
    merged: list[SkillCluster] = []
    for cluster in clusters:
        target = next(
            (
                kept
                for kept in merged
                if not ("cv" in kept.sources and "cv" in cluster.sources)
                and matcher.cosine(vectors[kept.name], vectors[cluster.name]) >= matcher.MATCH_THRESHOLD
            ),
            None,
        )
        if target is None:
            merged.append(cluster)
            continue
        for member in cluster.members:
            if member not in target.members:
                target.members.append(member)
        for source in cluster.sources:
            if source not in target.sources:
                target.sources.append(source)
        target.mention_count += cluster.mention_count
    return merged
