
## Текущ статус (2026-10-01)

Статусите по-долу отразяват изпълнимия код, а не само наличието на параметър или метод.

| Област | Статус | Завършено | Остава / дефект |
|---|---|---|---|
| Парсър | Частично | Namespace-aware lxml iterparse, recovery за invalid control chars с warning; inline tails и per-segment placeholder numbering | `parse_all()` пази всички TU в RAM; stdlib fallback е strict и зарежда целия XML документ |
| Cleaner | Основата е завършена | Unicode/HTML/URL/email cleanup, length/word/ratio, language-pair filters; printf placeholders се премахват като цяло или се пазят включително от HTML attributes | Preserve е opt-in; UI/CLI не излагат всички cleaner настройки |
| Validator | Частично | 8 checks се изпълняват; alignment/similar-word са warnings; `filter_valid()` запазва валидните с warnings | `include_warnings` не се използва; числата се сравняват като множества и се губи multiplicity/ред |
| Deduper | Частично | Exact, optional MinHash LSH, multi-file merge | Fuzzy кандидатите не се проверяват точно; комбинираният source+target hash може да махне валидна алтернатива |
| Analyzer | Частично | Running sums/min/max; optional tiktoken | Duplicate `seen` set е O(n); без tokenizer думите са whitespace tokens |
| Converter | Частично | 10 формата, bidirectional, seeded/stratified HF splits, ratio validation; JSONL streaming е изложен през `convert(..., streaming=True)` | HF split-овете и не-JSONL формати продължават да материализират списъци |
| CLI | Частично | 7 команди, aliases, `convert --streaming` и `--preserve-placeholders`; stream path използва `iter_units()`/`clean_iter()` | Streaming изисква `--no-dedupe`; dedupe/HF split paths остават memory-bound |
| FastAPI | Частично | 101 MiB ASGI request cap, 100 MiB file cap, chunked disk copy, temp cleanup, 60s background TTL sweep, 50-session/128 MiB-per-session/512 MiB-total estimated quotas | Memory quota estimates text/metadata and per-unit overhead, not actual process RSS; quota/stress race behavior still needs operational load testing |
| Web/Streamlit UI | Частично | Основните интерактивни потоци работят | 8 от 10 формата; няма ChatML/OpenAI избор; не съвпадат напълно с CLI/API |
| Тестове | Частично | Пълният suite: 72 tests passed без warning; TestClient използва `httpx2` | Остава stress/load coverage и измерване на quotas при реален peak RSS |

### Приоритет за работа
> Първоначалният checklist по-долу е исторически; актуалните нерешени задачи са в „Следващи задачи (актуални)“.
> Parser inline tails/placeholders, CLI HF metadata, split validation и целият наличен pytest suite са завършени. Продължи с новите тестове за deduper/analyzer/API lifecycle и streaming/upload hardening.
> Първоначалните задачи 1–2 по-долу са завършени. Следващи активни задачи: тестове за deduper/analyzer/API lifecycle и streaming/upload hardening.

1. Поправи парсера, за да не губи текст около inline тагове; добави regression fixtures и тестове.
2. Поправи CLI HF pipeline metadata и split логиката за малки набори; валидирай ratio входовете.
3. Добави тестове за converter, deduper, analyzer, CLI и всички API mutation/export маршрути.
4. Завърши streaming интеграцията и upload/session lifecycle.
5. Реши дали UI ще поддържа всичките 10 формата; синхронизирай документацията с избрания обхват.
6. По-късно: numeric/placeholder validation, alignment scoring и оценка за достатъчност на корпуса.

### Следващи задачи (актуални)

1. Добави stress test за TTL cleanup, който върви паралелно със session reads/mutations; базовият concurrent dedupe case вече е покрит.
2. Намали analyzer duplicate tracking memory; streaming през `convert()`/CLI вече е наличен за dedupe-free JSONL flows.
3. Измери session quota estimates спрямо реален peak RSS и валидирай лимитите под load; при deployment добави reverse-proxy cap.
4. Реши дали UI ще поддържа ChatML/OpenAI, или документирай 8-formats обхват като окончателен за UI.
5. Подобри numeric validation за дублирани числа/ред; alignment scoring остава future scope.

