# ltts — локальный синтез речи

Озвучивание текста **офлайн** на русском, английском и немецком. Три движка — **Silero**, **Piper**, **RHVoice** — одна команда `ltts`.

## Что умеет

| Режим | Для кого | Как запустить |
|---|---|---|
| **Командная строка** | скрипты, автоматизация | `ltts say "Привет"` |
| **Веб-интерфейс** | ручная озвучка в браузере | `ltts serve --open` |
| **Приложение Windows** | трей + окно без консоли | `ltts desktop` или `ltts-desktop.vbs` |
| **MCP** | Cursor, Claude Code и др. | `ltts mcp` |
| **HTTP API** | любой клиент OpenAI TTS | `ltts serve` → `POST /v1/audio/speech` |

Подробности по API, JSON, переменным окружения и сборке — в **[docs/REFERENCE.md](docs/REFERENCE.md)**.  
Для AI-агентов — также [skills/ltts/SKILL.md](skills/ltts/SKILL.md).

## Установка

**macOS / Linux**

```bash
curl -fsSL https://raw.githubusercontent.com/nikitakashin/local-tts/master/install.sh | sh
```

Из клона: `./install.sh` или `make install`. Без RHVoice: `... | sh -s -- --no-rhvoice`.

**Windows (PowerShell)**

```powershell
irm https://raw.githubusercontent.com/nikitakashin/local-tts/master/install.ps1 | iex
```

Из клона: `powershell -ExecutionPolicy Bypass -File install.ps1`.

После установки проверьте окружение:

```bash
ltts doctor
```

На **Windows** RHVoice не собирается — используйте Silero или Piper. Таблица платформ и путей к данным — в [справочнике](docs/REFERENCE.md#платформы-и-данные).

## Быстрый старт

```bash
# озвучить и услышать
ltts say "Привет, мир" --play

# сохранить в файл (формат из расширения)
ltts say "Текст" -o речь.mp3

# список голосов
ltts voices --installed

# веб-морда в браузере
ltts serve --open
```

Голос по умолчанию — женский Silero (**kseniya**). Свой голос: `-v piper:denis` или `ltts default piper:denis`.  
Язык текста определяется автоматически; для длинных пайпов удобен `echo "…" | ltts say -o out.wav`.

Скачать голоса заранее:

```bash
ltts download silero:kseniya piper:denis
```

## Какой голос выбрать

| Задача | Голос |
|---|---|
| Лучшее качество (RU) | `silero:kseniya`, `silero:aidar` |
| Быстро / длинные тексты (macOS, Linux) | `rhvoice:anna`, `rhvoice:aleksandr` |
| Лёгкие модели | `piper:irina`, `piper:denis` |
| English | `silero:en_0`, `piper:lessac` |
| Deutsch | `silero:eva_k`, `piper:thorsten` |

Полная таблица движков и имён — [docs/REFERENCE.md § Голоса](docs/REFERENCE.md#голоса).

**Silero (русский):** ударение через `+` перед гласной — `з+амок` / `зам+ок`. Свои формы слов — каталог [pronunciation/](pronunciation/README.md).

## Windows-приложение

После установки из репозитория: `ltts-update.bat`, затем двойной щелчок по **`ltts-desktop.vbs`** (без чёрного окна консоли). В трее — меню; внутри — тот же веб-интерфейс на WebView2.

Ярлык на рабочий стол:

```powershell
powershell -File create-desktop-shortcut.ps1
```

Сборка установщика `.exe` для распространения — в [справочнике](docs/REFERENCE.md#windows-приложение-и-сборка).

## Агенты и интеграции

**MCP** (одна строка в настройках MCP):

```bash
claude mcp add ltts -- ltts mcp
```

**OpenAI-совместимый TTS** (сервер должен быть запущен):

```bash
ltts serve
curl -s localhost:8765/v1/audio/speech -H 'Content-Type: application/json' \
  -d '{"model":"silero","input":"Привет","voice":"kseniya","response_format":"mp3"}' -o out.mp3
```

Если сервер уже крутится (в том числе из `ltts desktop`), обычный `ltts say` работает быстрее — модели уже в памяти. Поведение клиента, таймауты и эндпоинты — [docs/REFERENCE.md](docs/REFERENCE.md#интеграции-для-агентов).

## Разработка

Клон репозитория, зависимости и `make`:

```bash
make setup
make serve
```

Все команды `make` и детали dev-сборки — [docs/REFERENCE.md § Разработка](docs/REFERENCE.md#разработка-из-репозитория).

## Лицензии

Код проекта — см. репозиторий. **Модели** (Silero, Piper, RHVoice) распространяются на своих условиях; Silero — CC BY-NC (некоммерческое использование). Перед продакшеном проверьте лицензии выбранных голосов — [справочник](docs/REFERENCE.md#лицензии-моделей).
