#!/usr/bin/env python3
"""Render the canonical v3 Markdown as the derived, reviewable A4 PDF."""

from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs" / "architecture.md"
OUTPUT = ROOT / "docs" / "releases" / "山地遥感物理基座-架构文档-v3.pdf"
BODY_FONT = "/System/Library/Fonts/Supplemental/Songti.ttc"
HEADING_FONT = "/System/Library/Fonts/STHeiti Medium.ttc"


def clean_inline(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    return text.replace("&", "&amp;").replace("<b>", "<b>").replace("</b>", "</b>")


def draw_header_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#B7B7B7"))
    canvas.setLineWidth(0.35)
    canvas.line(doc.leftMargin, A4[1] - 15 * mm, A4[0] - doc.rightMargin, A4[1] - 15 * mm)
    canvas.setFont("MRS-Heiti", 8.7)
    canvas.setFillColor(colors.HexColor("#505050"))
    canvas.drawString(doc.leftMargin, A4[1] - 11 * mm, "山地遥感物理基座 · 架构文档（v3）")
    canvas.line(doc.leftMargin, 14 * mm, A4[0] - doc.rightMargin, 14 * mm)
    canvas.setFont("MRS-Songti", 8.2)
    canvas.drawCentredString(A4[0] / 2, 9 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"missing canonical Markdown: {SOURCE}")
    pdfmetrics.registerFont(TTFont("MRS-Songti", BODY_FONT, subfontIndex=0))
    pdfmetrics.registerFont(TTFont("MRS-Heiti", HEADING_FONT, subfontIndex=0))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="MRS-Title", parent=styles["Title"], fontName="MRS-Heiti", fontSize=22,
        leading=30, alignment=TA_CENTER, spaceAfter=16, textColor=colors.HexColor("#17365D"),
    ))
    styles.add(ParagraphStyle(
        name="MRS-H2", parent=styles["Heading2"], fontName="MRS-Heiti", fontSize=14,
        leading=20, spaceBefore=14, spaceAfter=7, keepWithNext=True, textColor=colors.HexColor("#17365D"),
    ))
    styles.add(ParagraphStyle(
        name="MRS-H3", parent=styles["Heading3"], fontName="MRS-Heiti", fontSize=11.3,
        leading=16, spaceBefore=10, spaceAfter=4, keepWithNext=True, textColor=colors.HexColor("#244061"),
    ))
    styles.add(ParagraphStyle(
        name="MRS-Body", parent=styles["BodyText"], fontName="MRS-Songti", fontSize=9.7,
        leading=16, alignment=TA_JUSTIFY, spaceAfter=5, wordWrap="CJK", allowWidows=0, allowOrphans=0,
    ))
    styles.add(ParagraphStyle(
        name="MRS-Bullet", parent=styles["BodyText"], fontName="MRS-Songti", fontSize=9.7,
        leading=15.5, leftIndent=11, firstLineIndent=-9, alignment=TA_JUSTIFY, spaceAfter=3, wordWrap="CJK",
    ))
    styles.add(ParagraphStyle(
        name="MRS-Quote", parent=styles["BodyText"], fontName="MRS-Songti", fontSize=10.2,
        leading=17, leftIndent=12, rightIndent=12, borderColor=colors.HexColor("#9EADBF"),
        borderWidth=0.7, borderPadding=8, backColor=colors.HexColor("#F2F5F8"), spaceAfter=9, wordWrap="CJK",
    ))

    story = []
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    paragraph = []

    def flush_paragraph():
        if paragraph:
            story.append(Paragraph(clean_inline(" ".join(paragraph)), styles["MRS-Body"]))
            paragraph.clear()

    for raw in lines:
        line = raw.strip()
        if not line:
            flush_paragraph()
            continue
        if line.startswith("# "):
            flush_paragraph()
            story.append(Spacer(1, 26 * mm))
            story.append(Paragraph(clean_inline(line[2:]), styles["MRS-Title"]))
            continue
        if line.startswith("## "):
            flush_paragraph()
            story.append(Paragraph(clean_inline(line[3:]), styles["MRS-H2"]))
            continue
        if line.startswith("### "):
            flush_paragraph()
            story.append(Paragraph(clean_inline(line[4:]), styles["MRS-H3"]))
            continue
        if line.startswith("> "):
            flush_paragraph()
            story.append(Paragraph(clean_inline(line[2:]), styles["MRS-Quote"]))
            continue
        if line.startswith("- "):
            flush_paragraph()
            story.append(Paragraph("• " + clean_inline(line[2:]), styles["MRS-Bullet"]))
            continue
        if line.endswith("  "):
            line = line[:-2]
        paragraph.append(line)
    flush_paragraph()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, leftMargin=19 * mm, rightMargin=19 * mm,
        topMargin=22 * mm, bottomMargin=20 * mm, title="山地遥感物理基座·架构文档 v3",
        author="MountainRS", subject="Derived publication of docs/architecture.md",
    )
    doc.build(story, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)
    print(OUTPUT)


if __name__ == "__main__":
    main()
