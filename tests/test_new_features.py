import pytest
from tmx_processor import DataCleaner, CleanConfig, DataConverter, DataAnalyzer, TranslationUnit

def test_pii_anonymizer():
    unit = TranslationUnit(
        tu_id="1", source_lang="en", target_lang="bg",
        source_text="Contact me at john@example.com or +359 888 123 456.",
        target_text="Пишете на john@example.com или +359 888 123 456."
    )
    cleaner = DataCleaner(CleanConfig(anonymize_pii=True))
    cleaned = cleaner.clean_unit(unit)

    assert "[REDACTED]" in cleaned.source_text
    assert "[REDACTED]" in cleaned.target_text
    assert "john@example.com" not in cleaned.source_text


def test_context_window_packer():
    units = [
        TranslationUnit(tu_id="1", source_lang="EN", target_lang="BG", source_text="Line 1", target_text="Ред 1"),
        TranslationUnit(tu_id="2", source_lang="EN", target_lang="BG", source_text="Line 2", target_text="Ред 2"),
    ]
    converter = DataConverter()
    packed = list(converter.pack_context_windows(units, max_chars=1000))

    assert len(packed) == 1
    assert "Line 1\nLine 2" in packed[0].source_text


def test_concordance_search():
    units = [
        TranslationUnit(tu_id="1", source_lang="EN", target_lang="BG", source_text="Artificial Intelligence model", target_text="Модел на изкуствен интелект"),
        TranslationUnit(tu_id="2", source_lang="EN", target_lang="BG", source_text="Database query", target_text="Заявка към база данни"),
    ]
    analyzer = DataAnalyzer()
    res = analyzer.search_concordance(units, query="Intelligence")

    assert len(res) == 1
    assert res[0]["id"] == "1"
