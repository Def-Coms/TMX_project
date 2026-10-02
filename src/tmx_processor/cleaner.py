from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .parser import TranslationUnit


@dataclass
class CleanConfig:
    strip_whitespace: bool = True
    normalize_unicode: bool = True
    unicode_form: str = "NFKC"
    remove_html_tags: bool = True
    remove_control_chars: bool = True
    remove_urls: bool = False
    remove_emails: bool = False
    normalize_spaces: bool = True
    fix_punctuation: bool = True
    remove_placeholder_tags: bool = True
    min_length: int = 1
    max_length: int = 10000
    min_words: int = 0
    max_words: int = 0
    max_length_ratio: float = 3.0
    lang_detect: bool = False
    language_pairs: Optional[List[str]] = None  # e.g., ["EN-BG", "BG-EN"]
    preserve_placeholders: bool = False  # Keep {0}, {1} etc. placeholders


HTML_TAG_RE = re.compile(r"<[^>]+>")
URL_RE = re.compile(
    r"https?://\S+|www\.\S+|ftp://\S+",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
)
PLACEHOLDER_RE = re.compile(
    r"\{[^{}]+\}|\[[^\]]+\]|<[^>]+>|%(?:\d+\$)?[A-Za-z]|\$\{[^}]+\}"
)
PLACEHOLDER_TOKEN_RE = re.compile(
    r"\{[^{}]+\}|\[[^\]]+\]|%(?:\d+\$)?[A-Za-z]|\$\{[^}]+\}"
)
MULTISPACE_RE = re.compile(r"\s+")
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MULTI_PUNCT_RE = re.compile(r"([.!?])\1+")
SPACE_PUNCT_RE = re.compile(r"\s+([.,;:!?])")
# Do not insert a space after . or , when a digit follows (29.99, 1,000).
PUNCT_SPACE_RE = re.compile(r"([;:!?])(?=\S)|([.,])(?=[^\d\s])")


class DataCleaner:
    def __init__(self, config: Optional[CleanConfig] = None):
        self.config = config or CleanConfig()
        self._lang_detector = None

    def _get_lang_detector(self):
        if self._lang_detector is None and self.config.lang_detect:
            try:
                from langdetect import detect

                self._lang_detector = detect
            except ImportError:
                self._lang_detector = None
        return self._lang_detector

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""

        result = text

        if self.config.strip_whitespace:
            result = result.strip()

        if self.config.normalize_unicode:
            result = unicodedata.normalize(self.config.unicode_form, result)

        if self.config.remove_control_chars:
            result = CONTROL_CHARS_RE.sub("", result)

        if self.config.remove_html_tags:
            if self.config.preserve_placeholders:
                result = HTML_TAG_RE.sub(
                    lambda match: " ".join(
                        PLACEHOLDER_TOKEN_RE.findall(match.group(0))
                    ),
                    result,
                )
            else:
                result = HTML_TAG_RE.sub(" ", result)

        if self.config.remove_placeholder_tags and not self.config.preserve_placeholders:
            result = PLACEHOLDER_RE.sub(" ", result)

        if self.config.remove_urls:
            result = URL_RE.sub(" ", result)

        if self.config.remove_emails:
            result = EMAIL_RE.sub(" ", result)

        if self.config.fix_punctuation:
            result = MULTI_PUNCT_RE.sub(r"\1", result)
            result = SPACE_PUNCT_RE.sub(r"\1", result)
            result = PUNCT_SPACE_RE.sub(
                lambda m: (m.group(1) or m.group(2)) + " ", result
            )

        if self.config.normalize_spaces:
            result = MULTISPACE_RE.sub(" ", result)

        if self.config.strip_whitespace:
            result = result.strip()

        return result

    def _check_length_filters(
        self, src: str, tgt: str
    ) -> bool:
        cfg = self.config

        if cfg.min_length > 0:
            if len(src) < cfg.min_length or len(tgt) < cfg.min_length:
                return False

        if cfg.max_length > 0:
            if len(src) > cfg.max_length or len(tgt) > cfg.max_length:
                return False

        if cfg.min_words > 0:
            src_words = len(src.split())
            tgt_words = len(tgt.split())
            if src_words < cfg.min_words or tgt_words < cfg.min_words:
                return False

        if cfg.max_words > 0:
            src_words = len(src.split())
            tgt_words = len(tgt.split())
            if src_words > cfg.max_words or tgt_words > cfg.max_words:
                return False

        if cfg.max_length_ratio > 0 and src and tgt:
            ratio = max(len(src), len(tgt)) / max(min(len(src), len(tgt)), 1)
            if ratio > cfg.max_length_ratio:
                return False

        return True

    def _check_language(
        self, src: str, tgt: str, src_lang: str, tgt_lang: str
    ) -> bool:
        if not self.config.lang_detect:
            return True
        detector = self._get_lang_detector()
        if not detector:
            return True
        try:
            detected_src = detector(src).lower()
            detected_tgt = detector(tgt).lower()
            expected_src = (src_lang or "").lower()[:2]
            expected_tgt = (tgt_lang or "").lower()[:2]
            if expected_src and detected_src != expected_src:
                return False
            if expected_tgt and detected_tgt != expected_tgt:
                return False
        except Exception:
            pass
        return True

    def _check_language_pair(self, src_lang: str, tgt_lang: str) -> bool:
        """Filter by specific language pairs (e.g., 'EN-BG', 'BG-EN')."""
        if not self.config.language_pairs:
            return True
        src_upper = (src_lang or "").upper()
        tgt_upper = (tgt_lang or "").upper()
        pair_str = f"{src_upper}-{tgt_upper}"
        return pair_str in [p.upper() for p in self.config.language_pairs]

    def clean_unit(self, unit: TranslationUnit) -> Optional[TranslationUnit]:
        if not unit or not unit.source_text or not unit.target_text:
            return None

        if not self._check_language_pair(unit.source_lang, unit.target_lang):
            return None

        cleaned_src = self._clean_text(unit.source_text)
        cleaned_tgt = self._clean_text(unit.target_text)

        if not cleaned_src or not cleaned_tgt:
            return None

        if not self._check_length_filters(cleaned_src, cleaned_tgt):
            return None

        if not self._check_language(
            cleaned_src, cleaned_tgt, unit.source_lang, unit.target_lang
        ):
            return None

        result = TranslationUnit(
            tu_id=unit.tu_id,
            source_lang=unit.source_lang,
            target_lang=unit.target_lang,
            source_text=cleaned_src,
            target_text=cleaned_tgt,
            metadata=unit.metadata,
            notes=unit.notes,
        )
        return result

    def clean_units(
        self, units: List[TranslationUnit]
    ) -> List[TranslationUnit]:
        results: List[TranslationUnit] = []
        for unit in units:
            cleaned = self.clean_unit(unit)
            if cleaned is not None:
                results.append(cleaned)
        return results

    def clean_iter(self, units):
        for unit in units:
            cleaned = self.clean_unit(unit)
            if cleaned is not None:
                yield cleaned
