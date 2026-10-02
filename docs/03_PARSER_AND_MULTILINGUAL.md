# 📥 Парсване и Многоезичност

Модулът `parser.py` осигурява високопроизводително, стрийминг парсване на TMX (Translation Memory eXchange) файлове от произволен размер (дори файлове над 1 GiB).

---

## 💡 Основни характеристики

1. **Namespace-Aware XML Streaming (`lxml.iterparse`)**:
   - Автоматично борави с XML namespaces и локални тагове (`tu`, `tuv`, `seg`, `note`, `prop`), игнорирайки разлики в декларациите за namespace (`xmlns`).
2. **Възстановяване при счупен XML (`XML Recovery`)**:
   - Автоматично пропуска непозволени XML 1.0 контролни знаци и лошо форматирани фрагменти, издавайки предупреждения вместо да срива процеса.
3. **Откриване на езици и езикови двойки**:
   - Методите `get_available_languages()` и `get_language_pairs()` сканират TMX файла и връщат списък с всички намерени езикови кодове (напр. `EN`, `BG`, `DE`) и конкретни езикови двойки (напр. `("EN", "BG")`).
4. **Експлозия на мултиезични TMX файлове (`expand_multilingual`)**:
   - При TMX файлове, съдържащи 3 или повече езика в един `<tu>` (напр. EN, BG, DE), парсърът разлага единиците към всички комбинации от двойки (`EN→BG`, `EN→DE`, `BG→DE` и т.н.).

---

## 💻 Пример за използване през Python API

```python
from pathlib import Path
from tmx_processor.parser import TMXParser

# 1. Инициализация
tmx_path = Path("examples/sample_en_bg.tmx")
parser = TMXParser(tmx_path, preserve_tags=True)

# 2. Четене на метаданни от заглавната част (Header)
header = parser.parse_header()
print(f"Изходен език: {header.source_lang}")
print(f"Инструмент: {header.creation_tool}")

# 3. Откриване на наличните езици
langs = parser.get_available_languages()
pairs = parser.get_language_pairs()
print(f"Налични езици: {langs}")
print(f"Езикови двойки: {pairs}")

# 4. Стрийминг обхождане на единиците (пази RAM)
for unit in parser.iter_units(stream=True):
    print(f"[{unit.source_lang}] {unit.source_text} -> [{unit.target_lang}] {unit.target_text}")

# 5. Мултиезична експлозия за TMX с 3+ езика
multilingual_units = parser.parse_all(expand_multilingual=True)
print(f"Общо генерирани двойки след експлозия: {len(multilingual_units)}")
```

---

## ⚙️ Опции на TMXParser

| Параметър | Тип | Подразбиране | Описание |
|-----------|-----|--------------|----------|
| `file_path` | `Union[str, Path]` | *Задължителен* | Път до TMX файла на диска |
| `preserve_tags` | `bool` | `False` | Дали inline таговете (`bpt`, `ept`, `ph`) да се запазват като `{0}`, `{1}` placeholders |
| `expand_multilingual` | `bool` | `False` | Разлагане на 3+ езични сегменти към всички възможни двойки |