### Проверки при тази сверка

- `compileall` за `src`, `tests` и `examples`: успешно.
- `compileall -q src tests`: успешно след текущите промени.
- README Python workflow върху `examples/sample_en_bg.tmx`: успешно; 25 TU парснати, 23 след clean, 22 след dedupe; JSONL, Alpaca template и HF splits са създадени.
- Числова punctuation smoke check за `29.99` и `1,000`: успешно.
- Mozilla corpus streaming checks: 32,820 EN-US→BG и 52,164 EN-US→FR TU; големите корпуси нямат празни/невалидни TU; малкият demo има 1 очакван празен source.
- Cleaner scan върху корпусите: 5,812 positional printf placeholders; default removal оставя 0 частични остатъка, preserve mode губи 0 токена.
- README локални Markdown линкове: всички намерени targets съществуват.
- `pytest -q`: успешно, 72 passed, без warnings; dev extra инсталира `httpx2` вместо deprecated `httpx` fallback.
- `big_test.tmx`: 548,960,658 bytes, 708,658 parsed TU; CLI streaming export завърши с 706,728 JSONL records (296,787,476 bytes) и 12 placeholders.
- Windows process counters за същия export: peak working set 34.5 MiB, private bytes 26.6 MiB; стойностите важат за текущата машина и corpus.
- `big_test.tmx` има 3 XML 1.0 invalid vertical-tab символа; lxml recovery ги пропусна и издаде warning с първата позиция.
- Streaming regressions: Python `convert(..., streaming=True)` използва streaming writer; CLI `--streaming --no-dedupe` използва parser/cleaner iterators; CLI отказва streaming, ако dedupe е включен.
- Large-file Mozilla smoke: 14 MB TMX → 51,772 streaming JSONL records, 3,552 printf placeholders запазени с `--preserve-placeholders`.
- Inline-tag regression tests: минават в normal и preserve-tags режим; запазват tail текста и еднаквите placeholder номера в source/target.
- HF pipeline regression tests: CLI HF metadata (counts, ratios, seed, stratification) и tiny JSONL/HF split cases минават през Typer `CliRunner`.
- Streaming regressions: Python `convert(..., streaming=True)` и CLI `--streaming --no-dedupe` минават; CLI отказва streaming, ако dedupe е включен.
- Web lifecycle regression tests: размерът се проверява преди четене, upload TMX файловете се трият след parse/pipeline, а TTL sweep маха изтекли сесии при заявки.
- Web lifecycle regression tests: upload limits/temp cleanup, TTL expiry/refresh и concurrent dedupe access минават.
- Inline-tag regression smoke check: текстът след inline таговете се запазва и placeholder numbering съвпада между source/target.
- Split runtime checks: валидни са 0/1/2/10-записните набори; ratios с грешен сбор се отказват; HF export за един TU записва всичкия ред в train.
- `compileall -q src tests`: успешно след добавяне на regression тестовете.

Историческите секции следва да се четат с този статус като източник на истина.
# TMX Processor — анализ и план за подобрения

Дата: 2026-10-01  
Версия на кода: `0.1.0`

Проектът е платформа за обработка на TMX (Translation Memory eXchange) файлове с цел подготовка на паралелни данни за обучение на AI модели (машинен превод, instruction tuning, чат модели).

Ядрото е логично: `parse → clean → dedupe → validate → convert`, с три интерфейса (CLI, FastAPI UI, Streamlit) върху едни и същи модули. Примерният `examples/sample_en_bg.tmx` покрива дубликати, HTML, URL, placeholder-и и шум.

Документът описва какво работи, къде кодът се разминава с README, какви са реалните капани и какво липсва за сериозно обучение. Работата е разделена на три стъпки: **A стабилност**, **B данни за обучение**, **C качество и скала**.

