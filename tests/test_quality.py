import pytest
from tmx_processor import DataValidator, ValidationConfig, TranslationUnit

def test_script_mismatch_and_quality_checks():
    validator = DataValidator()

    # Normal unit
    unit_ok = TranslationUnit(
        tu_id="1",
        source_lang="en", target_lang="bg",
        source_text="Hello world", target_text="Здравей свят"
    )
    res_ok = validator.validate(unit_ok)
    assert res_ok.is_valid
    assert len(res_ok.warnings) == 0

    # Script mismatch (BG text with Latin characters mixed incorrectly)
    unit_script = TranslationUnit(
        tu_id="2",
        source_lang="en", target_lang="bg",
        source_text="Hello world", target_text="Zdravey svyat"
    )
    res_script = validator.validate(unit_script)
    assert res_script.is_valid
    assert any("латиница" in w.lower() or "кирилица" in w.lower() for w in res_script.warnings)
