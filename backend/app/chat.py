"""Intelligent operations copilot with deterministic reasoning, dynamic ECharts generation, LLM streaming, and safe action proposals."""

from collections import Counter, defaultdict
import hashlib
import json
import re
import time
from typing import AsyncGenerator

from .ai import Plan, ProviderRouter, build_context
from .domain import CATEGORIES, missing, numeric


def local_plan(message: str) -> Plan | None:
    text = message.lower()
    if any(
        w in text
        for w in (
            "clean",
            "normalize",
            "standardize",
            "apply",
            "delete",
            "remove duplicate",
            "missing",
            "null",
            "empty",
            "impute",
            "sanitize",
            "remove missing",
        )
    ):
        col = None
        for candidate in (
            "date",
            "shift",
            "site",
            "attendance_status",
            "check_in",
            "check_out",
            "hours_worked",
        ):
            if candidate in text or candidate.replace("_", " ") in text:
                col = candidate
                break
        return Plan(tool="preview_cleaning", column=col)
    if "export" in text or "excel" in text:
        return Plan(
            tool="export_filtered_rows", severity="critical" if "critical" in text else None
        )
    if any(w in text for w in ("report", "mis", "pdf")):
        return Plan(tool="generate_report")
    if any(w in text for w in ("chart", "graph", "visual", "plot", "bana", "dikha")):
        return Plan(tool="create_chart", value="attendance" if "attendance" in text else "staffing")
    if any(w in text for w in ("critical", "issue", "flag", "exception", "problem")):
        return Plan(tool="get_issues", severity="critical" if "critical" in text else None)
    if "absenteeism" in text or "absent" in text:
        return Plan(tool="group_and_aggregate", column="site", value="absenteeism")
    if any(w in text for w in ("summary", "overview", "records", "quality", "kpi", "performance")):
        return Plan(tool="get_dataset_summary")
    return None