---

## 1. Архитектура (текущо състояние)

```
examples/*.tmx
CLI (tmx-proc)
Web UI (FastAPI)     ──►  tmx_processor  ──►  JSONL / Parquet / Alpaca / ShareGPT / HF splits
Streamlit UI

src/tmx_processor/
  parser.py      TMXParser + TranslationUnit (streaming iterparse)
  cleaner.py     DataCleaner + CleanConfig
  validator.py   DataValidator + ValidationConfig
  deduper.py     Exact + MinHash LSH (datasketch)
  analyzer.py    DatasetStats
   converter.py   10 OutputFormat
  cli.py         Typer
  web_api.py     FastAPI + in-memory сесии
  web_streamlit.py
  web/index.html Tailwind + Alpine SPA
```

Публичното API е в `__init__.py`. Проектът има `.gitignore`, MIT `LICENSE`, pytest конфигурация и unit/API тестове. Текущият статус е сверяван отново на 2026-10-01.

---

## 2. Какво работи добре

- Streaming парсинг през `lxml.iterparse` с fallback към `xml.etree`.
- Fallback-и за JSONL и fuzzy без datasketch; без `typer`/`rich` CLI извежда инсталационно съобщение и приключва.
- Почистване: Unicode NFKC, HTML, URL/email, length/word/ratio филтри, опционален langdetect.
- Exact дедупликация по (lang, source, target).
- Експорт: JSONL, JSON, CSV, TSV, Parquet, Alpaca, ShareGPT, ChatML, OpenAI messages и HF train/validation/test.
- Уеб: качване, preview, clean, dedupe, validate, stats, convert, one-shot pipeline + ZIP.
- Примерният TMX е полезен за демо на edge cases.

---

## 3. Критични разминавания README ↔ код

| README | Реалност |
|--------|----------|
| Python API сигнатури в стария README | Вече поправени в README; актуалният executable API пример използва наличните методи |
| `convert(..., instruction_tmpl=..., train_ratio=...)` | Поддържа се; instruction interpolation е реализирана |
| `tmx-proc convert ... --fmt ...` и `validate --report` | Поддържат се; `pipeline --clean/--no-clean` и `--dedupe/--no-dedupe` също са налични |
| `stats --format table` | Поддържа се; налични са `table` и `json` |
| Валидаторът има 8 checks | Checks се изпълняват; alignment/similar-word резултатите са warnings |
| MIT license, `.gitignore`, pytest | Файловете и базовият pytest suite съществуват |
| README локални пътища | Пътищата към примери вече са относителни |
| Примери за Python API | Актуалният README пример вече използва валидните сигнатури; добави го към автоматичните smoke checks |

---

## 4. Грешки и капани по модули
> Исторически списък от първата проверка. Част от находките по-долу вече са поправени; текущият статус за всеки модул е таблицата в началото, а нерешените рискове са в §5.

### 4.1 Парсър (`parser.py`)

- `findall("tu"|"tuv"|"seg"|"prop"|"note")` и `iterparse(..., tag=("tu",))` **не намират** елементи при TMX с default namespace (`xmlns="http://www.lisa.org/tmx14"`). Много реални TMX файлове са такива — изходът изглежда празен.
- `_localname()` вече съществува, но `_parse_tu` и header path не го ползват последователно.
- TU с 3+ езика се режат до **една** source→target двойка. За мултиезични TM трябва експлозия към всички двойки (стъпка B).
- Inline тагове (`bpt`, `ept`, `ph`, `it`, `hi`, `ut`) се изтриват без опция да се запазят като `{1}` placeholder-и.
- `parse_header` + `iter_units` четат файла **два пъти**.
- Неизползван import: `os`.

### 4.2 Чистене (`cleaner.py`)

