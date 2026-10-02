import urllib.request
import urllib.parse
import json
from pathlib import Path

sample = Path(__file__).parent / "sample_en_bg.tmx"

BASE = "http://127.0.0.1:8001"

print("# 1. GET / UI page")
req = urllib.request.Request(f"{BASE}/")
with urllib.request.urlopen(req, timeout=10) as r:
    html = r.read().decode("utf-8", errors="ignore")
print("  Status:", r.status, " | Has title:", "<title>TMX Processor" in html)
assert r.status == 200 and "<title>TMX Processor" in html, "UI page failed"

print("\n# 2. POST /api/upload with sample TMX")
data = sample.read_bytes()
boundary = "----TMXTestBoundaryXYZ123"
part1 = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="file"; filename="sample_en_bg.tmx"\r\n'
    f"Content-Type: application/octet-stream\r\n\r\n"
).encode("utf-8")
body = part1 + data + f"\r\n--{boundary}--\r\n".encode("utf-8")
req = urllib.request.Request(
    f"{BASE}/api/upload",
    data=body,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=20) as r:
    resp = json.loads(r.read().decode("utf-8"))
print("  Status:", r.status)
print("  key:", resp.get("key"))
print("  total_units:", resp.get("total_units"))
print("  header.source_lang:", resp.get("header", {}).get("source_lang"))
print("  preview items:", len(resp.get("preview", [])))
assert r.status == 200 and resp.get("total_units", 0) >= 20, "Upload failed"

key = resp["key"]

print("\n# 3. GET /api/preview")
with urllib.request.urlopen(f"{BASE}/api/preview/{key}?limit=10", timeout=10) as r:
    p = json.loads(r.read().decode("utf-8"))
print("  Status:", r.status, "total:", p.get("total"), "rows:", len(p.get("rows", [])))
assert r.status == 200 and len(p.get("rows", [])) > 0

print("\n# 4. GET /api/stats")
with urllib.request.urlopen(f"{BASE}/api/stats/{key}", timeout=10) as r:
    s = json.loads(r.read().decode("utf-8"))
print("  Status:", r.status, "language_pairs:", list(s.get("language_pairs", {}).keys()))
assert r.status == 200 and s.get("language_pairs")

print("\n# 5. GET /api/validate")
with urllib.request.urlopen(f"{BASE}/api/validate/{key}", timeout=10) as r:
    v = json.loads(r.read().decode("utf-8"))
print("  Status:", r.status, "valid:", v.get("valid"), "of", v.get("total"))
assert r.status == 200

print("\n# 6. POST /api/clean")
clean_fields = {
    "key": key,
    "min_length": "2",
    "max_length": "10000",
    "min_words": "0",
    "max_words": "0",
    "max_length_ratio": "5.0",
}
req = urllib.request.Request(
    f"{BASE}/api/clean",
    data=urllib.parse.urlencode(clean_fields).encode(),
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=20) as r:
    c = json.loads(r.read().decode("utf-8"))
print("  Status:", r.status, c)
assert r.status == 200 and c.get("before") == resp["total_units"]

print("\n# 7. POST /api/dedupe")
req = urllib.request.Request(
    f"{BASE}/api/dedupe",
    data=urllib.parse.urlencode({"key": key, "fuzzy_threshold": "0.9"}).encode(),
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=20) as r:
    d = json.loads(r.read().decode("utf-8"))
print("  Status:", r.status, d)
assert r.status == 200 and d.get("removed") >= 0

print("\n# 8. POST /api/convert -> ALPACA")
conv_fields = {"key": key, "fmt": "alpaca"}
req = urllib.request.Request(
    f"{BASE}/api/convert",
    data=urllib.parse.urlencode(conv_fields).encode(),
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=30) as r:
    payload = r.read()
    cd = r.headers.get("Content-Disposition", "")
print("  Status:", r.status, "size:", len(payload), "bytes")
print("  Content-Disposition:", cd)
first_line = payload.decode("utf-8").splitlines()[0]
parsed = json.loads(first_line)
print("  First line keys:", list(parsed.keys()))
assert r.status == 200 and len(payload) > 100
assert set(parsed.keys()) == {"instruction", "input", "output"}

print("\n# 9. POST /api/pipeline endpoint (full one-shot + ZIP)")
import io

data = sample.read_bytes()
pipeline_body = part1 + data + (
    f"\r\n--{boundary}\r\n"
    f'Content-Disposition: form-data; name="fmt"\r\n\r\nhf_dataset\r\n'
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="clean"\r\n\r\non\r\n'
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="dedupe"\r\n\r\non\r\n'
    f"--{boundary}--\r\n"
).encode("utf-8")
req = urllib.request.Request(
    f"{BASE}/api/pipeline",
    data=pipeline_body,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=30) as r:
    zip_bytes = r.read()
    cd = r.headers.get("Content-Disposition", "")
print("  Status:", r.status, "size:", len(zip_bytes), "bytes")
print("  Content-Disposition:", cd)
assert r.status == 200 and zip_bytes.startswith(b"PK"), "Expected ZIP"
print("\n\n>>> ВСИЧКИ 9 API/UI ТЕСТОВЕ МИНАВАТ УСПЕШНО! <<<")
