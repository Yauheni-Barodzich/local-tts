# Словарь произношения

Каталог по умолчанию: `%LOCALAPPDATA%\ltts\pronunciation` (Windows) или `~/.local/share/ltts/pronunciation`.

Не кладите большие базы в `config.json` — только настройки:

```json
{
  "pronunciation": {
    "enabled": true,
    "paths": ["D:/data/my-pronunciation"],
    "include": ["**/*.json", "**/*.jsonl"]
  }
}
```

Отключить: `"enabled": false`, `LTTS_PRONUNCIATION=0` или переключатель на странице **Настройки** (`/settings` в веб-морде).

## Форматы

**JSON** — один объект или секции:

```json
{
  "words": { "замок": "з+амок", "лtts": "эл-те-те-эс" },
  "phrases": { "не смотря ни на что": "не см+отря ни на что" },
  "english": { "nginx": "эндж+ин-икс" }
}
```

Плоский JSON `{ "слово": "произношение" }` = секция `words`.

**JSONL** — по строке на запись (удобно для больших баз и догрузки):

```jsonl
{"k":"замок","v":"з+амок","t":"word"}
{"k":"GitLab CI","v":"г+итлаб си+ай","t":"phrase"}
{"k":"kubernetes","v":"куберн+етис","t":"english"}
```

Поля: `k` / `v`, тип `t`: `word` | `phrase` | `english` (или `lang":"en"`).

## Порядок и объём

- Подкаталоги `ru/`, `en/` и т.д. — для удобства; загружаются все `*.json` / `*.jsonl`.
- Файлы сортируются по пути; **поздний перекрывает ранний**.
- Кэш сбрасывается при изменении mtime файлов; принудительно: `ltts lexicon --reload`.
- **Слова** (100k+): O(1) на слово в тексте.
- **Фразы**: перебор по длине; для десятков тысяч фраз лучше выносить редкие фразы в отдельные файлы или дублировать как отдельные `word` там, где можно.

Применяется при **Silero ru** после чисел→слова: русские замены, затем латиница (`english` + встроенный словарь в коде).

Проверка: `ltts lexicon`, `ltts doctor`.

## Импорт RUAccent / Supertonic

Скрипт `scripts/ruaccent_to_lexicon.py` переводит JSON-словарь `слово → ударение` в JSONL для каталога произношения:

- RUAccent: в значении уже есть `+` перед ударной гласной.
- Supertonic: комбинируемый acute (U+0301) → `+`.
- По умолчанию отбрасываются омографы (`--omographs omographs.json.gz`), слова длиннее 9 букв, односложные и строки без явного ударения.

```powershell
# один раз: скачать в кэш и собрать JSONL (файлы HF ~21 MB + 219 KB)
$cache = "$env:LOCALAPPDATA\ltts\cache\ruaccent"
New-Item -ItemType Directory -Force -Path $cache | Out-Null
curl.exe -fsSL -o "$cache\accents.json.gz" https://huggingface.co/ruaccent/accentuator/resolve/main/dictionary/accents.json.gz
curl.exe -fsSL -o "$cache\omographs.json.gz" https://huggingface.co/ruaccent/accentuator/resolve/main/dictionary/omographs.json.gz
uv run python scripts/ruaccent_to_lexicon.py -i "$cache\accents.json.gz" -o "$env:LOCALAPPDATA\ltts\pronunciation\ruaccent-words.jsonl" --omographs "$cache\omographs.json.gz" --format plus
ltts lexicon --reload
```
