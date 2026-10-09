"""LinkedIn evidence from the user's own "Download your data" export. This module never scrapes LinkedIn.

    read_export(filename, content)  -> str          plain text of an exported PDF or TXT
    skills_from_linkedin(text)      -> ExtractedCV  M1's extractor run on the export, every skill stamped "linkedin"
"""
from __future__ import annotations

from backend.schemas import ExtractedCV
from backend.services.cv_text import CVTextError, extract_text
from backend.services.extractor import extract_from_text

EXPORT_EXTENSIONS = {".pdf", ".txt"}


def read_export(filename: str, content: bytes) -> str:
    """Text of a LinkedIn export file. Raises CVTextError (user-safe message) for other formats or unreadable files."""
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in EXPORT_EXTENSIONS:
        raise CVTextError("Upload the LinkedIn export as a PDF or TXT file.")
    return extract_text(filename, content)


def skills_from_linkedin(text: str) -> ExtractedCV:
    """Skills, projects and experience from the export text, with `sources=["linkedin"]` on each skill."""
    result = extract_from_text(text)
    for skill in result.skills:
        skill.sources = ["linkedin"]
    return result
