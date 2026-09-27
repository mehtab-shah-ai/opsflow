"""Deterministic validation, non-destructive transformations and analytical facts."""

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime
from statistics import median

NULLS = {"", "n/a", "na", "-", "null", "none", "nan"}
CATEGORIES = {
    "attendance_status": {
        "present": "Present",
        "p": "Present",
        "absent": "Absent",
        "a": "Absent",
        "leave": "Leave",
        "on leave": "Leave",
    },
    "shift": {"day": "Day", "night": "Night", "evening": "Evening", "morning": "Morning"},
    "task_status": {
        "complete": "Completed",
        "completed": "Completed",
        "done": "Completed",
        "pending": "Pending",
        "in progress": "In progress",
    },
    "sla_status": {
        "met": "Met",
        "compliant": "Met",
        "breached": "Breached",
        "breach": "Breached",
        "at risk": "At risk",
    },
}
NUMERIC_COLUMNS = {
    "hours_worked",
    "required_staff",
    "incident_count",
    "amount",
    "total",
    "price",
    "salary",
    "revenue",
    "cost",
    "quantity",
    "percentage",
    "rate",
}
REQUIRED = {"employee_id", "site", "date", "shift", "attendance_status"}


def missing(v):
    return v is None or isinstance(v, str) and v.strip().lower() in NULLS


def numeric(v):
    if isinstance(v, bool) or missing(v):
        return None
    if isinstance(v, (int, float)):
        return v if math.isfinite(v) else None
    value = re.sub(r"[₹$€£,\s]", "", str(v))
    if not re.fullmatch(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[kK%])?", value):
        return None
    scale = 1000 if value.lower().endswith("k") else 0.01 if value.endswith("%") else 1
    try:
        result = float(value.rstrip("kK%")) * scale
        return result if math.isfinite(result) else None
    except ValueError:
        return None


def date_value(v):
    value = str(v).strip()
    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2}|\d{4})", value)
    if m and int(m[1]) <= 12 and int(m[2]) <= 12 and m[1] != m[2]:
        return None, "ambiguous_date"
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%d %b %Y",
        "%d %B %Y",
    ):
        try:
            return datetime.strptime(value, fmt).date().isoformat(), None
        except ValueError:
            pass
    return None, "invalid_date"


def columns_of(rows):
    return [c for c in dict.fromkeys(k for row in rows for k in row) if not c.startswith("_")]


def infer_schema(rows):
    schema = []
    for col in columns_of(rows):
        values = [r.get(col) for r in rows if not missing(r.get(col))]
        nums = [numeric(v) for v in values]
        if "date" in col or col in {"day", "timestamp"}:
            kind = "date"
        elif (
            col in NUMERIC_COLUMNS
            or values
            and sum(v is not None for v in nums) / len(values) >= 0.85
            and not col.endswith("_id")
        ):
            kind = "numeric"
        elif len(set(map(str, values))) <= 30:
            kind = "category"
        else:
            kind = "text"
        schema.append(
            {
                "name": col,
                "type": kind,
                "missing": len(rows) - len(values),
                "unique": len(set(map(str, values))),
            }
        )
    return schema


