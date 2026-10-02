import pytest
from pathlib import Path
from tmx_processor.batch import BatchProcessor, find_tmx_files
from tmx_processor.converter import ConvertOptions, OutputFormat


def test_batch_processor_process_file(tmp_path):
    sample_tmx = Path("examples/sample_en_bg.tmx")
    out_file = tmp_path / "output.jsonl"

    batch = BatchProcessor(clean=True, dedupe=True)
    opts = ConvertOptions(include_id=True)
    stats = batch.process_file(sample_tmx, out_file, fmt=OutputFormat.JSONL, convert_options=opts)

    assert stats["input_units"] == 25
    assert stats["after_clean"] == 23
    assert stats["after_dedupe"] == 22
    assert stats["output_units"] == 22
    assert out_file.exists()


def test_batch_processor_process_files_separate_and_merged(tmp_path):
    sample_tmx = Path("examples/sample_en_bg.tmx")
    out_dir = tmp_path / "out_batch"

    batch = BatchProcessor(clean=True, dedupe=True)

    # Separate
    results = batch.process_files([sample_tmx], out_dir, fmt=OutputFormat.JSONL, merge=False)
    assert str(sample_tmx) in results
    assert (out_dir / "sample_en_bg.jsonl").exists()

    # Merged
    out_dir_merged = tmp_path / "out_merged"
    results_merged = batch.process_files([sample_tmx, sample_tmx], out_dir_merged, fmt=OutputFormat.JSONL, merge=True)
    assert "merged" in results_merged
    assert (out_dir_merged / "merged.jsonl").exists()


def test_batch_processor_merge_files(tmp_path):
    sample_tmx = Path("examples/sample_en_bg.tmx")
    out_file = tmp_path / "merged_direct.jsonl"

    batch = BatchProcessor(clean=True, dedupe=True)
    stats = batch.merge_files([sample_tmx, sample_tmx], out_file, fmt=OutputFormat.JSONL)
    assert stats["input_units"] == 50
    assert stats["output_units"] == 22  # deduplicated down to 22 unique
    assert out_file.exists()


def test_find_tmx_files(tmp_path):
    tmx1 = tmp_path / "test1.tmx"
    tmx1.write_text("<tmx></tmx>")

    found = find_tmx_files("*.tmx", base_dir=tmp_path)
    assert len(found) == 1
    assert found[0] == tmx1

    found_single = find_tmx_files("test1.tmx", base_dir=tmp_path)
    assert len(found_single) == 1

    found_none = find_tmx_files("nonexistent.tmx", base_dir=tmp_path)
    assert len(found_none) == 0
