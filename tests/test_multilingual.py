import pytest
from pathlib import Path
from tmx_processor.parser import TMXParser
from tmx_processor.cleaner import DataCleaner, CleanConfig

def test_multilingual_discovery_and_filtering():
    sample_tmx = Path("examples/sample_en_bg.tmx")
    parser = TMXParser(sample_tmx)

    langs = parser.get_available_languages()
    assert "EN" in langs
    assert "BG" in langs

    pairs = parser.get_language_pairs()
    assert ("EN", "BG") in pairs

    units = parser.parse_all()

    # Filter only EN-BG
    cleaner = DataCleaner(CleanConfig(language_pairs=["EN-BG"]))
    cleaned_en_bg = cleaner.clean_units(units)
    assert len(cleaned_en_bg) > 0
    assert all(u.source_lang == "EN" and u.target_lang == "BG" for u in cleaned_en_bg)

    # Filter non-existent pair
    cleaner_none = DataCleaner(CleanConfig(language_pairs=["EN-FR"]))
    cleaned_none = cleaner_none.clean_units(units)
    assert len(cleaned_none) == 0
