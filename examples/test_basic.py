from pathlib import Path
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tmx_processor.parser import TMXParser, TranslationUnit
from tmx_processor.cleaner import DataCleaner, CleanConfig
from tmx_processor.validator import DataValidator
from tmx_processor.deduper import DataDeduper
from tmx_processor.analyzer import DataAnalyzer
from tmx_processor.converter import DataConverter, OutputFormat

TMX_FILE = Path(__file__).parent / "sample_en_bg.tmx"
OUT_DIR = Path(__file__).parent / "test_output"
OUT_DIR.mkdir(exist_ok=True)

print("=== 1. TEST PARSER ===")
parser = TMXParser(TMX_FILE)
header = parser.parse_header()
print(f"Source lang: {header.source_lang}")
print(f"Tool: {header.creation_tool}")
units = parser.parse_all()
print(f"Total TUs: {len(units)}")
for i, u in enumerate(units[:3]):
    print(f"  TU {i+1}: src_lang={u.source_lang}, tgt_lang={u.target_lang}")
    print(f"    SRC (chars: {len(u.source_text)}")
    print(f"    TGT (chars): {len(u.target_text)}")

print("\n=== 2. TEST CLEANER ===")
cleaner = DataCleaner(CleanConfig(min_length=2, max_length_ratio=5.0))
cleaned = cleaner.clean_units(units)
print(f"Before: {len(units)}, After: {len(cleaned)}")
assert len(cleaned) <= len(units)

print("\n=== 3. TEST VALIDATOR ===")
validator = DataValidator()
report = validator.report(units)
print(f"Total: {report['total']}, Valid: {report['valid']}, Pct: {report['valid_pct']:.1f}%")
if report["error_counts"]:
    print("Errors:", report["error_counts"])
if report["warning_counts"]:
    print("Warnings:", report["warning_counts"])

print("\n=== 4. TEST DEDUPER (exact) ===")
dd = DataDeduper(exact=True)
before = len(cleaned)
deduped = dd.dedupe_exact(list(cleaned))
print(f"Before: {before}, After dedup: {len(deduped)}, Removed exact duplicates: {before - len(deduped)}")

print("\n=== 5. TEST ANALYZER ===")
analyzer = DataAnalyzer()
stats = analyzer.analyze(deduped)
print(f"Valid units: {stats.valid_units}/{stats.total_units}")
print(f"Key-based duplicates found in sample: {stats.duplicates_found}")
print(f"Avg src len: {stats.avg_source_length:.1f} chars, Avg tgt len: {stats.avg_target_length:.1f} chars")
print(f"Total src chars: {stats.total_source_chars}, total tgt chars: {stats.total_target_chars}")
print(f"Language pairs: {dict(stats.language_pairs)}")

print("\n=== 6. TEST CONVERTER (fallback JSONL, CSV, JSON) ===")
converter = DataConverter()

out_jsonl = converter.convert(deduped, OUT_DIR / "out.jsonl", OutputFormat.JSONL)
print(f"JSONL -> {out_jsonl} exists: {out_jsonl.exists()} and size {out_jsonl.stat().st_size}")

out_json = converter.convert(deduped, OUT_DIR / "out.json", OutputFormat.JSON)
print(f"JSON -> {out_json} exists: {out_json.exists()} size {out_json.stat().st_size}")

out_csv = converter.convert(deduped, OUT_DIR / "out.csv", OutputFormat.CSV)
print(f"CSV -> {out_csv} exists: {out_csv.exists()} size {out_csv.stat().st_size}")

out_alpaca = converter.convert(deduped, OUT_DIR / "alpaca.jsonl", OutputFormat.ALPACA)
print(f"Alpaca -> {out_alpaca} exists: {out_alpaca.exists()}")

out_sharegpt = converter.convert(deduped, OUT_DIR / "sharegpt.jsonl", OutputFormat.SHAREGPT)
print(f"ShareGPT -> {out_sharegpt} exists: {out_sharegpt.exists()}")

out_hf = converter.convert(deduped, OUT_DIR / "hf_splits", OutputFormat.HF_DATASET)
print(f"HF splits dir exists: {(OUT_DIR / 'hf_splits').exists()}")
for s in ["train", "validation", "test"]:
    p = OUT_DIR / "hf_splits" / f"{s}.jsonl"
    print(f"  - {s}.jsonl: {p.exists()} (size {p.stat().st_size if p.exists() else 0})")

print("\n=== SAMPLE of JSONL record (Alpaca format):===")
import json as _json
with open(out_alpaca, encoding="utf-8") as f:
    lines = [l for l in f.readlines() if l.strip()][:1]
    for line in lines:
        rec = _json.loads(line)
        print(f"  instruction: {rec.get('instruction', '')[:80]}")
        print(f"  input (len): {len(rec.get('input', ''))} chars")
        print(f"  output (len): {len(rec.get('output', ''))} chars")

print("\n✅ ALL TESTS PASSED")
