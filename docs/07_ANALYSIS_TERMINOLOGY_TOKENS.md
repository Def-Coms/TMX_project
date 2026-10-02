# 📊 Статистика, Токени и Терминология

Модулът `analyzer.py` осигурява задълбочен аналитичен преглед на паралелния корпус, изчислява необходимите токени за популярни LLM модели и автоматично извлича терминологични речници.

---

## 🧮 1. Токен калкулатор за LLM модели (`estimate_llm_tokens`)

Функцията `estimate_llm_tokens()` оценява точния брой токени, необходими при фино конфигуриране (fine-tuning) на популярни големи езикови модели:

- **Llama-3 Tokenizer**
- **Qwen Tokenizer**
- **GPT-4 Tokenizer**
- **Mistral Tokenizer**

---

## 📋 2. Доклад за готовност за Fine-Tuning (`readiness_report`)

Анализаторът проверява дали корпусът разполага с достатъчно валидни данни за качествен fine-tuning и изчислява препоръчителния брой обучения (epochs):

```python
stats = analyzer.analyze(units)
readiness = stats.readiness_report()

print("Статус:", readiness["dataset_status"])
print("Готов ли е?", readiness["is_ready"])
print("Очаквани Llama-3 токени:", readiness["token_estimates"]["llama3_estimated_tokens"])
print("Препоръчителни епохи за обучение:", readiness["recommended_epochs"])
```

---

## 📖 3. Автоматично извличане на терминология (`extract_terminology`)

Функцията `extract_terminology(units, min_freq=2)` анализира паралелните сегменти и извлича най-често срещаните специфични термини и техни преводи:

```python
terms = analyzer.extract_terminology(units, min_freq=2, max_terms=30)
for t in terms[:5]:
    print(f"{t['source_term']} ➔ {t['target_term']} (Честота: {t['frequency']})")
```

---

## 🔍 4. Търсачка за Конкорданс (`search_concordance`)

Методът `search_concordance(units, query)` позволява бързо търсене на конкретни думи или фрази в целия паралелен корпус:

```python
matches = analyzer.search_concordance(units, query="artificial intelligence", max_results=10)
for m in matches:
    print(f"[{m['id']}] {m['source_text']} === {m['target_text']}")
```
