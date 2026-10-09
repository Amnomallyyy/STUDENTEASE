"""Generate demo/demo_cv.pdf and demo/linkedin_export.pdf from their .txt sources.

    python scripts/make_demo_files.py          # write both PDFs and verify them
    python scripts/make_demo_files.py --check  # only verify the existing PDFs

The .txt files are the source of truth (edit those, then rerun). Verification extracts the PDF text with
pdfplumber, the same library the backend uses, and checks that the planted overclaim "Expert in Docker"
appears exactly once in the CV and that the planted skills / repos are present.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"

FILES = {
    DEMO / "demo_cv.txt": DEMO / "demo_cv.pdf",
    DEMO / "linkedin_export.txt": DEMO / "linkedin_export.pdf",
}

# Lines that start a section get a heading style; everything else is body text.
CV_HEADINGS = {"SUMMARY", "EDUCATION", "SKILLS", "PROJECTS", "EXPERIENCE"}
LINKEDIN_HEADINGS = {"Profile", "Experience", "Education", "Skills"}


def write_pdf(source: Path, target: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontName="Helvetica", fontSize=10.5, leading=14)
    heading = ParagraphStyle("heading", parent=body, fontName="Helvetica-Bold", fontSize=12, spaceBefore=8, spaceAfter=2)
    title = ParagraphStyle("title", parent=body, fontName="Helvetica-Bold", fontSize=16, leading=20, spaceAfter=4)

    lines = source.read_text(encoding="utf-8").splitlines()
    headings = CV_HEADINGS if "cv" in source.name else LINKEDIN_HEADINGS
    flow = []
    for i, raw in enumerate(lines):
        line = raw.rstrip()
        if not line:
            flow.append(Spacer(1, 4))
            continue
        text = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if i == 0:
            flow.append(Paragraph(text, title))
        elif line in headings:
            flow.append(Paragraph(text, heading))
        else:
            flow.append(Paragraph(text, body))

    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=lines[0] if lines else target.stem,
        author="CareerLens demo (synthetic)",
    )
    doc.build(flow)


def pdf_text(path: Path) -> str:
    import pdfplumber

    with pdfplumber.open(str(path)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def verify() -> list[str]:
    """Return a list of problems (empty = all good)."""
    problems: list[str] = []
    for pdf in FILES.values():
        if not pdf.is_file():
            problems.append(f"{pdf.relative_to(ROOT)} is missing")
    if problems:
        return problems

    cv = pdf_text(DEMO / "demo_cv.pdf")
    squashed = " ".join(cv.split())
    n = squashed.count("Expert in Docker")
    if n != 1:
        problems.append(f"'Expert in Docker' appears {n} times in demo_cv.pdf text (expected exactly 1)")
    if squashed.lower().count("docker") != 1:
        problems.append("'Docker' must be mentioned exactly once in the CV (overclaim rule = single mention)")
    for needle in ("Kubernetes", "Python", "Pandas", "NumPy", "Matplotlib", "Jupyter", "Excel", "Statistics", "Git",
                   "Communication", "Teamwork", "Sales Dashboard", "Student Grades Analysis", "Data Intern",
                   "Example Analytics (Pvt) Ltd", "Jun 2025 - Aug 2025"):
        if needle not in squashed:
            problems.append(f"CV text is missing '{needle}'")
    if "JavaScript" in squashed:
        problems.append("CV must not mention JavaScript (it is the planted missed strength)")

    li = " ".join(pdf_text(DEMO / "linkedin_export.pdf").split())
    for needle in ("Data Intern", "Example Analytics (Pvt) Ltd", "Jun 2025", "Aug 2025", "Python", "Pandas", "Matplotlib",
                   "Excel", "Statistics", "Git", "Communication", "Teamwork"):
        if needle not in li:
            problems.append(f"LinkedIn export text is missing '{needle}'")
    for forbidden in ("Docker", "Kubernetes", "JavaScript"):
        if forbidden.lower() in li.lower():
            problems.append(f"LinkedIn export must not mention {forbidden}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="verify the existing PDFs without regenerating them")
    args = parser.parse_args()

    if not args.check:
        for source, target in FILES.items():
            write_pdf(source, target)
            print(f"wrote {target.relative_to(ROOT)} ({target.stat().st_size} bytes)")

    problems = verify()
    for p in problems:
        print(f"PROBLEM: {p}", file=sys.stderr)
    if not problems:
        print("verified: text extracts with pdfplumber; 'Expert in Docker' appears exactly once in the CV")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
