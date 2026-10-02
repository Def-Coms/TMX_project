"""Unit tests for data validator."""
import pytest
from tmx_processor import DataValidator, ValidationConfig, TranslationUnit


def test_validator_init():
    """Test validator initialization."""
    validator = DataValidator()
    assert validator.config is not None


def test_validate_valid_unit():
    """Test validation of a valid unit."""
    validator = DataValidator()
    unit = TranslationUnit(
        source_lang="EN",
        target_lang="BG",
        source_text="Hello world",
        target_text="Здравей свят",
    )
    result = validator.validate(unit)
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_validate_empty_unit():
    """Test validation of empty unit."""
    validator = DataValidator()
    unit = TranslationUnit(
        source_lang="EN",
        target_lang="BG",
        source_text="",
        target_text="",
    )
    result = validator.validate(unit)
    assert result.is_valid is False
    assert len(result.errors) > 0


def test_validate_same_language():
    """Test validation when source and target are same language."""
    validator = DataValidator()
    unit = TranslationUnit(
        source_lang="EN",
        target_lang="EN",
        source_text="Hello",
        target_text="Hello",
    )
    result = validator.validate(unit)
    assert result.is_valid is False


def test_validate_digit_mismatch():
    """Test digit mismatch validation with improved number checking."""
    config = ValidationConfig(max_digit_mismatch_ratio=0.5)
    validator = DataValidator(config)

    # Same numbers - should pass
    unit1 = TranslationUnit(
        source_lang="EN",
        target_lang="BG",
        source_text="The price is 29.99",
        target_text="Цената е 29.99",
    )
    result1 = validator.validate(unit1)
    assert result1.is_valid is True

    # Different numbers - should fail
    unit2 = TranslationUnit(
        source_lang="EN",
        target_lang="BG",
        source_text="The price is 29.99",
        target_text="Цената е 30.00",
    )
    result2 = validator.validate(unit2)
    assert result2.is_valid is False


def test_filter_valid():
    """Test filtering valid units."""
    validator = DataValidator()
    units = [
        TranslationUnit(source_lang="EN", target_lang="BG", source_text="A", target_text="B"),
        TranslationUnit(source_lang="EN", target_lang="BG", source_text="", target_text="B"),
        TranslationUnit(source_lang="EN", target_lang="BG", source_text="C", target_text="D"),
    ]
    filtered = validator.filter_valid(units)
    # Should only include valid units (first and third)
    assert len(filtered) == 2
