"""Unit tests for web API using TestClient."""
"""Unit tests for web API using TestClient."""
import asyncio
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from tmx_processor import web_api
from tmx_processor import web_api
from tmx_processor.parser import TranslationUnit
from tmx_processor.web_api import app


client = TestClient(app)
client = TestClient(app)


@pytest.fixture
def store_units():
    keys = []

    def store(units):
        key = web_api._store_units(units)
        keys.append(key)
        return key

    yield store

    with web_api._SESSION_LOCK:
        for key in keys:
            web_api._STORAGE.pop(key, None)
            web_api._HEADERS.pop(key, None)
            web_api._TIMESTAMPS.pop(key, None)
            web_api._SESSION_SIZES.pop(key, None)


@pytest.fixture
def isolated_session_store():
    with web_api._SESSION_LOCK:
        saved = (
            dict(web_api._STORAGE),
            dict(web_api._HEADERS),
            dict(web_api._TIMESTAMPS),
            dict(web_api._SESSION_SIZES),
        )
        web_api._STORAGE.clear()
        web_api._HEADERS.clear()
        web_api._TIMESTAMPS.clear()
        web_api._SESSION_SIZES.clear()

    yield

    with web_api._SESSION_LOCK:
        web_api._STORAGE.clear()
        web_api._STORAGE.update(saved[0])
        web_api._HEADERS.clear()
        web_api._HEADERS.update(saved[1])
        web_api._TIMESTAMPS.clear()
        web_api._TIMESTAMPS.update(saved[2])
        web_api._SESSION_SIZES.clear()
        web_api._SESSION_SIZES.update(saved[3])


def test_root_endpoint():
    """Test root endpoint returns HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_docs_endpoint():
    """Test Swagger docs endpoint."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_upload_nonexistent_file():
    """Test upload with invalid file."""
    # Create a fake file object
    from io import BytesIO

    files = {"file": ("test.txt", BytesIO(b"not a tmx"), "text/plain")}
    response = client.post("/api/upload", files=files)
    assert response.status_code == 400


def test_upload_valid_tmx(monkeypatch, tmp_path):
    """Test upload with valid TMX file."""
    tmx_path = Path("examples/sample_en_bg.tmx")
    if not tmx_path.exists():
        pytest.skip("Sample TMX file not found")

    monkeypatch.setattr(web_api, "UPLOAD_DIR", tmp_path)
    with open(tmx_path, "rb") as f:
        files = {"file": ("sample.tmx", f, "application/octet-stream")}
        response = client.post("/api/upload", files=files)

    assert response.status_code == 200
    data = response.json()
    assert "key" in data
    assert "total_units" in data
    assert list(tmp_path.iterdir()) == []


def test_oversized_upload_is_rejected_before_reading(tmp_path, monkeypatch):
    class ReadTrackingFile(BytesIO):
        read_calls = 0

        def read(self, *args, **kwargs):
            self.read_calls += 1
            return super().read(*args, **kwargs)

    monkeypatch.setattr(web_api, "UPLOAD_DIR", tmp_path)
    upload_file = ReadTrackingFile(b"12345")
    upload = SimpleNamespace(filename="large.tmx", file=upload_file)

    with pytest.raises(HTTPException) as error:
        web_api._save_upload(upload, max_size=4)

    assert error.value.status_code == 413
    assert upload_file.read_calls == 0
    assert list(tmp_path.iterdir()) == []


def test_request_body_limit_rejects_content_length_before_downstream():
    downstream_called = False
    receive_called = False
    sent = []

    async def downstream(scope, receive, send):
        nonlocal downstream_called
        downstream_called = True

    async def receive():
        nonlocal receive_called
        receive_called = True
        return {"type": "http.request", "body": b"12345", "more_body": False}

    async def send(message):
        sent.append(message)

    middleware = web_api.RequestBodyLimitMiddleware(downstream, max_body_size=4)
    asyncio.run(
        middleware(
            {"type": "http", "headers": [(b"content-length", b"5")]},
            receive,
            send,
        )
    )

    assert not downstream_called
    assert not receive_called
    assert sent[0]["status"] == 413