def analyze(rows: list[dict]) -> dict:
    schema, issues = infer_schema(rows), []
    columns = [s["name"] for s in schema]

    def issue(index, col, kind, severity, reason, suggested=None, safe=False, confidence=1.0):
        current = rows[index].get(col)
        identity = json.dumps([index, col, kind, current], sort_keys=True, default=str)
        issues.append(
            {
                "issue_id": hashlib.sha256(identity.encode()).hexdigest()[:20],
                "row": index + 1,
                "source_row": rows[index].get("_source_row", index + 2),
                "column": col,
                "issue_type": kind,
                "severity": severity,
                "current_value": current,
                "suggested_value": suggested,
                "reason": reason,
                "rule": kind,
                "confidence": confidence,
                "auto_fixable": safe,
            }
        )

    seen, attendance, identifiers = {}, {}, {}
    for idx, row in enumerate(rows):
        signature = json.dumps({c: row.get(c) for c in columns}, sort_keys=True, default=str)
        if signature in seen:
            issue(
                idx,
                columns[0],
                "duplicate_row",
                "warning",
                f"Exact duplicate of row #{seen[signature] + 1}. Check if this row was accidentally entered twice.",
            )
        seen[signature] = idx
        if all(not missing(row.get(c)) for c in ("employee_id", "date", "shift")):
            key = tuple(str(row[c]).strip().casefold() for c in ("employee_id", "date", "shift"))
            if key in attendance:
                issue(
                    idx,
                    "employee_id",
                    "duplicate_attendance",
                    "critical",
                    f"Duplicate shift: Employee already recorded on row #{attendance[key] + 1} for this date and shift.",
                )
            attendance[key] = idx
        elif "employee_id" in row and not missing(row["employee_id"]):
            key = str(row["employee_id"]).strip()
            if key in identifiers:
                issue(
                    idx,
                    "employee_id",
                    "duplicate_id",
                    "warning",
                    "Same employee ID appears with incomplete shift details. Please verify.",
                )
            identifiers[key] = idx
        for s in schema:
            col, val = s["name"], row.get(s["name"])
            if missing(val):
                if col in REQUIRED:
                    issue(
                        idx,
                        col,
                        "required_field",
                        "critical",
                        "Required field is empty. Please enter the missing value.",
                    )
                elif val is not None:
                    issue(
                        idx,
                        col,
                        "null_representation",
                        "info",
                        "Empty placeholder (e.g. 'N/A' or '-') converted to clean blank cell.",
                        None,
                        True,
                    )
                else:
                    issue(
                        idx,
                        col,
                        "missing_value",
                        "info",
                        "Empty cell detected; kept blank.",
                    )
                continue
            suggestion, rule, reason = val, None, None
            if isinstance(val, str) and val.startswith("="):
                issue(
                    idx,
                    col,
                    "formula",
                    "warning",
                    "Spreadsheet formula kept as regular text to prevent errors.",
                )
                continue
            if s["type"] == "numeric":
                number = numeric(val)
                if number is None:
                    issue(idx, col, "invalid_type", "warning", "Not a valid number (contains letters, symbols, or unreadable characters).")
                elif isinstance(val, str):
                    suggestion, rule, reason = (
                        number,
                        "numeric_string",
                        "Number was stored as text; converted to a standard number.",
                    )
            elif s["type"] == "date":
                parsed, error = date_value(val)
                if error:
                    issue(
                        idx,
                        col,
                        error,
                        "warning",
                        "Unclear date format (could be day/month or month/day). Please confirm the correct date."
                        if error == "ambiguous_date"
                        else "Invalid calendar date. Please check the date format.",
                    )
                elif parsed != val:
                    suggestion, rule, reason = (
                        parsed,
                        "date_format",
                        "Converted date to standard calendar format (YYYY-MM-DD).",
                    )
            elif col in CATEGORIES:
                normalized = CATEGORIES[col].get(str(val).strip().casefold())
                if normalized is None:
                    issue(
                        idx,
                        col,
                        "invalid_category",
                        "warning",
                        f"Unrecognized {col.replace('_', ' ')} value. Please verify against standard options.",
                    )
                elif normalized != val:
                    suggestion, rule, reason = (
                        normalized,
                        "known_category",
                        "Corrected status/category spelling to standard format (e.g. 'P' to 'Present').",
                    )
            elif col in {"site", "client"} and isinstance(val, str):
                normalized = val.strip().title()
                if normalized != val:
                    suggestion, rule, reason = (
                        normalized,
                        "case_normalization",
                        "Fixed capitalization and removed extra spacing.",
                    )
            elif isinstance(val, str) and val.strip().lower() in {"yes", "no", "true", "false"}:
                suggestion = val.strip().lower() in {"yes", "true"}
                rule, reason = "boolean", "Converted to standard Yes/No indicator."
            elif isinstance(val, str) and val.strip() != val:
                suggestion, rule, reason = (
                    val.strip(),
                    "whitespace",
                    "Removed accidental spaces before or after the text.",
                )
            if rule and (type(val) is not type(suggestion) or val != suggestion):
                issue(idx, col, rule, "info", reason, suggestion, True)
        hours = numeric(row.get("hours_worked"))
        if hours is not None:
            if hours < 0 or hours > 16:
                issue(
                    idx,
                    "hours_worked",
                    "hours_range",
                    "critical",
                    "Unusual working hours (recorded hours outside standard 0 to 16h). Check for typo or excessive overtime.",
                )
            if hours == 0 and str(row.get("attendance_status")).strip().lower() in {"present", "p"}:
                issue(
                    idx,
                    "hours_worked",
                    "attendance_contradiction",
                    "critical",
                    "Conflict: Employee marked 'Present' but logged 0 working hours.",
                )
        for field in ("required_staff", "incident_count"):
            n = numeric(row.get(field))
            if n is not None and (n < 0 or n != int(n)):
                issue(
                    idx,
                    field,
                    "invalid_range",
                    "critical",
                    "Count must be zero or a positive whole number (cannot be negative or decimal).",
                )
        if str(row.get("sla_status")).strip().lower() in {"breach", "breached"}:
            issue(
                idx,
                "sla_status",
                "sla_breach",
                "critical",
                "SLA Service Target Breached: Needs supervisor review and action.",
            )
        incidents = numeric(row.get("incident_count"))
        if (
            incidents
            and incidents > 0
            and str(row.get("task_status")).strip().lower() not in {"complete", "completed", "done"}
        ):
            issue(
                idx,
                "incident_count",
                "open_incident",
                "warning",
                "Open incident logged on an unfinished task; verify resolution.",
            )
        if row.get("check_in") and row.get("check_out"):
            try:
                begin = datetime.strptime(str(row["check_in"]), "%H:%M")
                end = datetime.strptime(str(row["check_out"]), "%H:%M")
                if end < begin and str(row.get("shift")).strip().lower() != "night":
                    issue(
                        idx,
                        "check_out",
                        "time_range",
                        "warning",
                        "Check-out time is earlier than check-in time (possible AM/PM error).",
                    )
            except ValueError:
                issue(
                    idx,
                    "check_in",
                    "invalid_time",
                    "warning",
                    "Invalid time format (must use standard HH:MM, e.g. 09:30 or 18:00).",
                )
    for s in schema:
        if s["type"] != "numeric":
            continue
        vals = [numeric(r.get(s["name"])) for r in rows]
        valid = sorted(v for v in vals if v is not None)
        if len(valid) < 8:
            continue
        mid = median(valid)
        mad = median([abs(v - mid) for v in valid])
        if mad:
            for idx, val in enumerate(vals):
                if val is not None and abs(val - mid) > 8 * mad:
                    issue(
                        idx,
                        s["name"],
                        "outlier",
                        "warning",
                        "Unusually high or low number (extreme outlier compared to other rows). Double check this value.",
                    )
    weights = {"critical": 5, "warning": 2, "info": 1}
    penalties = defaultdict(int)
    for i in issues:
        penalties[i["row"]] += weights[i["severity"]]
    score = round(
        100 * max(0, 1 - sum(penalties.values()) / (5 * max(1, len(rows)) * max(1, len(columns)))),
        1,
    )
    operations = operation_metrics(rows)
    return {
        "rows": len(rows),
        "columns": len(schema),
        "schema": schema,
        "issues": issues,
        "quality_score": score,
        "valid_records": len(rows) - len(penalties),
        "severity": {s: sum(i["severity"] == s for i in issues) for s in weights},
        "categories": dict(Counter(i["issue_type"] for i in issues)),
        "safe_changes": sum(i["auto_fixable"] for i in issues),
        "operations": operations,
        "charts": recommend_charts(rows, schema, operations),
        "summary": f"Reviewed {len(rows):,} total records. Found {len(issues):,} items for review across {len(penalties):,} rows. {sum(i['auto_fixable'] for i in issues):,} safe formatting fixes are ready to apply. Your original uploaded data is completely safe and untouched.",
    }


