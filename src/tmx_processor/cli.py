from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import typer as _typer
    from rich.console import Console as _Console
    from rich.panel import Panel as _Panel
    from rich.progress import (
        BarColumn as _BarColumn,
        MofNCompleteColumn as _MofNCompleteColumn,
        Progress as _Progress,
        SpinnerColumn as _SpinnerColumn,
        TextColumn as _TextColumn,
        TimeElapsedColumn as _TimeElapsedColumn,
    )
    from rich.table import Table as _Table

    _HAS_RICHTYPER = True
except ImportError:  # pragma: no cover
    _typer = None
    _Console = None
    _Panel = None
    _BarColumn = None
    _MofNCompleteColumn = None
    _Progress = None
    _SpinnerColumn = None
    _TextColumn = None
    _TimeElapsedColumn = None
    _Table = None
    _HAS_RICHTYPER = False

from .analyzer import DataAnalyzer
from .cleaner import CleanConfig, DataCleaner
from .converter import ConvertOptions, DataConverter, OutputFormat, _split_sizes
from .deduper import DataDeduper
from .parser import TMXParser, TranslationUnit
from .validator import DataValidator, ValidationConfig


if not _HAS_RICHTYPER:  # pragma: no cover
    def main_fallback():
        print("=" * 60)
        print("TMX Processor CLI")
        print("=" * 60)
        print("\nЗависимостите за CLI не са инсталирани.")
        print("Инсталирайте ги с:")
        print("  pip install typer rich tqdm")
        print("\nИли използвайте API директно през Python скриптове.")
        print("Пример: examples/basic_pipeline.py")
        sys.exit(1)

    def main():
        main_fallback()

    if __name__ == "__main__":
        main()

    class _Placeholder:
        def Typer(self, *a, **kw):
            return None

        def Option(self, *a, **kw):
            return None

        def Argument(self, *a, **kw):
            return None

    app = None