def test_request_body_limit_counts_chunked_requests():
    sent = []

    async def downstream(scope, receive, send):
        await receive()

    async def receive():
        return {"type": "http.request", "body": b"12345", "more_body": True}

    async def send(message):
        sent.append(message)

    middleware = web_api.RequestBodyLimitMiddleware(downstream, max_body_size=4)
    asyncio.run(middleware({"type": "http", "headers": []}, receive, send))

    assert sent[0]["status"] == 413


def test_request_body_limit_uses_large_cap_only_for_stream_pipeline():
    limits = []

    async def downstream(scope, receive, send):
        await receive()
        limits.append(scope["path"])

    async def receive():
        return {"type": "http.request", "body": b"12345", "more_body": False}

    async def send(_message):
        pass

    middleware = web_api.RequestBodyLimitMiddleware(
        downstream, max_body_size=4, large_body_size=8
    )
    asyncio.run(
        middleware({"type": "http", "path": "/api/upload", "headers": []}, receive, send)
    )
    asyncio.run(
        middleware(
            {"type": "http", "path": "/api/large-pipeline", "headers": []},
            receive,
            send,
        )
    )

    assert limits == ["/api/large-pipeline"]


def test_pipeline_removes_uploaded_file_after_parsing(tmp_path, monkeypatch):
    monkeypatch.setattr(web_api, "UPLOAD_DIR", tmp_path)
    tmx = '''<?xml version="1.0" encoding="UTF-8"?>
<tmx xmlns="urn:example:tmx">
  <header srclang="EN" />
  <body><tu>
    <tuv xml:lang="EN"><seg>source text</seg></tuv>
    <tuv xml:lang="BG"><seg>target text</seg></tuv>
  </tu></body>
</tmx>
'''.encode("utf-8")

    response = client.post(
        "/api/pipeline",
        files={"file": ("sample.tmx", BytesIO(tmx), "application/octet-stream")},
        data={"fmt": "jsonl", "clean": "false", "dedupe": "false"},
    )

    assert response.status_code == 200
    assert response.content.startswith(b"PK")
    assert list(tmp_path.iterdir()) == []


