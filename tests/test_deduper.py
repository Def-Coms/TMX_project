"""Tests for exact and optional fuzzy deduplication."""
import sys

import pytest

from tmx_processor.deduper import DataDeduper
from tmx_processor.parser import TranslationUnit


def _unit(source, target, source_lang="EN", target_lang="BG"):
    return TranslationUnit(
        source_lang=source_lang,
        target_lang=target_lang,
        source_text=source,
        target_text=target,
    )


def _write_tmx(path, source, target):
    path.write_text(
        f'''<?xml version="1.0" encoding="UTF-8"?>
<tmx xmlns="urn:example:tmx">
  <header srclang="EN" />
  <body><tu>
    <tuv xml:lang="EN"><seg>{source}</seg></tuv>
    <tuv xml:lang="BG"><seg>{target}</seg></tuv>
  </tu></body>
</tmx>
''',
        encoding="utf-8",
    )


def test_exact_dedupe_normalizes_whitespace_but_keeps_language_direction():
    units = [
        _unit("Hello   world", "Здравей свят"),
        _unit("Hello\nworld", "Здравей свят"),
        _unit("Hello world", "Здравей свят", "BG", "EN"),
    ]

    results = DataDeduper().dedupe(units)

    assert results == [units[0], units[2]]


def test_case_insensitive_exact_dedupe():
    units = [_unit("Hello", "Bonjour"), _unit("HELLO", "bonjour")]

    results = DataDeduper(case_sensitive=False).dedupe(units)

    assert results == [units[0]]


def test_exact_dedupe_resets_seen_state_between_calls():
    deduper = DataDeduper()
    unit = _unit("Hello", "Здравей")

    assert deduper.dedupe([unit]) == [unit]
    assert deduper.dedupe([unit]) == [unit]


def test_fuzzy_dedupe_falls_back_to_exact_without_datasketch(monkeypatch):
    monkeypatch.setitem(sys.modules, "datasketch", None)
    units = [_unit("Hello", "Здравей"), _unit("Hello", "Здравей")]

    results = DataDeduper(fuzzy=True).dedupe(units)

    assert results == [units[0]]


def test_merge_tmx_files_deduplicates_across_files(tmp_path):
    first = tmp_path / "first.tmx"
    second = tmp_path / "second.tmx"
    _write_tmx(first, "Hello world", "Здравей свят")
    _write_tmx(second, "Hello world", "Здравей свят")

    merged = DataDeduper().merge_tmx_files([first, second])

    assert len(merged) == 1
    assert merged[0].source_text == "Hello world"


def test_merge_tmx_files_can_keep_duplicates(tmp_path):
    first = tmp_path / "first.tmx"
    second = tmp_path / "second.tmx"
    _write_tmx(first, "Hello world", "Здравей свят")
    _write_tmx(second, "Hello world", "Здравей свят")

    merged = DataDeduper().merge_tmx_files([first, second], dedupe=False)

    assert len(merged) == 2