def generate_dynamic_chart(chart_type: str, dataset: dict, message: str) -> dict | None:
    """Constructs Apache ECharts compatible ChartSpec structures dynamically."""
    rows = dataset.get("data", [])
    analysis = dataset.get("analysis", {})
    ops = analysis.get("operations", {})
    schema = analysis.get("schema", [])

    if chart_type == "overtime":
        site_ot = defaultdict(float)
        for r in rows:
            hrs = numeric(r.get("hours_worked"))
            if hrs is not None and hrs > 8:
                site = str(r.get("site") or "Unassigned").strip().title()
                site_ot[site] += round(hrs - 8, 1)
        data = [
            {"site": s, "overtime_hours": round(h, 1)}
            for s, h in sorted(site_ot.items(), key=lambda x: x[1], reverse=True)
        ]
        if not data and ops.get("sites"):
            data = [{"site": s["site"], "overtime_hours": 0.0} for s in ops["sites"]]
        return {
            "id": "chart_overtime",
            "type": "bar",
            "title": "Overtime Hours by Facility Site",
            "subtitle": "Total accumulated hours logged beyond the standard 8-hour shift",
            "x": "site",
            "series": ["overtime_hours"],
            "data": data or [{"site": "No Overtime", "overtime_hours": 0}],
        }

    if chart_type == "absenteeism":
        if ops.get("available") and ops.get("sites"):
            data = [
                {
                    "site": s["site"],
                    "absenteeism_rate": round(100 * s["absent"] / max(1, s["records"]), 1),
                    "absent_count": s["absent"],
                }
                for s in sorted(
                    ops["sites"], key=lambda s: s["absent"] / max(1, s["records"]), reverse=True
                )
            ]
        else:
            site_stats = defaultdict(lambda: {"records": 0, "absent": 0})
            for r in rows:
                site = str(r.get("site") or "Unassigned").strip().title()
                status = str(r.get("attendance_status", "")).strip().lower()
                site_stats[site]["records"] += 1
                if status in ("absent", "a", "leave", "on leave"):
                    site_stats[site]["absent"] += 1
            data = [
                {
                    "site": s,
                    "absenteeism_rate": round(100 * v["absent"] / max(1, v["records"]), 1),
                    "absent_count": v["absent"],
                }
                for s, v in sorted(
                    site_stats.items(),
                    key=lambda x: x[1]["absent"] / max(1, x[1]["records"]),
                    reverse=True,
                )
            ]
        return {
            "id": "chart_absenteeism",
            "type": "bar",
            "title": "Absenteeism Rate by Site (%)",
            "subtitle": "Unplanned absence rate across facility locations",
            "x": "site",
            "series": ["absenteeism_rate"],
            "data": data or [{"site": "All Sites", "absenteeism_rate": 0}],
        }

    if chart_type == "shift":
        shift_counts = Counter()
        for r in rows:
            raw_s = str(r.get("shift") or "Unassigned").strip().title()
            shift_counts[raw_s] += 1
        data = [{"shift": k, "staff_count": v} for k, v in shift_counts.most_common()]
        return {
            "id": "chart_shift_distribution",
            "type": "donut",
            "title": "Workforce Deployment by Shift",
            "subtitle": "Distribution of personnel across operating shifts",
            "x": "shift",
            "series": ["staff_count"],
            "data": data or [{"shift": "General", "staff_count": len(rows)}],
        }

    if chart_type == "attendance_trend":
        trend = ops.get("trend", [])
        if trend:
            return {
                "id": "chart_attendance_trend",
                "type": "line",
                "title": "Daily Attendance Rate (%)",
                "subtitle": "Verified staff attendance trend over operating dates",
                "x": "date",
                "series": ["attendance_rate"],
                "data": trend,
            }

    if chart_type == "attendance_site":
        if ops.get("available") and ops.get("sites"):
            data = [
                {
                    "site": s["site"],
                    "attendance_rate": s["attendance_rate"],
                }
                for s in sorted(ops["sites"], key=lambda s: s["attendance_rate"], reverse=True)
            ]
            return {
                "id": "chart_attendance_site",
                "type": "bar",
                "title": "Verified Attendance Rate by Site (%)",
                "subtitle": "Percentage of planned shifts successfully staffed",
                "x": "site",
                "series": ["attendance_rate"],
                "data": data,
            }

    if chart_type == "coverage":
        if ops.get("available") and ops.get("sites"):
            return {
                "id": "chart_coverage",
                "type": "bar",
                "title": "Site Coverage: Required vs Available Staff",
                "subtitle": "Contractual client staffing requirements vs deployed manpower",
                "x": "site",
                "series": ["required", "available"],
                "data": ops["sites"],
            }

    if chart_type == "missing":
        data = [
            {"column": s["name"].replace("_", " ").title(), "missing_cells": s.get("missing", 0)}
            for s in schema
            if s.get("missing", 0) > 0
        ]
        return {
            "id": "chart_missing",
            "type": "bar",
            "title": "Missing Cells by Field",
            "subtitle": "Count of empty or incomplete cells requiring sanitization",
            "x": "column",
            "series": ["missing_cells"],
            "data": data or [{"column": "All Complete", "missing_cells": 0}],
        }

    if chart_type == "sla":
        met = 0
        breached = 0
        for r in rows:
            sla = str(r.get("sla_status", "")).strip().lower()
            if sla in ("breached", "breach"):
                breached += 1
            elif sla in ("met", "compliant"):
                met += 1
        return {
            "id": "chart_sla",
            "type": "donut",
            "title": "SLA Compliance Breakdown",
            "subtitle": "Proportion of shifts meeting contractual client SLAs",
            "x": "status",
            "series": ["count"],
            "data": [{"status": "Met", "count": met}, {"status": "Breached", "count": breached}],
        }

    # Schema-aware dynamic charts for any general dataset (e.g. cars, sales, retail)
    msg_lower = message.lower()
    for col_info in schema:
        c_name = col_info["name"].lower()
        if c_name in msg_lower or c_name.replace("_", " ") in msg_lower:
            for c in analysis.get("charts", []):
                if c_name in c.get("id", "").lower() or c_name in c.get("title", "").lower():
                    return c
            if col_info.get("type") == "numeric":
                vals = [numeric(r.get(col_info["name"])) for r in rows if numeric(r.get(col_info["name"])) is not None]
                if vals:
                    lo, hi = min(vals), max(vals)
                    step = (hi - lo) / 8 or 1
                    bins = [0] * 8
                    for v in vals:
                        bins[min(7, int((v - lo) / step))] += 1
                    return {
                        "id": f"chart_{c_name}",
                        "type": "bar",
                        "title": f"{col_info['name'].replace('_', ' ').title()} Distribution",
                        "subtitle": f"Numeric value distribution across {len(vals):,} rows",
                        "x": "range",
                        "series": ["count"],
                        "data": [{"range": f"{round(lo + i*step, 1)}-{round(lo + (i+1)*step, 1)}", "count": b} for i, b in enumerate(bins)],
                    }

    if analysis.get("charts"):
        return analysis["charts"][0]
    return None