def clean(rows: list[dict], issues: list[dict], approved: list[str]):
    by_id = {i["issue_id"]: i for i in issues}
    if (
        not approved
        or len(approved) != len(set(approved))
        or any(i not in by_id or not by_id[i]["auto_fixable"] for i in approved)
    ):
        raise ValueError("Select valid, non-duplicate safe changes from the current preview.")
    result, audit = deepcopy(rows), []
    for key in approved:
        i = by_id[key]
        result[i["row"] - 1][i["column"]] = i["suggested_value"]
        audit.append(
            {
                "row": i["row"],
                "column": i["column"],
                "old_value": i["current_value"],
                "new_value": i["suggested_value"],
                "rule": i["rule"],
                "reason": i["reason"],
                "confidence": i["confidence"],
                "approval": "manually_approved",
            }
        )
    return result, audit


def operation_metrics(rows):
    if not any("attendance_status" in r for r in rows):
        return {"available": False, "sites": [], "trend": []}
    seen, groups, sites, days = set(), {}, {}, {}
    present = absent = counted = tasks = done = breached = sla_count = open_incidents = 0
    overtime = 0.0
    excluded = 0
    for r in rows:
        emp, day, shift = r.get("employee_id"), r.get("date"), r.get("shift")
        parsed_day, _ = date_value(day) if not missing(day) else (None, None)
        complete_key = not missing(emp) and parsed_day and not missing(shift)
        key = (str(emp).strip(), parsed_day, str(shift).strip().lower()) if complete_key else None
        if key and key in seen:
            excluded += 1
            continue
        if key:
            seen.add(key)
        site = str(r.get("site")).strip().title() if not missing(r.get("site")) else "Unassigned"
        status = CATEGORIES["attendance_status"].get(
            str(r.get("attendance_status", "")).strip().lower()
        )
        p = int(status == "Present")
        if status:
            counted += 1
            present += p
            absent += int(status == "Absent")
        stat = sites.setdefault(
            site,
            {
                "site": site,
                "present": 0,
                "records": 0,
                "absent": 0,
                "required": 0,
                "available": 0,
                "gap": 0,
            },
        )
        stat["present"] += p
        stat["records"] += int(status is not None)
        stat["absent"] += int(status == "Absent")
        if parsed_day:
            d = days.setdefault(parsed_day, {"date": parsed_day, "present": 0, "records": 0})
            d["present"] += p
            d["records"] += int(status is not None)
        # Requirements describe a site/day/shift, not a per-employee additive quantity.
        if parsed_day and not missing(shift) and site != "Unassigned":
            group = groups.setdefault(
                (site, parsed_day, str(shift).strip().lower()), {"required": 0, "people": set()}
            )
            req = numeric(r.get("required_staff"))
            if req is not None and 0 <= req <= 10000 and req == int(req):
                group["required"] = max(group["required"], req)
            if p and not missing(emp):
                group["people"].add(str(emp).strip())
        hours = numeric(r.get("hours_worked"))
        if hours is not None and 0 <= hours <= 16:
            overtime += max(0, hours - 8)
        if not missing(r.get("task_status")):
            tasks += 1
            done += str(r["task_status"]).strip().lower() in {"done", "complete", "completed"}
        if str(r.get("sla_status", "")).strip().lower() in {
            "met",
            "compliant",
            "breach",
            "breached",
            "at risk",
        }:
            sla_count += 1
            breached += str(r["sla_status"]).strip().lower() in {"breach", "breached"}
        incidents = numeric(r.get("incident_count"))
        if (
            incidents
            and incidents > 0
            and str(r.get("task_status", "")).strip().lower()
            not in {"done", "completed", "complete"}
        ):
            open_incidents += incidents
    for (site, _, _), g in groups.items():
        sites[site]["required"] += g["required"]
        sites[site]["available"] += len(g["people"])
        sites[site]["gap"] += max(0, g["required"] - len(g["people"]))
    required = sum(s["required"] for s in sites.values())
    gap = sum(s["gap"] for s in sites.values())
    for s in sites.values():
        s["attendance_rate"] = round(100 * s["present"] / max(1, s["records"]), 1)
    return {
        "available": True,
        "attendance_rate": round(100 * present / max(1, counted), 1),
        "absenteeism": round(100 * absent / max(1, counted), 1),
        "shift_coverage": round(100 * (required - gap) / max(1, required), 1),
        "staffing_gap": gap,
        "required_staff": required,
        "overtime_hours": round(overtime, 1),
        "task_completion": round(100 * done / max(1, tasks), 1),
        "sla_compliance": round(100 * (sla_count - breached) / max(1, sla_count), 1),
        "open_incidents": open_incidents,
        "duplicate_records_excluded": excluded,
        "sites": sorted(sites.values(), key=lambda s: s["gap"], reverse=True),
        "trend": [
            dict(d, attendance_rate=round(100 * d["present"] / max(1, d["records"]), 1))
            for _, d in sorted(days.items())
        ],
    }


