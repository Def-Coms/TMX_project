from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .parser import TranslationUnit


@dataclass
class ValidationConfig:
    require_both_nonempty: bool = True
    require_languages: bool = True
    require_different_texts: bool = True
    check_noise_ratio: bool = True
    max_noise_ratio: float = 0.3
    check_alignment_chars: bool = True
    check_no_bad_placeholders: bool = True
    max_digit_mismatch_ratio: float = 1.0
    min_similar_words_ratio: float = 0.0
    max_alignment_ratio: float = 5.0


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        return ValidationResult(
            is_valid=self.is_valid and other.is_valid,
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
        )


DIGIT_RE = re.compile(r"\d+")
ALPHA_RE = re.compile(r"[^\W\d_]", re.UNICODE)
PLACEHOLDER_COUNT_RE = re.compile(r"\{(\d+)\}")
CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
LATIN_RE = re.compile(r"[a-zA-Z]")


class DataValidator:
    def __init__(self, config: Optional[ValidationConfig] = None):
        self.config = config or ValidationConfig()

    def _check_nonempty(self, unit: TranslationUnit) -> ValidationResult:
        errors: List[str] = []
        if self.config.require_both_nonempty:
            if not unit.source_text:
                errors.append("Празен изходен текст")
            if not unit.target_text:
                errors.append("Празен преведен текст")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def _check_languages(self, unit: TranslationUnit) -> ValidationResult:
        errors: List[str] = []
        if self.config.require_languages:
            if not unit.source_lang:
                errors.append("Липсва език на оригинала")
            if not unit.target_lang:
                errors.append("Липсва език на превода")
            if (
                unit.source_lang
                and unit.target_lang
                and unit.source_lang == unit.target_lang
            ):
                errors.append(
                    f"Едни и същи езици: {unit.source_lang}"
                )
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def _check_different(self, unit: TranslationUnit) -> ValidationResult:
        errors: List[str] = []
        if (
            self.config.require_different_texts
            and unit.source_text
            and unit.target_text
        ):
            if unit.source_text.strip() == unit.target_text.strip():
                errors.append("Изходният и преведеният текст са еднакви")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def _check_noise(self, unit: TranslationUnit) -> ValidationResult:
        warnings: List[str] = []
        if self.config.check_noise_ratio:
            for name, text in [
                ("source", unit.source_text),
                ("target", unit.target_text),
            ]:
                if not text:
                    continue
                alpha_chars = len(ALPHA_RE.findall(text))
                total_chars = len(text)
                if total_chars > 0:
                    noise_ratio = 1.0 - (alpha_chars / total_chars)
                    if noise_ratio > self.config.max_noise_ratio:
                        warnings.append(
                            f"Висок процент шум в {name}: {noise_ratio:.1%}"
                        )
        return ValidationResult(is_valid=True, warnings=warnings)

    @staticmethod
    def _number_mismatch_ratio(src_numbers: Sequence[str], tgt_numbers: Sequence[str]) -> float:
        if not src_numbers and not tgt_numbers:
            return 0.0
        if not src_numbers or not tgt_numbers:
            return 1.0
        src_counts = Counter(src_numbers)
        tgt_counts = Counter(tgt_numbers)
        multiplicity_mismatch = sum((src_counts - tgt_counts).values()) + sum(
            (tgt_counts - src_counts).values()
        )
        total = len(src_numbers) + len(tgt_numbers)
        ratio = multiplicity_mismatch / total if total else 0.0
        if multiplicity_mismatch == 0 and list(src_numbers) != list(tgt_numbers):
            length = max(len(src_numbers), len(tgt_numbers))
            hamming = sum(
                1
                for left, right in zip(src_numbers, tgt_numbers)
                if left != right
            ) + abs(len(src_numbers) - len(tgt_numbers))
            ratio = max(ratio, hamming / length)
        return ratio

    def _check_digits(self, unit: TranslationUnit) -> ValidationResult:
        errors: List[str] = []
        if self.config.max_digit_mismatch_ratio >= 0:
            src_numbers = DIGIT_RE.findall(unit.source_text or "")
            tgt_numbers = DIGIT_RE.findall(unit.target_text or "")
            if src_numbers or tgt_numbers:
                ratio = self._number_mismatch_ratio(src_numbers, tgt_numbers)
                if ratio > self.config.max_digit_mismatch_ratio:
                    errors.append(
                        f"Несъвпадение на числа: {ratio:.1%} "
                        f"(src={list(src_numbers)[:5]}, tgt={list(tgt_numbers)[:5]})"
                    )
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def _check_placeholders(self, unit: TranslationUnit) -> ValidationResult:
        warnings: List[str] = []
        if self.config.check_no_bad_placeholders:
            src_ph = set(PLACEHOLDER_COUNT_RE.findall(unit.source_text or ""))
            tgt_ph = set(PLACEHOLDER_COUNT_RE.findall(unit.target_text or ""))
            missing = src_ph - tgt_ph
            extra = tgt_ph - src_ph
            if missing:
                warnings.append(
                    f"Липсващи placeholder-и в превод: {sorted(missing)}"
                )
            if extra:
                warnings.append(
                    f"Лишни placeholder-и в превод: {sorted(extra)}"
                )
        return ValidationResult(is_valid=True, warnings=warnings)

    def _check_alignment_chars(self, unit: TranslationUnit) -> ValidationResult:
        warnings: List[str] = []
        if not self.config.check_alignment_chars:
            return ValidationResult(is_valid=True)
        src = unit.source_text or ""
        tgt = unit.target_text or ""
        if src and tgt:
            ratio = max(len(src), len(tgt)) / max(min(len(src), len(tgt)), 1)
            if ratio > self.config.max_alignment_ratio:
                warnings.append(
                    f"Силно разминаване в дължина (ratio={ratio:.1f})"
                )
        return ValidationResult(is_valid=True, warnings=warnings)

    def _check_script_mismatch(self, unit: TranslationUnit) -> ValidationResult:
        warnings: List[str] = []
        tgt_lang = (unit.target_lang or "").lower()[:2]
        tgt_text = unit.target_text or ""
        if tgt_lang in ("bg", "ru", "mk", "uk", "sr") and tgt_text:
            cyr_count = len(CYRILLIC_RE.findall(tgt_text))
            lat_count = len(LATIN_RE.findall(tgt_text))
            if lat_count > cyr_count and lat_count > 3:
                warnings.append(
                    f"Преводът за кирилски език '{tgt_lang}' съдържа предимно латиница: cyr={cyr_count}, lat={lat_count}"
                )
        return ValidationResult(is_valid=True, warnings=warnings)

    def _check_similar_words(self, unit: TranslationUnit) -> ValidationResult:
        if self.config.min_similar_words_ratio <= 0:
            return ValidationResult(is_valid=True)
        src = set((unit.source_text or "").lower().split())
        tgt = set((unit.target_text or "").lower().split())
        if not src or not tgt:
            return ValidationResult(is_valid=True)
        overlap = len(src & tgt) / max(len(src), 1)
        if overlap < self.config.min_similar_words_ratio:
            return ValidationResult(
                is_valid=True,
                warnings=[
                    f"Малко общи думи между source/target: {overlap:.1%}"
                ],
            )
        return ValidationResult(is_valid=True)

    def validate(self, unit: TranslationUnit) -> ValidationResult:
        result = ValidationResult(is_valid=True)
        result = result.merge(self._check_nonempty(unit))
        result = result.merge(self._check_languages(unit))
        result = result.merge(self._check_different(unit))
        result = result.merge(self._check_noise(unit))
        result = result.merge(self._check_digits(unit))
        result = result.merge(self._check_placeholders(unit))
        result = result.merge(self._check_alignment_chars(unit))
        result = result.merge(self._check_similar_words(unit))
        result = result.merge(self._check_script_mismatch(unit))
        return result

    def filter_valid(
        self, units: List[TranslationUnit], include_warnings: bool = True
    ) -> List[TranslationUnit]:
        results: List[TranslationUnit] = []
        for unit in units:
            vr = self.validate(unit)
            if not vr.is_valid:
                continue
            if not include_warnings and vr.warnings:
                continue
            results.append(unit)
        return results

    def report(
        self, units: List[TranslationUnit]
    ) -> Dict[str, object]:
        total = len(units)
        valid = 0
        error_counts: Dict[str, int] = {}
        warning_counts: Dict[str, int] = {}
        for unit in units:
            vr = self.validate(unit)
            if vr.is_valid:
                valid += 1
            for err in vr.errors:
                error_counts[err] = error_counts.get(err, 0) + 1
            for warn in vr.warnings:
                warning_counts[warn] = warning_counts.get(warn, 0) + 1
        return {
            "total": total,
            "valid": valid,
            "invalid": total - valid,
            "valid_pct": (valid / total * 100) if total else 0.0,
            "error_counts": error_counts,
            "warning_counts": warning_counts,
        }