def detect_chat_action(dataset: dict, message: str) -> dict:
    """Deterministically identifies the tool, UI action, and relevant rows or chart."""
    text = message.lower().strip()
    rows = dataset.get("data", [])
    a = dataset.get("analysis", {})
    ops = a.get("operations", {})
    schema = a.get("schema", [])
    cols = [s["name"] for s in schema]
    issues = a.get("issues", [])

    # 1. Missing, Nulls, Duplicates, and Cleaning
    is_missing_or_clean = any(
        w in text
        for w in (
            "clean",
            "missing",
            "null",
            "empty",
            "nan",
            "duplicate",
            "duplicates",
            "impute",
            "sanitize",
            "remove missing",
            "missing values",
            "fix data",
            "standardize",
            "normalize",
            "hatao",
            "nikalo",
        )
    )
    if is_missing_or_clean:
        missing_per_col = {s["name"]: s.get("missing", 0) for s in schema if s.get("missing", 0) > 0}
        target_col = None
        for col in cols:
            if col.lower() in text or col.lower().replace("_", " ") in text:
                target_col = col
                break

        fixes = [i for i in issues if i.get("auto_fixable") and (not target_col or i.get("column") == target_col)]
        missing_rows = []
        for r in rows:
            if target_col:
                if missing(r.get(target_col)):
                    missing_rows.append(r)
            else:
                if any(missing(r.get(c)) for c in missing_per_col):
                    missing_rows.append(r)
            if len(missing_rows) >= 20:
                break

        chart = None
        if any(w in text for w in ("chart", "visual", "graph", "plot")):
            chart = generate_dynamic_chart("missing", dataset, message)

        return {
            "action": "preview_cleaning",
            "column": target_col,
            "items": missing_rows if missing_rows else fixes[:20],
            "chart": chart,
        }

    # 2. Dynamic Chart Generation
    is_chart_query = any(w in text for w in ("chart", "graph", "visual", "plot", "visualize", "dikha", "bana"))
    if is_chart_query:
        chart_kind = "attendance_site"
        if any(w in text for w in ("overtime", "ot", "hours worked")):
            chart_kind = "overtime"
        elif any(w in text for w in ("absent", "absenteeism", "leave")):
            chart_kind = "absenteeism"
        elif any(w in text for w in ("shift", "roster", "distribution")):
            chart_kind = "shift"
        elif any(w in text for w in ("trend", "date", "daily", "timeline")):
            chart_kind = "attendance_trend"
        elif any(w in text for w in ("coverage", "staffing", "gap", "required")):
            chart_kind = "coverage"
        elif any(w in text for w in ("missing", "null", "quality", "clean")):
            chart_kind = "missing"
        elif any(w in text for w in ("sla", "incident", "breach")):
            chart_kind = "sla"
        chart = generate_dynamic_chart(chart_kind, dataset, message)
        return {
            "action": "create_chart",
            "chart": chart,
        }

    # 3. Report & PDF Generation
    if any(w in text for w in ("report", "mis", "daily report", "download report", "pdf")):
        return {
            "action": "generate_report",
            "download": "format=pdf&report=daily",
        }

    # 4. Excel / Spreadsheet Export
    if any(w in text for w in ("export", "download excel", "xlsx", "csv", "excel")):
        return {
            "action": "export_filtered_rows",
            "download": "format=xlsx&kind=issues",
        }

    # 5. Absenteeism Query (Only if attendance_status column exists)
    is_absent_query = any(
        w in text
        for w in (
            "who is absent",
            "list absent",
            "absent employees",
            "absent staff",
            "absenteeism",
            "chutti",
            "absent list",
        )
    )
    if is_absent_query and any(s["name"] == "attendance_status" for s in schema):
        absent_rows = []
        for r in rows:
            status = str(r.get("attendance_status", "")).strip().lower()
            if status in ("absent", "a", "leave", "on leave"):
                absent_rows.append(
                    {
                        "employee_id": r.get("employee_id") or "N/A",
                        "employee_name": r.get("employee_name") or r.get("name") or "Staff",
                        "site": str(r.get("site") or "Unassigned").strip().title(),
                        "shift": r.get("shift") or "General",
                        "date": r.get("date") or "N/A",
                        "attendance_status": "Absent" if status in ("absent", "a") else "Leave",
                    }
                )
        return {
            "action": "filter_rows",
            "items": absent_rows[:20],
        }

    # 6. Overtime Query (Only if hours_worked column exists)
    is_ot_query = any(
        w in text
        for w in (
            "overtime",
            "ot",
            "who worked overtime",
            "excess hours",
            "extra hours",
            "fatigue",
            "highest overtime",
        )
    )
    if is_ot_query and any(s["name"] == "hours_worked" for s in schema):
        ot_rows = []
        for r in rows:
            hrs = numeric(r.get("hours_worked"))
            if hrs is not None and hrs > 8:
                ot = round(hrs - 8, 1)
                site = str(r.get("site") or "Unassigned").strip().title()
                ot_rows.append(
                    {
                        "employee_id": r.get("employee_id") or "N/A",
                        "employee_name": r.get("employee_name") or r.get("name") or "Staff",
                        "site": site,
                        "shift": r.get("shift") or "General",
                        "hours_worked": hrs,
                        "overtime_hours": ot,
                        "date": r.get("date") or "N/A",
                    }
                )
        ot_rows.sort(key=lambda x: x["overtime_hours"], reverse=True)
        return {
            "action": "filter_rows",
            "items": ot_rows[:20],
            "chart": generate_dynamic_chart("overtime", dataset, message),
        }

    # 7. Shift Coverage Query (Only if facility operations available)
    is_cov_query = any(
        w in text
        for w in (
            "coverage",
            "staffing gap",
            "shortage",
            "understaffed",
            "deficit",
            "required staff",
        )
    )
    if is_cov_query and ops.get("available"):
        gap_sites = [s for s in ops.get("sites", []) if s.get("gap", 0) > 0]
        return {
            "action": "group_and_aggregate",
            "items": gap_sites or ops.get("sites", [])[:10],
            "chart": generate_dynamic_chart("coverage", dataset, message),
        }

    # 8. Specific Employee Search
    emp_match = re.search(r"(emp[-_]?\d+|\baarav\b|\bpriya\b|\bimran\b|\bsneha\b|\brohan\b|\banjali\b|\bkabir\b|\bneha\b)", text)
    if emp_match and any("name" in s["name"] or "employee" in s["name"] for s in schema):
        query_val = emp_match.group(1).lower()
        matched = []
        for r in rows:
            eid = str(r.get("employee_id", "")).strip().lower()
            ename = str(r.get("employee_name", "") or r.get("name", "")).strip().lower()
            if query_val in eid or query_val in ename:
                matched.append(r)
        if matched:
            return {
                "action": "filter_rows",
                "items": matched[:10],
            }

    return {"action": "get_dataset_summary"}


