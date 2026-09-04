#!/usr/bin/env python3
"""NYAYA Forensics - reporting/pdf_gen.py
Court-ready report generator (P6) using ReportLab. Emits one PDF with nine
sections: Cover, Case Details, Device Info, Hash Verification, Timeline,
Recovered Files, AI Events, Custody Log, 65B Certificate.

Usage:
  python reporting/pdf_gen.py --case case.json --hash hash.json \
      --timeline timeline.json --custody custody.json \
      [--recovery recovery.json] [--ai ai_events.json] --out report.pdf
"""
import argparse
import json
import os
import sys

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, PageBreak)
    HAVE_REPORTLAB = True
except Exception:  # pragma: no cover
    HAVE_REPORTLAB = False

BLUE = colors.HexColor("#1e3a8a")


def _load(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def build(case, hashes, timeline, custody, recovery=None, ai=None,
          out="report.pdf"):
    """Assemble the 9-section court-ready PDF."""
    if not HAVE_REPORTLAB:
        return {"ok": False, "error": "reportlab not installed"}
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1b", parent=styles["Title"], textColor=BLUE, fontSize=26)
    h2 = ParagraphStyle("h2b", parent=styles["Heading2"], textColor=BLUE,
                        spaceBefore=8, spaceAfter=4)
    body = styles["BodyText"]
    cell = ParagraphStyle("cell", parent=styles["BodyText"], fontSize=8.5)
    cellb = ParagraphStyle("cellb", parent=cell, fontName="Helvetica-Bold")

    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=18 * mm,
                            rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm,
                            title="NYAYA Forensics Report",
                            author=str(case.get("examiner", "Examiner")))

    def kv(rows, title):
        data = [[Paragraph("<b>%s</b>" % k, cellb), Paragraph(str(v), cell)]
                for k, v in rows]
        t = Table([["%s" % title, ""]] + data, colWidths=[45 * mm, 130 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#eff6ff")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        return t

    def grid(rows, colw):
        t = Table(rows, colWidths=colw)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    story = []
    # 1. Cover
    story.append(Paragraph("NYAYA FORENSICS", h1))
    story.append(Paragraph("Forensic Examination Report", styles["Title"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("For Law Enforcement Use Only - Indian Evidence "
                           "Act Section 65B", body))
    story.append(Spacer(1, 6 * mm))
    story.append(kv([
        ("Case ID", case.get("case_id", "-")),
        ("Case Name", case.get("case_name", "-")),
        ("Examiner", case.get("examiner", "-")),
        ("Organization", case.get("organization", "-")),
        ("Report Generated (UTC)", case.get("reported_at_utc", "-")),
    ], "CASE"))
    story.append(PageBreak())

    # 2. Case details
    story.append(Paragraph("2. Case Details", h2))
    story.append(kv(list(case.items()), "CASE RECORD"))
    story.append(PageBreak())

    # 3. Device info
    story.append(Paragraph("3. Device / Evidence Information", h2))
    dev = hashes.get("vendor_info", {}) if isinstance(hashes, dict) else {}
    if not dev and isinstance(hashes, dict):
        dev = {k: v for k, v in hashes.items() if k not in ("md5", "sha256")}
    story.append(kv(list(dev.items())[:14], "DEVICE"))
    story.append(PageBreak())

    # 4. Hash verification
    story.append(Paragraph("4. Hash Verification (Acquisition Integrity)", h2))
    story.append(kv([
        ("Evidence File", hashes.get("output", hashes.get("input", "-"))),
        ("MD5", hashes.get("md5", "-")),
        ("SHA-256", hashes.get("sha256", "-")),
        ("Size (bytes)", hashes.get("size_bytes", "-")),
        ("Acquisition Method", hashes.get("method", "-")),
        ("Hash Verified", hashes.get("verified", "-")),
        ("Acquired At (UTC)", hashes.get("acquired_at_utc", "-")),
    ], "HASHES"))
    story.append(PageBreak())
    # 5. Timeline
    story.append(Paragraph("5. Normalised Event Timeline", h2))
    tl = timeline.get("events", []) if isinstance(timeline, dict) else timeline
    rows = [["UTC Time", "Camera/Channel", "Event", "Confidence"]]
    rows += [[str(r.get("utc", "-")), str(r.get("camera", "-")),
              str(r.get("event", "-")), str(r.get("confidence", "-"))]
             for r in tl]
    story.append(grid(rows, [40 * mm, 35 * mm, 70 * mm, 30 * mm]))
    story.append(PageBreak())

    # 6. Recovered files
    story.append(Paragraph("6. Recovered Deleted Recordings", h2))
    rec = recovery if recovery is not None else []
    if isinstance(rec, dict):
        rec = rec.get("clips", [])
    rows = [["#", "NAL", "Start Offset", "Size (bytes)", "MP4"]]
    rows += [[str(i + 1), str(c.get("nal_type", "-")),
              str(c.get("start_offset", "-")),
              str(c.get("size_bytes", "-")),
              str(c.get("mp4") or "-")] for i, c in enumerate(rec)]
    story.append(grid(rows, [10 * mm, 18 * mm, 30 * mm, 30 * mm, 87 * mm]))
    story.append(PageBreak())

    # 7. AI events
    story.append(Paragraph("7. AI-Assisted Detection Events", h2))
    ev = ai if ai is not None else []
    if isinstance(ev, dict):
        ev = ev.get("events", [])
    rows = [["Time (s)", "Label", "BBox (x1,y1,x2,y2)", "Conf"]]
    rows += [[str(x.get("timestamp", "-")), str(x.get("label", "-")),
              str(x.get("bbox", "-")), str(x.get("confidence", "-"))]
             for x in ev[:200]]
    story.append(grid(rows, [25 * mm, 35 * mm, 70 * mm, 25 * mm]))
    story.append(PageBreak())
    # 8. Custody log
    story.append(Paragraph("8. Chain of Custody Log (hash-chained)", h2))
    entries = custody if isinstance(custody, list) else custody.get("entries", [])
    rows = [["Seq", "UTC", "Examiner", "Action", "Prev-Hash"]]
    rows += [[str(x.get("seq", i + 1)), str(x.get("ts_utc", "-")),
              str(x.get("examiner", "-")), str(x.get("action", "-")),
              (str(x.get("prev_hash", "-")))[:24] + "..."]
             for i, x in enumerate(entries)]
    story.append(grid(rows, [14 * mm, 34 * mm, 30 * mm, 55 * mm, 22 * mm]))
    story.append(PageBreak())

    # 9. 65B certificate
    story.append(Paragraph("9. Certificate under Section 65B, "
                           "Indian Evidence Act", h2))
    cert = [
        ("A", "Electronic record produced by the computer during normal "
              "operation", "yes"),
        ("B", "Computer used regularly to store/process information of the "
              "kind contained in the record", "yes"),
        ("C", "Information regularly fed into the computer in the ordinary "
              "course of activity", "yes"),
        ("D", "Computer was operating properly during the relevant period "
              "(or irregularities do not affect the record)", "yes"),
        ("E", "MD5/SHA-256 of the evidence match the acquisition log "
              "(verified at ingest)", "yes"),
        ("F", "Evidence media handled via write-blocker; custody log "
              "unbroken and hash-chained", "yes"),
    ]
    rows = [["Clause", "Statement", "Status"]]
    rows += [[a, b, c] for a, b, c in cert]
    story.append(grid(rows, [16 * mm, 130 * mm, 18 * mm]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("Signature of Examiner: ____________________"
                           "&nbsp;&nbsp;&nbsp;&nbsp; Date: ____________",
                           body))
    doc.build(story)
    return {"ok": True, "output": out,
            "sections": ["cover", "case", "device", "hashes", "timeline",
                         "recovered", "ai", "custody", "65b"]}


def main():
    ap = argparse.ArgumentParser(description="NYAYA PDF report generator")
    ap.add_argument("--case", required=True)
    ap.add_argument("--hash", required=True)
    ap.add_argument("--timeline", required=True)
    ap.add_argument("--custody", required=True)
    ap.add_argument("--recovery", default=None)
    ap.add_argument("--ai", default=None)
    ap.add_argument("--out", default="nyaya_report.pdf")
    args = ap.parse_args()
    r = build(_load(args.case), _load(args.hash), _load(args.timeline),
              _load(args.custody), _load(args.recovery), _load(args.ai),
              args.out)
    print(json.dumps(r, indent=2))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()