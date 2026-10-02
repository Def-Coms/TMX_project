"""Tests for dataset conversion and split allocation."""
import json

import pytest

from tmx_processor.converter import DataConverter, OutputFormat, _split_sizes
from tmx_processor.parser import TranslationUnit


@pytest.mark.parametrize(
    ("total", "ratios", "expected"),
    [
        (0, (0.9, 0.05, 0.05), (0, 0, 0)),
        (1, (0.9, 0.05, 0.05), (1, 0, 0)),
        (2, (0.9, 0.05, 0.05), (2, 0, 0)),
        (10, (0.8, 0.1, 0.1), (8, 1, 1)),
        (25, (0.8, 0.1, 0.1), (20, 3, 2)),
    ],
)
def test_split_sizes_conserve_records(total, ratios, expected):
    sizes = _split_sizes(total, *ratios)

    assert sizes == expected
    assert sum(sizes) == total


@pytest.mark.parametrize(
    "ratios",
    [
        (-0.1, 0.5, 0.6),
        (0.8, 0.1, 0.05),
        (float("nan"), 0.05, 0.05),
    ],
)
def test_split_sizes_reject_invalid_ratios(ratios):
    with pytest.raises(ValueError):
        _split_sizes(10, *ratios)


def test_tiny_hf_dataset_keeps_records_in_train(tmp_path):
    units = [
        TranslationUnit(
            source_lang="EN",
            target_lang="BG",
            source_text="source",
            target_text="target",
        )
    ]
    output = tmp_path / "dataset"

    DataConverter().convert(units, output, OutputFormat.HF_DATASET)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert (metadata["train"], metadata["validation"], metadata["test"]) == (1, 0, 0)
    assert sum(
        len((output / f"{name}.jsonl").read_text(encoding="utf-8").splitlines())
        for name in ("train", "validation", "test")
    ) == 1


def test_convert_streaming_writes_generator_incrementally(tmp_path, monkeypatch):
    units = (
        TranslationUnit(
            source_lang="EN",
            target_lang="BG",
            source_text=f"source {index}",
            target_text=f"target {index}",
        )
        for index in range(3)
    )
    output = tmp_path / "records.jsonl"

    converter = DataConverter()
    writer_called = False
    write_stream = converter._write_jsonl_streaming

    def record_streaming_writer(records, output_path):
        nonlocal writer_called
        writer_called = True
        return write_stream(records, output_path)

    monkeypatch.setattr(converter, "_write_jsonl_streaming", record_streaming_writer)
    converter.convert(units, output, OutputFormat.JSONL, streaming=True)

    assert writer_called
    records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 3
    assert records[0]["source"] == "source 0"
    assert records[-1]["target"] == "target 2"


def test_convert_rejects_streaming_for_non_jsonl_formats(tmp_path):
    unit = TranslationUnit(source_lang="EN", target_lang="BG", source_text="one", target_text="uno")

    with pytest.raises(ValueError, match="JSONL-based"):
        DataConverter().convert([unit], tmp_path / "records.json", OutputFormat.JSON, streaming=True)


def test_dpo_format_has_prompt_chosen_rejected(tmp_path):
    unit = TranslationUnit(source_lang="EN", target_lang="BG", source_text="Hello", target_text="Здравей")
    output = tmp_path / "dpo.jsonl"
    
    DataConverter().convert([unit], output, OutputFormat.DPO)
    
    with open(output, "r", encoding="utf-8") as f:
        record = json.loads(f.read())
    
    assert "prompt" in record
    assert "chosen" in record
    assert "rejected" in record
    assert "Hello" in record["prompt"]
    assert record["chosen"] == "Здравей"
    assert record["rejected"] == unit.target_text[: len(unit.target_text) // 2]


def test_prompt_completion_format(tmp_path):
    unit = TranslationUnit(source_lang="EN", target_lang="BG", source_text="Hello", target_text="Здравей")
    output = tmp_path / "prompt_completion.jsonl"
    
    DataConverter().convert([unit], output, OutputFormat.PROMPT_COMPLETION)
    
    with open(output, "r", encoding="utf-8") as f:
        record = json.loads(f.read())
    
    assert "prompt" in record
    assert "completion" in record
    assert "Hello" in record["prompt"]
    assert record["completion"] == "Здравей"


def test_reasoning_format_has_messages_with_reasoning(tmp_path):
    unit = TranslationUnit(source_lang="EN", target_lang="BG", source_text="Hello", target_text="Здравей")
    output = tmp_path / "reasoning.jsonl"
    
    DataConverter().convert([unit], output, OutputFormat.REASONING)
    
    with open(output, "r", encoding="utf-8") as f:
        record = json.loads(f.read())
    
    assert "messages" in record
    assert len(record["messages"]) == 3
    assert record["messages"][0]["role"] == "system"
    assert record["messages"][1]["role"] == "user"
    assert record["messages"][2]["role"] == "assistant"
    assert "reasoning" in record["messages"][2]["content"].lower() or "context" in record["messages"][2]["content"].lower()
    assert "Здравей" in record["messages"][2]["content"]


def test_dpo_format_with_custom_instruction(tmp_path):
    unit = TranslationUnit(source_lang="EN", target_lang="BG", source_text="Hello", target_text="Здравей")
    output = tmp_path / "dpo_custom.jsonl"
    
    converter = DataConverter()
    converter.convert(
        [unit], 
        output, 
        OutputFormat.DPO, 
        instruction_tmpl="Custom instruction: {src} to {tgt}"
    )
    
    with open(output, "r", encoding="utf-8") as f:
        record = json.loads(f.read())
    
    assert "Custom instruction" in record["prompt"]
    assert "EN" in record["prompt"]
    assert "BG" in record["prompt"]
