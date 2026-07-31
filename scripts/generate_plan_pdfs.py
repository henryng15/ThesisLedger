#!/usr/bin/env python3
"""Generate ThesisLedger 3-dev sprint PDF — balanced B/C, C does deploy."""

from __future__ import annotations
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs-local"

NAVY = colors.HexColor("#1a365d")
SLATE = colors.HexColor("#2d3748")
LIGHT = colors.HexColor("#edf2f7")
ACCENT = colors.HexColor("#2b6cb0")
BORDER = colors.HexColor("#cbd5e0")
GREEN = colors.HexColor("#276749")
YELLOW = colors.HexColor("#b7791f")


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("Title", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=14, leading=17, textColor=NAVY, spaceAfter=4, alignment=TA_CENTER),
        "subtitle": ParagraphStyle("Subtitle", parent=base["Normal"], fontSize=8, leading=10,
            textColor=SLATE, alignment=TA_CENTER, spaceAfter=10),
        "h1": ParagraphStyle("H1", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=11, leading=13, textColor=NAVY, spaceBefore=10, spaceAfter=4),
        "h2": ParagraphStyle("H2", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=9, leading=11, textColor=ACCENT, spaceBefore=6, spaceAfter=3),
        "body": ParagraphStyle("Body", parent=base["Normal"], fontSize=7.5, leading=9.5,
            textColor=SLATE, spaceAfter=3),
        "cell": ParagraphStyle("Cell", parent=base["Normal"], fontSize=6.5, leading=8, textColor=SLATE),
        "cell_head": ParagraphStyle("CellHead", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=6.5, leading=8, textColor=colors.white),
        "note": ParagraphStyle("Note", parent=base["Normal"], fontSize=7, leading=9,
            textColor=SLATE, leftIndent=10, spaceAfter=2),
    }


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(0.4*inch, 0.4*inch, letter[0]-0.4*inch, 0.4*inch)
    canvas.setFont("Helvetica", 6)
    canvas.setFillColor(colors.grey)
    canvas.drawString(0.4*inch, 0.25*inch, "ThesisLedger — 2-Day Sprint (3 Devs) + Production Deploy")
    canvas.drawRightString(letter[0]-0.4*inch, 0.25*inch, f"Page {doc.page}")
    canvas.restoreState()