def build_dataset_chat_prompt(dataset: dict, message: str) -> tuple[str, str]:
    """Prepares structured prompt grounded strictly in the active dataset schema and rows."""
    rows = dataset.get("data", [])
    analysis = dataset.get("analysis", {})
    schema = analysis.get("schema", [])
    issues = analysis.get("issues", [])
    ops = analysis.get("operations", {})
    is_facility = bool(ops.get("available"))

    filename = dataset.get("filename", "Current Dataset")
    total_rows = len(rows)
    cols_summary = ", ".join(f"{s['name']} ({s.get('inferred_type', s.get('type', 'text'))})" for s in schema[:15])

    missing_by_col = {s["name"]: s.get("missing", 0) for s in schema if s.get("missing", 0) > 0}
    total_missing = sum(missing_by_col.values())
    missing_desc = (
        ", ".join(f"{k}: {v} empty" for k, v in list(missing_by_col.items())[:6])
        if missing_by_col
        else "0 blank/missing cells across all columns"
    )

    auto_fixes = [i for i in issues if i.get("auto_fixable")]
    dup_issues = [i for i in issues if "duplicate" in i.get("issue_type", "")]
    quality_score = analysis.get("quality_score", 100)

    facility_section = ""
    if is_facility:
        att = ops.get("attendance_rate", "—")
        cov = ops.get("shift_coverage", "—")
        gap = ops.get("staffing_gap", 0)
        ot = ops.get("overtime_hours", 0)
        facility_section = f"""
Operational Facility Metrics:
- Attendance Rate: {att}%
- Shift Coverage: {cov}%
- Staffing Gap / Shortage: {gap} shifts
- Total Overtime: {ot} hours
"""

    sample_rows = json.dumps(rows[:3], default=str) if rows else "[]"

    system = (
        "You are OpsFlow AI Copilot, a sharp, friendly, and practical business data analyst. "
        "Your mission is to explain data clearly in simple, day-to-day plain human words without robotic jargon.\n"
        "Strict Guidelines:\n"
        "1. Answer strictly based on the provided dataset context. Never invent numbers, columns, or assumptions.\n"
        "2. If this is NOT a facility operations dataset (no shifts/sites), NEVER mention facility management, shifts, check-ins, or client SLAs. Talk strictly about the user's columns (e.g. cars, sales, users).\n"
        "3. If asked about nulls, missing, duplicates or cleaning:\n"
        "   - Clearly state the exact count of missing cells (if 0, clearly say 0 missing cells in these columns).\n"
        "   - Mention formatting anomalies (e.g. extra whitespace or numbers saved as text) and reassure the user that OpsFlow can safely standardize them.\n"
        "   - State whether duplicate rows exist.\n"
        "4. Keep explanations conversational, structured with bold highlights and clean bullet points (max 2-4 brief paragraphs or bullets).\n"
        "5. Keep next steps actionable (e.g. previewing changes or viewing charts)."
    )

    user_prompt = f"""
Dataset Context:
- File Name: {filename}
- Total Records: {total_rows:,}
- Columns: {cols_summary}
- Missing / Null Cells: {total_missing} ({missing_desc})
- Auto-Fixable Formatting Issues: {len(auto_fixes)} (safe standardizations like whitespace trimming, type cleanup)
- Duplicate Records: {len(dup_issues)}
- Data Quality Score: {quality_score}%
{facility_section}
Sample Rows (First 3):
{sample_rows}

User Question:
"{message}"

Please explain the answer in simple, friendly, day-to-day plain language:
"""
    return system, user_prompt


