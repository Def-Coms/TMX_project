from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from .parser import TranslationUnit


@dataclass
class DatasetStats:
    total_units: int = 0
    valid_units: int = 0
    language_pairs: Counter = field(default_factory=Counter)
    source_languages: Counter = field(default_factory=Counter)
    target_languages: Counter = field(default_factory=Counter)
    # Running statistics instead of storing all values
    source_length_sum: int = 0
    target_length_sum: int = 0
    source_word_sum: int = 0
    target_word_sum: int = 0
    source_length_count: int = 0
    target_length_count: int = 0
    source_word_count: int = 0
    target_word_count: int = 0
    source_length_min: int = float('inf')
    source_length_max: int = 0
    target_length_min: int = float('inf')
    target_length_max: int = 0
    source_word_min: int = float('inf')
    source_word_max: int = 0
    target_word_min: int = float('inf')
    target_word_max: int = 0
    duplicates_found: int = 0
    empty_pairs: int = 0

    @property
    def avg_source_length(self) -> float:
        return (
            self.source_length_sum / self.source_length_count
            if self.source_length_count
            else 0.0
        )

    @property
    def avg_target_length(self) -> float:
        return (
            self.target_length_sum / self.target_length_count
            if self.target_length_count
            else 0.0
        )

    @property
    def avg_source_words(self) -> float:
        return (
            self.source_word_sum / self.source_word_count
            if self.source_word_count
            else 0.0
        )

    @property
    def avg_target_words(self) -> float:
        return (
            self.target_word_sum / self.target_word_count
            if self.target_word_count
            else 0.0
        )

    @property
    def total_source_chars(self) -> int:
        return self.source_length_sum

    @property
    def total_target_chars(self) -> int:
        return self.target_length_sum

    @property
    def total_source_tokens(self) -> int:
        return self.source_word_sum

    @property
    def total_target_tokens(self) -> int:
        return self.target_word_sum

    def to_dict(self) -> Dict:
        lp = {}
        for (src, tgt), cnt in self.language_pairs.items():
            lp[f"{src}-{tgt}"] = cnt
        return {
            "total_units": self.total_units,
            "valid_units": self.valid_units,
            "empty_pairs": self.empty_pairs,
            "duplicates_found": self.duplicates_found,
            "language_pairs": lp,
            "source_languages": dict(self.source_languages),
            "target_languages": dict(self.target_languages),
            "source": {
                "avg_chars": self.avg_source_length,
                "avg_words": self.avg_source_words,
                "total_chars": self.total_source_chars,
                "total_words": self.total_source_tokens,
                "min_chars": int(self.source_length_min) if self.source_length_min != float('inf') else 0,
                "max_chars": self.source_length_max,
                "min_words": int(self.source_word_min) if self.source_word_min != float('inf') else 0,
                "max_words": self.source_word_max,
            },
            "target": {
                "avg_chars": self.avg_target_length,
                "avg_words": self.avg_target_words,
                "total_chars": self.total_target_chars,
                "total_words": self.total_target_tokens,
                "min_chars": int(self.target_length_min) if self.target_length_min != float('inf') else 0,
                "max_chars": self.target_length_max,
                "min_words": int(self.target_word_min) if self.target_word_min != float('inf') else 0,
                "max_words": self.target_word_max,
            },
        }


class DataAnalyzer:
    def __init__(self, use_tokenizer: bool = False):
        self._word_re = re.compile(r"\S+")
        self._tokenizer = None
        if use_tokenizer:
            try:
                import tiktoken
                self._tokenizer = tiktoken.get_encoding("cl100k_base")
            except ImportError:
                pass

    def _count_words(self, text: str) -> int:
        if not text:
            return 0
        if self._tokenizer:
            # Use tiktoken for more accurate token count
            return len(self._tokenizer.encode(text))
        return len(self._word_re.findall(text))

    def analyze(self, units: Iterable[TranslationUnit]) -> DatasetStats:
        stats = DatasetStats()
        seen: set = set()
        for unit in units:
            stats.total_units += 1
            if not unit.source_text or not unit.target_text:
                stats.empty_pairs += 1
                continue
            stats.valid_units += 1
            lang_pair = (unit.source_lang or "UNK", unit.target_lang or "UNK")
            stats.language_pairs[lang_pair] += 1
            if unit.source_lang:
                stats.source_languages[unit.source_lang] += 1
            if unit.target_lang:
                stats.target_languages[unit.target_lang] += 1
            src_len = len(unit.source_text)
            tgt_len = len(unit.target_text)
            src_words = self._count_words(unit.source_text)
            tgt_words = self._count_words(unit.target_text)

            # Update running statistics
            stats.source_length_sum += src_len
            stats.target_length_sum += tgt_len
            stats.source_word_sum += src_words
            stats.target_word_sum += tgt_words
            stats.source_length_count += 1
            stats.target_length_count += 1
            stats.source_word_count += 1
            stats.target_word_count += 1

            # Update min/max
            stats.source_length_min = min(stats.source_length_min, src_len)
            stats.source_length_max = max(stats.source_length_max, src_len)
            stats.target_length_min = min(stats.target_length_min, tgt_len)
            stats.target_length_max = max(stats.target_length_max, tgt_len)
            stats.source_word_min = min(stats.source_word_min, src_words)
            stats.source_word_max = max(stats.source_word_max, src_words)
            stats.target_word_min = min(stats.target_word_min, tgt_words)
            stats.target_word_max = max(stats.target_word_max, tgt_words)

            digest = hashlib.blake2b(digest_size=16)
            digest.update((unit.source_lang or "").encode("utf-8"))
            digest.update(b"\0")
            digest.update((unit.target_lang or "").encode("utf-8"))
            digest.update(b"\0")
            digest.update(unit.source_text.encode("utf-8"))
            digest.update(b"\0")
            digest.update(unit.target_text.encode("utf-8"))
            key = digest.digest()
            if key in seen:
                stats.duplicates_found += 1
            else:
                seen.add(key)
        return stats
