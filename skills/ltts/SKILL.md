---
name: ltts
description: Озвучить текст локально (русский и английский, офлайн) через CLI ltts — Silero, Piper, RHVoice. Используй, когда нужно сгенерировать аудио/голос из текста, озвучить ответ, сделать войсовер или проиграть фразу вслух.
---

# ltts — локальный синтез речи

`ltts` уже установлен (`ltts doctor` покажет, какие движки и голоса доступны).

## Озвучить

```bash
ltts say "Текст" --json                    # -> {"ok":true,"path":"...wav","duration":2.1,"voice":"silero:xenia",...}
ltts say "Текст" -o /abs/path/out.mp3 --json
cat long.txt | ltts say -v rhvoice:anna -o out.ogg --json
ltts say "Текст" --play                    # проиграть через динамики
```

- `-v`: `engine:voice` (`silero:xenia`, `silero:aidar`, `piper:denis`, `rhvoice:anna`), только имя или только движок.
- `--lang auto|ru|en`: по умолчанию язык определяется сам, и под английский текст берётся английский голос того же движка и пола (`requested_voice` в JSON покажет замену).
- `-s`: скорость 0.25–4.0. `-f`: wav|mp3|ogg|opus|flac|pcm (по умолчанию из расширения `-o`, иначе wav).
- Без `-o` файл кладётся в `<данные ltts>/out/` (`~/.local/share/ltts` на macOS/Linux, `%LOCALAPPDATA%\ltts` на Windows), путь — в `path`.
- На Windows RHVoice недоступен — бери silero или piper.
- `--rate 48000`: одна частота на выходе для всех движков (иначе Silero 48k, Piper 22.05k, RHVoice 24k). Обязательно, если склеиваешь файлы.
- Ошибка: код выхода 1 и `{"ok":false,"error":"..."}` при `--json`. Порядок ключей JSON фиксированный.
- Если `ltts serve` завис, через `--timeout` (по умолчанию 120 с) синтез пойдёт локально: `"via":"local"` и поле `fallback`.
- Что-то сломано: `ltts doctor --verify --json` проверит модели, битые удалит, и при следующем вызове они скачаются заново.

## Выбор голоса

- Русский: `silero:xenia` (жен.), `silero:aidar` (муж.). Английский: `kokoro:af_heart` (жен.), `kokoro:am_michael` (муж.), британский `kokoro:bf_emma` / `kokoro:bm_george`. На других платформах: `piper:lessac` / `piper:ryan`.
- Максимальная скорость или длинные тексты: `rhvoice:anna` / `rhvoice:aleksandr`.
- `ltts voices --installed --json` — что уже скачано; нескачанные голоса скачаются при первом вызове.

## Клонирование голоса (Apple Silicon)

```bash
ltts clone add me /abs/sample.wav --text "что сказано в записи" --json   # 8–20 с чистой речи
ltts say "Текст" -v clone:me --json        # OmniVoice: быстро, 24 кГц, любой язык
ltts say "Текст" -v clone:me --hq --json   # VoxCPM2: 48 кГц, медленнее, нужен --text образца
```

Клонируй только с согласия владельца голоса. В MCP есть инструмент `clone_voice(name, audio_path, text)`.

## Советы

- Silero понимает ударения через `+` перед гласной: `з+амок` / `зам+ок`.
- Цифры у Silero превращаются в слова без согласования падежей; если нужна точность, пиши числа словами.
- Если запущен `ltts serve`, вызовы быстрее (модели прогреты) — ничего менять не нужно.
