# ltts — локальный синтез речи

Silero, Piper и RHVoice — русский, английский и немецкий в одной команде. Всё работает офлайн.

- **CLI для агентов**: `--json`, stdin, понятные коды выхода, никакого интерактива
- **MCP-сервер**: `ltts mcp` — инструменты `speak` и `list_voices`
- **OpenAI-совместимый API**: `POST /v1/audio/speech` — подходит любой клиент OpenAI TTS
- **Веб-морда** для людей: `ltts serve --open`

## Установка

**macOS / Linux:**

```bash
curl -fsSL https://raw.githubusercontent.com/nikitakashin/local-tts/master/install.sh | sh
```

или из клона: `./install.sh` (или `make install`). Без сборки RHVoice: `... | sh -s -- --no-rhvoice`.

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/nikitakashin/local-tts/master/install.ps1 | iex
```

или из клона: `powershell -ExecutionPolicy Bypass -File install.ps1`.

| | macOS | Linux | Windows |
|---|---|---|---|
| Silero, Piper | ✓ (Apple Silicon и Intel) | ✓ (x86_64, arm64; torch ставится CPU-шный) | ✓ (x86_64) |
| RHVoice | ✓ собирается из исходников | ✓ собирается из исходников | — готовых сборок нет |
| Воспроизведение `--play` | afplay | paplay / pw-play / aplay / ffplay | winsound |
| Данные | `~/.local/share/ltts` | `$XDG_DATA_HOME/ltts` (`~/.local/share/ltts`) | `%LOCALAPPDATA%\ltts` |

Установщик ставит [uv](https://docs.astral.sh/uv/) (если его нет), затем `ltts` с Python 3.12 в изолированное окружение,
качает голоса по умолчанию и собирает RHVoice из исходников (1–3 минуты; нужны Xcode CLT на macOS или
`cmake g++ git` на Linux). Если RHVoice не собран, он соберётся сам, когда в первый раз выберешь его голос. ffmpeg не нужен: mp3/ogg/opus/flac кодируются через libsndfile.

Где лежат данные — в таблице выше; меняется через `LTTS_HOME`.

## CLI

```bash
ltts say "Привет, мир" --play                  # синтез + проигрывание, в stdout — путь к файлу
echo "Текст из пайпа" | ltts say -o out.mp3     # формат берётся из расширения
ltts say "Быстрее" -v piper:denis -s 1.3 --json # метаданные в JSON
ltts say "Hello from local TTS"                 # английский: сам возьмёт английский голос
ltts say "Привет" -f opus -o - > out.ogg        # аудио прямо в stdout
ltts say "Склейка" -v piper:denis --rate 48000  # единая частота для пайплайнов (иначе 48k/22.05k/24k)
ltts voices [--installed] [--engine rhvoice] [--lang en] [--json]
ltts download rhvoice:tatiana piper:ruslan      # или --all rhvoice; --force — перекачать
ltts default piper:denis                        # голос по умолчанию (для языка этого голоса)
ltts default piper:lessac                       # ...и для английского

