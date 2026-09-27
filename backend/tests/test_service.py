import io
import json
import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        yield c


HEAD = {"X-Workspace-Token": "a" * 32}


def wait_job(c, job, headers=HEAD):
    for _ in range(100):
        j = c.get(f"/api/jobs/{job}", headers=headers).json()
        if j.get("status") in ("completed", "failed", "awaiting_selection"):
            return j
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_full_upload_clean_export_immutable(client):
    raw = b"employee_id,site,date,shift,hours_worked,attendance_status\n E1 ,VIKHROLI ,2026-09-01,day,8,present\n"
    r = client.post("/api/uploads", headers=HEAD, files={"file": ("ops.csv", raw, "text/csv")})
    assert r.status_code == 202
    j = wait_job(client, r.json()["id"])
    assert j["status"] == "completed", j
    did = j["dataset_id"]
    data = client.get(f"/api/datasets/{did}", headers=HEAD).json()
    fixes = [i["issue_id"] for i in data["analysis"]["issues"] if i["auto_fixable"]]
    assert (
        client.post(
            f"/api/datasets/{did}/clean",
            headers=HEAD,
            json={"version": 0, "approved_ids": fixes, "confirmed": False},
        ).status_code
        == 422
    )
    applied = client.post(
        f"/api/datasets/{did}/clean",
        headers=HEAD,
        json={"version": 0, "approved_ids": fixes, "confirmed": True},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["version"] == 1
    assert client.get(f"/api/datasets/{did}/original", headers=HEAD).content == raw
    assert (
        client.post(
            f"/api/datasets/{did}/clean",
            headers=HEAD,
            json={"version": 0, "approved_ids": fixes, "confirmed": True},
        ).status_code
        == 409
    )
    assert client.get(f"/api/datasets/{did}/audit", headers=HEAD).json()["items"]
    for fmt in ("csv", "xlsx", "pdf"):
        exported = client.get(f"/api/datasets/{did}/export?format={fmt}", headers=HEAD)
        assert exported.status_code == 200 and len(exported.content) > 30
    assert (
        client.get(f"/api/datasets/{did}", headers={"X-Workspace-Token": "b" * 32}).status_code
        == 404
    )


def test_invalid_file_fails_job_without_blocking_next(client):
    bad = client.post(
        "/api/uploads", headers=HEAD, files={"file": ("corrupt.xlsx", b"garbage")}
    ).json()
    assert wait_job(client, bad["id"])["status"] == "failed"
    good = client.post("/api/demo", headers=HEAD).json()
    assert wait_job(client, good["id"])["status"] == "completed"


def test_csv_formula_export_and_duplicate_upload(client):
    raw = b"name,value\n=HYPERLINK(test),5\n"
    first = client.post("/api/uploads", headers=HEAD, files={"file": ("risk.csv", raw)}).json()
    done = wait_job(client, first["id"])
    second = client.post("/api/uploads", headers=HEAD, files={"file": ("risk.csv", raw)}).json()
    assert second["id"] == first["id"]
    exported = client.get(f"/api/datasets/{done['dataset_id']}/export?format=csv", headers=HEAD)
    assert "'=HYPERLINK" in exported.text


def test_pdf_and_workbook_selection(client):
    from openpyxl import Workbook

    book = Workbook()
    book.active.append(["site", "hours"])
    book.active.append(["Mumbai", 8])
    sheet = book.create_sheet("Second")
    sheet.append(["site", "hours"])
    sheet.append(["Thane", 9])
    buf = io.BytesIO()
    book.save(buf)
    job = client.post(
        "/api/uploads", headers=HEAD, files={"file": ("multi.xlsx", buf.getvalue())}
    ).json()
    done = wait_job(client, job["id"])
    assert done["status"] == "awaiting_selection"
    assert len(done["tables"]) == 2
    assert (
        client.post(f"/api/jobs/{job['id']}/select", headers=HEAD, json={"table": 1}).status_code
        == 202
    )
    done = wait_job(client, job["id"])
    assert done["status"] == "completed"
    rows = client.get(f"/api/datasets/{done['dataset_id']}/rows", headers=HEAD).json()
    assert rows["items"][0]["site"] == "Thane"


def test_safe_chat_does_not_apply_mutations(client):
    done = wait_job(client, client.post("/api/demo", headers=HEAD).json()["id"])
    did = done["dataset_id"]
    result = client.post(
        f"/api/datasets/{did}/chat", headers=HEAD, json={"message": "Normalize the date values"}
    ).json()
    assert result["action"] == "preview_cleaning"
    assert client.get(f"/api/datasets/{did}", headers=HEAD).json()["version"] == 0
    chart = client.post(
        f"/api/datasets/{did}/chat",
        headers=HEAD,
        json={"message": "Create a site-wise attendance chart"},
    ).json()
    assert chart["chart"]["data"]

    # Test missing value query triggers preview_cleaning
    missing_resp = client.post(
        f"/api/datasets/{did}/chat",
        headers=HEAD,
        json={"message": "Remove missing values and clean data"},
    ).json()
    assert missing_resp["action"] == "preview_cleaning"
    assert "missing" in missing_resp["text"].lower() or "auto-fixable" in missing_resp["text"].lower()

    # Test absent staff lookup
    absent_resp = client.post(
        f"/api/datasets/{did}/chat",
        headers=HEAD,
        json={"message": "Who is absent?"},
    ).json()
    assert absent_resp["items"]
    assert any("absent" in str(r.get("attendance_status", "")).lower() for r in absent_resp["items"])

    # Test dynamic overtime chart and records
    ot_resp = client.post(
        f"/api/datasets/{did}/chat",
        headers=HEAD,
        json={"message": "Show overtime chart and top overtime hours"},
    ).json()
    assert ot_resp["chart"]["data"]
    assert "overtime" in ot_resp["text"].lower()

    # Test SSE chat streaming endpoint
    with client.stream(
        "POST",
        f"/api/datasets/{did}/chat/stream",
        headers=HEAD,
        json={"message": "any null and duplicates values"},
    ) as stream_resp:
        assert stream_resp.status_code == 200
        assert "text/event-stream" in stream_resp.headers["content-type"]
        events = []
        for line in stream_resp.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
        assert len(events) >= 1
        assert any("token" in ev for ev in events)
        assert any(ev.get("done") is True for ev in events)


def test_user_auth_and_data_isolation(client):
    # Register user 1
    reg1 = client.post(
        "/api/auth/register",
        json={"email": "alice@opsflow.ai", "name": "Alice", "password": "password123"},
    )
    assert reg1.status_code == 200, reg1.text
    token1 = reg1.json()["token"]
    head1 = {"X-Workspace-Token": token1}

    # Duplicate register should fail
    dup = client.post(
        "/api/auth/register",
        json={"email": "alice@opsflow.ai", "name": "Alice 2", "password": "password123"},
    )
    assert dup.status_code == 409

    # Register user 2
    reg2 = client.post(
        "/api/auth/register",
        json={"email": "bob@opsflow.ai", "name": "Bob", "password": "password456"},
    )
    assert reg2.status_code == 200
    token2 = reg2.json()["token"]
    head2 = {"X-Workspace-Token": token2}

    # Verify /api/auth/me
    me1 = client.get("/api/auth/me", headers=head1).json()
    assert me1["authenticated"] is True
    assert me1["user"]["email"] == "alice@opsflow.ai"

    # User 1 creates a dataset
    raw1 = b"employee_id,site,date,shift,hours_worked,attendance_status\nE101,SiteAlpha,2026-09-01,day,8,present\n"
    j1 = client.post("/api/uploads", headers=head1, files={"file": ("alice_ops.csv", raw1, "text/csv")}).json()
    done1 = wait_job(client, j1["id"], headers=head1)
    assert done1["status"] == "completed"
    did1 = done1["dataset_id"]

    # User 1 can see dataset
    assert client.get(f"/api/datasets/{did1}", headers=head1).status_code == 200

    # User 2 CANNOT see user 1's dataset (ISOLATION)
    assert client.get(f"/api/datasets/{did1}", headers=head2).status_code == 404

    # User 2's job list is empty
    jobs2 = client.get("/api/jobs", headers=head2).json()["items"]
    assert len(jobs2) == 0

    # User 1's job list has user 1's job
    jobs1 = client.get("/api/jobs", headers=head1).json()["items"]
    assert len(jobs1) == 1
    assert jobs1[0]["filename"] == "alice_ops.csv"

    # Test clean workspace for User 1
    clean_res = client.post("/api/workspace/clean", headers=head1)
    assert clean_res.status_code == 200
    assert len(client.get("/api/jobs", headers=head1).json()["items"]) == 0
    assert client.get(f"/api/datasets/{did1}", headers=head1).status_code == 404

    # Test fast demo-login
    demo_auth = client.post("/api/auth/demo-login").json()
    assert demo_auth["token"]
    assert demo_auth["user"]["email"] == "demo.operator@opsflow.ai"


