# 🗑️ Дедупликация и Пакетна обработка

Модулът `deduper.py` извършва отстраняване на дубликати (дедупликация), а `batch.py` осигурява паралелна мулти-процесорна обработка на голям брой TMX файлове.

---

## 🗑️ 1. Режими на дедупликация (`DataDeduper`)

1. **Точна дедупликация (Exact Deduplication)**:
   - Сравнява нормализираните двойки `(source_lang, target_lang, source_text, target_text)`.
   - За големи корпуси стрийминг интерфейсът ползва временна SQLite база на диска, за да избегне препълване на RAM паметта.
2. **Fuzzy дедупликация (MinHash LSH)**:
   - Използва MinHash LSH (`datasketch`) за откриване и премахване на почти идентични изречения с праг на сходство (`fuzzy_threshold=0.9`).

```python
from tmx_processor.deduper import DataDeduper

deduper = DataDeduper(exact=True, fuzzy=True, fuzzy_threshold=0.9)
deduped_units = deduper.dedupe(units)
```

---

## ⚡ 2. Мулти-процесорна пакетна обработка (`BatchProcessor`)

Кластът `BatchProcessor` автоматично разпределя обработката на множество TMX файлове между всички налични процесорни ядра (`ProcessPoolExecutor`).

### Пример за пакетно почистване и конвертиране:

```python
from pathlib import Path
from tmx_processor.batch import BatchProcessor, find_tmx_files
from tmx_processor.converter import ConvertOptions, OutputFormat

# 1. Откриване на всички TMX файлове в директория
files = find_tmx_files("*.tmx", base_dir=Path("./corpus"))

# 2. Инициализиране на пакетния процесор
batch = BatchProcessor(clean=True, dedupe=True, fuzzy_dedupe=False)

opts = ConvertOptions(include_id=True, language_pairs=["EN-BG"])

# 3. Паралелна обработка на всички файлове на отделни ядра
results = batch.process_files(
    tmx_files=files,
    output_dir=Path("./processed_output"),
    fmt=OutputFormat.ALPACA,
    convert_options=opts,
    merge=False, # merge=True обединява всичко в един общ файл
)

print("Резултати по файлове:", results)
```