ltts doctor [--verify] [--json]                 # что установлено, что сломано; --verify сверяет sha256 моделей
```

Голос задаётся как `engine:voice` (`silero:kseniya`), просто имя (`denis`) или просто движок (`rhvoice`).
Нескачанный голос скачается при первом использовании.

**Язык** определяется по тексту (`--lang auto`, по умолчанию). Если текст на английском, а голос русский,
берётся английский голос того же движка и пола: `kseniya → silero:en_0`, `aidar → silero:en_2`,
`irina → piper:lessac`, `anna → rhvoice:slt`. Это работает и в обратную сторону. В `--json` заменённый голос виден в `requested_voice`.
`--lang ru|en|de` фиксирует язык: тогда явно выбранный голос используется как есть.
Английские слова внутри русской фразы читает русский голос, поэтому с акцентом.

Если запущен `ltts serve`, команда `ltts say` идёт через него: модели уже прогреты, ответ за ~0.3 с вместо ~1.8 с
(`"via": "server"`). Если сервер не ответил за `--timeout` (120 с, `LTTS_TIMEOUT`), синтез идёт локально,
и в JSON появляется поле `fallback`. `--local` — сразу синтезировать в процессе.
Повторный `ltts serve` на занятом порту не запускается: если там уже ltts, он предложит переиспользовать его.

**JSON** у `say` всегда в одном порядке ключей: `ok, path, format, bytes, engine, voice, [requested_voice], lang, duration,
sample_rate, synth_seconds, via, [fallback]`. Ошибка: код выхода 1 и `{"ok": false, "error": "..."}`.

**Частота:** у движков она разная (Silero 48 кГц, Piper 22.05 кГц, RHVoice 24 кГц). Для склейки и видео
задавай `--rate 48000` (или `LTTS_RATE=48000` на всё). mp3/opus поддерживают не все частоты: тогда берётся ближайшая
допустимая, и фактическая указана в `sample_rate`.

**Надёжность загрузок:** модель скачивается во временный `.part`, сверяется длина, считается sha256,
потом файл атомарно переименовывается и рядом пишется маркер `.complete`. Голос считается установленным, только если
маркер на месте и размер совпадает. Если файл всё равно не загрузился, он удаляется и скачивается заново при том же вызове.

**`out/`** (файлы без `-o`) хранит последние 200 файлов (`LTTS_OUT_KEEP`, `0` — без ротации).

## Голоса

| Движок | Русский | English | Deutsch | Скорость | Особенности |
|---|---|---|---|---|---|
| silero | kseniya, xenia, baya, aidar, eugene (v5_5_ru) | en_0, en_14, en_99 (жен.), en_2, en_13, en_79 (муж.) — и любой из en_0…en_117 (v3_en) | **eva_k** (жен., по умолч.), hokuspokus, karlsson, bernd_ungerer, friedrich (v3_de) | ~0.5 с / фраза | лучшее качество; ударения `+` (`з+амок`); числа — словами автоматически |
| piper | irina, denis, dmitri, ruslan | lessac, amy, ryan, joe (US), cori, alan (UK) | **thorsten** (муж., high), eva_k, pavoque, karlsson, kerstin, ramona | ~0.4 с | ONNX, лёгкий |
| rhvoice | anna, aleksandr, elena, tatiana, … (23) | slt, clb, lyubov, bdl, alan, ksp, evgeniy-eng, dasha-eng | — | ~0.1 с | самый быстрый, классический звук |

**Немецкий.** Латинский текст считается немецким, если в нём есть умлауты или ß, или немецких служебных слов
(und, der, ist, nicht…) больше, чем английских. Если у выбранного движка нет немецкого (RHVoice),
берётся лучший немецкий голос того же пола. Замер Whisper: `silero:eva_k` — 3.8% ошибок, `silero:karlsson` — 9%,
`piper:thorsten` — самый естественный мужской. `kerstin` и `ramona` — модели low, у них около 23% ошибок.

## Для агентов

**MCP** (Claude Code, Cursor и т.д.):

```bash
claude mcp add ltts -- ltts mcp
```

**OpenAI API** (`ltts serve`):

```bash
curl -s localhost:8765/v1/audio/speech -H 'Content-Type: application/json' \
  -d '{"model":"silero","input":"Привет","voice":"kseniya","response_format":"mp3"}' -o out.mp3
```

`model`: `silero` | `piper` | `rhvoice` | `tts-1` (голос по умолчанию). `voice`: наш голос или OpenAI-имя
(`nova`, `onyx`, …): оно заменяется на женский или мужской голос выбранного движка на языке текста. Форматы: `mp3`, `opus`, `wav`, `flac`, `pcm`,
`aac` (для aac нужен ffmpeg).

Свой API: `GET /api/voices`, `POST /api/synth {text, voice, speed, format, lang, rate}` (метаданные в заголовке `X-LTTS-Meta`),
`GET /api/status`. В OpenAI-запросе можно передать расширение `sample_rate`.

Ошибки — всегда JSON в формате OpenAI: `{"error": {"message", "type", "param", "code"}}`
(на `/api/*` есть ещё `detail`). Коды: 400 — неверный запрос (`invalid_request_error`), 503 — модель повреждена
(`code: model_unavailable`, перекачается при следующем запросе), 500 — внутренняя ошибка (`server_error`).

Готовая инструкция для агента — [skills/ltts/SKILL.md](skills/ltts/SKILL.md).

## Разработка

```bash
make            # список команд
make setup      # .venv + голоса + RHVoice
make serve      # веб-морда на http://127.0.0.1:8765
make say TEXT="Привет" VOICE=piper:denis
```

Лицензии моделей разные: модели Silero — некоммерческие (CC BY-NC), голоса RHVoice и Piper — у каждого своя.
