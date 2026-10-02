# 🧹 Почистване и PII Анонимизиране

Модулът `cleaner.py` предоставя богат набор от правила за нормализация на текста, премахване на шум и сигурно анонимизиране на чувствителни лични данни (PII).

---

## ✨ Ключови правила за почистване

1. **Unicode Нормализация (`NFKC`)**:
   - Преобразува нестандартни символи, ширинни вариации и диакритични знаци в каноничен вид.
2. **HTML & URL Премахване**:
   - Безопасно премахва HTML тагове, скриптове, линкове и имейли.
3. **Запазване на Placeholders**:
   - Опция `preserve_placeholders=True` запазва променливи като `{0}`, `%s`, `printf` формати и placeholders вътре в HTML атрибути.
4. **Запазване на числа в пунктуацията**:
   - Нормализира пунктуацията без да чупи десетични числа и запетаи за хиляди (напр. `29.99` и `1,000` остават непокътнати).
5. **PII Redactor / Анонимизатор (`anonymize_pii`)**:
   - Автоматично открива и маскира чувствителни лични данни в източника и превода:
     - ✉️ Имейл адреси (`john@example.com`)
     - 📞 Телефонни номера (`+359 888 123 456`)
     - 💳 Номера на кредитни/дебитни карти (`4532 1123 8890 1234`)
     - 🏛️ IBAN банкови сметки (`BG80BNBG91234567890123`)
   - Заменя откритите лични данни с `[REDACTED]`.

---

## 💻 Пример за използване през Python API

```python
from tmx_processor import DataCleaner, CleanConfig, TranslationUnit

# Конфигурация за почистване и анонимизация
config = CleanConfig(
    min_length=2,
    max_length_ratio=3.0,
    remove_html_tags=True,
    remove_urls=True,
    anonymize_pii=True,             # Маскиране на лични данни
    pii_mask="[REDACTED]",
    language_pairs=["EN-BG"],       # Филтрирай само за EN-BG
    remove_untranslated=True,       # Премахни непреведени копия
)

cleaner = DataCleaner(config)

unit = TranslationUnit(
    tu_id="101",
    source_lang="EN", target_lang="BG",
    source_text="Call +359888123456 or email john@company.com for order #55.",
    target_text="Обадете се на +359888123456 или пипете на john@company.com за поръчка #55."
)

cleaned = cleaner.clean_unit(unit)
print("Почистен изход:", cleaned.source_text)
print("Почистен превод:", cleaned.target_text)
# Изход:
# Почистен изход: Call [REDACTED] or email [REDACTED] for order #55.
# Почистен превод: Обадете се на [REDACTED] или пипете на [REDACTED] за поръчка #55.
```

---

## ⚙️ Конфигурационни опции (`CleanConfig`)

| Параметър | Тип | Подразбиране | Описание |
|-----------|-----|--------------|----------|
| `min_length` | `int` | `1` | Минимална дължина в символи |
| `max_length` | `int` | `10000` | Максимална дължина в символи |
| `max_length_ratio` | `float` | `3.0` | Максимално съотношение между източника и превода |
| `remove_html_tags` | `bool` | `True` | Премахване на HTML тагове |
| `preserve_placeholders` | `bool` | `False` | Запазване на placeholders (`{0}`, `%s`) |
| `anonymize_pii` | `bool` | `False` | Автоматично анонимизиране на лични данни |
| `pii_mask` | `str` | `"[REDACTED]"` | Маска за заместване на PII |
| `language_pairs` | `List[str]` | `None` | Списък с позволени езикови двойки (напр. `["EN-BG"]`) |
| `remove_untranslated` | `bool` | `True` | Изхвърляне на непреведени копия |
