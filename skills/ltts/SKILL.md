---
name: ltts
description: Озвучить текст локально (русский, английский, немецкий, офлайн) через CLI ltts — Silero, Piper, RHVoice. Используй, когда нужно сгенерировать аудио/голос из текста, озвучить ответ, сделать войсовер или проиграть фразу вслух.
---

# ltts — локальный синтез речи

`ltts` уже установлен (`ltts doctor` покажет, какие движки и голоса доступны).

## Озвучить

```bash
ltts say "Текст" --json                    # -> {"ok":true,"path":"...wav","duration":2.1,"voice":"silero:kseniya",...}
ltts say "Текст" -o /abs/path/out.mp3 --json
cat long.txt | ltts say -v rhvoice:anna -o out.ogg --json
ltts say "Текст" --play                    # проиграть через динамики
```

- `-v`: `engine:voice` (`silero:kseniya`, `silero:aidar`, `piper:denis`, `rhvoice:anna`), только имя или только движок.
- `--lang auto|ru|en|de`: по умолчанию язык определяется сам, и под текст берётся голос нужного языка того же движка и пола (или другого движка, если в этом нет такого языка) (`requested_voice` в JSON покажет замену).
- `-s`: скорость 0.25–4.0. `-f`: wav|mp3|ogg|opus|flac|pcm (по умолчанию из расширения `-o`, иначе wav).
- Без `-o` файл кладётся в `<данные ltts>/out/` (`~/.local/share/ltts` на macOS/Linux, `%LOCALAPPDATA%\ltts` на Windows), путь — в `path`.
- На Windows RHVoice недоступен — бери silero или piper.
- `--rate 48000`: одна частота на выходе для всех движков (иначе Silero 48k, Piper 22.05k, RHVoice 24k). Обязательно, если склеиваешь файлы.
- Ошибка: код выхода 1 и `{"ok":false,"error":"..."}` при `--json`. Порядок ключей JSON фиксированный.
- Если `ltts serve` завис, через `--timeout` (по умолчанию 120 с) синтез пойдёт локально: `"via":"local"` и поле `fallback`.
- Что-то сломано: `ltts doctor --verify --json` проверит модели, битые удалит, и при следующем вызове они скачаются заново.

## Выбор голоса

- Русский: `silero:kseniya` / `silero:xenia` (жен.), `silero:aidar` (муж.). Английский: `silero:en_0`, `piper:lessac` / `piper:ryan`. Немецкий: `silero:eva_k` (жен.), `piper:thorsten` (муж.).
- Максимальная скорость или длинные тексты: `rhvoice:anna` / `rhvoice:aleksandr` (macOS/Linux).
- `ltts voices --installed --json` — что уже скачано; нескачанные голоса скачаются при первом вызове.

## Советы

- Silero понимает ударения через `+` перед гласной: `з+амок` / `зам+ок`.
- Цифры у Silero превращаются в слова без согласования падежей; если нужна точность, пиши числа словами.
- Если запущен `ltts serve`, вызовы быстрее (модели прогреты) — ничего менять не нужно.
