from __future__ import annotations

import asyncio
import hashlib
import io
import json
import shutil
import sqlite3
import sys
import tempfile
import time
import threading
import zipfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Optional

from starlette.background import BackgroundTask
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse

from tmx_processor.analyzer import DataAnalyzer
from tmx_processor.cleaner import CleanConfig, DataCleaner
from tmx_processor.converter import ConvertOptions, DataConverter, OutputFormat
from tmx_processor.deduper import DataDeduper
from tmx_processor.parser import TMXParser, TranslationUnit
from tmx_processor.validator import DataValidator

BASE_DIR = Path(__file__).parent.resolve()
UPLOAD_DIR = BASE_DIR / "_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Configuration
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_REQUEST_BODY_SIZE = MAX_UPLOAD_SIZE + 1024 * 1024  # allow multipart overhead
MAX_STREAM_UPLOAD_SIZE = 1024 * 1024 * 1024  # 1 GiB; disk-backed streaming pipeline
MAX_STREAM_REQUEST_BODY_SIZE = MAX_STREAM_UPLOAD_SIZE + 1024 * 1024
STREAM_JOB_TTL = 3600
MAX_SESSIONS = 50
MAX_SESSION_ESTIMATED_BYTES = 128 * 1024 * 1024
MAX_TOTAL_SESSION_ESTIMATED_BYTES = 512 * 1024 * 1024
SESSION_TTL = 3600  # 1 hour in seconds
SESSION_CLEANUP_INTERVAL = 60
DEFAULT_HOST = "127.0.0.1"

class _RequestBodyTooLarge(Exception):
    pass


class RequestBodyLimitMiddleware:
    def __init__(
        self, app, max_body_size: int, large_body_size: Optional[int] = None
    ):
        self.app = app
        self.max_body_size = max_body_size
        self.large_body_size = large_body_size or max_body_size

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_limit = (
            self.large_body_size
            if scope.get("path") == "/api/large-pipeline"
            else self.max_body_size
        )
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    if int(value) > request_limit:
                        await self._send_too_large(send)
                        return
                except ValueError:
                    pass

        received_size = 0
        response_started = False

        async def limited_receive():
            nonlocal received_size
            message = await receive()
            if message["type"] == "http.request":
                received_size += len(message.get("body", b""))
                if received_size > request_limit:
                    raise _RequestBodyTooLarge
            return message

        async def track_response(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, track_response)
        except _RequestBodyTooLarge:
            if not response_started:
                await self._send_too_large(send)

    async def _send_too_large(self, send):
        body = b'{"detail":"Request body too large"}'
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


async def _session_cleanup_loop():
    while True:
        await asyncio.sleep(SESSION_CLEANUP_INTERVAL)
        _cleanup_old_sessions()