def generate_fallback_text(dataset: dict, message: str, meta: dict) -> str:
    """High-accuracy deterministic fallback explanation when external LLM is offline."""
    rows = dataset.get("data", [])
    analysis = dataset.get("analysis", {})
    schema = analysis.get("schema", [])
    issues = analysis.get("issues", [])
    ops = analysis.get("operations", {})
    is_facility = bool(ops.get("available"))
    text = message.lower().strip()

    missing_by_col = {s["name"]: s.get("missing", 0) for s in schema if s.get("missing", 0) > 0}
    total_missing = sum(missing_by_col.values())
    auto_fixes = [i for i in issues if i.get("auto_fixable")]
    dup_issues = [i for i in issues if "duplicate" in i.get("issue_type", "")]

    if meta.get("action") == "preview_cleaning" or any(w in text for w in ("clean", "null", "missing", "duplicate", "duplicates", "empty")):
        breakdown = (
            ", ".join(f"`{k}` ({v} empty)" for k, v in list(missing_by_col.items())[:5])
            if missing_by_col
            else "no empty fields found"
        )
        if is_facility:
            return (
                f"We scanned **{len(rows):,} records** in `{dataset.get('filename', 'dataset')}`.\n\n"
                f"• **Missing Cells:** Found **{total_missing} missing cells** ({breakdown}).\n"
                f"• **Formatting Anomalies:** Found **{len(auto_fixes)} auto-fixable formatting items** (whitespace trimming, date normalization).\n"
                f"• **Duplicates:** Found **{len(dup_issues)} duplicate records**.\n\n"
                "OpsFlow handles cleaning safely without touching your original files. Click **Preview changes** below to inspect side-by-side values before applying."
            )
        else:
            return (
                f"We analyzed **{len(rows):,} rows** in `{dataset.get('filename', 'your dataset')}`:\n\n"
                f"• **Missing / Null Values:** Found **{total_missing} empty cells** across all columns ({breakdown}).\n"
                f"• **Formatting Anomalies:** Detected **{len(auto_fixes)} auto-fixable formatting items** (such as extra spaces or numbers stored as text).\n"
                f"• **Duplicates:** Found **{len(dup_issues)} duplicate entries**.\n\n"
                "Your original file remains completely safe and untouched. Click **Preview changes** below to review the proposed fixes."
            )

    if meta.get("action") == "create_chart":
        return "Interactive visual chart generated from your current dataset. You can hover over elements to inspect exact values."

    if meta.get("action") == "generate_report":
        return "Your management report has been prepared with full metrics, priority findings, and data quality audits. Download your publication-ready PDF below."

    if meta.get("action") == "export_filtered_rows":
        return "Export package ready: Verified operational records and exception logs exported as a clean Excel workbook with formula-safe encoding."

    if meta.get("action") == "filter_rows":
        item_count = len(meta.get("items", []))
        return f"Found **{item_count} matching records** in your dataset. Review the table below for details."

    # General dataset summary
    cols_str = ", ".join(s["name"] for s in schema[:8])
    return (
        f"**Dataset Overview ({len(rows):,} total records):**\n\n"
        f"• **Columns:** {cols_str}\n"
        f"• **Data Health:** **{analysis.get('quality_score', 100)}% quality score** ({len(auto_fixes)} formatting fixes ready to apply)\n"
        f"• **Empty Cells:** {total_missing} total\n\n"
        "Feel free to ask about missing values, request a chart, or ask for a clean export."
    )


