from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Union

DEFAULT_SPLIT_SEED = 42


def _split_sizes(
    total: int,
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
) -> tuple[int, int, int]:
    ratios = (train_ratio, val_ratio, test_ratio)
    if (
        total < 0
        or any(not math.isfinite(ratio) or ratio < 0 for ratio in ratios)
        or not math.isclose(sum(ratios), 1.0, rel_tol=0.0, abs_tol=1e-9)
    ):
        raise ValueError("Split ratios трябва да са крайни, неотрицателни и със сбор 1.")

    exact_sizes = [total * ratio for ratio in ratios]
    sizes = [int(size) for size in exact_sizes]
    remainder = total - sum(sizes)
    order = sorted(
        range(len(sizes)),
        key=lambda index: exact_sizes[index] - sizes[index],
        reverse=True,
    )
    for index in order[:remainder]:
        sizes[index] += 1
    return sizes[0], sizes[1], sizes[2]

try:
    import jsonlines as _jsonlines

    _HAS_JSONLINES = True
except ImportError:
    _jsonlines = None
    _HAS_JSONLINES = False

try:
    import pandas as _pd

    _HAS_PANDAS = True
except ImportError:
    _pd = None
    _HAS_PANDAS = False

from .parser import TranslationUnit


class OutputFormat(str, Enum):
    JSONL = "jsonl"
    PARQUET = "parquet"
    CSV = "csv"
    TSV = "tsv"
    JSON = "json"
    HF_DATASET = "hf_dataset"
    ALPACA = "alpaca"
    SHAREGPT = "sharegpt"
    CHATML = "chatml"
    OPENAI = "openai"
    DPO = "dpo"
    PROMPT_COMPLETION = "prompt_completion"
    REASONING = "reasoning"


import random


class RejectedGenerator:
    """Generate rejected responses for DPO/ORPO preference pairs."""
    
    @staticmethod
    def generate_truncated(text: str, ratio: float = 0.5) -> str:
        """Truncate text to specified ratio."""
        if not text:
            return text
        cutoff = int(len(text) * ratio)
        return text[:cutoff]
    
    @staticmethod
    def generate_scrambled(text: str) -> str:
        """Scramble words in the text."""
        if not text:
            return text
        words = text.split()
        random.shuffle(words)
        return " ".join(words)
    
    @staticmethod
    def generate_noisy(text: str, noise_ratio: float = 0.1) -> str:
        """Inject random noise characters."""
        if not text:
            return text
        chars = list(text)
        num_noise = int(len(chars) * noise_ratio)
        for _ in range(num_noise):
            idx = random.randint(0, len(chars) - 1)
            chars[idx] = chr(random.randint(33, 126))
        return "".join(chars)
    
    @staticmethod
    def generate_copy_source(source_text: str) -> str:
        """Copy source text as rejected (no translation)."""
        return source_text
    
    @staticmethod
    def generate_empty() -> str:
        """Return empty string as rejected."""
        return ""
    
    @staticmethod
    def generate_repetition(text: str, repeat_ratio: float = 0.3) -> str:
        """Repeat random words in the text."""
        if not text:
            return text
        words = text.split()
        if len(words) < 2:
            return text
        num_repeat = int(len(words) * repeat_ratio)
        for _ in range(num_repeat):
            idx = random.randint(0, len(words) - 1)
            repeat_word = words[idx]
            insert_pos = random.randint(0, len(words))
            words.insert(insert_pos, repeat_word)
        return " ".join(words)


@dataclass
class ConvertOptions:
    include_metadata: bool = False
    include_id: bool = False
    source_key: str = "source"
    target_key: str = "target"
    lang_key: bool = True
    source_lang_key: str = "source_lang"
    target_lang_key: str = "target_lang"
    instruction_template: Optional[str] = None
    input_template: Optional[str] = None
    output_template: Optional[str] = None
    bidirectional: bool = False  # Export both EN→BG and BG→EN
    rejected_mode: str = "truncation"  # truncation, scramble, noise, copy_source, empty, repetition
    rejected_ratio: float = 0.5  # For truncation mode
    rejected_file: Optional[Path] = None  # For external rejected data


