import asyncio
import hashlib
import json
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .ai import ProviderRouter, executive_summary
from .chat import respond, stream_respond
from .config import CORS, MAX_QUEUE, MAX_STORAGE, MAX_UPLOAD, ROOT
from .demo import demo_csv
from .domain import analyze, clean, numeric
from .exports import export_table, report_pdf
from .ingestion import IngestionError, parse_file, sheet_csv_url
from .repository import Conflict, Repository

logger = logging.getLogger("opsflow")
logging.basicConfig(level=logging.INFO, format="%(message)s")
# Never log provider URLs/authorization or raw uploaded values.
logging.getLogger("httpx").setLevel(logging.WARNING)


class CleanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=0)
    approved_ids: list[str] = Field(min_length=1, max_length=100000)
    confirmed: Literal[True]


class Selection(BaseModel):
    table: int = Field(ge=0, le=100)


class SheetRequest(BaseModel):
    url: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1500)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(default="", max_length=100)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=128)


def owner_token(request: Request, x_workspace_token: str = Header(default="")):
    token = x_workspace_token
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    if not token or not re.fullmatch(r"[a-zA-Z0-9_-]{16,128}", token):
        raise HTTPException(
            401, "Workspace key missing. Reload the app or sign in to create a private workspace."
        )
    repo = getattr(request.app.state, "repo", None)
    if repo:
        user = repo.get_user_by_session(token)
        if user:
            return f"user_{user['id']}"
    return hashlib.sha256(token.encode()).hexdigest()



def public_job(job):
    return {k: v for k, v in job.items() if k not in {"owner", "fingerprint", "parsed"}}


def public_dataset(d):
    return {k: v for k, v in d.items() if k not in {"owner", "data", "fingerprint"}}


