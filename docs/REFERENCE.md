# Справочник ltts

Подробности по CLI, HTTP API, переменным окружения, платформам и сборке. Краткий обзор и установка — в [README.md](../README.md).

## Платформы и данные

| | macOS | Linux | Windows |
|---|---|---|---|
| Silero, Piper | ✓ (Apple Silicon и Intel) | ✓ (x86_64, arm64; torch ставится CPU-шный) | ✓ (x86_64) |
| RHVoice | ✓ собирается из исходников | ✓ собирается из исходников | — готовых сборок нет |
| Воспроизведение `--play` | afplay | paplay / pw-play / aplay / ffplay | winsound |
| Каталог данных | `~/.local/share/ltts` | `$XDG_DATA_HOME/ltts` (`~/.local/share/ltts`) | `%LOCALAPPDATA%\ltts` |

Каталог данных переопределяется переменной **`LTTS_HOME`**.

### Установщик

Скрипты `install.sh` / `install.ps1` ставят [uv](https://docs.astral.sh/uv/) (если его нет), затем `ltts` с Python 3.12 в изолированное окружение, качают голоса по умолчанию и на macOS/Linux собирают RHVoice из исходников (1–3 минуты; нужны Xcode CLT на macOS или `cmake g++ git` на Linux). Без RHVoice: `install.sh --no-rhvoice` или `... | sh -s -- --no-rhvoice`.

Если RHVoice не собран при установке, он соберётся при первом выборе голоса RHVoice. **ffmpeg не обязателен:** mp3/ogg/opus/flac кодируются через libsndfile (для формата `aac` в API нужен ffmpeg).

## Windows-приложение и сборка

**Разработка из клона:** `ltts-update.bat` (extra `[desktop]`), затем **`ltts-desktop.bat`** / **`ltts-desktop.vbs`** (без консоли) или `ltts desktop` — трей, аватар, WebView2, сервер в одном процессе (legacy `ltts tray` и отдельный serve убраны). **Dev аватара:** только **`ltts-desktop-dev.bat`**. **Dev веб-морды:** **`ltts-web-dev.bat`** — `src/ltts/web`, live-reload в браузере (`LTTS_WEB_DEV=1`; не `ltts-web.bat` / uv tool без пересборки). (hot-reload `avatar.html`, F12; опц. `LTTS_AVATAR_DEBUG_PORT=9223` → `edge://inspect`). Ярлык: `powershell -File create-desktop-shortcut.ps1`. Иконки: `src/ltts/assets/app.ico` (пересборка: `uv run python scripts/build_app_icon.py`). Первый запуск скачивает **silero:kseniya**; данные в `%LOCALAPPDATA%\ltts`.

**Установщик (PyInstaller + Inno Setup):**

```powershell
powershell -ExecutionPolicy Bypass -File packaging/windows/build.ps1
```

Артефакты: `dist/ltts/` (onedir) и `dist/ltts-setup-<версия>.exe`. Нужен [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/web-view2/). Подпись Authenticode для Setup.exe снижает предупреждения SmartScreen.

Для терминала и агентов по-прежнему: `ltts say`, `ltts mcp`, `ltts serve` (если desktop не запущен).

## CLI

```bash
ltts say "Привет, мир" --play                  # синтез + проигрывание, в stdout — путь к файлу
echo "Текст из пайпа" | ltts say -o out.mp3     # формат из расширения
ltts say "Быстрее" -v piper:denis -s 1.3 --json
ltts say "Hello from local TTS"                 # язык по тексту → английский голос
ltts say "Привет" -f opus -o - > out.ogg        # аудио в stdout
ltts say "Склейка" -v piper:denis --rate 48000  # единая частота для пайплайнов
ltts voices [--installed] [--engine rhvoice] [--lang en] [--json]
ltts download rhvoice:tatiana piper:ruslan      # или --all rhvoice; --force — перекачать
ltts default piper:denis                        # голос по умолчанию (для языка голоса)
ltts default piper:lessac                       # ...и для английского
ltts doctor [--verify] [--json]                 # установленное; --verify сверяет sha256 моделей
ltts lexicon                                    # словарь произношения (Silero ru)
```

Голос: `engine:voice` (`silero:kseniya`), имя (`denis`) или движок (`rhvoice`). Нескачанный голос скачается при первом использовании.

### Язык и подбор голоса

Язык по тексту (`--lang auto`, по умолчанию). Если текст на английском, а голос русский — берётся английский голос того же движка и пола: `kseniya → silero:en_0`, `aidar → silero:en_2`, `irina → piper:lessac`, `anna → rhvoice:slt` (и обратно). В `--json` замена видна в `requested_voice`. `--lang ru|en|de` фиксирует язык: выбранный голос не подменяется. Английские слова внутри русской фразы читает русский голос (с акцентом).

**Немецкий:** латиница считается немецкой при умлаутах/ß или преобладании немецких служебных слов (und, der, ist, …) над английскими. Если у движка нет немецкого (RHVoice), берётся лучший немецкий голос того же пола. Замеры Whisper: `silero:eva_k` — 3.8% ошибок, `silero:karlsson` — 9%, `piper:thorsten` — самый естественный мужской; `kerstin` и `ramona` (low) — около 23% ошибок.

### Клиент и сервер

Если запущен `ltts serve`, `ltts say` идёт через него (модели прогреты, ~0.3 с вместо ~1.8 с; в JSON `"via": "server"`). Нет ответа за `--timeout` (120 с по умолчанию, `LTTS_TIMEOUT`) — локальный синтез и поле `fallback`. `--local` — всегда в процессе. Повторный `ltts serve` на занятом порту: если там уже ltts, предложит переиспользовать.

### JSON (`say`)

Порядок ключей: `ok, path, format, bytes, engine, voice, [requested_voice], lang, duration, sample_rate, synth_seconds, via, [fallback]`. Ошибка: код 1 и `{"ok": false, "error": "..."}`.

### Частота дискретизации

У движков разная родная частота (Silero 48 кГц, Piper 22.05 кГц, RHVoice 24 кГц). Для склейки и видео: `--rate 48000` или `LTTS_RATE=48000`. mp3/opus не все частоты поддерживают — берётся ближайшая допустимая, фактическая в `sample_rate`.

### Загрузка моделей

Скачивание в `.part`, проверка длины и sha256, атомарное переименование, маркер `.complete`. Голос установлен только при маркере и совпадении размера. Сбой — удаление и повтор при следующем вызове.

### Каталог `out/`

Файлы без `-o` попадают в `<LTTS_HOME>/out/`; хранятся последние **200** файлов (`LTTS_OUT_KEEP`, `0` — без ротации).

### Произношение (Silero ru)

Словарь в `pronunciation/` — см. [pronunciation/README.md](../pronunciation/README.md). Отключение: `LTTS_PRONUNCIATION=0` или `pronunciation.enabled=false` в конфиге.

## Голоса

| Движок | Русский | English | Deutsch | Скорость | Особенности |
|---|---|---|---|---|---|
| silero | kseniya, xenia, baya, aidar, eugene (v5_5_ru) | en_0, en_14, en_99 (жен.), en_2, en_13, en_79 (муж.) — и en_0…en_117 (v3_en) | **eva_k** (жен.), hokuspokus, karlsson, bernd_ungerer, friedrich (v3_de) | ~0.5 с / фраза | лучшее качество; ударения `+`; числа словами |
| piper | irina, denis, dmitri, ruslan | lessac, amy, ryan, joe (US), cori, alan (UK) | **thorsten** (муж., high), eva_k, pavoque, karlsson, kerstin, ramona | ~0.4 с | ONNX, лёгкий |
| rhvoice | anna, aleksandr, elena, tatiana, … (23) | slt, clb, lyubov, bdl, alan, ksp, evgeniy-eng, dasha-eng | — | ~0.1 с | самый быстрый |

## Интеграции для агентов

### MCP

Инструменты: `speak`, `list_voices`.

**HTTP (вместе с `ltts serve` / `ltts desktop`)** — Streamable HTTP на том же порту:

```json
{
  "mcpServers": {
    "ltts": { "url": "http://127.0.0.1:8765/mcp" }
  }
}
```

Отключить: `LTTS_MCP_HTTP=0`. Проверка: `GET /health` → поле `mcp_http`.

**stdio** (отдельный процесс, если сервер не запущен):

```bash
claude mcp add ltts -- ltts mcp
```

### OpenAI-совместимый API (`ltts serve`)

```bash
curl -s localhost:8765/v1/audio/speech -H 'Content-Type: application/json' \
  -d '{"model":"silero","input":"Привет","voice":"kseniya","response_format":"mp3"}' -o out.mp3
```

- **`model`:** `silero` | `piper` | `rhvoice` | `tts-1` (голос по умолчанию).
- **`voice`:** id ltts или OpenAI-имя (`nova`, `onyx`, …) — маппинг на пол/язык текста для выбранного движка.
- **Форматы:** `mp3`, `opus`, `wav`, `flac`, `pcm`, `aac` (aac — нужен ffmpeg).
- В запросе можно передать расширение **`sample_rate`**.

**Собственные эндпоинты:**

- `GET /api/voices`
- `POST /api/synth` — body `{text, voice, speed, format, lang, rate}`; метаданные в заголовке `X-LTTS-Meta`
- `GET /api/status`
- `GET /api/settings`, `PATCH /api/settings` — `config.json` (голоса по умолчанию, `sample_rate`, `out_keep`, `pronunciation.enabled`); веб-страница **`/settings`**
- `POST /api/doctor/verify` — сверка sha256 моделей
- `POST /api/lexicon/reload` — перечитать словарь произношения

Произношение можно отключить в UI на `/settings` или через `pronunciation.enabled` в config; большие словари — только в каталоге `pronunciation/`, не в JSON.

Ошибки — JSON в стиле OpenAI: `{"error": {"message", "type", "param", "code"}}` (на `/api/*` также `detail`). Коды: **400** — `invalid_request_error`; **503** — `model_unavailable` (перекачается при следующем запросе); **500** — `server_error`.

Готовая инструкция для агента: [skills/ltts/SKILL.md](../skills/ltts/SKILL.md).

## Переменные окружения

| Переменная | Назначение |
|---|---|
| `LTTS_HOME` | каталог данных (модели, config, out) |
| `LTTS_PORT` | порт сервера по умолчанию (8765) |
| `LTTS_URL` | базовый URL для клиента `say` (по умолчанию `http://127.0.0.1:<порт>`) |
| `LTTS_TIMEOUT` | таймаут ожидания сервера, с (120) |
| `LTTS_RATE` | частота на выходе по умолчанию |
| `LTTS_VOICE` / `LTTS_VOICE_EN` / `LTTS_VOICE_DE` | голос по умолчанию для языка |
| `LTTS_OUT_KEEP` | сколько файлов держать в `out/` (200; 0 — без лимита) |
| `LTTS_PRONUNCIATION` | `0` / `false` — выключить словарь Silero ru |
| `LTTS_SSL_VERIFY` | `1` — строгая проверка SSL при загрузках |
| `LTTS_DESKTOP_WORKER` | внутреннее: воркер desktop-приложения |

## Разработка из репозитория

```bash
make            # список команд
make setup      # .venv + голоса + RHVoice
make serve      # http://127.0.0.1:8765
make say TEXT="Привет" VOICE=piper:denis
```

## Лицензии моделей

Модели Silero — некоммерческие (CC BY-NC). Голоса RHVoice и Piper — у каждого своя лицензия; проверяйте перед коммерческим использованием.
