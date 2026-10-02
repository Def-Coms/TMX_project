from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tmx_processor import (
    TMXParser,
    DataCleaner,
    CleanConfig,
    DataConverter,
    OutputFormat,
    DataValidator,
    DataDeduper,
    DataAnalyzer,
)

EXAMPLES_DIR = Path(__file__).parent
TMX_FILE = EXAMPLES_DIR / "sample_en_bg.tmx"
OUTPUT_DIR = EXAMPLES_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def step_1_parse():
    print("=" * 60)
    print("СТЪПКА 1: Парсване на TMX файла")
    print("=" * 60)
    parser = TMXParser(TMX_FILE)
    header = parser.parse_header()
    print(f"Файл: {TMX_FILE}")
    print(f"Изходен език: {header.source_lang}")
    print(f"Инструмент: {header.creation_tool}")
    units = parser.parse_all()
    print(f"Общо TU единици: {len(units)}")
    for u in units[:3]:
        print(f"  [{u.source_lang}] {u.source_text[:60]}")
        print(f"  [{u.target_lang}] {u.target_text[:60]}")
        print()
    return units


def step_2_clean(units):
    print("\n" + "=" * 60)
    print("СТЪПКА 2: Почистване и нормализация")
    print("=" * 60)
    cfg = CleanConfig(
        min_length=2,
        max_length_ratio=4.0,
        remove_html_tags=True,
    )
    cleaner = DataCleaner(cfg)
    cleaned = cleaner.clean_units(units)
    print(f"Преди почистване: {len(units)}")
    print(f"След почистване: {len(cleaned)}")
    print(f"Премахнати: {len(units) - len(cleaned)}")
    return cleaned


def step_3_validate(units):
    print("\n" + "=" * 60)
    print("СТЪПКА 3: Валидация")
    print("=" * 60)
    validator = DataValidator()
    report = validator.report(units)
    print(f"Общо: {report['total']}")
    print(f"Валидни: {report['valid']} ({report['valid_pct']:.1f}%)")
    if report["error_counts"]:
        print("\nГрешки:")
        for err, cnt in report["error_counts"].items():
            print(f"  - {err}: {cnt}")
    return validator.filter_valid(units)


def step_4_dedupe(units):
    print("\n" + "=" * 60)
    print("СТЪПКА 4: Дедупликация")
    print("=" * 60)
    dd = DataDeduper(exact=True, fuzzy=False)
    before = len(units)
    deduped = dd.dedupe_exact(units)
    print(f"Преди: {before}")
    print(f"След: {len(deduped)}")
    print(f"Премахнати дубликати: {before - len(deduped)}")
    return deduped


def step_5_analyze(units):
    print("\n" + "=" * 60)
    print("СТЪПКА 5: Анализ и статистика")
    print("=" * 60)
    analyzer = DataAnalyzer()
    stats = analyzer.analyze(units)
    print(f"Общо единици: {stats.total_units}")
    print(f"Валидни: {stats.valid_units}")
    print(f"Дубликати (по ключ): {stats.duplicates_found}")
    print(f"\nИзходен текст:")
    print(f"  Средна дължина: {stats.avg_source_length:.1f} знака")
    print(f"  Средно думи: {stats.avg_source_words:.1f}")
    print(f"  Общо знаци: {stats.total_source_chars}")
    print(f"\nПревод:")
    print(f"  Средна дължина: {stats.avg_target_length:.1f} знака")
    print(f"  Средно думи: {stats.avg_target_words:.1f}")
    print(f"  Общо знаци: {stats.total_target_chars}")
    print(f"\nЕзикови двойки:")
    for (s, t), c in stats.language_pairs.most_common():
        print(f"  {s} -> {t}: {c}")
    return stats


def step_6_convert(units):
    print("\n" + "=" * 60)
    print("СТЪПКА 6: Конвертиране към AI формати")
    print("=" * 60)
    converter = DataConverter()

    out_jsonl = converter.convert(units, OUTPUT_DIR / "dataset.jsonl", OutputFormat.JSONL)
    print(f"JSONL: {out_jsonl}")

    out_parquet = converter.convert(units, OUTPUT_DIR / "dataset.parquet", OutputFormat.PARQUET)
    print(f"Parquet: {out_parquet}")

    out_alpaca = converter.convert(units, OUTPUT_DIR / "dataset_alpaca.jsonl", OutputFormat.ALPACA)
    print(f"Alpaca format: {out_alpaca}")

    out_sharegpt = converter.convert(units, OUTPUT_DIR / "dataset_sharegpt.jsonl", OutputFormat.SHAREGPT)
    print(f"ShareGPT format: {out_sharegpt}")

    out_hf = converter.convert(units, OUTPUT_DIR / "hf_dataset", OutputFormat.HF_DATASET)
    print(f"HF Dataset splits: {out_hf}/ (train/validation/test)")


def main():
    print("\n📚 Пълно използване на TMX Processor библиотеката (API)\n")

    units = step_1_parse()
    cleaned = step_2_clean(units)
    valid = step_3_validate(cleaned)
    deduped = step_4_dedupe(valid)
    stats = step_5_analyze(deduped)
    step_6_convert(deduped)

    print("\n" + "=" * 60)
    print("✅ Всички стъпки завършени!")
    print(f"📁 Изходни файлове в: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