- `PUNCT_SPACE_RE` слага интервал след всяка пунктуация, която не е последвана от space/край. Резултат: `29.99` → `29. 99`, `1,000` → `1, 000`.
- `PLACEHOLDER_RE` маха `{0}`, `[...]`, `%s`, `${...}` — за MT често трябва да се **запазят**.
- `langdetect` е ненадежден за къси сегменти (типичните TM изречения).
- Пакетът `regex` е в `requirements.txt` / `pyproject.toml`, но кодът ползва само `re`.

### 4.3 Валидация (`validator.py`)

- `max_digit_mismatch_ratio = 0.0` прави **всяка** разлика в цифри грешка. Дати и формати (`1,000` vs `1000`) падат.
- Проверката е по **отделни цифри** (set от `0–9`), не по числа — `"12"` и `"21"` имат един и същ set `{1,2}`.
- `filter_valid(..., include_warnings=False)` по подразбиране **изхвърля** редове само с предупреждения (шум). `examples/basic_pipeline.py` ползва това и реже валидни данни.
- `check_alignment_chars` и `min_similar_words_ratio` са мъртъв конфиг.

### 4.4 Дедупликация (`deduper.py`)

- Fuzzy MinHash LSH може да даде false positives; няма последваща точна Jaccard проверка.
- Не прави first exact, after fuzzy.
- Хешира source+target заедно — близки двойки с различен превод може да се слеят (губи се валидна алтернатива).
- Неизползван import: `hashlib`.

### 4.5 Конвертор (`converter.py`)

- `to_hf_dataset`: `random.shuffle` **без seed** — split-овете не са възпроизводими.
- `convert()` не прокисва `train_ratio` / instruction към вътрешните методи.
- Alpaca/ShareGPT instruction не прави `.format(src=..., tgt=...)`.
- Няма ChatML / OpenAI `messages`, Llama-Factory, Unsloth.
- Няма двупосочен експорт (EN→BG и BG→EN).
- Зарежда всички записи в памет преди запис.

### 4.6 Analyzer (`analyzer.py`)

- Държи **всички** дължини в списъци — тежко при милиони TU.
- „Token counts“ са `split()` / `\S+`, не tokenizer (tiktoken / SentencePiece).
- `duplicates_found` брои излишни срещания, не уникални групи дубликати.
- Няма хистограми, quality score, оценка дали корпусът стига за fine-tune.

### 4.7 CLI (`cli.py`)

- Имена на опции не съвпадат с README (виж таблицата в §3).
- `pipeline` винаги clean+dedupe; при малък файл `max(1, int(n * ratio))` може да остави train почти празен.
- `clean` записва JSONL дори при неизвестен суфикс (не TMX).

### 4.8 Уеб API (`web_api.py`)

- Слуша на `0.0.0.0:8000` — достъпен в LAN.
- CORS `allow_origins=["*"]` + `allow_credentials=True`.
- Целият корпус е в `_STORAGE` (RAM), без TTL и без лимит.
- Качените файлове остават в `src/tmx_processor/_uploads/` завинаги.
- Няма лимит за размер на upload.
- `clean` / `dedupe` мутират сесията на място — няма undo / snapshot.
- Ключът е MD5 от `id(units)` — къс, теоретично колизии.
- Неизползвани import-и: `asdict`, `StaticFiles`, `ValidationConfig`.
- Boolean Form полета зависят от това как браузърът праща `true`/`on`.

### 4.9 Тестове и опаковане

- `examples/test_basic.py` е скрипт с print/assert, не pytest.
- `examples/test_web_api.py` изисква **вече пуснат** сървър на порт **8001**.
- Няма unit тестове за namespace TMX, числа при punctuation, empty splits, filter_valid.
- README инсталацията сочи към стара директория.

---

## 5. Какво липсва за обучение на модели
> Първоначален backlog. Някои изброени функции вече са реализирани в core/CLI; използвай актуалния списък в „Текущ статус“ и §5 само за незавършените точки.

Това е основната функционална дупка спрямо заявената цел.

