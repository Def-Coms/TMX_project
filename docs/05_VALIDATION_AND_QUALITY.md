# ✅ Валидация и Quality Scoring

Модулът `validator.py` осигурява динамична оценка на качеството (**Quality Score** от 0.0 до 100.0) и задълбочена валидация на паралелните сегменти.

---

## 🎯 Изчисление на Quality Score (0.0 – 100.0)

Функцията `calculate_quality_score(unit)` анализира преводния сегмент и прилага следните санкции:

1. **Разминаване на дължините**:
   - При съотношение > 3.0 между източника и превода се налага линейна санкция до -30 точки.
2. **Числови несъответствия**:
   - При разминаване в числата, техния ред или повторение се налага санкция до -40 точки.
3. **Непреведен еднакъв текст**:
   - Ако изходният текст и преводът са идентични (при различни езикови кодове), се налага санкция от -50 точки.
4. **Проверка за азбука/скрипт (Script Check)**:
   - За кирилски езици (`BG`, `RU`, `UK`, `MK`, `SR`), ако целевият текст съдържа повече латински символи отколкото кирилски, се налага санкция от -40 точки.

---

## 💻 Пример за използване през Python API

```python
from tmx_processor import DataValidator, ValidationConfig, TranslationUnit

# Настройка на праг за качество
config = ValidationConfig(
    require_both_nonempty=True,
    max_digit_mismatch_ratio=0.5,
    min_quality_score=70.0,  # Изисквай минимум 70/100 точки за валидност
)

validator = DataValidator(config)

unit_good = TranslationUnit(
    tu_id="1", source_lang="EN", target_lang="BG",
    source_text="Welcome to the platform.",
    target_text="Добре дошли в платформата."
)

result = validator.validate(unit_good)
score = validator.calculate_quality_score(unit_good)

print(f"Качествен дубъл? {result.is_valid}")
print(f"Качествен резултат: {score}/100")
```

---

## 📊 Генериране на валидационен отчет (`report`)

Методът `report(units)` генерира пълен обобщен отчет:

```python
report = validator.report(units)
print(f"Общо единици: {report['total']}")
print(f"Валидни: {report['valid']} ({report['valid_pct']:.1f}%)")
print(f"Грешки: {report['error_counts']}")
print(f"Предупреждения: {report['warning_counts']}")
```
