"""Reproducible synthetic facility operations. Never represents employer data."""

import csv
import io
import random
from datetime import date, timedelta


def demo_rows():
    rng = random.Random(42)
    sites = ["Vikhroli", "Andheri", "Lower Parel", "BKC", "Thane"]
    names = [
        "Aarav Shah",
        "Priya Nair",
        "Imran Khan",
        "Sneha Patil",
        "Rohan Das",
        "Anjali Rao",
        "Kabir Mehta",
        "Neha Kulkarni",
    ]
    rows = []
    for day in range(14):
        for s, site in enumerate(sites):
            for shift in ["Day", "Evening"]:
                for employee in range(9):
                    present = rng.random() > (0.2 if site == "Vikhroli" else 0.08)
                    rows.append(
                        {
                            "employee_id": f"EMP-{s * 100 + (0 if shift == 'Day' else 20) + employee + 1:04d}",
                            "employee_name": names[(employee + s) % len(names)],
                            "site": site,
                            "client": f"Demo client {s + 1}",
                            "date": (date(2026, 9, 1) + timedelta(days=day)).isoformat(),
                            "shift": shift,
                            "required_staff": 9,
                            "attendance_status": "Present" if present else "Absent",
                            "check_in": "08:00" if shift == "Day" else "14:00",
                            "check_out": "16:00" if shift == "Day" else "22:00",
                            "hours_worked": rng.choice([8, 8, 8, 9, 10]) if present else 0,
                            "task_status": "Completed" if rng.random() > 0.13 else "Pending",
                            "incident_count": 1 if rng.random() < 0.04 else 0,
                            "supervisor": f"Supervisor {s + 1}",
                            "remarks": "Synthetic demonstration record",
                            "sla_status": "Breached" if rng.random() < 0.045 else "Met",
                        }
                    )
    for i, r in enumerate(rows):
        if i % 11 == 0:
            r["site"] = " " + r["site"].upper() + " "
        if i % 17 == 0:
            r["attendance_status"] = str(r["attendance_status"]).lower()
        if i % 23 == 0:
            r["employee_id"] = " " + str(r["employee_id"]) + " "
        if i % 31 == 0:
            r["date"] = "14/09/2026"
        if i % 97 == 0:
            r["date"] = "01/02/26"
        if i % 103 == 0:
            r["hours_worked"] = 18
        if i % 127 == 0:
            r["employee_id"] = ""
        if i % 137 == 0:
            r["site"] = ""
        if i % 139 == 0:
            r["date"] = "2026-02-30"
        if i % 149 == 0:
            r["attendance_status"] = "Unknown"
        if i % 157 == 0:
            r["shift"] = ""
        if i % 163 == 0:
            r["hours_worked"] = 0
            r["attendance_status"] = "Present"
    rows.extend([dict(rows[i]) for i in (40, 160, 250, 370, 510, 710, 900, 1100)])
    return rows


def demo_csv():
    stream = io.StringIO(newline="")
    rows = demo_rows()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")