def task_table(headers, rows, s, col_widths):
    data = [[Paragraph(f"<b>{h}</b>", s["cell_head"]) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), s["cell"]) for c in row])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.3, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def build_pdf(path: Path, s):
    doc = SimpleDocTemplate(str(path), pagesize=letter,
        leftMargin=0.4*inch, rightMargin=0.4*inch, topMargin=0.4*inch, bottomMargin=0.55*inch)
    story = []
    w = letter[0] - 0.8*inch

    # Title
    story.append(Paragraph("ThesisLedger — 2-Day Sprint (3 Devs) + Production Deploy", s["title"]))
    story.append(Paragraph(
        "A: Backend + LangGraph + kind (~23h) · B: Frontend + Demo (~18.5h) · C: Data + Eval + Deploy (~19h)<br/>"
        "LLM: Ollama (local) + Oracle Cloud (prod) · Independence: Minimize blocking", s["subtitle"]))

    # Production Stack
    story.append(Paragraph("Production Stack (Oracle Cloud Always Free)", s["h1"]))
    story.append(task_table(
        ["Component", "Service", "Notes"],
        [["<b>VM</b>", "Oracle Cloud ARM (Ampere A1)", "4 vCPU, 24GB RAM, Always Free"],
         ["<b>LLM</b>", "Ollama on VM (llama3.2:3b)", "C sets up Ollama on VM"],
         ["<b>Embeddings</b>", "nomic-embed-text via Ollama", "768-dim vectors"],
         ["<b>Database</b>", "PostgreSQL + pgvector on VM", "In Docker Compose"],
         ["<b>Queue</b>", "Redis on VM", "Celery broker + cache"],
         ["<b>Reverse Proxy</b>", "Caddy (auto HTTPS)", "Or Nginx"],
         ["<b>Frontend</b>", "Next.js on VM", "SSR via Compose"]],
        s, [0.8*inch, w*0.4, w*0.45]))

    # Dependency Analysis
    story.append(Paragraph("Dependency Analysis (Minimal Blocking)", s["h1"]))
    story.append(task_table(
        ["From", "To", "What", "When", "Blocking?"],
        [["C", "A", "data/raw/ files", "Day 1 morning", "<font color='#276749'>No — A starts Job API first</font>"],
         ["A", "B", "Job API endpoints", "Day 1 ~11am", "<font color='#b7791f'>~2h — B does UI prep</font>"],
         ["A", "C", "docker-compose.prod.yml", "Day 2 ~12pm", "<font color='#b7791f'>C preps VM meanwhile</font>"],
         ["C", "B", "Production URL", "Day 2 ~4pm", "<font color='#b7791f'>~2h — B does kind demo</font>"]],
        s, [0.4*inch, 0.4*inch, w*0.32, 0.85*inch, w*0.23]))

    # Companies
    story.append(Paragraph("Target Companies (50)", s["h1"]))
    story.append(Paragraph(
        "<b>Tech:</b> AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, AVGO, ORCL, CRM, AMD, INTC · "
        "<b>Finance:</b> JPM, V, MA, BAC, WFC, GS, MS, BLK, AXP, SCHW · "
        "<b>Healthcare:</b> UNH, JNJ, LLY, PFE, ABBV, MRK, TMO, ABT · "
        "<b>Consumer:</b> WMT, PG, KO, PEP, COST, MCD, NKE, SBUX · "
        "<b>Industrial:</b> XOM, CVX, CAT, BA, UPS, HON, GE · "
        "<b>Media:</b> DIS, NFLX, CMCSA, T, VZ", s["body"]))

    # ========== DEVELOPER A ==========
    story.append(PageBreak())
    story.append(Paragraph("Developer A — Backend + LangGraph + kind (heaviest, ~23h)", s["h1"]))
    story.append(Paragraph("Focus: Django API, Celery/Redis, SEC ingest, embeddings, LangGraph, Compose file, kind", s["body"]))
    
    story.append(Paragraph("Day 1 Tasks", s["h2"]))
    story.append(task_table(
        ["#", "Task", "File(s)", "Depends", "Est."],
        [["A1", "Real AnalysisJob lifecycle", "views.py, services.py", "<font color='#276749'>None</font>", "2h"],
         ["A2", "Mock evidence writer", "services.py", "A1", "1h"],
         ["A3", "GET /jobs/{id}/ from DB", "views.py, serializers.py", "A1", "1.5h"],
         ["A4", "Celery app + Redis broker", "config/celery.py, settings.py", "<font color='#276749'>None</font>", "1h"],
         ["A5", "AnalysisJob Celery task", "tasks.py", "A4", "1.5h"],
         ["A6", "Redis cache-aside", "cache.py", "A4", "1h"],
         ["A7", "search_chunks() stub", "ingestion/search.py", "<font color='#276749'>None</font>", "0.5h"],
         ["A8", "SEC filing cleaner", "ingestion/cleaner.py", "<font color='#b7791f'>C's files</font>", "2h"]],
        s, [0.3*inch, w*0.36, w*0.22, 0.75*inch, 0.4*inch]))

    story.append(Paragraph("Day 2 Tasks", s["h2"]))
    story.append(task_table(
        ["#", "Task", "File(s)", "Depends", "Est."],
        [["A9", "Finish ingest + management cmd", "ingestion/ingest.py", "A8", "1.5h"],
         ["A10", "Embeddings: Ollama", "ingestion/embeddings.py", "A9", "1.5h"],
         ["A11", "Real search_chunks (pgvector)", "ingestion/search.py", "A10", "1h"],
         ["A12", "generate_claims() — LangGraph", "rag/extraction.py", "<font color='#276749'>None</font>", "1.5h"],
         ["A13", "classify_claim() — LangGraph", "rag/classification.py", "A11", "1.5h"],
         ["A14", "Full LangGraph pipeline", "rag/graph.py", "A12,A13", "1.5h"],
         ["A15", "Wire AI into API", "services.py", "A14", "1h"],
         ["A16", "<b>Compose prod (for C)</b>", "docker-compose.prod.yml, Caddyfile", "A15", "1.5h"],
         ["A17", "kind manifests", "k8s/*.yaml", "A16", "1.5h"],
         ["A18", "scripts/seed.py", "scripts/seed.py", "A9", "0.5h"]],
        s, [0.3*inch, w*0.38, w*0.24, 0.72*inch, 0.4*inch]))
    story.append(Paragraph("<b>Day 2 EOD:</b> LangGraph done, Compose ready by noon for C, kind ready", s["note"]))

    # ========== DEVELOPER B ==========
    story.append(PageBreak())
    story.append(Paragraph("Developer B — Frontend + Demo (~18.5h)", s["h1"]))
    story.append(Paragraph("Focus: Next.js frontend, Compose frontend, demo (test on C's prod URL), <b>eval/README</b>", s["body"]))
    
    story.append(Paragraph("Day 1 Tasks", s["h2"]))
    story.append(task_table(
        ["#", "Task", "File(s)", "Depends", "Est."],
        [["B1", "Refactor EvidenceCard", "components/EvidenceCard.tsx", "<font color='#276749'>None</font>", "1.5h"],
         ["B2", "Add ProgressBar", "components/ProgressBar.tsx", "<font color='#276749'>None</font>", "1h"],
         ["B3", "Handle all job states", "jobs/[id]/page.tsx", "<font color='#276749'>None</font>", "1.5h"],
         ["B4", "Poll real jobs from API", "jobs/[id]/page.tsx", "<font color='#b7791f'>A's API</font>", "1.5h"],
         ["B5", "Error toasts, loading states", "components/*, globals.css", "<font color='#276749'>None</font>", "1h"],
         ["B6", "UI polish (status colors)", "*.css, *.tsx", "<font color='#276749'>None</font>", "1.5h"],
         ["B7", "Screenshots mock flow", "docs-local/screenshots/", "B4", "1h"]],
        s, [0.3*inch, w*0.36, w*0.25, 0.8*inch, 0.4*inch]))

    story.append(Paragraph("Day 2 Tasks", s["h2"]))
    story.append(task_table(
        ["#", "Task", "File(s)", "Depends", "Est."],
        [["B8", "Frontend Dockerfile", "frontend/Dockerfile", "<font color='#276749'>None</font>", "1h"],
         ["B9", "Compose frontend service", "docker-compose.yml", "B8", "0.5h"],
         ["B10", "Wire NEXT_PUBLIC_API_BASE_URL", "frontend/.env, config.ts", "B9", "0.5h"],
         ["B11", "UI polish (responsive web)", "*.css, *.tsx", "<font color='#276749'>None</font>", "1.5h"],
         ["B12", "<b>eval/README.md</b> (from C)", "eval/README.md", "<font color='#b7791f'>C's eval</font>", "0.5h"],
         ["B13", "kind parallel-job demo", "—", "<font color='#b7791f'>A's kind</font>", "1h"],
         ["B14", "Demo script", "docs-local/DEMO_SCRIPT.md", "<font color='#276749'>None</font>", "1h"],
         ["B15", "<b>Test on production URL</b>", "—", "<font color='#b7791f'>C's deploy</font>", "1h"],
         ["B16", "Demo GIF / screenshots (prod)", "docs-local/", "B15", "1.5h"],
         ["B17", "Dry run ×2", "—", "All above", "1h"]],
        s, [0.3*inch, w*0.36, w*0.25, 0.8*inch, 0.4*inch]))
    story.append(Paragraph("<b>Note:</b> B12 (eval/README) moved from C for balance. B writes after testing C's eval.", s["note"]))

    # ========== DEVELOPER C ==========
    story.append(PageBreak())
    story.append(Paragraph("Developer C — Data + Eval + Ollama + Deploy (~19h)", s["h1"]))
    story.append(Paragraph("Focus: Download 50 SEC filings, Ollama, Oracle Cloud deploy, eval, <b>architecture diagram</b>", s["body"]))
    
    story.append(Paragraph("Day 1 Tasks", s["h2"]))
    story.append(task_table(
        ["#", "Task", "File(s)", "Depends", "Est."],
        [["C1", "Download SEC filings (50 cos)", "scripts/download_filings.py", "<font color='#276749'>None</font>", "3h"],
         ["C2", "Organize data/raw/", "data/raw/{TICKER}/", "C1", "0.5h"],
         ["C3", "data/raw/README.md", "data/raw/README.md", "C1", "0.5h"],
         ["C4", "Ollama Compose service", "docker-compose.yml", "<font color='#276749'>None</font>", "1h"],
         ["C5", "Model pull script", "scripts/setup_ollama.sh", "C4", "0.5h"],
         ["C6", "LLM Setup docs", "docs-local/LLM_SETUP.md", "C4", "0.5h"],
         ["C7", "<b>Oracle Cloud account + VM</b>", "—", "<font color='#276749'>None</font>", "1.5h"],
         ["C8", "Start eval set (~10 pairs)", "eval/claims.json", "<font color='#276749'>None</font>", "1.5h"]],
        s, [0.3*inch, w*0.38, w*0.24, 0.8*inch, 0.4*inch]))

    story.append(Paragraph("Day 2 Tasks", s["h2"]))
    story.append(task_table(
        ["#", "Task", "File(s)", "Depends", "Est."],
        [["C9", "Finish eval set (~20 pairs)", "eval/claims.json", "C8", "1.5h"],
         ["C10", "Eval runner script", "eval/runner.py", "C9", "1.5h"],
         ["C11", "Retrieval + accuracy metrics", "eval/runner.py", "C10", "1h"],
         ["C12", "<b>Architecture diagram</b> (from B)", "docs-local/architecture.png", "<font color='#276749'>None</font>", "1h"],
         ["C13", "<b>Deploy to Oracle Cloud</b>", "scripts/deploy/", "<font color='#b7791f'>A's compose</font>", "1.5h"],
         ["C14", "Pull models + seed on VM", "—", "C13", "1h"],
         ["C15", "README sections", "README.md", "<font color='#276749'>None</font>", "0.5h"],
         ["C16", "<b>Run eval on production</b>", "—", "C14", "1h"],
         ["C17", "Final metrics for demo", "docs-local/METRICS.md", "C16", "0.5h"]],
        s, [0.3*inch, w*0.38, w*0.24, 0.8*inch, 0.4*inch]))
    story.append(Paragraph("<b>Note:</b> C12 (architecture) moved from B for balance. C knows full infra now.", s["note"]))

    # ========== SUMMARY ==========
    story.append(PageBreak())
    story.append(Paragraph("Summary: Timeline & File Ownership", s["h1"]))
    
    story.append(Paragraph("Workload Balance", s["h2"]))
    story.append(task_table(
        ["Developer", "Day 1", "Day 2", "Total", "Role"],
        [["<b>A</b>", "10.5h", "12.5h", "<b>~23h</b>", "Backend + LangGraph + kind (heaviest)"],
         ["<b>B</b>", "9h", "9.5h", "<b>~18.5h</b>", "Frontend + Demo + eval/README"],
         ["<b>C</b>", "9h", "10h", "<b>~19h</b>", "Data + Eval + Deploy + architecture"]],
        s, [0.6*inch, 0.6*inch, 0.6*inch, 0.6*inch, w-2.4*inch]))
    
    story.append(Paragraph("Day 1 Timeline", s["h2"]))
    story.append(task_table(
        ["Time", "Developer A", "Developer B", "Developer C"],
        [["9:00-11:00", "A1-A3: Job API", "B1-B3: UI components", "C1: Download filings"],
         ["11:00-13:00", "A4-A6: Celery + Redis", "B4: Poll jobs", "C2-C3: data/raw/"],
         ["14:00-16:00", "A7: search_chunks stub", "B5-B6: Polish, errors", "C4-C6: Ollama + docs"],
         ["16:00-18:00", "A8: Start cleaner", "B7: Screenshots", "<b>C7: Oracle VM</b> + C8"]],
        s, [0.7*inch, (w-0.7*inch)/3, (w-0.7*inch)/3, (w-0.7*inch)/3]))

    story.append(Spacer(1, 8))
    story.append(Paragraph("Day 2 Timeline", s["h2"]))
    story.append(task_table(
        ["Time", "Developer A", "Developer B", "Developer C"],
        [["9:00-12:00", "A9-A11: Ingest + embed", "B8-B10: Compose frontend", "C9-C11: Finish eval"],
         ["12:00-14:00", "A12-A15: LangGraph", "B11: Polish", "<b>C12: Architecture</b>"],
         ["14:00-16:00", "<b>A16: Compose prod</b>", "B13-B14: kind + script", "<b>C13-C14: Deploy</b>"],
         ["16:00-18:00", "A17-A18: kind + seed", "<b>B15-B17: Prod test</b>", "<b>C16-C17: Prod eval</b>"]],
        s, [0.7*inch, (w-0.7*inch)/3, (w-0.7*inch)/3, (w-0.7*inch)/3]))
    story.append(Paragraph("<b>Tag e2e-real + v0.1.0</b> — Production live on Oracle Cloud", s["note"]))

    story.append(Spacer(1, 10))
    story.append(Paragraph("File Ownership (No Conflicts)", s["h2"]))
    story.append(task_table(
        ["Dev", "Owns"],
        [["<b>A</b>", "backend/apps/ · k8s/ · scripts/seed.py · docker-compose.prod.yml · Caddyfile"],
         ["<b>B</b>", "frontend/ · docs-local/screenshots/ · docs-local/DEMO_SCRIPT.md · <b>eval/README.md</b>"],
         ["<b>C</b>", "data/raw/ · scripts/download_filings.py · scripts/deploy/ · eval/claims.json · eval/runner.py · <b>architecture.png</b>"]],
        s, [0.5*inch, w-0.5*inch]))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Definition of Done — EOD Day 2", s["h2"]))
    story.append(task_table(
        ["Requirement", "Owner", "Check"],
        [["Real LLM claim generation (≤5)", "A", "☐"],
         ["RAG evidence with 3 statuses", "A", "☐"],
         ["Celery/Redis + cache-aside", "A", "☐"],
         ["docker-compose.prod.yml ready", "A", "☐"],
         ["<b>Production live on Oracle Cloud</b>", "C", "☐"],
         ["<b>HTTPS working</b>", "C", "☐"],
         ["kind + kubectl scale demo", "A+B", "☐"],
         ["Eval on production + metrics", "C", "☐"],
         ["Demo script + GIF (production)", "B", "☐"],
         ["Tags: e2e-mock, e2e-real, v0.1.0", "All", "☐"]],
        s, [w*0.52, 0.55*inch, 0.4*inch]))

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(f"Wrote {path}")


def main():
    s = styles()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    build_pdf(OUT_DIR / "SPRINT_2DAY_3DEVS.pdf", s)


if __name__ == "__main__":
    main()