1. **Филтър по езикова двойка** — задължително при смесени TM.
2. **Оценка на качество / alignment** — length ratio вече има; липсват LaBSE/COMET-lite, script mismatch (латиница vs кирилица), identical-except-case.
3. **Още training формати** — ChatML / OpenAI `messages`, Llama-Factory, Unsloth; български instruction шаблони с `{src}` / `{tgt}`.
4. **Двупосочен експорт** (EN→BG и BG→EN като отделни редове).
5. **Сливане на няколко TMX** + дедуп между файлове.
6. **Стратифициран split** по езикова двойка, не само random shuffle.
7. **Streaming към диск** — converter/analyzer държат всичко в списъци (проблемно над ~милиони TU).
8. **Реални token counts** и груба оценка дали корпусът стига за fine-tune.
9. **Опция да се пазят inline тагове** като `{1}` вместо да се трият.

---

## 6. План за работа
> Исторически план от началото на проекта. Отметките не са актуален статус; актуалните приоритети са в началната таблица.

### Стъпка A — Стабилност (първа)

Цел: реални TMX файлове да се парсват коректно, данните да не се чупят тихо, документацията да съвпада с CLI/API.

- [ ] Namespace-aware парсер (`_localname` навсякъде; iterparse без крехък `tag=`)
- [ ] Punctuation да не чупи числа (`29.99`, `1,000`)
- [ ] Възпроизводими HF splits (`random.seed`)
- [ ] `filter_valid`: предупрежденията да не дропват редове по подразбиране
- [ ] `.gitignore` (`.venv`, `__pycache__`, `_uploads`, изходи)
- [ ] `LICENSE` (MIT, както в README)
- [ ] CLI aliases: `--fmt`, `--report`; pipeline `--clean/--no-clean`, `--dedupe/--no-dedupe`
- [ ] Alpaca/ShareGPT: интерполация `{src}` / `{tgt}` в instruction
- [ ] README: реални пътища, реални имена на методи и опции
- [ ] Поправка на мъртъв validator конфиг или минимална реализация на alignment check

### Стъпка B — Данни за обучение

- [ ] Филтър по езикова двойка (`EN-BG` и т.н.)
- [ ] Експлозия на мултиезични TU към всички двойки
- [ ] Двупосочен експорт
- [ ] ChatML / OpenAI messages формат
- [ ] Merge на няколко TMX + глобален дедуп
- [ ] Стратифициран split по language pair
- [ ] Опция за запазване на placeholder/inline тагове

### Стъпка C — Качество и скала

- [ ] По-умен digit/placeholder check (числа, не отделни цифри)
- [ ] Streaming запис на JSONL без пълен list в RAM
- [ ] Upload лимити, TTL, изтриване на `_uploads`, bind `127.0.0.1` по подразбиране
- [ ] pytest unit + API тестове (без външен сървър; `TestClient`)
- [ ] Analyzer: running stats без гигантски списъци; опционален tokenizer
- [ ] (По-късно) alignment scoring (LaBSE и подобни) като optional extra

---

## 7. Приоритет при имплементация
> Стар приоритетен списък; текущият ред за работа е в началната таблица „Приоритет за работа“.

1. Парсър + punctuation + seed + filter_valid — иначе обучението върху реални TMX е ненадеждно.
2. Документация и CLI — иначе потребителят следва примери, които гърмят.
3. Формати и филтри за training (стъпка B).
4. Скала, тестове, API hardening (стъпка C).

---

## 8. Бележки след имплементация
> Исторически дневник на заявените промени. „Завършена“ в заглавията по-долу не означава, че всички свързани критерии са преминали проверка.

Попълва се тук след всяка завършена стъпка (какво е променено и как се проверява).

### Стъпка А - Стабилност (завършена на 2026-10-01)

**Направени промени:**

1. **Namespace-aware парсер** - Кодът вече използва `_localname` навсякъде чрез `_find_all` и `_find_one`. `iterparse` не ползва `tag=` параметър, което позволява правилно парсване на TMX файлове с namespace.

