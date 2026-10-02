# 🖥️ Интерфейси: CLI, FastAPI и Streamlit UI

Платформата **TMX Processor** предлага три независими начина за задвижване на ядрата: Команден ред (CLI), REST API с FastAPI SPA и интерактивен Streamlit UI.

---

## 1. CLI (Command Line Interface)

Команда за стартиране: `tmx-proc`

```bash
# Парсване и преглед на статистики
tmx-proc parse examples/sample_en_bg.tmx

# Почистване и филтриране по езикова двойка
tmx-proc clean examples/sample_en_bg.tmx -o output.jsonl --lang-pairs EN-BG

# Конвертиране в Alpaca формат
tmx-proc convert examples/sample_en_bg.tmx -o alpaca.jsonl --fmt alpaca

# Цял пайплайн до HuggingFace splits
tmx-proc pipeline examples/sample_en_bg.tmx -o hf_dataset --fmt hf_dataset
```

---

## 2. Уеб API & FastAPI SPA (`tmx-web`)

Стартирайте сървъра с командата:
```bash
tmx-web --port 8000
```
Отворете браузъра на адрес: `http://localhost:8000`

![FastAPI SPA UI](images/fastapi_ui.png)

### Налични REST Endpoints:

- `POST /api/upload`: Качване и парсване на TMX файл.
- `POST /api/clean`: Почистване, анонимизиране и филтриране по езикова двойка.
- `POST /api/dedupe`: Точна и fuzzy дедупликация.
- `GET /api/stats/{key}`: Връща статистика, токени и извлечена терминология.
- `GET /api/search/{key}?query=...`: Конкордансно търсене.
- `POST /api/convert`: Експорт към избран AI формат.
- `POST /api/large-pipeline`: Диск-базирана стрийминг обработка на файлове до 1 GiB.

---

## 3. Streamlit UI

За data science потребители с визуали задоволителни графики и интерактивност:

```bash
streamlit run src/tmx_processor/web_streamlit.py
```
Отворете браузъра на адрес: `http://localhost:8501`

![Streamlit UI](images/streamlit_upload.png)

Табове в Streamlit UI:
1. **📥 Качване & Преглед**: Визуализация на метаданни, намерени езици и първите единици.
2. **🧼 Почистване**: Интерактивни филтри, PII маскиране и филтър по езикови двойки.
3. **🔁 Дедупликация**: Слайдер за fuzzy праг (MinHash LSH).
4. **✅ Валидация & Статистика**: Таблица с грешки, терминология и калкулатор на токени.
5. **💾 Експорт**: Избор от 13 формата и директно сваляне.
