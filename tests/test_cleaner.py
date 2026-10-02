"""Unit tests for data cleaner."""
import pytest
from tmx_processor import TMXParser, DataCleaner, CleanConfig, TranslationUnit


def test_cleaner_init():
    """Test cleaner initialization."""
    cleaner = DataCleaner()
    assert cleaner.config is not None


def test_clean_unit():
    """Test cleaning a single translation unit."""
    cleaner = DataCleaner()
    unit = TranslationUnit(
        source_lang="EN",
        target_lang="BG",
        source_text="Hello world!",
        target_text="Здравей свят!",
    )
    cleaned = cleaner.clean_unit(unit)
    assert cleaned is not None
    assert cleaned.source_text == "Hello world!"
    assert cleaned.target_text == "Здравей свят!"


def test_clean_units():
    """Test cleaning multiple units."""
    cleaner = DataCleaner()
    units = [
        TranslationUnit(
            source_lang="EN",
            target_lang="BG",
            source_text=f"Test {i}",
            target_text=f"Тест {i}",
        )
        for i in range(10)
    ]
    cleaned = cleaner.clean_units(units)
    assert len(cleaned) == 10


def test_filter_by_language_pair():
    """Test filtering by language pair."""
    config = CleanConfig(language_pairs=["EN-BG"])
    cleaner = DataCleaner(config)

    units = [
        TranslationUnit(source_lang="EN", target_lang="BG", source_text="A", target_text="B"),
        TranslationUnit(source_lang="BG", target_lang="EN", source_text="C", target_text="D"),
        TranslationUnit(source_lang="EN", target_lang="DE", source_text="E", target_text="F"),
    ]

    cleaned = cleaner.clean_units(units)
    # Only EN-BG should pass
    assert len(cleaned) == 1
    assert cleaned[0].source_lang == "EN"
    assert cleaned[0].target_lang == "BG"


def test_punctuation_not_breaking_numbers():
    """Test that punctuation regex doesn't break numbers."""
    config = CleanConfig(fix_punctuation=True)
    cleaner = DataCleaner(config)

    unit = TranslationUnit(
        source_lang="EN",
        target_lang="BG",
        source_text="Price: 29.99, Quantity: 1,000",
        target_text="Цена: 29.99, Количество: 1,000",
    )

    cleaned = cleaner.clean_unit(unit)
    assert cleaned is not None
    # Numbers should remain intact
    assert "29.99" in cleaned.source_text
    assert "1,000" in cleaned.source_text


def test_preserve_placeholders():
    """Test placeholder preservation option."""
    config = CleanConfig(remove_placeholder_tags=False, preserve_placeholders=True)
    cleaner = DataCleaner(config)

    unit = TranslationUnit(
        source_lang="EN",
        target_lang="BG",
        source_text="Hello {0}, welcome to {1}; value %1$s",
        target_text="Здравей {0}, добре дошъл в {1}; стойност %1$s",
    )

    cleaned = cleaner.clean_unit(unit)
    assert cleaned is not None
    assert "{0}" in cleaned.source_text
    assert "{1}" in cleaned.source_text
    assert "%1$s" in cleaned.source_text


def test_positional_printf_placeholders_are_removed_as_whole_tokens():
    cleaner = DataCleaner()

    cleaned = cleaner._clean_text("The page at %1$s says: %2$d")

    assert cleaned == "The page at says:"


def test_preserve_placeholders_inside_removed_html_tags():
    cleaner = DataCleaner(CleanConfig(preserve_placeholders=True))

    cleaned = cleaner._clean_text(
        '<a href="%3$s">Privacy Policy</a> '
        '<span title="{0}">More information</span>'
    )

    assert "%3$s" in cleaned
    assert "{0}" in cleaned
    assert "Privacy Policy" in cleaned
    assert "More information" in cleaned
    assert "<a" not in cleaned
    assert "<span" not in cleaned
