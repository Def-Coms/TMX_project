from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple, Union

from .parser import TranslationUnit, TMXParser

_WHITESPACE_RE = re.compile(r"\s+")


class DataDeduper:
    def __init__(
        self,
        exact: bool = True,
        fuzzy: bool = False,
        fuzzy_threshold: float = 0.9,
        case_sensitive: bool = True,
        normalize_before: bool = True,
    ):
        self.exact = exact
        self.fuzzy = fuzzy
        self.fuzzy_threshold = fuzzy_threshold
        self.case_sensitive = case_sensitive
        self.normalize_before = normalize_before
        self._seen_exact: Set[Tuple[str, str, str, str]] = set()

    def _normalize(self, text: str) -> str:
        result = text
        if self.normalize_before:
            result = _WHITESPACE_RE.sub(" ", result).strip()
        if not self.case_sensitive:
            result = result.lower()
        return result

    def _hash_pair(
        self, src: str, tgt: str, src_lang: str, tgt_lang: str
    ) -> Tuple[str, str, str, str]:
        n_src = self._normalize(src)
        n_tgt = self._normalize(tgt)
        return (src_lang or "", tgt_lang or "", n_src, n_tgt)

    def is_duplicate(self, unit: TranslationUnit) -> bool:
        if not self.exact:
            return False
        key = self._hash_pair(
            unit.source_text,
            unit.target_text,
            unit.source_lang or "",
            unit.target_lang or "",
        )
        if key in self._seen_exact:
            return True
        self._seen_exact.add(key)
        return False

    def dedupe_exact(
        self, units: Iterable[TranslationUnit]
    ) -> List[TranslationUnit]:
        self._seen_exact.clear()
        results: List[TranslationUnit] = []
        for unit in units:
            if self.is_duplicate(unit):
                continue
            results.append(unit)
        return results

    @staticmethod
    def _ngrams(text: str, ngram: int = 3) -> Set[str]:
        if len(text) < ngram:
            return {text} if text else set()
        return {text[i : i + ngram] for i in range(len(text) - ngram + 1)}

    @staticmethod
    def _jaccard(left: Set[str], right: Set[str]) -> float:
        if not left and not right:
            return 1.0
        union = left | right
        if not union:
            return 1.0
        return len(left & right) / len(union)

    def _side_tokens(self, unit: TranslationUnit, side: str) -> Set[str]:
        if side == "source":
            text = f"{unit.source_lang or ''}||{self._normalize(unit.source_text)}"
        else:
            text = f"{unit.target_lang or ''}||{self._normalize(unit.target_text)}"
        return self._ngrams(text)

    def _is_fuzzy_duplicate(
        self,
        left: TranslationUnit,
        right: TranslationUnit,
        threshold: float,
        source_tokens: List[Set[str]],
        target_tokens: List[Set[str]],
        left_idx: int,
        right_idx: int,
    ) -> bool:
        source_score = self._jaccard(source_tokens[left_idx], source_tokens[right_idx])
        target_score = self._jaccard(target_tokens[left_idx], target_tokens[right_idx])
        return source_score >= threshold and target_score >= threshold

    def dedupe_fuzzy(
        self,
        units: List[TranslationUnit],
        threshold: Optional[float] = None,
    ) -> List[TranslationUnit]:
        threshold = threshold or self.fuzzy_threshold
        try:
            from datasketch import MinHash, MinHashLSH
        except ImportError:
            if self.exact:
                return list(units)
            return self.dedupe_exact(units)

        n = len(units)
        if n == 0:
            return []

        perm = 128
        lsh = MinHashLSH(threshold=threshold, num_perm=perm)
        source_tokens = [self._side_tokens(unit, "source") for unit in units]
        target_tokens = [self._side_tokens(unit, "target") for unit in units]
        hashes: List[MinHash] = []
        for idx, tokens in enumerate(source_tokens):
            mh = MinHash(num_perm=perm)
            for token in tokens or {""}:
                mh.update(token.encode("utf-8"))
            hashes.append(mh)
            lsh.insert(f"u{idx}", mh)

        removed_idx: Set[int] = set()
        results: List[TranslationUnit] = []
        for idx in range(n):
            if idx in removed_idx:
                continue
            unit = units[idx]
            duplicates = lsh.query(hashes[idx])
            for dup in duplicates:
                dup_idx = int(dup[1:])
                if dup_idx == idx or dup_idx in removed_idx:
                    continue
                if self._is_fuzzy_duplicate(
                    unit,
                    units[dup_idx],
                    threshold,
                    source_tokens,
                    target_tokens,
                    idx,
                    dup_idx,
                ):
                    removed_idx.add(dup_idx)
            results.append(unit)
        return results

    def dedupe(
        self, units: List[TranslationUnit]
    ) -> List[TranslationUnit]:
        result = list(units)
        if self.exact:
            result = self.dedupe_exact(result)
        if self.fuzzy:
            result = self.dedupe_fuzzy(result)
        return result

    def reset(self):
        self._seen_exact.clear()

    def merge_tmx_files(
        self,
        tmx_files: List[Union[str, Path]],
        dedupe: bool = True,
    ) -> List[TranslationUnit]:
        """Parse multiple TMX files and merge them with optional global deduplication."""
        all_units: List[TranslationUnit] = []
        for tmx_file in tmx_files:
            parser = TMXParser(tmx_file)
            units = parser.parse_all()
            all_units.extend(units)

        if dedupe:
            all_units = self.dedupe(all_units)

        return all_units