async def generate_dataset_explanation(dataset: dict, message: str, router: ProviderRouter, meta: dict) -> tuple[str, str]:
    """Generates an intelligent explanation using the LLM router, falling back smoothly to deterministic text."""
    system, prompt = build_dataset_chat_prompt(dataset, message)
    try:
        res = await router.generate_text(prompt, system)
        if res and res.get("text"):
            return res["text"].strip(), f"OpsFlow AI ({res.get('provider', 'LLM')})"
    except Exception:
        pass
    return generate_fallback_text(dataset, message, meta), "OpsFlow Engine"


async def stream_dataset_explanation(dataset: dict, message: str, router: ProviderRouter, meta: dict) -> AsyncGenerator[str, None]:
    """Yields streaming tokens from the LLM router, with fallback word-by-word streaming."""
    system, prompt = build_dataset_chat_prompt(dataset, message)
    streamed_any = False
    try:
        async for token in router.stream_text(prompt, system):
            streamed_any = True
            yield token
    except Exception:
        pass

    if not streamed_any:
        fallback = generate_fallback_text(dataset, message, meta)
        words = fallback.split(" ")
        for i, w in enumerate(words):
            yield w + (" " if i < len(words) - 1 else "")


async def respond(dataset: dict, message: str, router: ProviderRouter, repo) -> dict:
    """Non-streaming conversational chat endpoint response."""
    meta = detect_chat_action(dataset, message)
    text_explanation, provider = await generate_dataset_explanation(dataset, message, router, meta)

    response = {
        "role": "assistant",
        "text": text_explanation,
        "provider": provider,
        "timestamp": time.time(),
        **meta,
    }

    repo.messages(dataset["id"], {"role": "user", "text": message, "timestamp": time.time()})
    repo.messages(dataset["id"], response)
    return response


async def stream_respond(dataset: dict, message: str, router: ProviderRouter, repo) -> AsyncGenerator[str, None]:
    """SSE streaming response generator yielding token chunks and final payload."""
    repo.messages(dataset["id"], {"role": "user", "text": message, "timestamp": time.time()})
    meta = detect_chat_action(dataset, message)

    accumulated = []
    async for token in stream_dataset_explanation(dataset, message, router, meta):
        accumulated.append(token)
        yield f"data: {json.dumps({'token': token})}\n\n"

    full_text = "".join(accumulated).strip()
    if not full_text:
        full_text = generate_fallback_text(dataset, message, meta)
        yield f"data: {json.dumps({'token': full_text})}\n\n"

    final_message = {
        "role": "assistant",
        "text": full_text,
        "provider": "OpsFlow AI",
        "timestamp": time.time(),
        **meta,
    }

    repo.messages(dataset["id"], final_message)
    yield f"data: {json.dumps({'done': True, 'message': final_message})}\n\n"