def test_large_pipeline_streams_exact_dedupe_and_downloads_to_file(tmp_path, monkeypatch):
    monkeypatch.setattr(web_api, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(
        web_api.TMXParser,
        "parse_all",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("parse_all called")),
    )
    tmx = '''<?xml version="1.0" encoding="UTF-8"?>
<tmx xmlns="urn:example:tmx">
  <header srclang="EN" />
  <body>
    <tu><tuv xml:lang="EN"><seg>Hello world</seg></tuv><tuv xml:lang="BG"><seg>Здравей свят</seg></tuv></tu>
    <tu><tuv xml:lang="EN"><seg>Hello world</seg></tuv><tuv xml:lang="BG"><seg>Здравей свят</seg></tuv></tu>
  </body>
</tmx>
'''.encode("utf-8")

    response = client.post(
        "/api/large-pipeline",
        files={"file": ("large.tmx", BytesIO(tmx), "application/octet-stream")},
        data={"fmt": "jsonl", "clean": "false", "dedupe": "true"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["counts"] == {"parsed": 2, "after_clean": 2, "after_dedupe": 1}
    download = client.get(result["download_url"])
    assert download.status_code == 200
    records = [json.loads(line) for line in download.text.splitlines()]
    assert sum(record["source"] == "Hello world" for record in records) == 1
    assert result["job_id"] not in web_api._STREAM_JOBS
    assert list((tmp_path / "stream_jobs").iterdir()) == []


def test_large_pipeline_merges_multiple_files_with_global_dedupe(tmp_path, monkeypatch):
        monkeypatch.setattr(web_api, "UPLOAD_DIR", tmp_path)
        first = '''<tmx xmlns="urn:example:tmx"><header srclang="EN"/><body>
            <tu><tuv xml:lang="EN"><seg>Same source</seg></tuv><tuv xml:lang="BG"><seg>Един и същ</seg></tuv></tu>
        </body></tmx>'''.encode("utf-8")
        second = '''<tmx xmlns="urn:example:tmx"><header srclang="EN"/><body>
            <tu><tuv xml:lang="EN"><seg>Same source</seg></tuv><tuv xml:lang="BG"><seg>Един и същ</seg></tuv></tu>
            <tu><tuv xml:lang="EN"><seg>Another source</seg></tuv><tuv xml:lang="BG"><seg>Друг превод</seg></tuv></tu>
        </body></tmx>'''.encode("utf-8")

        response = client.post(
                "/api/large-pipeline",
                files=[
                        ("files", ("first.tmx", BytesIO(first), "application/octet-stream")),
                        ("files", ("second.tmx", BytesIO(second), "application/octet-stream")),
                ],
                data={"fmt": "jsonl", "clean": "false", "dedupe": "true"},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["counts"] == {"parsed": 3, "after_clean": 3, "after_dedupe": 2}
        assert result["filename"] == "first_2files_jsonl.jsonl"
        download = client.get(result["download_url"])
        records = [json.loads(line) for line in download.text.splitlines()]
        assert len(records) == 2


def test_large_pipeline_rejects_non_streaming_format(tmp_path, monkeypatch):
    monkeypatch.setattr(web_api, "UPLOAD_DIR", tmp_path)
    response = client.post(
        "/api/large-pipeline",
        files={"file": ("large.tmx", BytesIO(b"ignored"), "application/octet-stream")},
        data={"fmt": "hf_dataset"},
    )

    assert response.status_code == 400
    assert "JSONL" in response.json()["detail"]
    assert not (tmp_path / "stream_jobs").exists()


def test_large_pipeline_enforces_combined_upload_size(tmp_path, monkeypatch):
    monkeypatch.setattr(web_api, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(web_api, "MAX_STREAM_UPLOAD_SIZE", 10)
    response = client.post(
        "/api/large-pipeline",
        files=[
            ("files", ("one.tmx", BytesIO(b"123456"), "application/octet-stream")),
            ("files", ("two.tmx", BytesIO(b"abcdef"), "application/octet-stream")),
        ],
        data={"fmt": "jsonl"},
    )

    assert response.status_code == 413
    assert "Общият размер" in response.json()["detail"]
    assert not (tmp_path / "stream_jobs").exists()


def test_expired_sessions_are_cleaned_on_requests():
    key = "expired-session"
    web_api._STORAGE[key] = []
    web_api._HEADERS[key] = {}
    web_api._TIMESTAMPS[key] = time.time() - web_api.SESSION_TTL - 1
    web_api._SESSION_SIZES[key] = 0

    client.get("/")
    response = client.get(f"/api/stats/{key}")

    assert response.status_code == 404
    assert key not in web_api._STORAGE
    assert key not in web_api._HEADERS
    assert key not in web_api._TIMESTAMPS
    assert key not in web_api._SESSION_SIZES


def test_active_session_access_refreshes_ttl(store_units):
    key = store_units(
        [TranslationUnit(source_lang="EN", target_lang="BG", source_text="Hello", target_text="Здравей")]
    )
    with web_api._SESSION_LOCK:
        web_api._TIMESTAMPS[key] = time.time() - web_api.SESSION_TTL + 5

    response = client.get(f"/api/stats/{key}")

    assert response.status_code == 200
    with web_api._SESSION_LOCK:
        assert web_api._TIMESTAMPS[key] > time.time() - web_api.SESSION_TTL


def test_concurrent_dedupe_requests_preserve_session(store_units):
    key = store_units(
        [
            TranslationUnit(source_lang="EN", target_lang="BG", source_text="one", target_text="едно"),
            TranslationUnit(source_lang="EN", target_lang="BG", source_text="one", target_text="едно"),
            TranslationUnit(source_lang="EN", target_lang="BG", source_text="two", target_text="две"),
            TranslationUnit(source_lang="EN", target_lang="BG", source_text="two", target_text="две"),
        ]
    )

    def dedupe_once(_index):
        with TestClient(app) as thread_client:
            return thread_client.post("/api/dedupe", data={"key": key}).json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(dedupe_once, range(2)))

    assert all(response["after"] == 2 for response in responses)
    assert sorted(response["before"] for response in responses) == [2, 4]
    assert sorted(response["removed"] for response in responses) == [0, 2]
    assert len(web_api._STORAGE[key]) == 2


def test_session_count_quota_rejects_new_sessions(monkeypatch, isolated_session_store):
    monkeypatch.setattr(web_api, "MAX_SESSIONS", 1)
    web_api._store_units([TranslationUnit(source_lang="EN", target_lang="BG", source_text="a", target_text="б")])

    with pytest.raises(HTTPException) as error:
        web_api._store_units(
            [TranslationUnit(source_lang="EN", target_lang="BG", source_text="c", target_text="д")]
        )

    assert error.value.status_code == 503


def test_per_session_memory_quota_rejects_large_dataset(monkeypatch):
    monkeypatch.setattr(web_api, "MAX_SESSION_ESTIMATED_BYTES", 300)
    units = [
        TranslationUnit(
            source_lang="EN",
            target_lang="BG",
            source_text="a" * 100,
            target_text="б" * 100,
        )
    ]

    with pytest.raises(HTTPException) as error:
        web_api._store_units(units)

    assert error.value.status_code == 413


def test_total_session_memory_quota_rejects_additional_dataset(monkeypatch, isolated_session_store):
    monkeypatch.setattr(web_api, "MAX_SESSION_ESTIMATED_BYTES", 1000)
    monkeypatch.setattr(web_api, "MAX_TOTAL_SESSION_ESTIMATED_BYTES", 1200)
    units = lambda source: [
        TranslationUnit(
            source_lang="EN",
            target_lang="BG",
            source_text=source * 100,
            target_text="т" * 100,
        )
    ]
    web_api._store_units(units("a"))

    with pytest.raises(HTTPException) as error:
        web_api._store_units(units("b"))

    assert error.value.status_code == 503


def test_background_task_cleans_sessions_while_server_is_idle(monkeypatch):
    monkeypatch.setattr(web_api, "SESSION_CLEANUP_INTERVAL", 0.01)
    key = "idle-expired-session"
    web_api._STORAGE[key] = []
    web_api._HEADERS[key] = {}
    web_api._TIMESTAMPS[key] = time.time() - web_api.SESSION_TTL - 1
    web_api._SESSION_SIZES[key] = 0
    cleanup_ran = threading.Event()
    cleanup = web_api._cleanup_old_sessions

    def tracked_cleanup():
        cleanup()
        if key not in web_api._STORAGE:
            cleanup_ran.set()

    monkeypatch.setattr(web_api, "_cleanup_old_sessions", tracked_cleanup)
    with TestClient(app):
        assert cleanup_ran.wait(timeout=1)

    assert key not in web_api._STORAGE


def test_validate_with_key():
    """Test validation endpoint with session key."""
    # First upload a file
    tmx_path = Path("examples/sample_en_bg.tmx")
    if not tmx_path.exists():
        pytest.skip("Sample TMX file not found")

    with open(tmx_path, "rb") as f:
        files = {"file": ("sample.tmx", f, "application/octet-stream")}
        upload_response = client.post("/api/upload", files=files)

    key = upload_response.json()["key"]

    # Then validate
    response = client.get(f"/api/validate/{key}")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "valid" in data


def test_stats_with_key():
    """Test stats endpoint with session key."""
    # First upload a file
    tmx_path = Path("examples/sample_en_bg.tmx")
    if not tmx_path.exists():
        pytest.skip("Sample TMX file not found")

    with open(tmx_path, "rb") as f:
        files = {"file": ("sample.tmx", f, "application/octet-stream")}
        upload_response = client.post("/api/upload", files=files)

    key = upload_response.json()["key"]

    # Then get stats
    response = client.get(f"/api/stats/{key}")
    assert response.status_code == 200
    data = response.json()
    assert "total_units" in data


def test_preview_with_key():
    """Test preview endpoint with session key."""
    # First upload a file
    tmx_path = Path("examples/sample_en_bg.tmx")
    if not tmx_path.exists():
        pytest.skip("Sample TMX file not found")

    with open(tmx_path, "rb") as f:
        files = {"file": ("sample.tmx", f, "application/octet-stream")}
        upload_response = client.post("/api/upload", files=files)

    key = upload_response.json()["key"]

    # Then get preview
    response = client.get(f"/api/preview/{key}")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "rows" in data


def test_clean_endpoint_updates_session(store_units):
    key = store_units(
        [
            TranslationUnit(
                source_lang="EN",
                target_lang="BG",
                source_text="<b>Hello</b>",
                target_text="Здравей",
            ),
            TranslationUnit(
                source_lang="EN",
                target_lang="BG",
                source_text="x",
                target_text="y",
            ),
        ]
    )

    response = client.post(
        "/api/clean",
        data={"key": key, "min_length": "2", "remove_html": "true"},
    )

    assert response.status_code == 200
    assert response.json() == {"key": key, "before": 2, "after": 1, "removed": 1}
    rows = client.get(f"/api/preview/{key}").json()["rows"]
    assert rows[0]["source"] == "Hello"


def test_dedupe_endpoint_removes_exact_duplicates(store_units):
    key = store_units(
        [
            TranslationUnit(
                source_lang="EN", target_lang="BG", source_text="Hello", target_text="Здравей"
            ),
            TranslationUnit(
                source_lang="EN", target_lang="BG", source_text="Hello", target_text="Здравей"
            ),
            TranslationUnit(
                source_lang="EN", target_lang="BG", source_text="Goodbye", target_text="Довиждане"
            ),
        ]
    )

    response = client.post("/api/dedupe", data={"key": key})

    assert response.status_code == 200
    assert response.json() == {"key": key, "before": 3, "after": 2, "removed": 1}


def test_convert_endpoint_returns_jsonl_with_id_and_metadata(store_units):
    key = store_units(
        [
            TranslationUnit(
                tu_id="unit-1",
                source_lang="EN",
                target_lang="BG",
                source_text="Hello",
                target_text="Здравей",
                metadata={"origin": "fixture"},
            )
        ]
    )

    response = client.post(
        "/api/convert",
        data={
            "key": key,
            "fmt": "jsonl",
            "include_id": "true",
            "include_metadata": "true",
        },
    )

    assert response.status_code == 200
    record = json.loads(response.text)
    assert record["id"] == "unit-1"
    assert record["metadata"] == {"origin": "fixture"}
    assert record["source"] == "Hello"


def test_convert_endpoint_renders_instruction_template(store_units):
    key = store_units(
        [
            TranslationUnit(
                source_lang="EN",
                target_lang="BG",
                source_text="Hello",
                target_text="Здравей",
            )
        ]
    )

    response = client.post(
        "/api/convert",
        data={
            "key": key,
            "fmt": "alpaca",
            "instruction": "Translate from {src} to {tgt}",
        },
    )

    assert response.status_code == 200
    record = json.loads(response.text)
    assert record["instruction"] == "Translate from EN to BG"
    assert record["input"] == "Hello"
    assert record["output"] == "Здравей"
    assert record["output"] == "Здравей"


@pytest.mark.parametrize(
    ("endpoint", "form_data"),
    [
        ("/api/clean", {"key": "missing-session"}),
        ("/api/dedupe", {"key": "missing-session"}),
        ("/api/convert", {"key": "missing-session"}),
    ],
)
def test_mutation_and_convert_endpoints_reject_unknown_sessions(endpoint, form_data):
    response = client.post(endpoint, data=form_data)

    assert response.status_code == 404


def test_convert_endpoint_rejects_unknown_format(store_units):
    key = store_units(
        [TranslationUnit(source_lang="EN", target_lang="BG", source_text="Hello", target_text="Здравей")]
    )

    response = client.post("/api/convert", data={"key": key, "fmt": "not-a-format"})

    assert response.status_code == 400
    assert "Невалиден формат" in response.json()["detail"]


def test_convert_endpoint_supports_dpo_format(store_units):
    key = store_units(
        [TranslationUnit(source_lang="EN", target_lang="BG", source_text="Hello", target_text="Здравей")]
    )

    response = client.post("/api/convert", data={"key": key, "fmt": "dpo"})

    assert response.status_code == 200
    record = json.loads(response.text)
    assert "prompt" in record
    assert "chosen" in record
    assert "rejected" in record


def test_convert_endpoint_supports_prompt_completion_format(store_units):
    key = store_units(
        [TranslationUnit(source_lang="EN", target_lang="BG", source_text="Hello", target_text="Здравей")]
    )

    response = client.post("/api/convert", data={"key": key, "fmt": "prompt_completion"})

    assert response.status_code == 200
    record = json.loads(response.text)
    assert "prompt" in record
    assert "completion" in record


def test_convert_endpoint_supports_reasoning_format(store_units):
    key = store_units(
        [TranslationUnit(source_lang="EN", target_lang="BG", source_text="Hello", target_text="Здравей")]
    )

    response = client.post("/api/convert", data={"key": key, "fmt": "reasoning"})

    assert response.status_code == 200
    record = json.loads(response.text)
    assert "messages" in record
    assert len(record["messages"]) == 3
    assert record["messages"][0]["role"] == "system"
    assert record["messages"][1]["role"] == "user"
    assert record["messages"][2]["role"] == "assistant"
