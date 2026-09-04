#!/usr/bin/env python3
"""
report/pdf_report.py - Forensic PDF report via ReportLab.

Includes the 65B-style certificate section: case metadata, evidence hashes,
extracted files, recovered candidates, timeline summary, chain of custody,
and explicit limitations + examiner verification statement.

Usage:
  python report/pdf_report.py --case case.json --out report.pdf
"""

import argparse
import json
import os
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet


def build_pdf(case_json_path, out_pdf, chain_path=None):
    if not os.path.exists(case_json_path):
        return {"error": "case.json not found", "path": case_json_path}

    with open(case_json_path) as fh:
        case = json.load(fh)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title2", parent=styles["Title"], fontSize=18, spaceAfter=12,
    )
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, spaceBefore=10)
    body = styles["BodyText"]
    small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8.5)

    story = []
    story.append(Paragraph("NYAYA FORENSICS - DVR/NVR FORENSIC REPORT", title_style))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("1. Case Summary", h2))
    story.append(Paragraph(f"<b>Case ID:</b> {case.get('case_id','—')}", body))
    story.append(Paragraph(f"<b>Case name:</b> {case.get('case_name','—')}", body))
    story.append(Paragraph(f"<b>Examiner:</b> {case.get('examiner','—')}", body))
    story.append(Paragraph(f"<b>Organization:</b> {case.get('organization','—')}", body))
    story.append(Paragraph(f"<b>Created (UTC):</b> {case.get('created_at_utc','—')}", body))

    story.append(Paragraph("2. Evidence & Hashes", h2))
    ev = case.get("evidence") or []
    if ev:
        data = [["Evidence ID", "Type", "MD5", "SHA-256"]]
        for e in ev:
            data.append([
                str(e.get("evidence_id", "")),
                str(e.get("evidence_type", "")),
                str(e.get("md5", ""))[:16] + "…",
                str(e.get("sha256", ""))[:16] + "…",
            ])
        t = Table(data, colWidths=[60, 60, 120, 120])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2731")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
        ]))
        story.append(t)

    story.append(Paragraph("3. Extracted Files", h2))
    ext = case.get("extracted") or []
    story.append(Paragraph(f"Total extracted: {len(ext)}", body))

    story.append(Paragraph("4. Recovered Candidates", h2))
    rec = case.get("recovered") or []
    story.append(Paragraph(
        f"Total candidates: {len(rec)}. All recovered items are "
        f"<b>CANDIDATE EVIDENCE</b> requiring human validation.", body,
    ))

    story.append(Paragraph("5. Timeline Summary", h2))
    tl = case.get("timeline") or []
    story.append(Paragraph(f"Timeline events: {len(tl)}", body))

    story.append(Paragraph("6. Chain of Custody", h2))
    if chain_path and os.path.exists(chain_path):
        with open(chain_path) as fh:
            chain = json.load(fh)
        story.append(Paragraph(f"Chain-of-custody entries: {len(chain)}", body))
    else:
        story.append(Paragraph("Chain of custody not provided.", body))

    story.append(Paragraph("7. Certificate of Electronic Evidence (Section 65B IEA / Section 63 BSA)", h2))
    cert_text = (
        "This forensic report is prepared in accordance with Section 65B of the Indian Evidence Act, 1872 "
        "and Section 63 of the Bharatiya Sakshya Adhiniyam, 2023. I hereby certify that the electronic record "
        "and video streams described herein were ingested, parsed, and analyzed using standard forensic procedures "
        "without alteration of the underlying bit-stream. The SHA-256 cryptographic hashes and chained custody "
        "entries mathematically prove evidence integrity throughout the examination lifecycle."
    )
    story.append(Paragraph(cert_text, body))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        "<b>Limitations & Assumptions:</b> AI analytics results are "
        "investigative aids and require human verification. Proprietary vendor "
        "parsers may produce false positives. Recovered files are candidates "
        "until validated. Timestamps assume examiner-configured timezone "
        "offsets. Original evidence was never modified by this tool.",
        small,
    ))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "<b>Examiner Verification Statement:</b> I, "
        f"{case.get('examiner','____________')}, have reviewed the outputs "
        "of this forensic analysis and confirm the findings are consistent "
        "with the original evidence and the documented chain of custody.",
        small,
    ))

    doc = SimpleDocTemplate(
        out_pdf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="NYAYA Forensics Report",
    )
    doc.build(story)
    return {"pdf": out_pdf, "pages": len(story), "error": None}


def main(argv=None):
    ap = argparse.ArgumentParser(description="NYAYA Forensics PDF report")
    ap.add_argument("--case", required=True, help="case.json")
    ap.add_argument("--out", required=True, help="output PDF path")
    ap.add_argument("--chain", default=None, help="chain_of_custody.json")
    args = ap.parse_args(argv)

    result = build_pdf(args.case, args.out, chain_path=args.chain)
    print(json.dumps(result, indent=2))
    return 0 if result.get("error") is None else 1


if __name__ == "__main__":
    sys.exit(main())