2. **Punctuation regex** - Поправен е `PUNCT_SPACE_RE` в `cleaner.py` от `([.,])(?!\s|$|\d)` на `([.,])(?=[^\d\s])`, което вече не чупи числа като `29.99` и `1,000`.

3. **Възпроизводими HF splits** - Кодът вече използва `random.Random(seed)` на ред 237-238 в `converter.py`, което прави split-овете възпроизводими.

4. **filter_valid** - Поправен е методът в `validator.py` да не дропва валидни редове с предупреждения по подразбиране. Сега просто връща всички валидни единици.

5. **.gitignore** - Създаден е `.gitignore` файл с правилни изключения за Python, виртуални среди, `_uploads`, изходни директории и IDE файлове.

6. **LICENSE** - LICENSE файлът вече съществува с MIT лиценз.

7. **CLI aliases** - CLI вече поддържа `--fmt`, `--report`, `--clean/--no-clean`, `--dedupe/--no-dedupe` както е документирано.

8. **Alpaca/ShareGPT интерполация** - Методът `_render_template` в `converter.py` вече интерполира `{src}` и `{tgt}` в instruction templates.

9. **README поправки** - Поправени са пътищата от старата директория към текущата (`C:\Users\k.petrov\Desktop\TMX`), имената на методи (`clean_units` вместо `clean`), и опции на CLI (`-o` вместо позиционен аргумент, `instruction_tmpl` → `instruction`). Премахнати са `file:///` линковете.

10. **Validator конфиг** - `_check_alignment_chars` и `_check_similar_words` вече се извикват в `validate` метода и работят коректно.

**Как се проверява:**
- Стартирай `examples/basic_pipeline.py` за проверка на основния workflow
- Стартирай `tmx-proc --help` за проверка на CLI aliases
- Провери дали `29.99` и `1,000` не се чупят при почистване

### Стъпка Б - Данни за обучение (завършена на 2026-10-01)

**Направени промени:**

1. **Филтър по езикова двойка** - Добавен е `language_pairs` параметър в `CleanConfig` и метод `_check_language_pair` в `DataCleaner`. CLI поддържа `--lang-pairs` за филтриране (напр. `EN-BG,BG-EN`).

2. **Експлозия на мултиезични TU** - Добавен е метод `_parse_tu_expanded` в `TMXParser`, който разлага TU с 3+ езика към всички възможни двойки. Параметър `expand_multilingual` в `iter_units` и `parse_all`. CLI поддържа `--expand` флаг.

3. **Двупосочен експорт** - Добавен е `bidirectional` параметър в `ConvertOptions` и метод `_reverse_unit` в `DataConverter`. CLI поддържа `--bidirectional` флаг за експорт и в обратна посока.

4. **ChatML / OpenAI messages формат** - Добавени са нови формати `CHATML` и `OPENAI` в `OutputFormat` enum. Добавени са методи `_to_chatml` и `_to_openai` в `DataConverter`. Обновен е README с 10 формата.

5. **Merge на няколко TMX** - Добавен е метод `merge_tmx_files` в `DataDeduper`, който парсва множество TMX файлове и прилага глобална дедупликация. Добавена е нова CLI команда `merge`.

6. **Стратифициран split по language pair** - Добавен е `stratify_by_lang` параметър в `to_hf_dataset` метода. Кодът групира по езикови двойки и прилага split-овете вътре във всяка група. CLI поддържа `--stratify` флаг.

7. **Запазване на placeholder/inline тагове** - Добавен е `preserve_tags` параметър в `TMXParser.__init__` и логика в `_get_text_recursive` за запазване на тагове като `{0}`, `{1}` placeholder-и. Добавен е `preserve_placeholders` в `CleanConfig`. CLI поддържа `--preserve-tags` флаг.

