#!/usr/bin/env python3
"""Render a docs-local Markdown file to a matching PDF.

Usage: python scripts/generate_sprint_today_pdf.py [BASENAME]   (default SPRINT_TODAY)

Deliberately a small Markdown subset — headings, paragraphs, bullets, tables,
fenced code and bold/inline-code spans — which is all SPRINT_TODAY.md uses.
Styling follows scripts/generate_plan_pdfs.py so the two docs look like a set.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
NAME = sys.argv[1] if len(sys.argv) > 1 else "SPRINT_TODAY"
SRC = ROOT / "docs-local" / f"{NAME}.md"
OUT = ROOT / "docs-local" / f"{NAME}.pdf"

NAVY = colors.HexColor("#1a365d")
SLATE = colors.HexColor("#2d3748")
LIGHT = colors.HexColor("#edf2f7")
ACCENT = colors.HexColor("#2b6cb0")
BORDER = colors.HexColor("#cbd5e0")
CODEBG = colors.HexColor("#f7fafc")


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "T", parent=base["Title"], fontName="Helvetica-Bold", fontSize=14,
            leading=17, textColor=NAVY, spaceAfter=8, alignment=TA_CENTER),
        "h1": ParagraphStyle(
            "H1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=11,
            leading=13, textColor=NAVY, spaceBefore=12, spaceAfter=5),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=9,
            leading=11, textColor=ACCENT, spaceBefore=8, spaceAfter=3),
        "body": ParagraphStyle(
            "B", parent=base["Normal"], fontSize=7.5, leading=10, textColor=SLATE,
            spaceAfter=4),
        "bullet": ParagraphStyle(
            "L", parent=base["Normal"], fontSize=7.5, leading=10, textColor=SLATE,
            leftIndent=12, bulletIndent=4, spaceAfter=2),
        "cell": ParagraphStyle(
            "C", parent=base["Normal"], fontSize=6.8, leading=8.5, textColor=SLATE),
        "cellhead": ParagraphStyle(
            "CH", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=6.8,
            leading=8.5, textColor=colors.white),
        "code": ParagraphStyle(
            "P", parent=base["Code"], fontName="Courier", fontSize=6.5, leading=8,
            textColor=SLATE, leftIndent=8),
    }


def inline(text: str) -> str:
    """Markdown inline spans -> reportlab markup, escaping XML first."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`(.+?)`", r'<font face="Courier" size="7">\1</font>', text)
    return text


def make_table(rows: list[list[str]], st) -> Table:
    head = [Paragraph(inline(c), st["cellhead"]) for c in rows[0]]
    body = [[Paragraph(inline(c), st["cell"]) for c in r] for r in rows[1:]]
    table = Table([head] + body, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_separator(line: str) -> bool:
    return bool(re.fullmatch(r"\|[\s:|-]+\|", line.strip()))


def build(md: str, st) -> list:
    flow: list = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped or set(stripped) == {"-"} and len(stripped) >= 3:
            i += 1
            continue

        if stripped.startswith("```"):
            block: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            # reportlab's Preformatted raises on an empty body, and a fence with
            # only blank lines carries nothing worth rendering anyway.
            if not any(ln.strip() for ln in block):
                continue
            pre = Preformatted("\n".join(block), st["code"])
            wrap = Table([[pre]], hAlign="LEFT")
            wrap.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), CODEBG),
                ("BOX", (0, 0), (-1, -1), 0.4, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            flow += [Spacer(1, 3), wrap, Spacer(1, 5)]
            continue

        if stripped.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                if not is_separator(lines[i]):
                    rows.append(split_row(lines[i]))
                i += 1
            if rows:
                flow += [Spacer(1, 3), make_table(rows, st), Spacer(1, 6)]
            continue

        if stripped.startswith("### "):
            flow.append(Paragraph(inline(stripped[4:]), st["h2"]))
        elif stripped.startswith("## "):
            flow.append(Paragraph(inline(stripped[3:]), st["h1"]))
        elif stripped.startswith("# "):
            flow.append(Paragraph(inline(stripped[2:]), st["title"]))
        elif stripped.startswith("- "):
            flow.append(Paragraph(inline(stripped[2:]), st["bullet"], bulletText="•"))
        elif re.match(r"^\d+\.\s", stripped):
            num, rest = stripped.split(".", 1)
            flow.append(Paragraph(inline(rest.strip()), st["bullet"], bulletText=f"{num}."))
        else:
            flow.append(Paragraph(inline(stripped), st["body"]))
        i += 1

    return flow


def main() -> None:
    st = styles()
    doc = SimpleDocTemplate(
        str(OUT), pagesize=letter,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.5 * inch, bottomMargin=0.5 * inch,
        title=f"ThesisLedger — {NAME}",
    )
    doc.build(build(SRC.read_text(encoding="utf-8"), st))
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
