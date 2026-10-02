# TMX Processor

<div align="center">

![TMX Processor Logo](https://img.shields.io/badge/TMX-Processor-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.9+-green?style=for-the-badge&logo=python)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

**Платформа за обработка на TMX езикови файлове за обучение на AI модели**

[Функционалности](#-функционалности) • [Инсталация](#-инсталация) • [Документация](#-документация) • [API](#-api) • [Примери](#-примери)

</div>

---

## 📋 Съдържание

- [За проекта](#-за-проекта)
- [Функционалности](#-функционалности)
- [Технологичен стек](#-технологичен-стек)
- [Инсталация](#-инсталация)
- [Интерфейси](#-интерфейси)
- [Поддържани формати](#-поддържани-формати)
- [Python API](#-python-api)
- [CLI](#-cli)
- [Уеб API](#-уеб-api)
- [Конфигурация](#-конфигурация)
- [Примери](#-примери)
- [Тестове](#-тестове)
- [Архитектура](#-архитектура)
- [Приноси](#-приноси)
- [Лиценз](#-лиценз)

---

## 🎯 За проекта

**TMX Processor** е професионална платформа за обработка на TMX (Translation Memory eXchange) езикови файлове, предназначена за подготовка на данни за обучение на AI модели. Платформата предоставя пълен набор от инструменти за парсене, почистване, валидация, дедупликация и конвертиране на преводни данни към 13 различни формата за AI обучение.

### Основни цели

- 🚀 Подготовка на висококачествени данни за обучение на AI модели
- 🔄 Конвертиране към всички популярни формати за fine-tuning (SFT, DPO, ORPO, reasoning)
- 📊 Статистически анализ и валидация на преводни корпуси
- 🧹 Интелигентно почистване и дедупликация на данни
- 🌐 Поддръжка на множество езици и езикови двойки

### Предназначение

Платформата е подходяща за:
- 🤖 Обучение на машинен превод (Machine Translation)
- 🧠 Fine-tuning на големи езикови модели (LLM)
- 💬 Създаване на chat модели
- ⚖️ Preference tuning (DPO/ORPO)
- 🤔 Reasoning модели с chain-of-thought
- 📦 Подготовка на dataset-и за Hugging Face

---

## ✨ Функционалности

| Категория | Модул | Описание |
|-----------|-------|----------|
| 📥 **Парсене** | `TMXParser` | Namespace-aware lxml iterparse/streaming; XML recovery warnings; multilingual expansion |
| 🧹 **Почистване** | `DataCleaner` | Unicode нормализация, HTML/URL/email премахване, филтри по дължина, ratio, думи, placeholders |
| 🎯 **Валидация** | `DataValidator` | 8 проверки за текст, езици, числа, placeholders, шум и съотношение на дължини |
| 🗑️ **Дедупликация** | `DataDeduper` | Exact + Fuzzy MinHash LSH (datasketch) за ефективно премахване на дубликати |
| 📊 **Статистика** | `DataAnalyzer` | DatasetStats — езикови двойки, running min/max/средни; whitespace word counts или tiktoken |
| 🔄 **Конверсия** | `DataConverter` | 13 формата, двупосочен експорт и HF train/validation/test splits |

---

## 🛠 Технологичен стек

### Основни технологии

- **Python 3.9+** - Основен език за програмиране
- **lxml** - High-performance XML parser
- **pandas/pyarrow** - Data manipulation и Parquet support
- **fastapi/uvicorn** - Modern async web framework
- **streamlit** - Interactive data science UI

### Ключови библиотеки

```python
# XML Parsing
lxml >= 4.9.0
regex >= 2023.0.0

# NLP & Language Detection
langdetect >= 1.0.9

# Data Formats
jsonlines >= 4.0.0
pandas >= 2.0.0
pyarrow >= 12.0.0

# Deduplication
datasketch >= 1.5.0
numpy >= 1.24.0

# Web Framework
fastapi >= 0.110.0
uvicorn >= 0.27.0
python-multipart >= 0.0.9

# CLI & UI
typer >= 0.9.0
rich >= 13.0.0
tqdm >= 4.65.0
streamlit >= 1.30.0

# Tokenization (optional)
tiktoken >= 0.5.0
```

### Инструменти за разработка

- **pytest** - Unit testing
- **pytest-cov** - Code coverage
- **httpx2** - HTTP client testing

---

## 📦 Инсталация

### Изисквания

- Python 3.9 или по-нова версия
- pip или poetry за управление на зависимости

### Стъпка 1: Създай виртуална среда (препоръчително)

```bash
# С venv
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate  # Windows

# С conda
conda create -n tmx-processor python=3.9
conda activate tmx-processor
```

### Стъпка 2: Инсталирай пакета

```bash
# Всички интерфейси, включително Streamlit и tokenizer
pip install -e ".[all]"

# Само основни зависимости (без Streamlit)
pip install -e .

# Със Streamlit
pip install -e ".[streamlit]"

# За разработка и тестове
pip install -e ".[dev]"
python -m pytest
```

### Fallback механизми

Основните модули имат fallback за някои библиотеки:
- XML парсърът може да използва `xml.etree` вместо `lxml`
- JSONL има вграден writer без `jsonlines`
- Parquet експортът записва JSONL fallback без `pandas/pyarrow`
- CLI изисква `typer` и `rich`; без тях показва съобщение за инсталация

---

## 🖥 Интерфейси

Платформата предлага **4 начина** за употреба: CLI, Уеб API, Streamlit UI и Python API. Всички използват едно и също ядро.

### 1. CLI (Command Line Interface)

Entry point: `tmx-proc` или `python -m tmx_processor.cli`

```bash
# Виж всички команди
tmx-proc --help

# Парсване и преглед
tmx-proc parse examples/sample_en_bg.tmx

# Цял пайплайн — изход HuggingFace dataset splits
tmx-proc pipeline examples/sample_en_bg.tmx -o ./output --fmt hf_dataset

# Експорт за Alpaca instruction tuning
tmx-proc convert examples/sample_en_bg.tmx -o ./output/alpaca.jsonl --fmt alpaca

# Експорт за DPO preference tuning
tmx-proc convert examples/sample_en_bg.tmx -o ./output/dpo.jsonl --fmt dpo

# Streaming JSONL — parse/clean/write iteratively
tmx-proc convert examples/sample_en_bg.tmx -o ./output/stream.jsonl --fmt jsonl --streaming --no-dedupe --preserve-placeholders
```

#### Налични CLI команди

| Команда | Описание | Пример |
|---------|----------|--------|
| `parse` | Парсва TMX, показва статистики | `tmx-proc parse examples/sample_en_bg.tmx` |
| `clean` | Почиства и филтрира | `tmx-proc clean in.tmx -o out.jsonl --min-words 2 --lang-pairs EN-BG` |
| `convert` | Почиства, дедуплицира и конвертира | `tmx-proc convert in.tmx -o out.jsonl --fmt alpaca --instruction "Translate {src} to {tgt}"` |
| `validate` | Валидира TU, показва report | `tmx-proc validate in.tmx --report report.json` |
| `stats` | Генерира статистически отчет | `tmx-proc stats in.tmx --format table` |
| `pipeline` | Цял workflow — parse → clean → dedupe → convert | `tmx-proc pipeline in.tmx -o out_folder --fmt hf_dataset` |

### 2. Уеб API (FastAPI + HTML SPA)

Стартирай:
```bash
tmx-web
# или с custom порт
tmx-web --port 8001
```

API endpoints:

| Метод | Endpoint | Query Params | Описание |
|-------|----------|--------------|----------|
| `GET` | `/` | - | HTML SPA |
| `GET` | `/docs` | - | Swagger UI |
| `POST` | `/api/upload` | File: TMX | Upload & parse |
| `GET` | `/api/stats/{key}` | - | Session statistics |
| `GET` | `/api/validate/{key}` | - | Validation report |
| `GET` | `/api/preview/{key}` | `start, limit` | Preview rows |
| `POST` | `/api/clean` | Form: key, clean options | Clean data |
| `POST` | `/api/dedupe` | Form: key, fuzzy options | Deduplicate |
| `POST` | `/api/convert` | Form: key, fmt, options | Convert & download |
| `POST` | `/api/pipeline` | Form: file, fmt, options | Full pipeline ZIP |
| `POST` | `/api/large-pipeline` | Form: files (repeatable), fmt, clean, dedupe | Merge up to 50 TMX files; disk-backed streaming, 1 GiB total |
| `GET` | `/api/large-pipeline/{job_id}/download` | - | Direct download; job removed after download or after 1 hour |

🔗 API Docs с интерактивен playground са на `/docs` (Swagger UI).

#### TMX файлове 500–1000 MiB

В SPA интерфейса включете **„Големи или множество файлове — streaming до 1 GiB общо“** в „Бърз Пайплайн“. Изберете до 50 TMX файла; те се парсват и сливат последователно, без да се зареждат всички TU в RAM. Exact dedupe, ако е включено, е глобално за целия batch и използва временна SQLite база на диск. JSONL/AI JSONL export-ът също се записва потоково. Изходът се сваля директно от браузъра, а временният резултат се изтрива след сваляне или изтичане на едночасовия TTL.

Големият режим поддържа JSONL, Alpaca, ShareGPT, ChatML, OpenAI, DPO, Prompt/Completion и Reasoning. HuggingFace splits, JSON/CSV/TSV/Parquet, fuzzy dedupe и интерактивната session обработка (`/api/upload`) не са налични за този режим. Обикновените session uploads остават ограничени до 100 MiB; Streamlit UI също е предназначен за файлове, които могат да се държат в паметта.

Нужни са свободно дисково пространство за качения TMX, временната SQLite база и generated output. При reverse proxy задайте upload body limit поне 1025 MiB и достатъчно дълги request/read timeouts; лимитът на proxy/load balancer може да е по-нисък от лимита на приложението.

### 3. Streamlit UI

За data-science потребители с интерактивни dashboards.

Стартирай:
```bash
pip install -e ".[streamlit]"  # ако не е инсталирано
streamlit run src/tmx_processor/web_streamlit.py
```

Отвори в браузър: http://localhost:8501

#### 5 таба:

1. **📥 Качване & Преглед** — качи .tmx, виж stats + preview таблица
2. **🧹 Почистване** — интерактивна форма с toggle-и и range slider-и; живо before/after
3. **🗑️ Дедупликация** — exact vs fuzzy с threshold slider
4. **✅ Валидация & 📊 Статистика** — 2 колони: validation table + language pairs charts
5. **💾 Експорт** — dropdown с 13 формата и download button

### 4. Python API

За интеграция в собствени скриптове или Jupyter notebooks.

```python
from pathlib import Path
from tmx_processor import (
    TMXParser, DataCleaner, DataDeduper, DataValidator, DataAnalyzer, DataConverter,
    CleanConfig, OutputFormat,
)

# 1. Парсане на примерен файл
parser = TMXParser(Path("examples/sample_en_bg.tmx"))
all_units = parser.parse_all()
language_pairs = sorted({(u.source_lang, u.target_lang) for u in all_units})
print(f"Езикови двойки: {language_pairs} | Единици: {len(all_units)}")

# 2. Почистване
cleaner = DataCleaner(CleanConfig(
    min_length=2, max_length_ratio=5.0,
    remove_html_tags=True, remove_urls=False,
    preserve_placeholders=True,
))
clean_units = cleaner.clean_units(all_units)
print(f"Почистени: {len(clean_units)} от {len(all_units)}")

# 3. Дедупликация
deduper = DataDeduper()
deduped = deduper.dedupe(clean_units)
print(f"След дедуп: {len(deduped)}")

# 4. Валидация
validator = DataValidator()
report = validator.report(deduped)
print(f"Валидни: {report['valid']}/{report['total']}")

# 5. Статистика
analyzer = DataAnalyzer()
stats = analyzer.analyze(deduped)
print(f"Езикови двойки: {stats.language_pairs}")
print(f"Средна дълга на източника: {stats.avg_source_length:.0f} знака")

# 6. Експорт за AI обучение
converter = DataConverter()
out_dir = Path("./output")
out_dir.mkdir(exist_ok=True)

converter.convert(
    deduped, output_path=out_dir / "train.jsonl", fmt=OutputFormat.JSONL
)
converter.convert(
    deduped, output_path=out_dir / "alpaca.jsonl", fmt=OutputFormat.ALPACA,
    instruction_tmpl="Преведи следния текст от {src} на {tgt}:"
)
converter.convert(
    deduped, output_path=out_dir / "dpo.jsonl", fmt=OutputFormat.DPO,
    instruction_tmpl="Translate from {src} to {tgt}:"
)
converter.convert(
    deduped, output_path=out_dir / "hf_data", fmt=OutputFormat.HF_DATASET,
    train_ratio=0.8, val_ratio=0.1, test_ratio=0.1,
)
print(f"Експортирано в {out_dir}")
```

`parse_all()` връща списък и зарежда всички TU в паметта.
`preserve_placeholders=True` запазва tokens като `{0}`, `%1$s` и placeholders в HTML атрибути дори когато самите HTML тагове се премахват.

`DataConverter.convert(..., streaming=True)` подава generator-а директно към JSONL writer-а. CLI `--streaming` използва `iter_units()` и `clean_iter()`; той изисква `--no-dedupe`, защото deduper-ът материализира данните.

---

## 📊 Поддържани формати (13)

| Формат | `OutputFormat` | Подходящ за | Име на файл |
|--------|----------------|-------------|-------------|
| **JSONL** | `jsonl` | Универсален, скриптове | `output.jsonl` |
| **JSON** | `json` | Преглед, конфигове | `output.json` |
| **CSV** | `csv` | Excel, данъчни анализи | `output.csv` |
| **TSV** | `tsv` | Инструменти за MT | `output.tsv` |
| **Parquet** | `parquet` | Големи dataset-и, pandas/HF | `output.parquet` |
| **Alpaca** | `alpaca` | LLM instruction tuning | `alpaca.jsonl` |
| **ShareGPT** | `sharegpt` | Chat / multi-turn модели | `sharegpt.jsonl` |
| **ChatML** | `chatml` | Chat fine-tuning с `messages` | `chatml.jsonl` |
| **OpenAI messages** | `openai` | Chat training с `messages` | `openai.jsonl` |
| **DPO/ORPO** | `dpo` | Preference tuning (DPO/ORPO) | `dpo.jsonl` |
| **Prompt/Completion** | `prompt_completion` | Generic instruction tuning | `prompt_completion.jsonl` |
| **Reasoning** | `reasoning` | Chain-of-thought модели | `reasoning.jsonl` |
| **HuggingFace Dataset** | `hf_dataset` | train/validation/test splits | папка с `train.jsonl`, `validation.jsonl`, `test.jsonl`, `metadata.json` |

### Примери за AI формати

**Alpaca example row:**
```json
{
  "instruction": "Преведи от EN на BG:",
  "input": "Hello world",
  "output": "Здравей свят"
}
```

**ShareGPT example row:**
```json
{
  "conversations": [
    {"from": "system", "value": "Ти си професионален преводач."},
    {"from": "human",  "value": "Преведи: Hello world"},
    {"from": "gpt",    "value": "Здравей свят"}
  ]
}
```

**DPO example row:**
```json
{
  "prompt": "Translate from EN to BG:\nHello world",
  "chosen": "Здравей свят",
  "rejected": "[TRANSLATION ERROR] Здравей"
}
```

**Prompt/Completion example row:**
```json
{
  "prompt": "Translate from EN to BG: Hello world",
  "completion": "Здравей свят"
}
```

**Reasoning example row:**
```json
{
  "messages": [
    {"role": "system", "content": "Translate the following text from EN to BG. Show your reasoning."},
    {"role": "user", "content": "Hello world"},
    {"role": "assistant", "content": "Source text in EN: 'Hello world'. Context: formal translation task.\n\nTranslation: Здравей свят"}
  ]
}
```

---

## 🔧 Конфигурация

### Почистване (CleanConfig)

```python
from tmx_processor import CleanConfig

config = CleanConfig(
    min_length=2,              # Минимална дължина в символи
    max_length=10000,          # Максимална дължина в символи
    min_words=0,               # Минимален брой думи
    max_words=0,               # Максимален брой думи (0 = без лимит)
    max_length_ratio=3.0,      # Максимално съотношение източник/цел
    remove_html_tags=True,     # Премахни HTML тагове
    remove_urls=False,         # Премахни URL-ли
    remove_emails=False,       # Премахни имейли
    lang_detect=False,          # Езикова детекция
    preserve_placeholders=False, # Запази placeholders
)
```

### Конвертиране (ConvertOptions)

```python
from tmx_processor import ConvertOptions

options = ConvertOptions(
    include_metadata=False,      # Включи metadata
    include_id=False,            # Включи TU ID
    source_key="source",         # Ключ за източник
    target_key="target",         # Ключ за цел
    lang_key=True,               # Включи езикови ключове
    source_lang_key="source_lang",  # Ключ за изходен език
    target_lang_key="target_lang",  # Ключ за целеви език
    instruction_template=None,   # Персонализирана инструкция
    bidirectional=False,         # Експорт и в обратна посока
)
```

### Уеб API конфигурация

```python
# В web_api.py
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_SESSIONS = 50
MAX_SESSION_ESTIMATED_BYTES = 128 * 1024 * 1024  # 128 MB per session
MAX_TOTAL_SESSION_ESTIMATED_BYTES = 512 * 1024 * 1024  # 512 MB total
SESSION_TTL = 3600  # 1 hour
SESSION_CLEANUP_INTERVAL = 60  # seconds
```

---

## 📁 Примери

### Примерни файлове

- [examples/sample_en_bg.tmx](examples/sample_en_bg.tmx) — 25 примера EN↔BG (съдържа празни, шумни, дубликати, inline тагове)
- [examples/basic_pipeline.py](examples/basic_pipeline.py) — примерен Python API pipeline

Голям corpus за streaming проверка не се разпространява с репозиторията. За
тази проверка подайте собствен TMX файл, който имате право да използвате.
Локалните Mozilla корпуси също са изключени от Git, докато не бъдат потвърдени
правата за повторното им разпространение.

### Ръчни тестови скриптове

- [examples/test_basic.py](examples/test_basic.py) — ръчен smoke скрипт за избрани модули
- [examples/test_web_api.py](examples/test_web_api.py) — ръчен HTTP smoke скрипт
- [examples/verify_large_stream.py](examples/verify_large_stream.py) — streaming CLI integration check

### Пускане на примерите

```bash
# Базов pipeline
python examples/basic_pipeline.py

# Smoke тестове
python examples/test_basic.py

# Streaming verification — подайте собствен TMX corpus
python examples/verify_large_stream.py path/to/your-large-file.tmx
```

---

## 🧪 Тестове

### Пускане на тестовете

```bash
# Всички тестове
python -m pytest

# С coverage
python -m pytest --cov=tmx_processor

# Конкретен тест файл
python -m pytest tests/test_converter.py

# Конкретен тест
python -m pytest tests/test_converter.py::test_dpo_format_has_prompt_chosen_rejected -v
```

### Тестови файлове

- [tests/test_parser.py](tests/test_parser.py) — pytest тестове за парсър
- [tests/test_cleaner.py](tests/test_cleaner.py) — pytest тестове за cleaner
- [tests/test_converter.py](tests/test_converter.py) — pytest тестове за конвертор (15 теста)
- [tests/test_deduper.py](tests/test_deduper.py) — exact/fuzzy fallback и multi-file merge тестове
- [tests/test_analyzer.py](tests/test_analyzer.py) — statistics, empty input и duplicate counts
- [tests/test_validator.py](tests/test_validator.py) — pytest тестове за validator
- [tests/test_cli.py](tests/test_cli.py) — CLI pipeline/streaming regression tests
- [tests/test_web_api.py](tests/test_web_api.py) — базови API тестове с TestClient (29 теста)

### Покритие

Тестовете покриват основните модули, CLI и FastAPI API. GitHub Actions
изпълнява целия набор при push и pull request.

---

## 🏗 Архитектура

```
examples/*.tmx  ──┐
                  │
CLI (tmx-proc) ───┤
                  ├──►  TMXProcessor Core  ───►  Output files (.jsonl, .parquet, .zip)
Web API (tmx-web) ─┤         │
                  │         ├ parser.py     (TMXParser + streaming iterparse)
Streamlit UI ─────┘         ├ cleaner.py    (DataCleaner + 8 правил)
                            ├ validator.py  (DataValidator + 8 проверки)
                            ├ deduper.py    (Exact + MinHash LSH fuzzy)
                            ├ analyzer.py   (DatasetStats dataclass)
                            └ converter.py  (13 OutputFormat)
```

### Директорийна структура

```
TMX_project/
├── pyproject.toml              # Пакет metadata + entry points
├── requirements.txt            # Всички dependencies
├── README.md                   # Този файл
├── LICENSE                     # MIT License
├── src/
│   └── tmx_processor/
│       ├── __init__.py         # Public API export
│       ├── parser.py           # TMX streaming XML parser
│       ├── cleaner.py          # Почистване + филтри
│       ├── converter.py        # Конверсия към 13 формата
│       ├── validator.py        # Валидация TU
│       ├── deduper.py          # Exact + fuzzy дедупликация
│       ├── analyzer.py         # Статистика DatasetStats
│       ├── cli.py              # Typer CLI (tmx-proc)
│       ├── web_api.py          # FastAPI + REST endpoints (tmx-web)
│       ├── web_streamlit.py    # Streamlit UI в 5 таба
│       └── web/
│           └── index.html      # TailwindCSS + Alpine.js SPA
├── examples/
│   ├── sample_en_bg.tmx        # Примерен bilingual TMX
│   ├── basic_pipeline.py       # Python API пример
│   ├── test_basic.py           # Ръчен smoke скрипт
│   ├── test_web_api.py         # Ръчен HTTP smoke скрипт
│   └── verify_large_stream.py  # Streaming integration check
└── tests/
    ├── test_parser.py
    ├── test_cleaner.py
    ├── test_converter.py
    ├── test_deduper.py
    ├── test_analyzer.py
    ├── test_validator.py
    ├── test_cli.py
    └── test_web_api.py
```

---

## 🤝 Приноси

Приносите са добре дошли! Вижте [CONTRIBUTING.md](CONTRIBUTING.md) за
настройка на средата и правилата за pull request-и.

---

## 📄 Лиценз

Този проект е лицензиран под MIT License — вижте [LICENSE](LICENSE) за текста
на лиценза.

---

## 📞 Поддръжка

След публикуване на проекта в GitHub използвайте секцията **Issues** за
доклади за грешки и предложения. Посочете версията на Python, командата,
която сте изпълнили, и минимален пример без чувствителни TMX данни.

---

## 🙏 Благодарности

- **lxml** за high-performance XML parsing
- **Hugging Face** за dataset форматите и инструменти
- **FastAPI** за модерната web архитектура
- **Streamlit** за интерактивния UI
- Всички contributors към open-source библиотеките, които използваме

---

<div align="center">

**Made with ❤️ by TMX Processor Team**

[⬆ Back to top](#-tmx-processor)

</div>