else:

    app = _typer.Typer(
        add_completion=False,
        help="Платформа за обработка на TMX файлове за обучение на AI агенти",
        no_args_is_help=True,
    )
    console = _Console()

    def _progress():
        return _Progress(
            _SpinnerColumn(),
            _TextColumn("[progress.description]{task.description}"),
            _BarColumn(),
            _MofNCompleteColumn(),
            _TimeElapsedColumn(),
            console=console,
        )


    @app.command("parse")
    def parse_cmd(
        tmx_file: Path = _typer.Argument(..., exists=True, readable=True, help="Път до TMX файла"),
        output: Optional[Path] = _typer.Option(None, "-o", "--output", help="Изходен JSON файл"),
        limit: Optional[int] = _typer.Option(None, "-n", "--limit", help="Максимален брой единици"),
        show_sample: int = _typer.Option(0, "-s", "--sample", help="Покажи първите N примера"),
        expand: bool = _typer.Option(False, "--expand", help="Експлозия на мултиезични TU към всички двойки"),
        preserve_tags: bool = _typer.Option(False, "--preserve-tags", help="Запази inline тагове като placeholder-и"),
    ):
        """Парсване на TMX файл и показване на информация."""
        parser = TMXParser(tmx_file, preserve_tags=preserve_tags)
        header = parser.parse_header()

        console.print(
            _Panel.fit(
                f"[bold cyan]Файл:[/] {tmx_file.name}\n"
                f"[bold cyan]Изходен език (header):[/] {header.source_lang or 'N/A'}\n"
                f"[bold cyan]Инструмент:[/] {header.creation_tool or 'N/A'}\n"
                f"[bold cyan]Тип сегменти:[/] {header.seg_type or 'N/A'}\n"
                f"[bold cyan]Дата на създаване:[/] {header.creation_date or 'N/A'}",
                title="TMX Header",
                border_style="cyan",
            )
        )

        units: list[TranslationUnit] = []
        count = 0
        with _progress() as p:
            t = p.add_task("Парсване...", total=None)
            for unit in parser.iter_units(expand_multilingual=expand):
                units.append(unit)
                count += 1
                p.update(t, advance=1, total=count)
                if limit and count >= limit:
                    break

        console.print(f"\n[bold green]Общо извлечени TU:[/] {len(units)}")

        analyzer = DataAnalyzer()
        stats = analyzer.analyze(units)
        _print_stats_table(stats)

        if output:
            records = [u.to_dict() for u in units]
            output.parent.mkdir(parents=True, exist_ok=True)
            with open(output, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            console.print(f"[bold green]Записано в:[/] {output}")

        if show_sample > 0:
            console.print("\n[bold yellow]Примери:[/]")
            for i, u in enumerate(units[:show_sample]):
                console.print(
                    _Panel.fit(
                        f"[bold]{u.source_lang or '?'}:[/] {u.source_text[:150]}\n"
                        f"[bold]{u.target_lang or '?'}:[/] {u.target_text[:150]}",
                        title=f"TU #{i+1} (id={u.tu_id})",
                        border_style="blue",
                    )
                )


    @app.command("clean")
    def clean_cmd(
        tmx_file: Path = _typer.Argument(..., exists=True, readable=True),
        output: Path = _typer.Option(..., "-o", "--output", help="Изходен TMX/JSONL файл"),
        min_len: int = _typer.Option(1, "--min-len"),
        max_len: int = _typer.Option(10000, "--max-len"),
        min_words: int = _typer.Option(0, "--min-words"),
        max_words: int = _typer.Option(0, "--max-words"),
        max_ratio: float = _typer.Option(3.0, "--max-ratio"),
        no_html: bool = _typer.Option(True, "--remove-html/--keep-html"),
        no_urls: bool = _typer.Option(False, "--remove-urls"),
        no_emails: bool = _typer.Option(False, "--remove-emails"),
        detect_lang: bool = _typer.Option(False, "--lang-detect"),
        lang_pairs: Optional[str] = _typer.Option(None, "--lang-pairs", help="Филтър по езикови двойки, напр. EN-BG,BG-EN"),
        preserve_placeholders: bool = _typer.Option(
            False,
            "--preserve-placeholders",
            help="Запази printf/brace placeholders",
        ),
    ):
        """Почистване и нормализация на данните от TMX файл."""
        cfg = CleanConfig(
            min_length=min_len,
            max_length=max_len,
            min_words=min_words,
            max_words=max_words,
            max_length_ratio=max_ratio,
            remove_html_tags=no_html,
            remove_urls=no_urls,
            remove_emails=no_emails,
            lang_detect=detect_lang,
            language_pairs=[p.strip() for p in lang_pairs.split(",")] if lang_pairs else None,
            preserve_placeholders=preserve_placeholders,
        )
        cleaner = DataCleaner(cfg)
        parser = TMXParser(tmx_file)
        parser.parse_header()

        original_count = 0
        cleaned_units: list[TranslationUnit] = []
        with _progress() as p:
            t = p.add_task("Почистване...", total=None)
            for unit in parser.iter_units():
                original_count += 1
                cleaned = cleaner.clean_unit(unit)
                if cleaned:
                    cleaned_units.append(cleaned)
                p.update(t, advance=1, total=original_count)

        removed = original_count - len(cleaned_units)
        console.print(
            f"\n[bold]Оригинални:[/] {original_count} | "
            f"[bold green]Запазени:[/] {len(cleaned_units)} | "
            f"[bold red]Премахнати:[/] {removed} "
            f"({(removed/original_count*100) if original_count else 0:.1f}%)"
        )

        converter = DataConverter()
        suffix = output.suffix.lower()
        if suffix in (".jsonl",):
            converter.to_jsonl(cleaned_units, output)
        elif suffix in (".parquet",):
            converter.to_parquet(cleaned_units, output)
        elif suffix in (".csv",):
            converter.to_csv(cleaned_units, output)
        else:
            converter.to_jsonl(cleaned_units, output)
        console.print(f"[bold green]Записано в:[/] {output}")


    @app.command("convert")
    def convert_cmd(
        tmx_file: Path = _typer.Argument(..., exists=True, readable=True),
        output: Optional[Path] = _typer.Argument(
            None, help="Изходен път (алтернатива на -o)"
        ),
        output_opt: Optional[Path] = _typer.Option(
            None, "-o", "--output", help="Изходен път"
        ),
        fmt: OutputFormat = _typer.Option(
            OutputFormat.JSONL,
            "-f",
            "--format",
            "--fmt",
            case_sensitive=False,
        ),
        clean: bool = _typer.Option(True, "--clean/--no-clean"),
        dedupe: bool = _typer.Option(True, "--dedupe/--no-dedupe"),
        fuzzy_dedupe: bool = _typer.Option(False, "--fuzzy"),
        include_meta: bool = _typer.Option(False, "--include-metadata"),
        include_id: bool = _typer.Option(False, "--include-id"),
        instruction: Optional[str] = _typer.Option(None, "--instruction"),
        bidirectional: bool = _typer.Option(False, "--bidirectional", help="Експорт и в обратна посока"),
        preserve_placeholders: bool = _typer.Option(
            False,
            "--preserve-placeholders",
            help="Запази printf/brace placeholders и тези в HTML attributes",
        ),
        streaming: bool = _typer.Option(
            False,
            "--streaming",
            help="Парсвай/почиствай итеративно и записвай без да държиш целия корпус; изисква --no-dedupe",
        ),
        rejected_mode: str = _typer.Option(
            "truncation",
            "--rejected-mode",
            help="Режим за генериране на rejected текст за DPO: truncation, scramble, noise, copy_source, empty, repetition",
        ),
        rejected_ratio: float = _typer.Option(
            0.5,
            "--rejected-ratio",
            help="Съотношение за truncation mode (0.0-1.0)",
        ),
    ):
        """Конвертиране към формат за AI обучение (JSONL / Parquet / Alpaca / ShareGPT / HF)."""
        dest = output_opt or output
        if dest is None:
            raise _typer.BadParameter("Посочете изходен път: позиционен аргумент или -o/--output")
        if streaming and dedupe:
            raise _typer.BadParameter("--streaming изисква --no-dedupe, защото dedupe материализира корпуса")
        if streaming and fmt == OutputFormat.HF_DATASET:
            raise _typer.BadParameter("--streaming не поддържа HuggingFace splits")
        parser = TMXParser(tmx_file)
        units = parser.iter_units(stream=True) if streaming else parser.parse_all()

        if clean:
            cfg = CleanConfig(preserve_placeholders=preserve_placeholders)
            cleaner = DataCleaner(cfg)
            if streaming:
                units = cleaner.clean_iter(units)
                console.print("[cyan]Почистване:[/] streaming")
            else:
                before = len(units)
                units = cleaner.clean_units(units)
                console.print(f"[cyan]Почистване:[/] {before} -> {len(units)}")

        if dedupe:
            dd = DataDeduper(exact=True, fuzzy=fuzzy_dedupe)
            before = len(units)
            units = dd.dedupe(units)
            console.print(f"[cyan]Дедупликация:[/] {before} -> {len(units)}")

        if streaming:
            source_units = units

            def report_stream_progress():
                processed = 0
                for unit in source_units:
                    processed += 1
                    if processed % 50000 == 0:
                        console.print(f"[cyan]Streaming TU обработени:[/] {processed:,}")
                    yield unit
                console.print(f"[cyan]Streaming завърши:[/] {processed:,} TU")

            units = report_stream_progress()

        opts = ConvertOptions(
            include_metadata=include_meta,
            include_id=include_id,
            instruction_template=instruction,
            bidirectional=bidirectional,
            rejected_mode=rejected_mode,
            rejected_ratio=rejected_ratio,
        )
        converter = DataConverter(options=opts)
        out_path = converter.convert(units, dest, fmt, streaming=streaming)
        console.print(f"[bold green]Конвертирано успешно ->[/] {out_path}")


    @app.command("validate")
    def validate_cmd(
        tmx_file: Path = _typer.Argument(..., exists=True, readable=True),
        output: Optional[Path] = _typer.Option(
            None, "-o", "--output", "--report", help="JSON с репорт"
        ),
    ):
        """Валидация на TU единици и генерация на отчет за грешки."""
        parser = TMXParser(tmx_file)
        units = parser.parse_all()
        validator = DataValidator()
        report = validator.report(units)

        table = _Table(title="Валидационен отчет", show_header=True)
        table.add_column("Метрика", style="cyan")
        table.add_column("Стойност", justify="right")
        table.add_row("Общо", str(report["total"]))
        table.add_row("Валидни", f"[green]{report['valid']}[/]")
        table.add_row("Невалидни", f"[red]{report['invalid']}[/]")
        table.add_row("Процент валидни", f"{report['valid_pct']:.1f}%")
        console.print(table)

        if report["error_counts"]:
            et = _Table(title="Най-чести грешки", show_header=True)
            et.add_column("Грешка", style="red")
            et.add_column("Брой", justify="right")
            for err, cnt in sorted(
                report["error_counts"].items(), key=lambda x: -x[1]
            )[:15]:
                et.add_row(str(err), str(cnt))
            console.print(et)

        if report["warning_counts"]:
            wt = _Table(title="Предупреждения", show_header=True)
            wt.add_column("Предупреждение", style="yellow")
            wt.add_column("Брой", justify="right")
            for warn, cnt in sorted(
                report["warning_counts"].items(), key=lambda x: -x[1]
            )[:15]:
                wt.add_row(str(warn), str(cnt))
            console.print(wt)

        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            with open(output, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            console.print(f"[bold green]Отчет записан в:[/] {output}")


    @app.command("stats")
    def stats_cmd(
        tmx_file: Path = _typer.Argument(..., exists=True, readable=True),
        output: Optional[Path] = _typer.Option(None, "-o", "--output"),
        fmt: str = _typer.Option("table", "--format", help="table или json"),
    ):
        """Генерира подробна статистика за dataset-a."""
        parser = TMXParser(tmx_file)
        units = parser.parse_all()
        analyzer = DataAnalyzer()
        stats = analyzer.analyze(units)
        if fmt.lower() == "json":
            console.print_json(data=stats.to_dict())
        else:
            _print_stats_table(stats)

        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            with open(output, "w", encoding="utf-8") as f:
                json.dump(stats.to_dict(), f, ensure_ascii=False, indent=2)
            console.print(f"\n[bold green]Статистика записана в:[/] {output}")


    @app.command("pipeline")
    def pipeline_cmd(
        tmx_file: Path = _typer.Argument(..., exists=True, readable=True),
        output_dir: Path = _typer.Option(..., "-o", "--output-dir"),
        fmt: OutputFormat = _typer.Option(
            OutputFormat.JSONL, "-f", "--format", "--fmt"
        ),
        val_ratio: float = _typer.Option(0.05, "--val-ratio"),
        test_ratio: float = _typer.Option(0.05, "--test-ratio"),
        fuzzy: bool = _typer.Option(False, "--fuzzy"),
        clean: bool = _typer.Option(True, "--clean/--no-clean"),
        dedupe: bool = _typer.Option(True, "--dedupe/--no-dedupe"),
        seed: int = _typer.Option(42, "--seed"),
        stratify: bool = _typer.Option(False, "--stratify", help="Стратифициран split по езикова двойка"),
    ):
        """Пълен пайплайн: parse -> clean -> dedupe -> validate -> split + convert."""
        train_ratio = 1.0 - val_ratio - test_ratio
        _split_sizes(0, train_ratio, val_ratio, test_ratio)
        console.print(
            _Panel(
                "[bold]Пълен пайплайн за подготовка на AI training данни[/]",
                border_style="magenta",
            )
        )

        output_dir.mkdir(parents=True, exist_ok=True)

        parser = TMXParser(tmx_file)
        with _progress() as p:
            t = p.add_task("Парсване", total=None)
            units = []
            for u in parser.iter_units():
                units.append(u)
                p.update(t, advance=1, total=len(units))
        console.print(f"[cyan]1) Парсване:[/] {len(units)} единици")

        cleaner = DataCleaner()
        before = len(units)
        if clean:
            units = cleaner.clean_units(units)
            console.print(f"[cyan]2) Почистване:[/] {before} -> {len(units)}")
        else:
            console.print(f"[cyan]2) Почистване:[/] пропуснато ({len(units)})")

        dd = DataDeduper(exact=True, fuzzy=fuzzy)
        before = len(units)
        if dedupe:
            units = dd.dedupe(units)
            console.print(f"[cyan]3) Дедупликация:[/] {before} -> {len(units)}")
        else:
            console.print(f"[cyan]3) Дедупликация:[/] пропуснато ({len(units)})")

        validator = DataValidator()
        report = validator.report(units)
        console.print(
            f"[cyan]4) Валидация:[/] {report['valid']}/{report['total']} валидни "
            f"({report['valid_pct']:.1f}%)"
        )
        with open(output_dir / "validation_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        analyzer = DataAnalyzer()
        stats = analyzer.analyze(units)
        with open(output_dir / "dataset_stats.json", "w", encoding="utf-8") as f:
            json.dump(stats.to_dict(), f, ensure_ascii=False, indent=2)

        converter = DataConverter()
        if fmt == OutputFormat.HF_DATASET:
            # Use to_hf_dataset for stratified split
            converter.to_hf_dataset(
                units,
                output_dir,
                fmt=OutputFormat.JSONL,
                train_ratio=train_ratio,
                val_ratio=val_ratio,
                test_ratio=test_ratio,
                seed=seed,
                stratify_by_lang=stratify,
            )
            with open(output_dir / "metadata.json", encoding="utf-8") as f:
                split_metadata = json.load(f)
            n = split_metadata["total"]
            n_train = split_metadata["train"]
            n_val = split_metadata["validation"]
            n_test = split_metadata["test"]
            console.print(f"  [green]Splits created with stratification={stratify}[/]")
        else:
            # Manual split for other formats
            import random
            random.seed(seed)
            random.shuffle(units)
            n = len(units)
            n_train, n_val, n_test = _split_sizes(
                n, train_ratio, val_ratio, test_ratio
            )
            splits = {
                "train": units[:n_train],
                "validation": units[n_train : n_train + n_val],
                "test": units[n_train + n_val :],
            }

            for split_name, split_units in splits.items():
                if fmt == OutputFormat.JSONL:
                    out = output_dir / f"{split_name}.jsonl"
                    converter.to_jsonl(split_units, out, OutputFormat.JSONL)
                elif fmt == OutputFormat.PARQUET:
                    out = output_dir / f"{split_name}.parquet"
                    converter.to_parquet(split_units, out)
                elif fmt == OutputFormat.ALPACA:
                    out = output_dir / f"{split_name}_alpaca.jsonl"
                    converter.to_jsonl(split_units, out, OutputFormat.ALPACA)
                elif fmt == OutputFormat.SHAREGPT:
                    out = output_dir / f"{split_name}_sharegpt.jsonl"
                    converter.to_jsonl(split_units, out, OutputFormat.SHAREGPT)
                elif fmt == OutputFormat.CHATML:
                    out = output_dir / f"{split_name}_chatml.jsonl"
                    converter.to_jsonl(split_units, out, OutputFormat.CHATML)
                elif fmt == OutputFormat.OPENAI:
                    out = output_dir / f"{split_name}_openai.jsonl"
                    converter.to_jsonl(split_units, out, OutputFormat.OPENAI)
                elif fmt == OutputFormat.DPO:
                    out = output_dir / f"{split_name}_dpo.jsonl"
                    converter.to_jsonl(split_units, out, OutputFormat.DPO)
                elif fmt == OutputFormat.PROMPT_COMPLETION:
                    out = output_dir / f"{split_name}_prompt_completion.jsonl"
                    converter.to_jsonl(split_units, out, OutputFormat.PROMPT_COMPLETION)
                elif fmt == OutputFormat.REASONING:
                    out = output_dir / f"{split_name}_reasoning.jsonl"
                    converter.to_jsonl(split_units, out, OutputFormat.REASONING)
                else:
                    out = output_dir / f"{split_name}.jsonl"
                    converter.to_jsonl(split_units, out)
                console.print(
                    f"  [green]{split_name}:[/] {len(split_units)} -> {out.name}"
                )

        with open(output_dir / "metadata.json", "w", encoding="utf-8") as f:
            metadata = {
                "source_file": str(tmx_file),
                "total": n,
                "train": n_train,
                "validation": n_val,
                "test": n_test,
                "format": fmt.value,
                "seed": seed,
            }
            if fmt == OutputFormat.HF_DATASET:
                metadata.update(
                    {
                        "train_ratio": train_ratio,
                        "val_ratio": val_ratio,
                        "test_ratio": test_ratio,
                        "stratified": stratify,
                    }
                )
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        console.print(
            _Panel.fit(
                f"[bold green]Готово![/] Резултатите са в: {output_dir}",
                border_style="green",
            )
        )


    @app.command("merge")
    @app.command()
    def batch_cmd(
        pattern: str = _typer.Argument(..., help="Glob pattern за TMX файлове (напр. 'examples/*.tmx')"),
        output_dir: Path = _typer.Argument(..., help="Изходна директория"),
        fmt: OutputFormat = _typer.Option(
            OutputFormat.JSONL,
            "-f",
            "--format",
            "--fmt",
            case_sensitive=False,
        ),
        clean: bool = _typer.Option(True, "--clean/--no-clean"),
        dedupe: bool = _typer.Option(True, "--dedupe/--no-dedupe"),
        fuzzy_dedupe: bool = _typer.Option(False, "--fuzzy"),
        merge: bool = _typer.Option(False, "--merge", help="Обедини всички файлове в един"),
        instruction: Optional[str] = _typer.Option(None, "--instruction"),
        rejected_mode: str = _typer.Option(
            "truncation",
            "--rejected-mode",
            help="Режим за rejected текст (truncation, scramble, noise, copy_source, empty, repetition)",
        ),
    ):
        """Обработи множество TMX файлове наведнъж."""
        from tmx_processor import BatchProcessor, find_tmx_files, ConvertOptions
        
        tmx_files = find_tmx_files(pattern)
        if not tmx_files:
            console.print(f"[red]Няма намерени файлове по шаблона: {pattern}[/]")
            raise _typer.Exit(1)
        
        console.print(f"[cyan]Намерени {len(tmx_files)} TMX файла:[/]")
        for f in tmx_files:
            console.print(f"  - {f}")
        
        processor = BatchProcessor(clean=clean, dedupe=dedupe, fuzzy_dedupe=fuzzy_dedupe)
        opts = ConvertOptions(instruction_template=instruction, rejected_mode=rejected_mode)
        
        results = processor.process_files(tmx_files, output_dir, fmt, opts, merge=merge)
        
        console.print(f"\n[cyan]Резултати:[/]")
        for name, stats in results.items():
            console.print(f"  [green]{name}:[/] {stats['input_units']} -> {stats['output_units']}")


    def merge_cmd(
        tmx_files: List[Path] = _typer.Argument(..., exists=True, readable=True, help="TMX файлове за сливане"),
        output: Path = _typer.Option(..., "-o", "--output", help="Изходен файл за резултата"),
        dedupe: bool = _typer.Option(True, "--dedupe/--no-dedupe", help="Глобална дедупликация след сливане"),
        fuzzy: bool = _typer.Option(False, "--fuzzy", help="Fuzzy дедупликация"),
    ):
        """Сливане на няколко TMX файла с опционална глобална дедупликация."""
        console.print(
            _Panel(
                f"[bold]Сливане на {len(tmx_files)} TMX файла[/]",
                border_style="magenta",
            )
        )

        dd = DataDeduper(exact=True, fuzzy=fuzzy)
        units = dd.merge_tmx_files(tmx_files, dedupe=dedupe)

        console.print(f"[cyan]Общо единици след сливане:[/] {len(units)}")

        suffix = output.suffix.lower()
        converter = DataConverter()
        if suffix in (".jsonl",):
            converter.to_jsonl(units, output)
        elif suffix in (".parquet",):
            converter.to_parquet(units, output)
        elif suffix in (".csv",):
            converter.to_csv(units, output)
        else:
            converter.to_jsonl(units, output)

        console.print(f"[bold green]Записано в:[/] {output}")


    def _print_stats_table(stats):
        table = _Table(title="Статистика за dataset", show_header=True)
        table.add_column("Метрика", style="cyan")
        table.add_column("Изход", justify="right", style="blue")
        table.add_column("Превод", justify="right", style="magenta")
        table.add_row("Общо единици", str(stats.total_units), str(stats.total_units))
        table.add_row("Валидни единици", str(stats.valid_units), str(stats.valid_units))
        table.add_row("Празни двойки", "-", str(stats.empty_pairs))
        table.add_row("Дубликати", "-", str(stats.duplicates_found))
        table.add_row("Средна дължина (символа)", f"{stats.avg_source_length:.1f}", f"{stats.avg_target_length:.1f}")
        table.add_row("Средна дължина (думи)", f"{stats.avg_source_words:.1f}", f"{stats.avg_target_words:.1f}")
        table.add_row("Общо символи", str(stats.total_source_chars), str(stats.total_target_chars))
        table.add_row("Общо думи", str(stats.total_source_tokens), str(stats.total_target_tokens))
        console.print(table)

        if stats.language_pairs:
            lp = _Table(title="Езикови двойки", show_header=True)
            lp.add_column("Двойка", style="cyan")
            lp.add_column("Брой", justify="right")
            for (s, t), c in stats.language_pairs.most_common(10):
                lp.add_row(f"{s} -> {t}", str(c))
            console.print(lp)


    def main():
        try:
            app()
        except KeyboardInterrupt:
            console.print("\n[yellow]Прекъснато от потребителя.[/]")
            sys.exit(130)


    if __name__ == "__main__":
        main()
