import pytest
from tmx_processor import DataAnalyzer, DataValidator, ValidationConfig, TranslationUnit

def test_terminology_extraction_and_token_estimation():
    units = [
        TranslationUnit(tu_id="1", source_lang="en", target_lang="bg", source_text="Machine learning model", target_text="Модел за машинно обучение"),
        TranslationUnit(tu_id="2", source_lang="en", target_lang="bg", source_text="Machine learning algorithm", target_text="Алгоритъм за машинно обучение"),
        TranslationUnit(tu_id="3", source_lang="en", target_lang="bg", source_text="Deep learning model", target_text="Модел за дълбоко обучение"),
    ]

    analyzer = DataAnalyzer()
    stats = analyzer.analyze(units)

    # Token estimation check
    estimates = stats.estimate_llm_tokens()
    assert "llama3_estimated_tokens" in estimates
    assert estimates["llama3_estimated_tokens"] > 0

    # Readiness report check
    report = stats.readiness_report()
    assert "dataset_status" in report
    assert "is_ready" in report

    # Terminology extraction check
    terms = analyzer.extract_terminology(units, min_freq=2)
    assert len(terms) > 0
    assert any(t["source_term"] == "learning" for t in terms)


def test_quality_score_threshold_validation():
    unit_good = TranslationUnit(
        tu_id="1", source_lang="en", target_lang="bg",
        source_text="Welcome to the platform.", target_text="Добре дошли в платформата."
    )
    unit_bad = TranslationUnit(
        tu_id="2", source_lang="en", target_lang="bg",
        source_text="Welcome to the platform.", target_text="Welcome to the platform."
    )

    validator_strict = DataValidator(ValidationConfig(min_quality_score=60.0))
    res_good = validator_strict.validate(unit_good)
    res_bad = validator_strict.validate(unit_bad)

    assert res_good.is_valid
    assert not res_bad.is_valid
