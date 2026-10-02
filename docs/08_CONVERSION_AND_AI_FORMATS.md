# 🔄 Конвертиране и 13 AI Формата

Модулът `converter.py` осигурява експорт на почистените паралелни данни към **13 различни формата** за обучение на AI модели.

---

## 📋 Таблица на поддържаните формати (`OutputFormat`)

| Формат | `OutputFormat` enum | Предназначение | Файлово разширение |
|--------|---------------------|----------------|-------------------|
| **JSONL** | `jsonl` | Универсален ред-по-ред формат | `.jsonl` |
| **Parquet** | `parquet` | Бърз формат за pandas / HuggingFace | `.parquet` |
| **CSV** | `csv` | Стандартни таблични данни | `.csv` |
| **TSV** | `tsv` | За традиционни машинен превод (MT) системи | `.tsv` |
| **JSON** | `json` | Масив от обекти за преглед | `.json` |
| **Alpaca** | `alpaca` | Instruction tuning (`instruction`, `input`, `output`) | `.jsonl` |
| **ShareGPT** | `sharegpt` | Многоходови чат диалози (`conversations`) | `.jsonl` |
| **ChatML** | `chatml` | Chat fine-tuning с role/content | `.jsonl` |
| **OpenAI** | `openai` | OpenAI compatible fine-tuning (`messages`) | `.jsonl` |
| **DPO/ORPO** | `dpo` | Preference tuning (`prompt`, `chosen`, `rejected`) | `.jsonl` |
| **Prompt/Completion** | `prompt_completion` | Generic instruction (`prompt`, `completion`) | `.jsonl` |
| **Reasoning** | `reasoning` | Chain-of-thought модели с обосновка | `.jsonl` |
| **HuggingFace Dataset** | `hf_dataset` | Разделени `train`, `validation`, `test` splits | Папка / ZIP |

---

## 📦 Context Window Packing (`pack_context_windows`)

При фино конфигуриране на езикови модели подаването на много кратки изречения едно по едно е неефективно. Методът `pack_context_windows(units, max_chars=2048)` автоматично обединява последователни кратки сегменти в плътни контекстни блокове:

```python
from tmx_processor import DataConverter, ConvertOptions, OutputFormat

converter = DataConverter()

# 1. Обединяване на кратки изречения в прозорци от 2048 знака
packed_units = list(converter.pack_context_windows(units, max_chars=2048))

# 2. Конвертиране в Alpaca instruction формат за LLM
opts = ConvertOptions(
    instruction_template="Преведи следния текст от {src} на {tgt}:",
    language_pairs=["EN-BG"],
)
converter = DataConverter(options=opts)
converter.convert(packed_units, "output_alpaca.jsonl", fmt=OutputFormat.ALPACA)
```
