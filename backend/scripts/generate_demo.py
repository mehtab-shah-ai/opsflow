"""Regenerate public synthetic assets and the instant frontend snapshot."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.demo import demo_csv, demo_rows
from app.domain import analyze
from app.exports import export_table
from app.ingestion import parse_file

root = Path(__file__).resolve().parents[2]
out = root / "demo-data"
out.mkdir(exist_ok=True)
raw = demo_csv()
(out / "facility_operations_messy.csv").write_bytes(raw)
(out / "facility_operations_messy.xlsx").write_bytes(export_table(demo_rows(), "xlsx"))
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

columns = ["employee_id", "site", "date", "shift", "hours_worked", "attendance_status"]
matrix = [columns] + [[str(r[c]) for c in columns] for r in demo_rows()[20:44]]
t = Table(matrix, colWidths=[80, 85, 85, 65, 75, 95], repeatRows=1)
t.setStyle(
    TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E4F2E9")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#899F92")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]
    )
)
styles = getSampleStyleSheet()
SimpleDocTemplate(str(out / "facility_operations_report.pdf"), leftMargin=35, rightMargin=35).build(
    [
        Paragraph("OpsFlow | Facility operations sample", styles["Title"]),
        Paragraph(
            "Synthetic demonstration data. Not Grace Facility Service records.", styles["BodyText"]
        ),
        Spacer(1, 18),
        t,
    ]
)
rows = parse_file("demo.csv", raw)[0]["rows"]
analysis = analyze(rows)
snapshot = {
    "id": "preview",
    "job_id": "preview",
    "filename": "facility_operations_messy.csv",
    "table_name": "Synthetic facility operations",
    "created": 1788220800,
    "demo": True,
    "version": 0,
    "quality_before": analysis["quality_score"],
    "analysis": analysis,
    "warnings": [],
    "duration": 0,
}
public = root / "frontend" / "public"
public.mkdir(parents=True, exist_ok=True)
# The bundled preview carries aggregate facts and a sample, not thousands of issue objects.
snapshot["analysis"]["issues"] = analysis["issues"][:20]
(public / "demo-preview.json").write_text(
    json.dumps(snapshot, ensure_ascii=False), encoding="utf-8"
)
(public / "demo-rows.json").write_text(json.dumps(rows[:25], ensure_ascii=False), encoding="utf-8")
print(
    json.dumps(
        {
            "records": analysis["rows"],
            "issues": sum(analysis["severity"].values()),
            "quality": analysis["quality_score"],
            "safe_changes": analysis["safe_changes"],
        }
    )
)