class JobRunner:
    def __init__(self, repo):
        self.repo = repo
        self.queue = asyncio.Queue(MAX_QUEUE)
        self.selection = {}

    async def stage(self, job, name, progress):
        now = time.perf_counter()
        if job.get("_stage_started"):
            job["durations"][job["stage"]] = round(now - job["_stage_started"], 4)
        job.update(stage=name, progress=progress, _stage_started=now)
        self.repo.update_job(job)
        logger.info(json.dumps({"event": "job_stage", "job_id": job["id"], "stage": name}))

    async def worker(self):
        while True:
            job, selected = await self.queue.get()
            started = time.perf_counter()
            try:
                job.update(status="processing")
                if selected is None:
                    await self.stage(job, "Parsing", 12)
                    raw = self.repo.raw(job["id"], job["owner"])
                    tables = await asyncio.to_thread(parse_file, job["filename"], raw)
                    await self.stage(job, "Detecting schema", 28)
                    job["tables"] = [
                        {
                            "index": i,
                            "name": t["name"],
                            "rows": len(t["rows"]),
                            "columns": t["columns"],
                            "page": t["page"],
                            "confidence": t["confidence"],
                            "preview": t["rows"][:5],
                            "warnings": t["warnings"],
                        }
                        for i, t in enumerate(tables)
                    ]
                    if len(tables) > 1:
                        # Bound memory held by pending selection. User can reupload after restart/expiry.
                        if len(self.selection) >= 8:
                            raise IngestionError(
                                "Too many workbooks await table selection. Finish an existing import and retry."
                            )
                        self.selection[job["id"]] = (time.time(), tables)
                        job.update(status="awaiting_selection", stage="Choose a table", progress=30)
                        self.repo.update_job(job)
                        continue
                    table = tables[0]
                else:
                    table = selected
                await self.stage(job, "Profiling data", 38)
                await self.stage(job, "Scanning quality", 48)
                result = await asyncio.to_thread(analyze, table["rows"])
                await self.stage(job, "Checking business rules", 67)
                await self.stage(job, "Building analytics", 79)
                await self.stage(job, "Preparing results", 92)
                did = uuid.uuid4().hex
                dataset = {
                    "id": did,
                    "job_id": job["id"],
                    "owner": job["owner"],
                    "filename": job["filename"],
                    "table_name": table["name"],
                    "created": time.time(),
                    "fingerprint": job["fingerprint"],
                    "demo": job.get("demo", False),
                    "version": 0,
                    "quality_before": result["quality_score"],
                    "analysis": result,
                    "data": table["rows"],
                    "warnings": table["warnings"],
                    "duration": round(time.perf_counter() - started, 3),
                }
                self.repo.create_dataset(dataset)
                job.update(
                    status="completed",
                    stage="Ready for review",
                    progress=100,
                    dataset_id=did,
                    rows=result["rows"],
                    issues=len(result["issues"]),
                    quality_before=result["quality_score"],
                    duration=dataset["duration"],
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                safe = (
                    str(exc)
                    if isinstance(exc, (IngestionError, ValueError))
                    else "This file could not be processed safely. Retry with a smaller CSV or unlocked workbook. Original data was not changed."
                )
                job.update(status="failed", stage="Needs attention", error=safe, progress=0)
                logger.warning(
                    json.dumps(
                        {"event": "job_failed", "job_id": job["id"], "category": type(exc).__name__}
                    )
                )
            finally:
                job.pop("_stage_started", None)
                self.repo.update_job(job)
                self.queue.task_done()

    async def enqueue(self, owner, filename, raw, demo=False):
        if len(raw) > MAX_UPLOAD:
            raise HTTPException(
                413,
                f"File exceeds the {MAX_UPLOAD // 1024 // 1024} MB limit. Split it into smaller files.",
            )
        if not raw:
            raise HTTPException(400, "This file is empty. No data was changed.")
        fingerprint = hashlib.sha256(Path(filename).suffix.lower().encode() + raw).hexdigest()
        cached = self.repo.cached_job(owner, fingerprint)
        if cached:
            return public_job(cached)
        if self.queue.full():
            raise HTTPException(
                429,
                "The processing queue is full. Wait for an existing file to finish, then retry.",
            )
        if self.repo.storage_bytes() + len(raw) > MAX_STORAGE:
            raise HTTPException(
                507,
                "This demo runtime has reached its storage limit. Download existing results and restart the demo service.",
            )
        job = {
            "id": uuid.uuid4().hex,
            "owner": owner,
            "filename": re.sub(r"[^\w. -]", "_", Path(filename.replace("\\", "/")).name)[:150],
            "fingerprint": fingerprint,
            "created": time.time(),
            "status": "queued",
            "stage": "Queued",
            "progress": 2,
            "demo": demo,
            "durations": {},
        }
        self.repo.create_job(job, raw)
        self.queue.put_nowait((job, None))
        return public_job(job)


def create_app(runtime: Path | None = None):
    root = runtime or Path(os.getenv("RUNTIME_DIR", str(ROOT / "runtime")))

    @asynccontextmanager
    async def lifespan(app):
        app.state.repo = Repository(root)
        app.state.runner = JobRunner(app.state.repo)
        app.state.router = ProviderRouter()
        app.state.last_diagnostic = 0
        app.state.rate = {}
        app.state.started = time.time()
        task = asyncio.create_task(app.state.runner.worker())
        if os.getenv("PROVIDER_STARTUP_TEST", "false").lower() == "true":
            asyncio.create_task(app.state.router.diagnostics())
        yield
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    app = FastAPI(title="OpsFlow AI", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "X-Request-ID"],
    )

    @app.get("/health")
    def health_check():
        return {"status": "ok", "service": "OpsFlow Backend"}

    @app.middleware("http")
    async def safety(request: Request, call_next):
        rid = uuid.uuid4().hex[:16]
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > MAX_UPLOAD + 1024 * 1024):
            return JSONResponse(
                {"detail": "Request exceeds the upload limit. Original data was not changed."},
                status_code=413,
            )
        if request.method == "POST":
            identity = request.client.host if request.client else "unknown"
            now = time.time()
            rate = app.state.rate
            for key in list(rate):
                if rate[key][0] < now - 60:
                    del rate[key]
            start, count = rate.get(identity, (now, 0))
            if count >= 90:
                return JSONResponse(
                    {"detail": "Too many requests. Wait a minute and retry."}, status_code=429
                )
            rate[identity] = (start, count + 1)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(Conflict)
    async def conflict_handler(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(IngestionError)
    async def ingestion_handler(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(ValueError)
    async def value_handler(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(Exception)
    async def error_handler(request, exc):
        logger.error(json.dumps({"event": "request_failed", "category": type(exc).__name__}))
        return JSONResponse(
            {
                "detail": "The operation could not finish. Retry or upload a smaller file. Original data remains unchanged."
            },
            status_code=500,
        )

    def dataset(did, owner):
        value = app.state.repo.dataset(did, owner)
        if value is None:
            raise HTTPException(
                404,
                "Dataset not found in this workspace. The free runtime may have reset; import it again.",
            )
        return value

    @app.get("/health")
    async def health():
        return {"status": "ready", "version": "1.0.0", "database": "connected"}

    @app.post("/api/auth/register")
    async def register(body: RegisterRequest):
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", body.email):
            raise HTTPException(400, "Please enter a valid email address.")
        user = app.state.repo.create_user(body.email, body.name, body.password)
        token = app.state.repo.create_session(user["id"])
        app.state.repo.clear_owner_messages(f"user_{user['id']}")
        return {"token": token, "user": user}

    @app.post("/api/auth/login")
    async def login(body: LoginRequest):
        user = app.state.repo.authenticate_user(body.email, body.password)
        if not user:
            raise HTTPException(401, "Invalid email or password.")
        token = app.state.repo.create_session(user["id"])
        app.state.repo.clear_owner_messages(f"user_{user['id']}")
        return {"token": token, "user": user}

    @app.post("/api/auth/demo-login")
    async def demo_login():
        demo_email = "demo.operator@opsflow.ai"
        user = app.state.repo.authenticate_user(demo_email, "demo123456")
        if not user:
            user = app.state.repo.create_user(demo_email, "Demo Operator", "demo123456")
        token = app.state.repo.create_session(user["id"])
        app.state.repo.clear_owner_messages(f"user_{user['id']}")
        return {"token": token, "user": user}

    @app.get("/api/auth/me")
    async def me(request: Request, x_workspace_token: str = Header(default="")):
        token = x_workspace_token
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
        user = app.state.repo.get_user_by_session(token) if token else None
        if not user:
            return {"authenticated": False, "user": None}
        return {"authenticated": True, "user": user}

    @app.post("/api/auth/logout")
    async def logout(request: Request, x_workspace_token: str = Header(default="")):
        token = x_workspace_token
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
        if token:
            app.state.repo.delete_session(token)
        return {"ok": True}

    @app.post("/api/workspace/clean")
    async def clean_workspace(owner=Depends(owner_token)):
        app.state.repo.clear_owner_workspace(owner)
        return {"status": "cleaned", "message": "Workspace data has been reset."}

    @app.get("/api/status")
    async def status(owner=Depends(owner_token)):
        return {
            "backend": "ready",
            "version": "1.0.0",
            "database": "SQLite · WAL",
            "persistence": "Temporary runtime storage; resets on redeploy or restart on Render. Download important outputs.",
            "uptime_seconds": round(time.time() - app.state.started),
            "queue": app.state.runner.queue.qsize(),
            "queue_limit": MAX_QUEUE,
            "max_upload_mb": MAX_UPLOAD // 1024 // 1024,
            "max_rows": 20000,
            "providers": app.state.router.health(),
            "formats": ["CSV", "XLSX", "XLS", "Native PDF", "Public Google Sheets"],
            "vision": "Unavailable · upload native PDF or spreadsheet",
        }

    @app.post("/api/providers/test")
    async def providers(owner=Depends(owner_token)):
        if time.time() - app.state.last_diagnostic < 60:
            raise HTTPException(
                429, "Diagnostics were run recently. Wait one minute to protect your API quota."
            )
        app.state.last_diagnostic = time.time()
        return await app.state.router.diagnostics()

    @app.post("/api/uploads", status_code=202)
    async def upload(file: UploadFile, owner=Depends(owner_token)):
        try:
            raw = await file.read(MAX_UPLOAD + 1)
            return await app.state.runner.enqueue(owner, file.filename or "upload.csv", raw)
        finally:
            await file.close()

    @app.post("/api/demo", status_code=202)
    async def demo(owner=Depends(owner_token)):
        return await app.state.runner.enqueue(
            owner, "facility_operations_messy.csv", demo_csv(), True
        )

    @app.post("/api/sheets", status_code=202)
    async def sheets(body: SheetRequest, owner=Depends(owner_token)):
        url = sheet_csv_url(body.url)
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                for _ in range(4):
                    async with client.stream("GET", url) as response:
                        if response.is_redirect:
                            target = response.headers.get("location", "")
                            parsed = urlparse(target)
                            if (
                                parsed.scheme != "https"
                                or not parsed.hostname
                                or not (
                                    parsed.hostname == "docs.google.com"
                                    or parsed.hostname.endswith(".googleusercontent.com")
                                )
                                or parsed.port not in (None, 443)
                            ):
                                raise IngestionError(
                                    "This sheet requires sign-in or redirects outside the public Sheets export. Enable public link access and retry."
                                )
                            url = target
                            continue
                        if response.status_code != 200:
                            raise IngestionError(
                                "Google Sheet access was denied. Enable public link access and verify the worksheet."
                            )
                        data = bytearray()
                        async for chunk in response.aiter_bytes():
                            data.extend(chunk)
                            if len(data) > MAX_UPLOAD:
                                raise HTTPException(
                                    413, "Google Sheet exceeds the upload size limit."
                                )
                        if (
                            bytes(data[:200])
                            .lstrip()
                            .lower()
                            .startswith((b"<!doctype html", b"<html"))
                        ):
                            raise IngestionError(
                                "Google returned a sign-in page. Use a publicly accessible worksheet."
                            )
                        return await app.state.runner.enqueue(
                            owner, "google_sheet.csv", bytes(data)
                        )
                raise IngestionError("Too many redirects. Verify the public Google Sheet URL.")
        except httpx.HTTPError as exc:
            raise IngestionError(
                "The sheet could not be reached. Check its sharing permissions and retry."
            ) from exc

    @app.get("/api/jobs")
    def jobs(owner=Depends(owner_token)):
        return {"items": [public_job(j) for j in app.state.repo.jobs(owner)]}

    @app.get("/api/jobs/{jid}")
    def job(jid: str, owner=Depends(owner_token)):
        j = app.state.repo.get_job(jid, owner)
        if not j:
            raise HTTPException(404, "Run expired or not found. Re-import the source.")
        return public_job(j)

    @app.post("/api/jobs/{jid}/select", status_code=202)
    async def select(jid: str, body: Selection, owner=Depends(owner_token)):
        j = app.state.repo.get_job(jid, owner)
        runner = app.state.runner
        if not j:
            raise HTTPException(404, "Run not found.")
        stored = runner.selection.get(jid)
        if j["status"] != "awaiting_selection" or stored is None:
            raise HTTPException(
                409, "This selection expired or was already submitted. Re-import or refresh."
            )
        if runner.queue.full():
            raise HTTPException(429, "Queue full. Retry shortly.")
        tables = stored[1]
        if body.table >= len(tables):
            raise HTTPException(400, "Choose one of the detected tables.")
        chosen = tables[body.table]
        del runner.selection[jid]
        j.update(status="queued", stage="Table selected")
        app.state.repo.update_job(j)
        runner.queue.put_nowait((j, chosen))
        return public_job(j)

    @app.get("/api/datasets/{did}")
    def detail(did: str, owner=Depends(owner_token)):
        return public_dataset(dataset(did, owner))

    @app.get("/api/datasets/{did}/rows")
    def rows(
        did: str,
        page: int = Query(1, ge=1),
        size: int = Query(25, ge=1, le=100),
        search: str = Query("", max_length=200),
        sort: str = "",
        descending: bool = False,
        original: bool = False,
        owner=Depends(owner_token),
    ):
        d = dataset(did, owner)
        data = app.state.repo.original_rows(did, owner) if original else d["data"]
        if search:
            data = [
                r for r in data if any(search.casefold() in str(v).casefold() for v in r.values())
            ]
        if sort:
            if sort not in [s["name"] for s in d["analysis"]["schema"]]:
                raise HTTPException(400, "Unknown sort column.")
            data = sorted(
                data,
                key=lambda r: (
                    numeric(r.get(sort)) is not None,
                    numeric(r.get(sort)) or 0,
                    str(r.get(sort, "")),
                ),
                reverse=descending,
            )
        return {
            "items": data[(page - 1) * size : page * size],
            "total": len(data),
            "page": page,
            "size": size,
        }

    @app.get("/api/datasets/{did}/preview")
    def preview(did: str, owner=Depends(owner_token)):
        d = dataset(did, owner)
        return {
            "version": d["version"],
            "items": [i for i in d["analysis"]["issues"] if i["auto_fixable"]],
        }

    @app.post("/api/datasets/{did}/clean")
    def apply_clean(did: str, body: CleanRequest, owner=Depends(owner_token)):
        d = dataset(did, owner)
        if d["version"] != body.version:
            raise Conflict("Preview is outdated. Refresh before applying changes.")
        changed, audit = clean(d["data"], d["analysis"]["issues"], body.approved_ids)
        d.update(data=changed, version=d["version"] + 1, analysis=analyze(changed))
        app.state.repo.save_version(d, body.version, audit)
        return public_dataset(d)

    @app.get("/api/datasets/{did}/audit")
    def audit(did: str, owner=Depends(owner_token)):
        dataset(did, owner)
        return {"items": app.state.repo.audit(did)}

    @app.get("/api/datasets/{did}/original")
    def original(did: str, owner=Depends(owner_token)):
        d = dataset(did, owner)
        return Response(
            app.state.repo.raw(d["job_id"], owner),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": 'attachment; filename="original-source'
                + Path(d["filename"]).suffix
                + '"'
            },
        )

    @app.post("/api/datasets/{did}/summary")
    async def summary(did: str, owner=Depends(owner_token)):
        d = dataset(did, owner)
        return await executive_summary(d, app.state.router, app.state.repo)

    @app.get("/api/datasets/{did}/chat")
    def messages(did: str, owner=Depends(owner_token)):
        dataset(did, owner)
        return {"items": app.state.repo.messages(did)}

    @app.delete("/api/datasets/{did}/chat")
    def clear_chat_messages(did: str, owner=Depends(owner_token)):
        dataset(did, owner)
        app.state.repo.clear_messages(did)
        return {"ok": True}

    @app.post("/api/datasets/{did}/chat")
    async def chat(did: str, body: ChatRequest, owner=Depends(owner_token)):
        d = dataset(did, owner)
        return await respond(d, body.message, app.state.router, app.state.repo)

    @app.post("/api/datasets/{did}/chat/stream")
    async def chat_stream(did: str, body: ChatRequest, owner=Depends(owner_token)):
        d = dataset(did, owner)
        return StreamingResponse(
            stream_respond(d, body.message, app.state.router, app.state.repo),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/datasets/{did}/export")
    def export(
        did: str,
        format: Literal["csv", "xlsx", "pdf"] = "csv",
        kind: Literal["data", "issues", "audit"] = "data",
        severity: Literal["critical", "warning", "info"] | None = None,
        report: Literal["daily", "quality", "exceptions"] = "daily",
        period: Literal["all", "daily", "weekly", "monthly"] = "all",
        owner=Depends(owner_token),
    ):
        d = dataset(did, owner)
        if format == "pdf":
            # Periods are anchored to the latest valid dataset date, not the server clock.
            if period != "all":
                from datetime import date, timedelta

                from .domain import date_value

                dates = [(r, date_value(r.get("date"))[0]) for r in d["data"]]
                valid = [day for _, day in dates if day]
                if not valid:
                    raise HTTPException(
                        400, "Period reports require valid dates. Choose all records."
                    )
                latest = date.fromisoformat(max(valid))
                start = (
                    latest
                    if period == "daily"
                    else latest - timedelta(days=6)
                    if period == "weekly"
                    else latest.replace(day=1)
                )
                data = [
                    r for r, day in dates if day and start.isoformat() <= day <= latest.isoformat()
                ]
                from copy import deepcopy

                d = deepcopy(d)
                d["data"] = data
                d["analysis"] = analyze(data)
                period = f"{period}: {start} to {latest}; ambiguous/invalid dates excluded"
            content = report_pdf(d, app.state.repo.audit(did), report, period)
            mime = "application/pdf"
        else:
            rows = (
                d["analysis"]["issues"]
                if kind == "issues"
                else app.state.repo.audit(did)
                if kind == "audit"
                else d["data"]
            )
            if severity and kind == "issues":
                rows = [r for r in rows if r["severity"] == severity]
            content = export_table(rows, format)
            mime = (
                "text/csv; charset=utf-8"
                if format == "csv"
                else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        return Response(
            content,
            media_type=mime,
            headers={
                "Content-Disposition": f'attachment; filename="opsflow-{kind}-v{d["version"]}.{format}"'
            },
        )

    return app


app = create_app()