**Променени файлове:**
- `src/tmx_processor/cleaner.py` - language_pairs филтър, preserve_placeholders
- `src/tmx_processor/parser.py` - expand_multilingual, preserve_tags
- `src/tmx_processor/converter.py` - bidirectional, ChatML/OpenAI формати, stratified split
- `src/tmx_processor/deduper.py` - merge_tmx_files
- `src/tmx_processor/cli.py` - нови CLI опции и команди
- `README.md` - обновен с 10 формата

**Как се проверява:**
- `tmx-proc parse file.tmx --expand` за мултиезична експлозия
- `tmx-proc clean file.tmx -o out.jsonl --lang-pairs EN-BG` за филтър по език
- `tmx-proc convert file.tmx -o out.jsonl --fmt chatml --bidirectional` за нови формати
- `tmx-proc merge file1.tmx file2.tmx -o merged.jsonl` за сливане
- `tmx-proc pipeline file.tmx -o out --fmt hf_dataset --stratify` за стратифициран split

### Стъпка В - Качество и скала (завършена на 2026-10-01)

**Направени промени:**

1. **По-умен digit/placeholder check** - Regexът `DIGIT_RE` е променен от `\d` към `\d+`, което улавя цели числа, не отделни цифри. Сега `"12"` и `"21"` се третират като различни числа, а не като еднакъв set от цифри.

2. **Streaming запис на JSONL** - Добавен е метод `_write_jsonl_streaming` в `DataConverter`, който пише ред по ред без да зарежда всичко в RAM. Параметър `streaming` в `to_jsonl` за активиране.

3. **Upload лимити, TTL, изтриване на _uploads** - Добавени са:
   - `MAX_UPLOAD_SIZE = 100 MB` лимит
   - `SESSION_TTL = 1 hour` за автоматично изчистване на стари сесии
   - `_cleanup_old_sessions()` функция
   - `_TIMESTAMPS` dict за проследяване на сесии
   - Threading lock за thread-safe operations
   - `DEFAULT_HOST = "127.0.0.1"` вместо `0.0.0.0`
   - CORS ограничен до localhost
   - `--cleanup-uploads` флаг за изтриване на качените файлове при стартиране

4. **pytest unit + API тестове** - Създадена е `tests/` директория с:
   - `test_parser.py` - тестове за TMXParser
   - `test_cleaner.py` - тестове за DataCleaner
   - `test_validator.py` - тестове за DataValidator
   - `test_web_api.py` - API тестове с TestClient (без външен сървър)
   - `pytest.ini` - конфигурация за pytest
   - Добавен е `httpx` в dev dependencies
- Първоначално е добавен `httpx` в dev dependencies; заменен е с `httpx2`, след като Starlette декларира `httpx` fallback-а deprecated.

5. **Analyzer running stats** - `DatasetStats` вече използва running statistics вместо да държи всички дължини в списъци:
   - `source_length_sum`, `target_length_sum` за суми
   - `source_length_count`, `target_length_count` за бройки
   - `source_length_min/max`, `target_length_min/max` за min/max
   - `source_word_sum/count/min/max`, `target_word_sum/count/min/max` за думи
   - Добавен е `use_tokenizer` параметър в `DataAnalyzer` за опционално използване на tiktoken
   - Добавен е `tokenizer` optional dependency в pyproject.toml

**Променени файлове:**
- `src/tmx_processor/validator.py` - digit regex
- `src/tmx_processor/converter.py` - streaming JSONL
- `src/tmx_processor/web_api.py` - upload лимити, TTL, security
- `src/tmx_processor/analyzer.py` - running stats, tokenizer
- `tests/` - нова директория с тестове
- `pytest.ini` - нов файл
- `pyproject.toml` - обновени dependencies

**Как се проверява:**
- `pytest tests/` за изпълнение на всички тестове
- `pytest tests/test_parser.py` за конкретен модул
- `pytest tests/test_web_api.py` за API тестове
- `python -m tmx_processor.web_api --cleanup-uploads` за изтриване на upload-и
- `analyzer = DataAnalyzer(use_tokenizer=True)` за използване на tiktoken
