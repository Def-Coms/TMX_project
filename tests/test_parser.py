"""Unit tests for TMX parser."""
import pytest
from pathlib import Path
from tmx_processor import TMXParser, TranslationUnit


def test_parser_init():
    """Test parser initialization."""
    parser = TMXParser(Path("examples/sample_en_bg.tmx"))
    assert parser.file_path.name == "sample_en_bg.tmx"


def test_parse_header():
    """Test parsing TMX header."""
    parser = TMXParser(Path("examples/sample_en_bg.tmx"))
    header = parser.parse_header()
    assert header is not None
    assert header.source_lang is not None


def test_parse_all():
    """Test parsing all translation units."""
    parser = TMXParser(Path("examples/sample_en_bg.tmx"))
    units = parser.parse_all()
    assert len(units) > 0
    assert all(isinstance(u, TranslationUnit) for u in units)


def test_parse_expand_multilingual():
    """Test multilingual expansion (should not change bilingual file)."""
    parser = TMXParser(Path("examples/sample_en_bg.tmx"))
    units_normal = parser.parse_all(expand_multilingual=False)
    units_expanded = parser.parse_all(expand_multilingual=True)
    # For bilingual file, should be the same
    assert len(units_normal) == len(units_expanded)


def test_preserve_tags():
    """Test tag preservation option."""
    parser_normal = TMXParser(Path("examples/sample_en_bg.tmx"), preserve_tags=False)
    parser_preserve = TMXParser(Path("examples/sample_en_bg.tmx"), preserve_tags=True)

    units_normal = parser_normal.parse_all()
    units_preserve = parser_preserve.parse_all()

    # If there are inline tags, preserved version should have placeholders
    # This is a basic check - the actual behavior depends on the TMX content
    assert len(units_normal) == len(units_preserve)


@pytest.mark.parametrize(
    ("preserve_tags", "expected_source", "expected_target"),
    [
        (
            False,
            "source-before source-middle source-after",
            "target-before target-middle target-after",
        ),
        (
            True,
            "source-before{0} source-middle{1} source-after",
            "target-before{0} target-middle{1} target-after",
        ),
    ],
)
def test_inline_tag_tails_are_preserved(
    tmp_path, preserve_tags, expected_source, expected_target
):
    tmx_path = tmp_path / "inline_tags.tmx"
    tmx_path.write_text(
        '''<?xml version="1.0" encoding="UTF-8"?>
<tmx xmlns="urn:example:tmx">
  <header srclang="EN" />
  <body>
    <tu>
      <tuv xml:lang="EN"><seg>source-before<bpt>&lt;b&gt;</bpt> source-middle<ept>&lt;/b&gt;</ept> source-after</seg></tuv>
      <tuv xml:lang="BG"><seg>target-before<bpt>&lt;b&gt;</bpt> target-middle<ept>&lt;/b&gt;</ept> target-after</seg></tuv>
    </tu>
  </body>
</tmx>
''',
        encoding="utf-8",
    )

    units = TMXParser(tmx_path, preserve_tags=preserve_tags).parse_all()

    assert len(units) == 1
    assert units[0].source_text == expected_source
    assert units[0].target_text == expected_target


def test_lxml_recovers_xml_control_characters_without_dropping_text(tmp_path):
        pytest.importorskip("lxml.etree")
        tmx_path = tmp_path / "control_character.tmx"
        tmx_path.write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<tmx xmlns="urn:example:tmx">
    <header srclang="EN" />
    <body><tu>
        <tuv xml:lang="EN"><seg>before\x0bafter</seg></tuv>
        <tuv xml:lang="BG"><seg>преди\x0bслед</seg></tuv>
    </tu></body>
</tmx>
""",
                encoding="utf-8",
        )

        with pytest.warns(RuntimeWarning, match="Recovered from .* XML syntax issue"):
            units = TMXParser(tmx_path).parse_all()

        assert len(units) == 1
        assert units[0].source_text == "beforeafter"
        assert units[0].target_text == "предислед"