class DataConverter:
    def __init__(self, options: Optional[ConvertOptions] = None):
        self.options = options or ConvertOptions()

    def _unit_to_dict(self, unit: TranslationUnit) -> dict:
        opts = self.options
        record: dict = {}
        if opts.include_id and unit.tu_id:
            record["id"] = unit.tu_id
        if opts.lang_key:
            if unit.source_lang:
                record[opts.source_lang_key] = unit.source_lang
            if unit.target_lang:
                record[opts.target_lang_key] = unit.target_lang
        record[opts.source_key] = unit.source_text
        record[opts.target_key] = unit.target_text
        if opts.include_metadata and unit.metadata:
            record["metadata"] = dict(unit.metadata)
        return record

    def _to_alpaca(self, unit: TranslationUnit) -> dict:
        opts = self.options
        src_lang = unit.source_lang or "source"
        tgt_lang = unit.target_lang or "target"
        default = "Translate the following text from {src} to {tgt}."
        instruction = self._render_template(
            opts.instruction_template or default, src_lang, tgt_lang
        )
        input_text = opts.input_template or unit.source_text
        output_text = opts.output_template or unit.target_text
        return {
            "instruction": instruction,
            "input": input_text,
            "output": output_text,
        }

    def _to_sharegpt(self, unit: TranslationUnit) -> dict:
        opts = self.options
        src_lang = unit.source_lang or "source"
        tgt_lang = unit.target_lang or "target"
        default = (
            "You are a professional translator. "
            "Translate text from {src} to {tgt}."
        )
        system_msg = self._render_template(
            opts.instruction_template or default, src_lang, tgt_lang
        )
        return {
            "conversations": [
                {"from": "system", "value": system_msg},
                {"from": "human", "value": unit.source_text},
                {"from": "gpt", "value": unit.target_text},
            ]
        }

    def _to_chatml(self, unit: TranslationUnit) -> dict:
        opts = self.options
        src_lang = unit.source_lang or "source"
        tgt_lang = unit.target_lang or "target"
        default = "Translate the following text from {src} to {tgt}."
        system_msg = self._render_template(
            opts.instruction_template or default, src_lang, tgt_lang
        )
        return {
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": unit.source_text},
                {"role": "assistant", "content": unit.target_text},
            ]
        }

    def _to_openai(self, unit: TranslationUnit) -> dict:
        opts = self.options
        src_lang = unit.source_lang or "source"
        tgt_lang = unit.target_lang or "target"
        default = "Translate the following text from {src} to {tgt}."
        system_msg = self._render_template(
            opts.instruction_template or default, src_lang, tgt_lang
        )
        return {
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": unit.source_text},
                {"role": "assistant", "content": unit.target_text},
            ]
        }

    def _to_dpo(self, unit: TranslationUnit) -> dict:
        """DPO/ORPO preference format: prompt, chosen, rejected.
        For translation, we use source as prompt and target as chosen.
        Rejected text is generated based on rejected_mode."""
        opts = self.options
        src_lang = unit.source_lang or "source"
        tgt_lang = unit.target_lang or "target"
        default = "Translate the following text from {src} to {tgt}."
        instruction = self._render_template(
            opts.instruction_template or default, src_lang, tgt_lang
        )
        
        # Generate rejected text based on mode
        generator = RejectedGenerator()
        if opts.rejected_mode == "truncation":
            rejected = generator.generate_truncated(unit.target_text, opts.rejected_ratio)
        elif opts.rejected_mode == "scramble":
            rejected = generator.generate_scrambled(unit.target_text)
        elif opts.rejected_mode == "noise":
            rejected = generator.generate_noisy(unit.target_text)
        elif opts.rejected_mode == "copy_source":
            rejected = generator.generate_copy_source(unit.source_text)
        elif opts.rejected_mode == "empty":
            rejected = generator.generate_empty()
        elif opts.rejected_mode == "repetition":
            rejected = generator.generate_repetition(unit.target_text)
        else:
            # Fallback to truncation
            rejected = generator.generate_truncated(unit.target_text, opts.rejected_ratio)
        
        return {
            "prompt": instruction + "\n" + unit.source_text,
            "chosen": unit.target_text,
            "rejected": rejected,
        }

    def _to_prompt_completion(self, unit: TranslationUnit) -> dict:
        """Generic prompt/completion format for simple instruction tuning."""
        opts = self.options
        src_lang = unit.source_lang or "source"
        tgt_lang = unit.target_lang or "target"
        default = "Translate from {src} to {tgt}:"
        prompt = self._render_template(
            opts.instruction_template or default, src_lang, tgt_lang
        )
        return {
            "prompt": prompt + " " + unit.source_text,
            "completion": unit.target_text,
        }

    def _to_reasoning(self, unit: TranslationUnit) -> dict:
        """Reasoning format with chain-of-thought support.
        For translation, we add a simple reasoning step."""
        opts = self.options
        src_lang = unit.source_lang or "source"
        tgt_lang = unit.target_lang or "target"
        default = "Translate the following text from {src} to {tgt}. Show your reasoning."
        system_msg = self._render_template(
            opts.instruction_template or default, src_lang, tgt_lang
        )
        # Simple reasoning heuristic for translation
        reasoning = f"Source text in {src_lang}: '{unit.source_text}'. Context: formal translation task."
        return {
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": unit.source_text},
                {"role": "assistant", "content": reasoning + "\n\nTranslation: " + unit.target_text},
            ]
        }

    def _render_template(self, template: str, src_lang: str, tgt_lang: str) -> str:
        try:
            return template.format(
                src=src_lang,
                tgt=tgt_lang,
                source_lang=src_lang,
                target_lang=tgt_lang,
            )
        except (KeyError, IndexError, ValueError):
            return template

    def _format_record(
        self, unit: TranslationUnit, fmt: OutputFormat
    ) -> dict:
        if fmt == OutputFormat.ALPACA:
            return self._to_alpaca(unit)
        if fmt == OutputFormat.SHAREGPT:
            return self._to_sharegpt(unit)
        if fmt == OutputFormat.CHATML:
            return self._to_chatml(unit)
        if fmt == OutputFormat.OPENAI:
            return self._to_openai(unit)
        if fmt == OutputFormat.DPO:
            return self._to_dpo(unit)
        if fmt == OutputFormat.PROMPT_COMPLETION:
            return self._to_prompt_completion(unit)
        if fmt == OutputFormat.REASONING:
            return self._to_reasoning(unit)
        return self._unit_to_dict(unit)

    def _reverse_unit(self, unit: TranslationUnit) -> TranslationUnit:
        """Create a reversed copy of the unit (swap source and target)."""
        return TranslationUnit(
            tu_id=unit.tu_id,
            source_lang=unit.target_lang,
            target_lang=unit.source_lang,
            source_text=unit.target_text,
            target_text=unit.source_text,
            metadata=dict(unit.metadata),
            notes=list(unit.notes),
        )

    def convert_iter(
        self, units: Iterable[TranslationUnit], fmt: OutputFormat
    ) -> Iterator[dict]:
        for unit in units:
            yield self._format_record(unit, fmt)
            if self.options.bidirectional:
                reversed_unit = self._reverse_unit(unit)
                yield self._format_record(reversed_unit, fmt)

    def _write_jsonl(self, records: list, output_path: Path) -> None:
        if _HAS_JSONLINES:
            with _jsonlines.open(str(output_path), mode="w") as writer:
                writer.write_all(records)
        else:
            with open(output_path, "w", encoding="utf-8") as f:
                for rec in records:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _write_jsonl_streaming(self, records_iter: Iterator[dict], output_path: Path) -> None:
        """Write JSONL without loading all records into memory."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if _HAS_JSONLINES:
            with _jsonlines.open(str(output_path), mode="w") as writer:
                for rec in records_iter:
                    writer.write(rec)
        else:
            with open(output_path, "w", encoding="utf-8") as f:
                for rec in records_iter:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def to_jsonl(
        self,
        units: Iterable[TranslationUnit],
        output_path: Union[str, Path],
        fmt: OutputFormat = OutputFormat.JSONL,
        streaming: bool = False,
    ) -> Path:
        output_path = Path(output_path)
        if streaming:
            self._write_jsonl_streaming(self.convert_iter(units, fmt), output_path)
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            records = list(self.convert_iter(units, fmt))
            self._write_jsonl(records, output_path)
        return output_path

    def to_json(
        self,
        units: Iterable[TranslationUnit],
        output_path: Union[str, Path],
        fmt: OutputFormat = OutputFormat.JSON,
        streaming: bool = False,
    ) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if streaming:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("[\n")
                first = True
                for rec in self.convert_iter(units, fmt):
                    if not first:
                        f.write(",\n")
                    json.dump(rec, f, ensure_ascii=False)
                    first = False
                f.write("\n]\n")
            return output_path
        records = list(self.convert_iter(units, fmt))
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        return output_path

    def to_csv(
        self,
        units: Iterable[TranslationUnit],
        output_path: Union[str, Path],
        delimiter: str = ",",
        streaming: bool = False,
    ) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        records_iter = self.convert_iter(units, OutputFormat.JSONL)
        if streaming:
            try:
                first = next(records_iter)
            except StopIteration:
                with open(output_path, "w", encoding="utf-8", newline="") as f:
                    pass
                return output_path
            fieldnames = list(first.keys())
            with open(output_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=fieldnames, delimiter=delimiter
                )
                writer.writeheader()
                writer.writerow(first)
                for record in records_iter:
                    writer.writerow(record)
            return output_path
        records = list(records_iter)
        if not records:
            with open(output_path, "w", encoding="utf-8", newline="") as f:
                pass
            return output_path
        fieldnames = list(records[0].keys())
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=fieldnames, delimiter=delimiter
            )
            writer.writeheader()
            for record in records:
                writer.writerow(record)
        return output_path

    def to_tsv(
        self,
        units: Iterable[TranslationUnit],
        output_path: Union[str, Path],
        streaming: bool = False,
    ) -> Path:
        return self.to_csv(
            units, output_path, delimiter="\t", streaming=streaming
        )

    def to_parquet(
        self,
        units: Iterable[TranslationUnit],
        output_path: Union[str, Path],
        streaming: bool = False,
        batch_size: int = 4096,
    ) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if streaming:
            try:
                import pyarrow as pa
                import pyarrow.parquet as pq
            except ImportError:
                records = list(self.convert_iter(units, OutputFormat.JSONL))
                fallback = output_path.with_suffix(".jsonl")
                self._write_jsonl(records, fallback)
                raise RuntimeError(
                    "pandas/pyarrow не са инсталирани. "
                    f"Записах JSONL fallback във {fallback}. "
                    "Инсталирайте с: pip install pandas pyarrow"
                )
            writer = None
            batch: List[dict] = []
            try:
                for rec in self.convert_iter(units, OutputFormat.JSONL):
                    batch.append(rec)
                    if len(batch) >= batch_size:
                        table = pa.Table.from_pylist(batch)
                        if writer is None:
                            writer = pq.ParquetWriter(str(output_path), table.schema)
                        writer.write_table(table)
                        batch.clear()
                if batch:
                    table = pa.Table.from_pylist(batch)
                    if writer is None:
                        writer = pq.ParquetWriter(str(output_path), table.schema)
                    writer.write_table(table)
                if writer is None:
                    if _HAS_PANDAS:
                        _pd.DataFrame([]).to_parquet(output_path, index=False)
                    else:
                        output_path.write_bytes(b"")
            finally:
                if writer is not None:
                    writer.close()
            return output_path
        records = list(self.convert_iter(units, OutputFormat.JSONL))
        if _HAS_PANDAS:
            df = _pd.DataFrame(records)
            df.to_parquet(output_path, index=False)
        else:
            fallback = output_path.with_suffix(".jsonl")
            self._write_jsonl(records, fallback)
            raise RuntimeError(
                "pandas/pyarrow не са инсталирани. "
                f"Записах JSONL fallback във {fallback}. "
                "Инсталирайте с: pip install pandas pyarrow"
            )
        return output_path

    def to_hf_dataset(
        self,
        units: Iterable[TranslationUnit],
        output_path: Union[str, Path],
        fmt: OutputFormat = OutputFormat.JSONL,
        train_ratio: float = 0.9,
        val_ratio: float = 0.05,
        test_ratio: float = 0.05,
        seed: int = DEFAULT_SPLIT_SEED,
        stratify_by_lang: bool = False,
    ) -> Path:
        import random

        _split_sizes(0, train_ratio, val_ratio, test_ratio)
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)
        records = list(self.convert_iter(units, fmt))
        rng = random.Random(seed)

        if stratify_by_lang:
            # Stratified split by language pair
            from collections import defaultdict

            by_lang_pair: dict = defaultdict(list)
            for rec in records:
                src_lang = rec.get("source_lang", "unknown")
                tgt_lang = rec.get("target_lang", "unknown")
                pair = f"{src_lang}-{tgt_lang}"
                by_lang_pair[pair].append(rec)

            splits = {"train": [], "validation": [], "test": []}
            for pair, pair_records in by_lang_pair.items():
                rng.shuffle(pair_records)
                n = len(pair_records)
                n_train, n_val, _n_test = _split_sizes(
                    n, train_ratio, val_ratio, test_ratio
                )
                splits["train"].extend(pair_records[:n_train])
                splits["validation"].extend(pair_records[n_train : n_train + n_val])
                splits["test"].extend(pair_records[n_train + n_val :])
        else:
            rng.shuffle(records)
            n = len(records)
            n_train, n_val, _n_test = _split_sizes(
                n, train_ratio, val_ratio, test_ratio
            )
            splits = {
                "train": records[:n_train],
                "validation": records[n_train : n_train + n_val],
                "test": records[n_train + n_val :],
            }

        for split_name, split_data in splits.items():
            split_path = output_path / f"{split_name}.jsonl"
            self._write_jsonl(split_data, split_path)
        meta = {
            "total": len(records),
            "train": len(splits["train"]),
            "validation": len(splits["validation"]),
            "test": len(splits["test"]),
            "format": fmt.value,
            "seed": seed,
            "train_ratio": train_ratio,
            "val_ratio": val_ratio,
            "test_ratio": test_ratio,
            "stratified": stratify_by_lang,
        }
        with open(output_path / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        return output_path

    def convert(
        self,
        units: Iterable[TranslationUnit],
        output_path: Union[str, Path],
        fmt: Union[OutputFormat, str] = OutputFormat.JSONL,
        *,
        train_ratio: float = 0.9,
        val_ratio: float = 0.05,
        test_ratio: float = 0.05,
        seed: int = DEFAULT_SPLIT_SEED,
        instruction_tmpl: Optional[str] = None,
        stratify_by_lang: bool = False,
        streaming: bool = False,
    ) -> Path:
        if instruction_tmpl:
            self.options.instruction_template = instruction_tmpl
        if isinstance(fmt, str):
            fmt = OutputFormat(fmt.lower())
        jsonl_like = (
            OutputFormat.JSONL,
            OutputFormat.ALPACA,
            OutputFormat.SHAREGPT,
            OutputFormat.CHATML,
            OutputFormat.OPENAI,
            OutputFormat.DPO,
            OutputFormat.PROMPT_COMPLETION,
            OutputFormat.REASONING,
        )
        if streaming and fmt not in jsonl_like:
            raise ValueError("Streaming output is only supported for JSONL-based formats.")
        if fmt in jsonl_like:
            return self.to_jsonl(units, output_path, fmt, streaming=streaming)
        if fmt == OutputFormat.JSON:
            return self.to_json(units, output_path, fmt, streaming=streaming)
        if fmt == OutputFormat.CSV:
            return self.to_csv(units, output_path, streaming=streaming)
        if fmt == OutputFormat.TSV:
            return self.to_tsv(units, output_path, streaming=streaming)
        if fmt == OutputFormat.PARQUET:
            return self.to_parquet(units, output_path, streaming=streaming)
        if streaming:
            raise ValueError("Streaming output is not supported for HuggingFace dataset splits.")
        if fmt == OutputFormat.HF_DATASET:
            return self.to_hf_dataset(
                units,
                output_path,
                train_ratio=train_ratio,
                val_ratio=val_ratio,
                test_ratio=test_ratio,
                seed=seed,
                stratify_by_lang=stratify_by_lang,
            )
        raise ValueError(f"Неподдържан формат: {fmt}")
