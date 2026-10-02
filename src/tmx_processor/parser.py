from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple, Union
import warnings
import re

try:
    from lxml import etree as _etree

    _HAS_LXML = True
except ImportError:  # pragma: no cover
    import xml.etree.ElementTree as _etree

    _HAS_LXML = False


def _localname(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _find_all(element, local_tag: str):
    """Find direct children by local tag name, ignoring XML namespaces."""
    for child in element:
        if _localname(child.tag) == local_tag:
            yield child


def _find_one(element, local_tag: str):
    for child in _find_all(element, local_tag):
        return child
    return None


_XML_ILLEGAL_BYTES_RE = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class _XmlSanitizingReader:
    """Strip XML 1.0 illegal control bytes so stdlib iterparse can stream."""

    def __init__(self, path: Path):
        self._fh = open(path, "rb")
        self.stripped = 0
        self.first_offset: Optional[int] = None
        self._offset = 0

    def read(self, size: int = -1) -> bytes:
        data = self._fh.read(size)
        if not data:
            return data
        cleaned, count = _XML_ILLEGAL_BYTES_RE.subn(b"", data)
        if count:
            if self.first_offset is None:
                self.first_offset = self._offset
            self.stripped += count
        self._offset += len(data)
        return cleaned

    def close(self) -> None:
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        self.close()


@dataclass
class TranslationUnit:
    tu_id: Optional[str] = None
    source_lang: Optional[str] = None
    target_lang: Optional[str] = None
    source_text: str = ""
    target_text: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return bool(
            self.source_text
            and self.target_text
            and self.source_lang
            and self.target_lang
        )

    @property
    def langs(self) -> Tuple[str, str]:
        return (self.source_lang or "", self.target_lang or "")

    def to_dict(self) -> Dict:
        return {
            "id": self.tu_id,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "source": self.source_text,
            "target": self.target_text,
            "metadata": self.metadata,
            "notes": self.notes,
        }


@dataclass
class TMXHeader:
    source_lang: Optional[str] = None
    creation_tool: Optional[str] = None
    creation_date: Optional[str] = None
    seg_type: Optional[str] = None
    admin_lang: Optional[str] = None
    properties: Dict[str, str] = field(default_factory=dict)
    target_langs: List[str] = field(default_factory=list)


class TMXParser:
    NAMESPACES = {"xml": "http://www.w3.org/XML/1998/namespace"}

    def __init__(self, file_path: Union[str, Path], preserve_tags: bool = False):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"TMX файлът не е намерен: {self.file_path}")
        self.header: Optional[TMXHeader] = None
        self.preserve_tags = preserve_tags
        self._tag_counter = 0

    def _get_lang(self, element) -> Optional[str]:
        lang = element.get(f"{{{self.NAMESPACES['xml']}}}lang")
        if lang is None:
            lang = element.get("lang")
        return lang.upper() if lang else None

    def _get_text_recursive(self, element) -> str:
        parts: List[str] = []
        if element.text:
            parts.append(element.text)
        for child in element:
            tag = _localname(child.tag)
            if tag in ("bpt", "ept", "ph", "it", "hi", "ut"):
                if self.preserve_tags:
                    # Preserve as placeholder
                    parts.append(f"{{{self._tag_counter}}}")
                    self._tag_counter += 1
            else:
                parts.append(self._get_text_recursive(child))
            if child.tail:
                parts.append(child.tail)
        return "".join(parts).strip()

    def _parse_header_element(self, header_el) -> TMXHeader:
        header = TMXHeader()
        header.source_lang = header_el.get("srclang")
        if header.source_lang:
            header.source_lang = header.source_lang.upper()
        header.creation_tool = header_el.get("creationtool")
        header.creation_date = header_el.get("creationdate")
        header.seg_type = header_el.get("segtype")
        header.admin_lang = header_el.get("adminlang")
        for prop in _find_all(header_el, "prop"):
            prop_type = prop.get("type", "unknown")
            header.properties[prop_type] = prop.text or ""
        return header

    def parse_header(self) -> TMXHeader:
        reader = None
        header = TMXHeader()
        try:
            if _HAS_LXML:
                context = _etree.iterparse(
                    str(self.file_path), events=("end",), recover=True
                )
            else:
                reader = _XmlSanitizingReader(self.file_path)
                context = _etree.iterparse(reader, events=("end",))
            for _event, elem in context:
                if _localname(elem.tag) != "header":
                    continue
                header = self._parse_header_element(elem)
                elem.clear()
                break
            del context
        finally:
            if reader is not None:
                reader.close()
        self.header = header
        return header

    def _parse_tu(self, tu_element) -> Optional[TranslationUnit]:
        tu = TranslationUnit()
        tu.tu_id = tu_element.get("tuid")

        for note in _find_all(tu_element, "note"):
            if note.text:
                tu.notes.append(note.text.strip())

        for prop in _find_all(tu_element, "prop"):
            prop_type = prop.get("type", "unknown")
            tu.metadata[prop_type] = prop.text or ""

        segments: Dict[str, str] = {}
        tuv_langs: List[str] = []

        for tuv in _find_all(tu_element, "tuv"):
            lang = self._get_lang(tuv)
            if not lang:
                if self.header and self.header.source_lang and not tuv_langs:
                    lang = self.header.source_lang
                else:
                    continue
            seg = _find_one(tuv, "seg")
            if seg is not None:
                if self.preserve_tags:
                    self._tag_counter = 0
                text = self._get_text_recursive(seg)
                if text:
                    segments[lang] = text
                    tuv_langs.append(lang)
            for prop in _find_all(tuv, "prop"):
                prop_type = prop.get("type", f"tuv_{lang}_prop")
                tu.metadata[prop_type] = prop.text or ""

        if len(segments) >= 2:
            langs_ordered = list(segments.keys())
            if self.header and self.header.source_lang in segments:
                src_lang = self.header.source_lang
                other_langs = [l for l in langs_ordered if l != src_lang]
                if other_langs:
                    tu.source_lang = src_lang
                    tu.target_lang = other_langs[0]
                    tu.source_text = segments[src_lang]
                    tu.target_text = segments[other_langs[0]]
            else:
                tu.source_lang = langs_ordered[0]
                tu.target_lang = langs_ordered[1]
                tu.source_text = segments[langs_ordered[0]]
                tu.target_text = segments[langs_ordered[1]]
        elif len(segments) == 1 and self.header and self.header.source_lang:
            only_lang = list(segments.keys())[0]
            tu.source_lang = self.header.source_lang
            tu.target_lang = only_lang
            tu.source_text = ""
            tu.target_text = segments[only_lang]

        return tu

    def _parse_tu_expanded(self, tu_element) -> List[TranslationUnit]:
        """Parse a TU and expand it to all possible language pairs if multilingual."""
        tu = TranslationUnit()
        tu.tu_id = tu_element.get("tuid")

        for note in _find_all(tu_element, "note"):
            if note.text:
                tu.notes.append(note.text.strip())

        for prop in _find_all(tu_element, "prop"):
            prop_type = prop.get("type", "unknown")
            tu.metadata[prop_type] = prop.text or ""

        segments: Dict[str, str] = {}
        tuv_langs: List[str] = []

        for tuv in _find_all(tu_element, "tuv"):
            lang = self._get_lang(tuv)
            if not lang:
                if self.header and self.header.source_lang and not tuv_langs:
                    lang = self.header.source_lang
                else:
                    continue
            seg = _find_one(tuv, "seg")
            if seg is not None:
                if self.preserve_tags:
                    self._tag_counter = 0
                text = self._get_text_recursive(seg)
                if text:
                    segments[lang] = text
                    tuv_langs.append(lang)
            for prop in _find_all(tuv, "prop"):
                prop_type = prop.get("type", f"tuv_{lang}_prop")
                tu.metadata[prop_type] = prop.text or ""

        # If 2 or fewer languages, return single TU
        if len(segments) <= 2:
            return [self._parse_tu(tu_element)]

        # Expand to all possible pairs
        units: List[TranslationUnit] = []
        langs = list(segments.keys())
        for i in range(len(langs)):
            for j in range(len(langs)):
                if i != j:
                    new_tu = TranslationUnit(
                        tu_id=tu.tu_id,
                        source_lang=langs[i],
                        target_lang=langs[j],
                        source_text=segments[langs[i]],
                        target_text=segments[langs[j]],
                        metadata=dict(tu.metadata),
                        notes=list(tu.notes),
                    )
                    units.append(new_tu)
        return units

    def _note_target_lang(self, tu: TranslationUnit) -> None:
        if not self.header or not tu.target_lang:
            return
        if tu.target_lang not in self.header.target_langs:
            self.header.target_langs.append(tu.target_lang)

    def _clear_elem(self, elem) -> None:
        elem.clear()
        if not _HAS_LXML:
            return
        for ancestor in elem.xpath("ancestor-or-self::*"):
            while ancestor.getprevious() is not None:
                del ancestor.getparent()[0]

    def _emit_tu(self, elem, expand_multilingual: bool) -> Iterator[TranslationUnit]:
        if expand_multilingual:
            units = self._parse_tu_expanded(elem)
            for tu in units:
                if tu is not None:
                    self._note_target_lang(tu)
                    yield tu
            return
        tu = self._parse_tu(elem)
        if tu is not None:
            self._note_target_lang(tu)
            yield tu

    def iter_units(self, stream: bool = True, expand_multilingual: bool = False) -> Iterator[TranslationUnit]:
        self.parse_header()
        reader = None
        try:
            if stream:
                if _HAS_LXML:
                    context = _etree.iterparse(
                        str(self.file_path), events=("end",), recover=True
                    )
                else:
                    reader = _XmlSanitizingReader(self.file_path)
                    context = _etree.iterparse(reader, events=("end",))
                for _event, elem in context:
                    if _localname(elem.tag) != "tu":
                        continue
                    yield from self._emit_tu(elem, expand_multilingual)
                    self._clear_elem(elem)
                if _HAS_LXML:
                    recovery_errors = list(context.error_log)
                    if recovery_errors:
                        first_error = recovery_errors[0]
                        warnings.warn(
                            f"Recovered from {len(recovery_errors)} XML syntax issue(s) "
                            f"in {self.file_path.name}; first at line {first_error.line}, "
                            f"column {first_error.column}: {first_error.message}",
                            RuntimeWarning,
                            stacklevel=2,
                        )
                elif reader is not None and reader.stripped:
                    warnings.warn(
                        f"Stripped {reader.stripped} illegal XML control byte(s) "
                        f"in {self.file_path.name}; first near offset {reader.first_offset}",
                        RuntimeWarning,
                        stacklevel=2,
                    )
                del context
            else:
                tree = _etree.parse(str(self.file_path))
                root = tree.getroot()
                body = None
                for child in root:
                    if _localname(child.tag) == "body":
                        body = child
                        break
                if body is None:
                    return
                for tu_element in body:
                    if _localname(tu_element.tag) != "tu":
                        continue
                    yield from self._emit_tu(tu_element, expand_multilingual)
        finally:
            if reader is not None:
                reader.close()

    def get_available_languages(self) -> List[str]:
        """Discover all unique language codes present in the TMX file."""
        langs = set()
        if self.header and self.header.source_lang:
            langs.add(self.header.source_lang)
        for tu in self.iter_units(stream=True):
            if tu.source_lang:
                langs.add(tu.source_lang)
            if tu.target_lang:
                langs.add(tu.target_lang)
        return sorted(langs)

    def get_language_pairs(self, expand_multilingual: bool = False) -> List[Tuple[str, str]]:
        """Discover all unique language pairs (source_lang, target_lang) in the TMX file."""
        pairs = set()
        for tu in self.iter_units(stream=True, expand_multilingual=expand_multilingual):
            if tu.source_lang and tu.target_lang:
                pairs.add((tu.source_lang, tu.target_lang))
        return sorted(pairs)

    def parse_all(self, expand_multilingual: bool = False) -> List[TranslationUnit]:
        return list(self.iter_units(stream=True, expand_multilingual=expand_multilingual))

    def __repr__(self) -> str:
        return f"<TMXParser file={self.file_path.name}>"
