"""Pipeline CLI regression tests."""
import json

import pytest

pytest.importorskip("typer")
from typer.testing import CliRunner

from tmx_processor import cli as cli_module

if cli_module.app is None:
    pytest.skip("typer/rich CLI dependencies are unavailable", allow_module_level=True)


@pytest.fixture
def one_unit_tmx(tmp_path):
    path = tmp_path / "one_unit.tmx"
    path.write_text(
        '''<?xml version="1.0" encoding="UTF-8"?>
<tmx xmlns="urn:example:tmx">
  <header srclang="EN" />
  <body>
    <tu>
      <tuv xml:lang="EN"><seg>source text</seg></tuv>
      <tuv xml:lang="BG"><seg>target text</seg></tuv>
    </tu>
  </body>
</tmx>
''',
        encoding="utf-8",
    )
    return path


def _run_pipeline(tmx_file, output, output_format):
    return CliRunner().invoke(
        cli_module.app,
        [
            "pipeline",
            str(tmx_file),
            "-o",
            str(output),
            "--fmt",
            output_format,
            "--no-clean",
            "--no-dedupe",
        ],
    )


def test_pipeline_hf_dataset_writes_split_metadata(one_unit_tmx, tmp_path):
    output = tmp_path / "hf_output"

    result = _run_pipeline(one_unit_tmx, output, "hf_dataset")

    assert result.exit_code == 0, result.output
    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["total"] == 1
    assert (metadata["train"], metadata["validation"], metadata["test"]) == (1, 0, 0)
    assert metadata["format"] == "hf_dataset"
    assert metadata["seed"] == 42
    assert metadata["train_ratio"] == pytest.approx(0.9)
    assert metadata["stratified"] is False


def test_pipeline_small_jsonl_dataset_has_nonnegative_splits(one_unit_tmx, tmp_path):
    output = tmp_path / "jsonl_output"

    result = _run_pipeline(one_unit_tmx, output, "jsonl")

    assert result.exit_code == 0, result.output
    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["total"] == 1
    assert (metadata["train"], metadata["validation"], metadata["test"]) == (1, 0, 0)
    assert (output / "train.jsonl").read_text(encoding="utf-8").count("\n") == 1


def test_convert_cli_streams_parser_cleaner_and_jsonl_writer(one_unit_tmx, tmp_path, monkeypatch):
    monkeypatch.setattr(
        cli_module.TMXParser,
        "parse_all",
        lambda _parser: pytest.fail("streaming CLI must not call parse_all"),
    )
    monkeypatch.setattr(
        cli_module.DataCleaner,
        "clean_units",
        lambda _cleaner, _units: pytest.fail("streaming CLI must use clean_iter"),
    )
    output = tmp_path / "streamed.jsonl"
    result = CliRunner().invoke(
        cli_module.app,
        [
            "convert",
            str(one_unit_tmx),
            "-o",
            str(output),
            "--fmt",
            "jsonl",
            "--no-dedupe",
            "--streaming",
        ],
    )

    assert result.exit_code == 0, result.output
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["source"] == "source text"
    assert rows[0]["target"] == "target text"
    assert "Streaming завърши: 1 TU" in result.output


def test_convert_cli_streaming_requires_dedupe_disabled(one_unit_tmx, tmp_path):
    result = CliRunner().invoke(
        cli_module.app,
        [
            "convert",
            str(one_unit_tmx),
            "-o",
            str(tmp_path / "streamed.jsonl"),
            "--streaming",
        ],
    )

    assert result.exit_code != 0
    assert "--no-dedupe" in result.output


def test_convert_cli_can_preserve_positional_placeholders(tmp_path):
        tmx_file = tmp_path / "placeholders.tmx"
        tmx_file.write_text(
                '''<?xml version="1.0" encoding="UTF-8"?>
<tmx xmlns="urn:example:tmx">
    <header srclang="EN" />
    <body><tu>
        <tuv xml:lang="EN"><seg>The page at %1$s says: %2$d</seg></tuv>
        <tuv xml:lang="BG"><seg>Страницата %1$s казва: %2$d</seg></tuv>
    </tu></body>
</tmx>
''',
                encoding="utf-8",
        )
        output = tmp_path / "placeholders.jsonl"

        result = CliRunner().invoke(
                cli_module.app,
                [
                        "convert",
                        str(tmx_file),
                        "-o",
                        str(output),
                        "--fmt",
                        "jsonl",
                        "--no-dedupe",
                        "--streaming",
                        "--preserve-placeholders",
                ],
        )

        assert result.exit_code == 0, result.output
        record = json.loads(output.read_text(encoding="utf-8"))
        assert "%1$s" in record["source"]
        assert "%2$d" in record["target"]