@asynccontextmanager
async def lifespan(_app):
    cleanup_task = asyncio.create_task(_session_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="TMX Processor API",
    description="API за обработка на TMX езикови файлове за AI обучение",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    RequestBodyLimitMiddleware,
    max_body_size=MAX_REQUEST_BODY_SIZE,
    large_body_size=MAX_STREAM_REQUEST_BODY_SIZE,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_STORAGE: Dict[str, List[TranslationUnit]] = {}
_HEADERS: Dict[str, dict] = {}
_TIMESTAMPS: Dict[str, float] = {}  # Track last session activity
_SESSION_SIZES: Dict[str, int] = {}
_SESSION_LOCK = threading.Lock()
_STREAM_JOBS: Dict[str, dict] = {}
_STREAM_ACTIVE: set[str] = set()
_STREAM_JOB_LOCK = threading.Lock()


@app.middleware("http")
async def cleanup_expired_sessions(request, call_next):
    _cleanup_old_sessions()
    return await call_next(request)


def _cleanup_old_sessions():
    """Remove sessions idle longer than the TTL."""
    current_time = time.time()
    with _SESSION_LOCK:
        expired_keys = [
            key for key, ts in _TIMESTAMPS.items()
            if current_time - ts > SESSION_TTL
        ]
        for key in expired_keys:
            _STORAGE.pop(key, None)
            _HEADERS.pop(key, None)
            _TIMESTAMPS.pop(key, None)
            _SESSION_SIZES.pop(key, None)
    _cleanup_old_stream_jobs()


def _cleanup_old_stream_jobs() -> None:
    cutoff = time.time() - STREAM_JOB_TTL
    with _STREAM_JOB_LOCK:
        expired = [key for key, job in _STREAM_JOBS.items() if job["created"] < cutoff]
        for key in expired:
            shutil.rmtree(job["directory"], ignore_errors=True)
            _STREAM_JOBS.pop(key, None)


def _object_graph_size(value) -> int:
    size = sys.getsizeof(value)
    if isinstance(value, dict):
        for key, item in value.items():
            size += _object_graph_size(key) + _object_graph_size(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            size += _object_graph_size(item)
    return size


def _estimate_session_size(units: List[TranslationUnit]) -> int:
    """Approximate CPython object-graph bytes for session quota checks."""
    size = sys.getsizeof(units)
    for unit in units:
        size += sys.getsizeof(unit)
        if unit.tu_id is not None:
            size += sys.getsizeof(unit.tu_id)
        if unit.source_lang is not None:
            size += sys.getsizeof(unit.source_lang)
        if unit.target_lang is not None:
            size += sys.getsizeof(unit.target_lang)
        size += sys.getsizeof(unit.source_text)
        size += sys.getsizeof(unit.target_text)
        size += _object_graph_size(unit.metadata)
        size += _object_graph_size(unit.notes)
    return size


def process_rss_bytes() -> Optional[int]:
    """Best-effort peak RSS in bytes (Linux ru_maxrss is KiB)."""
    try:
        import resource

        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except Exception:
        return None
    if sys.platform == "darwin":
        return int(rss)
    return int(rss) * 1024


def _set_session_units_locked(key: str, units: List[TranslationUnit]) -> None:
    size = _estimate_session_size(units)
    if size > MAX_SESSION_ESTIMATED_BYTES:
        raise HTTPException(status_code=413, detail="Dataset exceeds per-session memory quota")

    is_existing = key in _STORAGE
    if not is_existing and len(_STORAGE) >= MAX_SESSIONS:
        raise HTTPException(status_code=503, detail="Maximum number of active sessions reached")

    other_session_sizes = sum(_SESSION_SIZES.values()) - _SESSION_SIZES.get(key, 0)
    if other_session_sizes + size > MAX_TOTAL_SESSION_ESTIMATED_BYTES:
        raise HTTPException(status_code=503, detail="Total session memory quota exceeded")

    _STORAGE[key] = units
    _SESSION_SIZES[key] = size
    _TIMESTAMPS[key] = time.time()


def _save_upload(file: UploadFile, max_size: int = MAX_UPLOAD_SIZE) -> Path:
    """Save uploaded file with size limit."""
    upload = file.file
    upload.seek(0, 2)
    size = upload.tell()
    if size > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {max_size // (1024*1024)} MB"
        )
    upload.seek(0)
    h = hashlib.md5(file.filename.encode() + str(id(file)).encode()).hexdigest()[:10]
    suffix = Path(file.filename or "file.tmx").suffix or ".tmx"
    out = UPLOAD_DIR / f"{h}{suffix}"
    written = 0
    try:
        with open(out, "wb") as output:
            while chunk := upload.read(1024 * 1024):
                written += len(chunk)
                if written > max_size:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size is {max_size // (1024*1024)} MB",
                    )
                output.write(chunk)
    except Exception:
        out.unlink(missing_ok=True)
        raise
    return out


def _iter_exact_unique(units, database_path: Path):
    """Deduplicate a stream using a disk-backed SQLite key table."""
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE seen (key BLOB PRIMARY KEY) WITHOUT ROWID"
        )
        for unit in units:
            source = " ".join(unit.source_text.split())
            target = " ".join(unit.target_text.split())
            key = json.dumps(
                [unit.source_lang or "", unit.target_lang or "", source, target],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            cursor = connection.execute(
                "INSERT OR IGNORE INTO seen(key) VALUES (?)", (key,)
            )
            if cursor.rowcount:
                yield unit


def _delete_stream_job(job_id: str) -> None:
    with _STREAM_JOB_LOCK:
        job = _STREAM_JOBS.pop(job_id, None)
    if job:
        shutil.rmtree(job["directory"], ignore_errors=True)


@app.post("/api/large-pipeline")
def api_large_pipeline(
    file: Optional[UploadFile] = File(None),
    files: Optional[List[UploadFile]] = File(None),
    fmt: str = Form("jsonl"),
    clean: bool = Form(True),
    dedupe: bool = Form(False),
    fuzzy: bool = Form(False),
    include_metadata: bool = Form(False),
    include_id: bool = Form(False),
    instruction: Optional[str] = Form(None),
):
    """Merge and process up to 50 TMX files (1 GiB total) with bounded RAM."""
    input_files = files or ([file] if file is not None else [])
    if not input_files:
        raise HTTPException(status_code=400, detail="Качете поне един .tmx файл")
    if len(input_files) > 50:
        raise HTTPException(status_code=400, detail="Едновременно се приемат до 50 TMX файла")
    if any(not item.filename or not item.filename.lower().endswith(".tmx") for item in input_files):
        raise HTTPException(status_code=400, detail="Всички файлове трябва да са .tmx")
    aggregate_size = 0
    for item in input_files:
        item.file.seek(0, 2)
        aggregate_size += item.file.tell()
        item.file.seek(0)
    if aggregate_size > MAX_STREAM_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Общият размер надвишава {MAX_STREAM_UPLOAD_SIZE // (1024 * 1024)} MiB",
        )
    if fuzzy:
        raise HTTPException(
            status_code=400,
            detail="Fuzzy дедупликацията не е налична в streaming режим; изключете я.",
        )
    try:
        fmt_enum = OutputFormat(fmt.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Невалиден формат: {fmt}")
    streaming_formats = {
        OutputFormat.JSONL,
        OutputFormat.ALPACA,
        OutputFormat.SHAREGPT,
        OutputFormat.CHATML,
        OutputFormat.OPENAI,
        OutputFormat.DPO,
        OutputFormat.PROMPT_COMPLETION,
        OutputFormat.REASONING,
    }
    if fmt_enum not in streaming_formats:
        raise HTTPException(
            status_code=400,
            detail="Големи файлове поддържат JSONL и AI JSONL формати; HF splits, CSV, JSON и Parquet не са налични в този режим.",
        )

    _cleanup_old_stream_jobs()
    job_id = uuid.uuid4().hex
    with _STREAM_JOB_LOCK:
        if len(_STREAM_JOBS) + len(_STREAM_ACTIVE) >= 4:
            raise HTTPException(
                status_code=503,
                detail="Има твърде много активни или готови големи задачи. Изтеглете готовите файлове или опитайте по-късно.",
            )
        _STREAM_ACTIVE.add(job_id)

    job_dir = UPLOAD_DIR / "stream_jobs" / job_id
    output_path = job_dir / "dataset.jsonl"
    upload_path = None
    input_paths = []
    try:
        job_dir.mkdir(parents=True, exist_ok=False)
        for index, uploaded_file in enumerate(input_files):
            upload_path = _save_upload(uploaded_file, max_size=MAX_STREAM_UPLOAD_SIZE)
            input_path = job_dir / f"input_{index:03d}.tmx"
            shutil.move(str(upload_path), input_path)
            upload_path = None
            input_paths.append(input_path)

        counters = {"parsed": 0, "after_clean": 0, "after_dedupe": 0}

        def count_parsed():
            for input_path in input_paths:
                for unit in TMXParser(input_path).iter_units():
                    counters["parsed"] += 1
                    yield unit

        units = count_parsed()
        if clean:
            units = DataCleaner().clean_iter(units)
        cleaned_units = units

        def count_cleaned():
            for unit in cleaned_units:
                counters["after_clean"] += 1
                yield unit

        units = count_cleaned()
        if dedupe:
            units = _iter_exact_unique(units, job_dir / "dedupe.sqlite3")

        def count_deduped():
            for unit in units:
                counters["after_dedupe"] += 1
                yield unit

        options = ConvertOptions(
            include_metadata=include_metadata,
            include_id=include_id,
            instruction_template=instruction,
        )
        DataConverter(options=options).convert(
            count_deduped(), output_path, fmt_enum, streaming=True
        )
        for input_path in input_paths:
            input_path.unlink(missing_ok=True)
        (job_dir / "dedupe.sqlite3").unlink(missing_ok=True)
        first_stem = Path(input_files[0].filename).stem
        batch_suffix = f"_{len(input_files)}files" if len(input_files) > 1 else ""
        filename = f"{first_stem}{batch_suffix}_{fmt_enum.value}.jsonl"
        with _STREAM_JOB_LOCK:
            _STREAM_JOBS[job_id] = {
                "directory": job_dir,
                "output": output_path,
                "filename": filename,
                "created": time.time(),
            }
        return JSONResponse(
            {
                "job_id": job_id,
                "filename": filename,
                "download_url": f"/api/large-pipeline/{job_id}/download",
                "counts": counters,
                "output_bytes": output_path.stat().st_size,
            }
        )
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Грешка при streaming обработка: {exc}") from exc
    finally:
        if upload_path is not None:
            upload_path.unlink(missing_ok=True)
        with _STREAM_JOB_LOCK:
            _STREAM_ACTIVE.discard(job_id)


@app.get("/api/large-pipeline/{job_id}/download")
def api_large_pipeline_download(job_id: str):
    _cleanup_old_stream_jobs()
    with _STREAM_JOB_LOCK:
        job = _STREAM_JOBS.get(job_id)
    if not job or not job["output"].is_file():
        raise HTTPException(status_code=404, detail="Файлът вече не е наличен.")
    return FileResponse(
        job["output"],
        filename=job["filename"],
        media_type="application/x-ndjson",
        background=BackgroundTask(_delete_stream_job, job_id),
    )




def _store_units(units: List[TranslationUnit], header=None) -> str:
    key = hashlib.md5(str(id(units)).encode()).hexdigest()[:8]
    _cleanup_old_sessions()
    with _SESSION_LOCK:
        _set_session_units_locked(key, units)
        if header:
            _HEADERS[key] = header
    return key


def _get_session_units(key: str, detail: str) -> List[TranslationUnit]:
    with _SESSION_LOCK:
        units = _STORAGE.get(key)
        if units is None:
            raise HTTPException(status_code=404, detail=detail)
        _TIMESTAMPS[key] = time.time()
        return list(units)


@app.get("/", response_class=HTMLResponse)
def index():
    html_path = BASE_DIR / "web" / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>TMX Processor API</h1><p>Документация: <a href='/docs'>/docs</a></p>")


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".tmx"):
        raise HTTPException(status_code=400, detail="Моля, качете .tmx файл")
    path = _save_upload(file, MAX_UPLOAD_SIZE)
    try:
        parser = TMXParser(path)
        header = parser.parse_header()
        units = parser.parse_all()
    finally:
        path.unlink(missing_ok=True)
    session_header = {
        "source_lang": header.source_lang,
        "creation_tool": header.creation_tool,
        "seg_type": header.seg_type,
        "properties": header.properties,
    }
    key = _store_units(units, session_header)
    discovered_langs = sorted(list({u.source_lang for u in units if u.source_lang} | {u.target_lang for u in units if u.target_lang}))
    discovered_pairs = sorted(list({f"{u.source_lang}-{u.target_lang}" for u in units if u.source_lang and u.target_lang}))
    preview = [
        {
            "id": u.tu_id,
            "source_lang": u.source_lang,
            "target_lang": u.target_lang,
            "source": u.source_text[:120],
            "target": u.target_text[:120],
        }
        for u in units[:5]
    ]
    return JSONResponse({
        "key": key,
        "total_units": len(units),
        "header": session_header,
        "available_languages": discovered_langs,
        "language_pairs": discovered_pairs,
        "preview": preview,
    })


@app.post("/api/clean")
def api_clean(
    key: str = Form(...),
    min_length: int = Form(1),
    max_length: int = Form(10000),
    min_words: int = Form(0),
    max_words: int = Form(0),
    max_length_ratio: float = Form(3.0),
    remove_html: bool = Form(True),
    remove_urls: bool = Form(False),
    remove_emails: bool = Form(False),
    lang_detect: bool = Form(False),
    preserve_placeholders: bool = Form(False),
    language_pairs: Optional[str] = Form(None), # Comma-separated pairs e.g. "EN-BG,BG-EN"
):
    lang_pairs_list = [p.strip() for p in language_pairs.split(",")] if language_pairs else None
    cfg = CleanConfig(
        min_length=min_length,
        max_length=max_length,
        min_words=min_words,
        max_words=max_words,
        max_length_ratio=max_length_ratio,
        remove_html_tags=remove_html,
        remove_urls=remove_urls,
        remove_emails=remove_emails,
        lang_detect=lang_detect,
        preserve_placeholders=preserve_placeholders,
        language_pairs=lang_pairs_list,
    )
    cleaner = DataCleaner(cfg)
    with _SESSION_LOCK:
        units = _STORAGE.get(key)
        if units is None:
            raise HTTPException(status_code=404, detail="Няма качен файл. Качете отново.")
        before = len(units)
        cleaned = cleaner.clean_units(units)
        _set_session_units_locked(key, cleaned)
    return JSONResponse({
        "key": key,
        "before": before,
        "after": len(cleaned),
        "removed": before - len(cleaned),
    })


@app.post("/api/dedupe")
def api_dedupe(
    key: str = Form(...),
    fuzzy: bool = Form(False),
    fuzzy_threshold: float = Form(0.9),
):
    dd = DataDeduper(exact=True, fuzzy=fuzzy, fuzzy_threshold=fuzzy_threshold)
    with _SESSION_LOCK:
        units = _STORAGE.get(key)
        if units is None:
            raise HTTPException(status_code=404, detail="Няма данни. Качете и обработете файл.")
        before = len(units)
        deduped = dd.dedupe(list(units))
        _set_session_units_locked(key, deduped)
    return JSONResponse({
        "key": key,
        "before": before,
        "after": len(deduped),
        "removed": before - len(deduped),
    })


@app.get("/api/validate/{key}")
def api_validate(key: str):
    validator = DataValidator()
    report = validator.report(_get_session_units(key, "Няма данни."))
    return JSONResponse(report)


@app.get("/api/stats/{key}")
def api_stats(key: str):
    analyzer = DataAnalyzer()
    stats = analyzer.analyze(_get_session_units(key, "Няма данни."))
    return JSONResponse(stats.to_dict())


@app.get("/api/preview/{key}")
def api_preview(key: str, start: int = 0, limit: int = 50):
    units = _get_session_units(key, "Няма данни.")
    end = min(start + limit, len(units))
    rows = [u.to_dict() for u in units[start:end]]
    return JSONResponse({
        "key": key,
        "total": len(units),
        "start": start,
        "end": end,
        "rows": rows,
    })


@app.post("/api/convert")
def api_convert(
    key: str = Form(...),
    fmt: str = Form("jsonl"),
    include_metadata: bool = Form(False),
    include_id: bool = Form(False),
    instruction: Optional[str] = Form(None),
    language_pairs: Optional[str] = Form(None), # Comma-separated pairs e.g. "EN-BG,BG-EN"
):
    units = _get_session_units(key, "Няма данни.")
    try:
        fmt_enum = OutputFormat(fmt.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Невалиден формат: {fmt}")

    lang_pairs_list = [p.strip() for p in language_pairs.split(",")] if language_pairs else None
    opts = ConvertOptions(
        include_metadata=include_metadata,
        include_id=include_id,
        instruction_template=instruction,
        language_pairs=lang_pairs_list,
    )
    converter = DataConverter(options=opts)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        try:
            if fmt_enum == OutputFormat.HF_DATASET:
                folder = tmp_path / "hf_splits"
                converter.convert(units, folder, fmt_enum)
                zip_buf = io.BytesIO()
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for p in folder.rglob("*"):
                        if p.is_file():
                            zf.write(p, arcname=p.relative_to(tmp_path))
                zip_buf.seek(0)
                return StreamingResponse(
                    zip_buf,
                    media_type="application/zip",
                    headers={"Content-Disposition": f"attachment; filename=hf_dataset.zip"},
                )
            else:
                suffix = "." + (fmt if fmt not in ("sharegpt", "dpo", "prompt_completion", "reasoning") else "jsonl")
                if fmt == "parquet":
                    suffix = ".parquet"
                elif fmt == "csv":
                    suffix = ".csv"
                elif fmt == "tsv":
                    suffix = ".tsv"
                elif fmt == "json":
                    suffix = ".json"
                else:
                    suffix = ".jsonl"
                out_file = tmp_path / f"output{suffix}"
                converter.convert(units, out_file, fmt_enum)
                data = out_file.read_bytes()
                return StreamingResponse(
                    io.BytesIO(data),
                    media_type="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename=output{suffix}"},
                )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pipeline")
async def api_pipeline(
    file: UploadFile = File(...),
    fmt: str = Form("jsonl"),
    clean: bool = Form(True),
    dedupe: bool = Form(True),
    fuzzy: bool = Form(False),
    include_metadata: bool = Form(False),
    include_id: bool = Form(False),
):
    if not file.filename or not file.filename.lower().endswith(".tmx"):
        raise HTTPException(status_code=400, detail="Трябва .tmx файл")
    path = _save_upload(file, MAX_UPLOAD_SIZE)
    try:
        parser = TMXParser(path)
        parser.parse_header()
        units = parser.parse_all()
    finally:
        path.unlink(missing_ok=True)

    stats: dict = {}
    validator = DataValidator()
    report_pre = validator.report(units)
    before_clean = len(units)

    if clean:
        cleaner = DataCleaner()
        units = cleaner.clean_units(units)
    after_clean = len(units)

    before_dedupe = len(units)
    if dedupe:
        dd = DataDeduper(exact=True, fuzzy=fuzzy)
        units = dd.dedupe(list(units))
    after_dedupe = len(units)

    analyzer = DataAnalyzer()
    stats = analyzer.analyze(units).to_dict()
    report_post = validator.report(units)

    try:
        fmt_enum = OutputFormat(fmt.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Невалиден формат: {fmt}")

    opts = ConvertOptions(include_metadata=include_metadata, include_id=include_id)
    converter = DataConverter(options=opts)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        if fmt_enum == OutputFormat.HF_DATASET:
            folder = tmp_path / "hf_splits"
            converter.convert(units, folder, fmt_enum)
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                meta = {
                    "pipeline": {
                        "before_clean": before_clean,
                        "after_clean": after_clean,
                        "before_dedupe": before_dedupe,
                        "after_dedupe": after_dedupe,
                        "validation_pre": report_pre,
                        "validation_post": report_post,
                    },
                    "stats": stats,
                }
                zf.writestr("pipeline_report.json", json.dumps(meta, ensure_ascii=False, indent=2))
                for p in folder.rglob("*"):
                    if p.is_file():
                        zf.write(p, arcname=p.relative_to(tmp_path))
            zip_buf.seek(0)
            return StreamingResponse(
                zip_buf,
                media_type="application/zip",
                headers={"Content-Disposition": f"attachment; filename=tmx_pipeline_hf.zip"},
            )
        else:
            suffix = ".parquet" if fmt == "parquet" else (
                ".csv" if fmt == "csv" else (
                    ".tsv" if fmt == "tsv" else (
                        ".json" if fmt == "json" else ".jsonl"
                    )
                )
            )
            out_file = tmp_path / f"dataset{suffix}"
            converter.convert(units, out_file, fmt_enum)
            data = out_file.read_bytes()

            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(f"dataset{suffix}", data)
                meta = {
                    "pipeline": {
                        "before_clean": before_clean,
                        "after_clean": after_clean,
                        "before_dedupe": before_dedupe,
                        "after_dedupe": after_dedupe,
                        "validation_pre": report_pre,
                        "validation_post": report_post,
                    },
                    "stats": stats,
                }
                zf.writestr("pipeline_report.json", json.dumps(meta, ensure_ascii=False, indent=2))
            buf.seek(0)
            return StreamingResponse(
                buf,
                media_type="application/zip",
                headers={"Content-Disposition": f"attachment; filename=tmx_pipeline_output.zip"},
            )


def main():
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="TMX Processor Web UI")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--cleanup-uploads", action="store_true", help="Изтрий качените файлове при стартиране")
    args = parser.parse_args()

    if args.cleanup_uploads:
        for f in UPLOAD_DIR.glob("*"):
            if f.is_file():
                f.unlink()

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
