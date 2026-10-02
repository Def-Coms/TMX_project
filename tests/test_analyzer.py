"""Tests for dataset statistics."""
import pytest

from tmx_processor.analyzer import DataAnalyzer
from tmx_processor.parser import TranslationUnit


def _unit(source, target, source_lang="EN", target_lang="BG"):
    return TranslationUnit(
        source_lang=source_lang,
        target_lang=target_lang,
        source_text=source,
        target_text=target,
    )


def test_analyzer_running_stats_and_duplicate_counts():
    units = [
        _unit("one two", "uno"),
        _unit("one two", "uno"),
        _unit("three", "tres dos"),
        _unit("", "empty"),
    ]

    stats = DataAnalyzer().analyze(units)
    output = stats.to_dict()

    assert stats.total_units == 4
    assert stats.valid_units == 3
    assert stats.empty_pairs == 1
    assert stats.duplicates_found == 1
    assert stats.language_pairs[("EN", "BG")] == 3
    assert stats.source_length_sum == 19
    assert stats.target_length_sum == 14
    assert stats.avg_source_length == pytest.approx(19 / 3)
    assert stats.avg_target_length == pytest.approx(14 / 3)
    assert (output["source"]["min_chars"], output["source"]["max_chars"]) == (5, 7)
    assert (output["target"]["min_chars"], output["target"]["max_chars"]) == (3, 8)
    assert output["source"]["total_words"] == 5
    assert output["target"]["total_words"] == 4


def test_analyzer_empty_dataset_serializes_zero_minima():
    stats = DataAnalyzer().analyze([])
    output = stats.to_dict()

    assert stats.total_units == 0
    assert stats.avg_source_length == 0
    assert output["source"]["min_chars"] == 0
    assert output["target"]["min_words"] == 0
