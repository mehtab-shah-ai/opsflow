from copy import deepcopy
from io import BytesIO

import pytest
from openpyxl import Workbook

from app.domain import analyze, clean, numeric
from app.ingestion import IngestionError, parse_file, sheet_csv_url


def test_csv_delimiter_encoding_and_preserved_rows():
    tables = parse_file("messy.csv", "site;hours_worked\nCafé;8\nMumbai;18".encode("cp1252"))
    assert tables[0]["rows"][0]["site"] == "Café"
    assert len(tables[0]["rows"]) == 2


@pytest.mark.parametrize(
    "name,content",
    [("empty.csv", b""), ("bad.xlsx", b"hello"), ("bad.csv", b"PK\x03\x04"), ("bad.exe", b"abc")],
)
def test_invalid_uploads_rejected(name, content):
    with pytest.raises(IngestionError):
        parse_file(name, content)


def test_multi_sheet_and_offset_headers():
    book = Workbook()
    book.active.append(["Monthly operations"])
    book.active.append(["employee_id", "site", "hours_worked"])
    book.active.append(["E1", "Mumbai", 8])
    sheet = book.create_sheet("Second")
    sheet.append(["employee_id", "site"])
    sheet.append(["E2", "Thane"])
    stream = BytesIO()
    book.save(stream)
    tables = parse_file("book.xlsx", stream.getvalue())
    assert len(tables) == 2
    assert tables[0]["rows"][0]["employee_id"] == "E1"


def test_cleaning_preserves_original_and_flags_ambiguity():
    rows = [
        {
            "employee_id": " E1 ",
            "site": "VIKHROLI ",
            "date": "01/02/26",
            "hours_worked": "18",
            "attendance_status": "Present",
        }
    ]
    original = deepcopy(rows)
    result = analyze(rows)
    assert any(
        x["issue_type"] == "ambiguous_date" and not x["auto_fixable"] for x in result["issues"]
    )
    fixes = [i["issue_id"] for i in result["issues"] if i["auto_fixable"]]
    cleaned, audit = clean(rows, result["issues"], fixes)
    assert rows == original
    assert len(cleaned) == len(rows)
    assert cleaned[0]["site"] == "Vikhroli"
    assert audit and audit[0]["old_value"] != audit[0]["new_value"]
    assert analyze(cleaned)["quality_score"] > result["quality_score"]


def test_duplicates_flagged_not_deleted():
    row = {
        "employee_id": "E1",
        "date": "2026-09-01",
        "shift": "Day",
        "site": "Mumbai",
        "attendance_status": "Present",
        "hours_worked": 8,
        "required_staff": 2,
    }
    result = analyze([row, row.copy()])
    assert any(i["issue_type"] == "duplicate_row" for i in result["issues"])
    assert result["operations"]["sites"][0]["available"] == 1
    assert result["operations"]["sites"][0]["gap"] == 1


@pytest.mark.parametrize("value,expected", [("₹12,500", 12500), ("12.5k", 12500), ("18%", 0.18)])
def test_number_formats(value, expected):
    assert numeric(value) == expected


def test_google_sheet_url_is_allowlisted():
    assert sheet_csv_url("https://docs.google.com/spreadsheets/d/abc123/edit#gid=42").endswith(
        "gid=42"
    )
    with pytest.raises(IngestionError):
        sheet_csv_url("http://127.0.0.1/secret")


def test_cleaning_rejects_forged_ids():
    with pytest.raises(ValueError):
        clean([{"site": "Mumbai"}], [], ["invented"])