def recommend_charts(rows, schema, operations):
    charts = []
    if operations["available"]:
        charts.append(
            {
                "id": "staffing",
                "type": "bar",
                "title": "Coverage, site by site",
                "subtitle": "Required and available staff-shifts; repeats excluded",
                "x": "site",
                "series": ["required", "available"],
                "data": operations["sites"],
            }
        )
        charts.append(
            {
                "id": "attendance",
                "type": "line",
                "title": "Attendance over time",
                "subtitle": "Present / recognized attendance records (%)",
                "x": "date",
                "series": ["attendance_rate"],
                "data": operations["trend"],
            }
        )
    cats = [
        s
        for s in schema
        if s["type"] == "category" and s["unique"] <= 30 and not s["name"].endswith("_id")
    ]
    nums = [s["name"] for s in schema if s["type"] == "numeric"]
    for s in cats[:2]:
        counts = Counter(
            str(r.get(s["name"])) if not missing(r.get(s["name"])) else "Missing" for r in rows
        )
        charts.append(
            {
                "id": f"count_{s['name']}",
                "type": "donut" if len(counts) <= 5 else "bar",
                "title": s["name"].replace("_", " ").title(),
                "subtitle": "Record distribution · includes missing values",
                "x": "category",
                "series": ["count"],
                "data": [{"category": k, "count": v} for k, v in counts.most_common(30)],
            }
        )
    if nums:
        col = nums[0]
        vals = [v for r in rows if (v := numeric(r.get(col))) is not None]
        if vals:
            lo, hi = min(vals), max(vals)
            step = (hi - lo) / 8 or 1
            bins = [0] * 8
            for v in vals:
                bins[min(7, int((v - lo) / step))] += 1
            charts.append(
                {
                    "id": "histogram",
                    "type": "bar",
                    "title": f"{col.replace('_', ' ').title()} distribution",
                    "subtitle": "Eight equal-width bins of valid numeric values",
                    "x": "range",
                    "series": ["count"],
                    "data": [
                        {"range": f"{lo + i * step:.1f}–{lo + (i + 1) * step:.1f}", "count": n}
                        for i, n in enumerate(bins)
                    ],
                }
            )
        if cats:
            groups = defaultdict(float)
            for r in rows:
                n = numeric(r.get(col))
                if n is not None:
                    groups[str(r.get(cats[0]["name"]) or "Missing")] += n
            charts.append(
                {
                    "id": "aggregate",
                    "type": "bar",
                    "title": f"{col.replace('_', ' ').title()} by {cats[0]['name'].replace('_', ' ')}",
                    "subtitle": "Sum of valid numeric values; top 20 groups",
                    "x": "category",
                    "series": ["total"],
                    "data": [
                        {"category": k, "total": round(v, 2)}
                        for k, v in sorted(groups.items(), key=lambda p: p[1], reverse=True)[:20]
                    ],
                }
            )
    if len(nums) >= 2:
        data = [
            {"x": numeric(r.get(nums[0])), "y": numeric(r.get(nums[1]))}
            for r in rows
            if numeric(r.get(nums[0])) is not None and numeric(r.get(nums[1])) is not None
        ][:500]
        charts.append(
            {
                "id": "scatter",
                "type": "scatter",
                "title": f"{nums[0]} vs {nums[1]}",
                "subtitle": "First 500 complete numeric pairs",
                "x": "x",
                "series": ["y"],
                "data": data,
            }
        )
    dates = [s["name"] for s in schema if s["type"] == "date"]
    if dates and nums and not operations["available"]:
        totals = defaultdict(float)
        for r in rows:
            day, error = date_value(r.get(dates[0]))
            n = numeric(r.get(nums[0]))
            if day and n is not None:
                totals[day] += n
        charts.append(
            {
                "id": "timeline",
                "type": "line",
                "title": f"{nums[0]} over time",
                "subtitle": "Sum by unambiguous date",
                "x": "date",
                "series": ["total"],
                "data": [{"date": k, "total": v} for k, v in sorted(totals.items())],
            }
        )
    charts.append(
        {
            "id": "missing",
            "type": "bar",
            "title": "Completeness by column",
            "subtitle": "Missing values remain visible; never silently filled",
            "x": "column",
            "series": ["missing"],
            "data": [{"column": s["name"], "missing": s["missing"]} for s in schema[:30]],
        }
    )
    return charts
