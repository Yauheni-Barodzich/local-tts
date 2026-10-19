/* shared: theme, icons, localStorage */
const LTTS_ICONS = {
  wave: '<path d="M2 10v3"/><path d="M6 6v11"/><path d="M10 3v18"/><path d="M14 8v7"/><path d="M18 5v13"/><path d="M22 10v3"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
  auto: '<rect width="20" height="14" x="2" y="3" rx="2"/><line x1="8" x2="16" y1="21" y2="21"/><line x1="12" x2="12" y1="17" y2="21"/>',
  settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
  loader: '<path d="M21 12a9 9 0 1 1-6.219-8.56"/>',
  alert: '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
  terminal: '<polyline points="4 17 10 11 4 5"/><line x1="12" x2="20" y1="19" y2="19"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>',
  copy: '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
};

function lttsIcon(name, cls = "") {
  return `<svg class="icon ${cls}" data-i="${name}" viewBox="0 0 24 24" aria-hidden="true">${LTTS_ICONS[name] || ""}</svg>`;
}

function lttsHydrateIcons(root = document) {
  root.querySelectorAll("svg.icon[data-i]:not([viewBox])").forEach((s) => {
    s.setAttribute("viewBox", "0 0 24 24");
    s.setAttribute("aria-hidden", "true");
    s.innerHTML = LTTS_ICONS[s.dataset.i] || "";
  });
}

const lttsStore = {
  get(k, d) {
    try {
      const v = localStorage.getItem("ltts." + k);
      return v === null ? d : JSON.parse(v);
    } catch {
      return d;
    }
  },
  set(k, v) {
    try {
      localStorage.setItem("ltts." + k, JSON.stringify(v));
    } catch {}
  },
};

const LTTS_THEMES = [["auto", "Тема: как в системе"], ["light", "Тема: светлая"], ["dark", "Тема: тёмная"]];

function lttsApplyTheme(t, btn) {
  if (t === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", t);
  if (!btn) return;
  const label = LTTS_THEMES.find(([k]) => k === t)[1];
  btn.innerHTML = lttsIcon(t === "auto" ? "auto" : t === "light" ? "sun" : "moon");
  btn.setAttribute("aria-label", label);
  btn.title = label;
}

function lttsBindTheme(btn) {
  let theme = lttsStore.get("theme", "auto");
  lttsApplyTheme(theme, btn);
  btn.onclick = () => {
    theme = LTTS_THEMES[(LTTS_THEMES.findIndex(([k]) => k === theme) + 1) % LTTS_THEMES.length][0];
    lttsStore.set("theme", theme);
    lttsApplyTheme(theme, btn);
  };
}

/** Контекст для сниппетов агентов из GET /api/settings (или минимальный fallback). */
function lttsAgentContextFromSettings(settings) {
  const s = settings || {};
  const serverUrl = typeof location !== "undefined" ? location.origin : "http://127.0.0.1:8765";
  const mcpHttp = s.integrations?.mcp_http || `${serverUrl}/mcp`;
  return {
    serverUrl,
    mcpHttpUrl: mcpHttp,
    home: s.paths?.home,
    defaultVoices: s.effective?.default_voices || { ru: "silero:kseniya", en: "silero:en_0", de: "silero:eva_k" },
    windows: !!s.platform?.windows,
    version: s.version,
  };
}

function lttsVoiceApiName(voiceId) {
  if (!voiceId) return "kseniya";
  const p = String(voiceId).split(":");
  return p.length > 1 ? p[1] : p[0];
}

function lttsBuildAgentSnippets(ctx) {
  const base = ctx.serverUrl || "http://127.0.0.1:8765";
  const mcpUrl = (ctx.mcpHttpUrl || `${base}/mcp`).replace(/\/$/, "");
  const dv = ctx.defaultVoices || {};
  const ruV = lttsVoiceApiName(dv.ru);
  const enV = lttsVoiceApiName(dv.en);
  const winLine = ctx.windows
    ? "- На Windows нет RHVoice — используй silero или piper.\n"
    : "- Быстрые длинные тексты: rhvoice:anna / rhvoice:aleksandr (macOS/Linux).\n";
  const homeLine = ctx.home ? `- Данные: \`${ctx.home}\`\n` : "";

  const skillBody = `# ltts — локальный синтез речи

Озвучивай текст **офлайн** (ru/en/de): Silero, Piper, RHVoice. Сервер уже доступен: **${base}**.

## Когда использовать
- Нужно сгенерировать аудио, войсовер, проиграть ответ вслух.
- Пользователь просит TTS, «озвучь», голосовое сообщение из текста.

## Предпочтительный порядок
1. **MCP HTTP** \`${mcpUrl}\` — при запущенном desktop/serve (инструменты \`speak\`, \`list_voices\`).
2. **MCP stdio** \`ltts mcp\` — если HTTP недоступен.
3. **CLI** \`ltts say\` — shell; при warm-сервере быстрее.
4. **HTTP** \`${base}/v1/audio/speech\` или \`POST ${base}/api/synth\`.

## Команды
\`\`\`bash
ltts say "Текст" --json
ltts say "Текст" -v ${dv.ru || "silero:kseniya"} -o /abs/path/out.mp3 --json
ltts say "Текст" --play
ltts voices --installed --json
\`\`\`

- Голоса по умолчанию: ru \`${dv.ru}\`, en \`${dv.en}\`, de \`${dv.de}\`.
- \`-v engine:voice\`, \`--lang auto|ru|en|de\`, \`-s\` скорость, \`-f\` формат.
${homeLine}${winLine}- Ошибки: \`ltts doctor --verify --json\`. Настройки: ${base}/settings
`;

  const skill = `---
name: ltts
description: Локальный офлайн TTS (ru/en/de) через ltts — Silero, Piper, RHVoice. Используй для озвучки текста, войсовера, play=true, сохранения в файл; сервер ${base}.
---

${skillBody}`;

  const subagent = `Ты субагент озвучки **ltts** (локальный TTS, без облака).

**Сервер:** ${base} (desktop или \`ltts serve\`).
**Голоса по умолчанию:** ru=${dv.ru}, en=${dv.en}, de=${dv.de}.

**MCP:** ${mcpUrl} (или stdio \`ltts mcp\`).

**Действия:**
1. MCP — \`speak\` / \`list_voices\`.
2. Shell: \`ltts say "<текст>" --json\` (\`-v\`, \`-o\`, \`--play\`).
3. HTTP POST ${base}/api/synth — метаданные в X-LTTS-Meta.

Не выдумывай голоса — проверь \`list_voices\` или \`GET ${base}/api/voices\`. ${ctx.windows ? "RHVoice на Windows недоступен." : ""}
После синтеза сообщи пользователю путь к файлу из поля \`path\` / JSON.`;

  const mcpCursorHttp = JSON.stringify(
    {
      mcpServers: {
        ltts: {
          url: mcpUrl,
        },
      },
    },
    null,
    2
  );

  const mcpCursor = JSON.stringify(
    {
      mcpServers: {
        ltts: {
          command: "ltts",
          args: ["mcp"],
        },
      },
    },
    null,
    2
  );

  const cli = `# Быстрый старт (сервер: ${base})
ltts say "Привет" --play
ltts say "Hello" --json
ltts say "текст" -v ${dv.ru || "silero:kseniya"} -o out.mp3 --json
echo "длинный текст" | ltts say -v ${dv.en || "silero:en_0"} --json

# MCP (stdio) — лучший вариант для IDE-агентов
ltts mcp`;

  const curl = `curl -sS "${base}/v1/audio/speech" \\
  -H "Content-Type: application/json" \\
  -d '{"model":"silero","input":"Привет","voice":"${ruV}","response_format":"mp3"}' \\
  -o out.mp3

# Свой API (метаданные в X-LTTS-Meta):
curl -sS "${base}/api/synth" \\
  -H "Content-Type: application/json" \\
  -d '{"text":"Привет","voice":"${dv.ru}","format":"mp3","lang":"ru"}' \\
  -o out.mp3 -D headers.txt`;

  const curlPs = `$body = @{
  model = "silero"
  input = "Привет"
  voice = "${ruV}"
  response_format = "mp3"
} | ConvertTo-Json -Compress

Invoke-RestMethod -Uri "${base}/v1/audio/speech" -Method Post -ContentType "application/json" -Body $body -OutFile out.mp3`;

  return [
    {
      id: "mcp-http",
      badge: "MCP",
      title: "Cursor — MCP по URL (desktop / serve)",
      hint: "Рекомендуется: MCP уже на этом сервере, отдельный процесс ltts mcp не нужен.",
      text: mcpCursorHttp,
    },
    {
      id: "skill",
      badge: "Skill",
      title: "Cursor Skill (SKILL.md)",
      hint: "Сохраните как .cursor/skills/ltts/SKILL.md или в личные skills — агент поймёт, когда вызывать TTS.",
      text: skill,
    },
    {
      id: "subagent",
      badge: "Subagent",
      title: "Промпт субагента / Task",
      hint: "Вставьте в описание субагента или в system/instructions одноразовой задачи.",
      text: subagent,
    },
    {
      id: "mcp-cursor",
      badge: "MCP",
      title: "Cursor — MCP stdio (ltts mcp)",
      hint: "Если desktop не запущен: команда ltts в PATH, отдельный subprocess на сессию IDE.",
      text: mcpCursor,
    },
    {
      id: "mcp-claude",
      badge: "MCP",
      title: "Claude Code CLI",
      hint: "Одна команда для регистрации stdio-сервера.",
      text: "claude mcp add ltts -- ltts mcp",
    },
    {
      id: "cli",
      badge: "CLI",
      title: "Терминал (ltts say)",
      hint: "Работает без MCP; при запущенном desktop модели уже в памяти.",
      text: cli,
    },
    {
      id: "curl",
      badge: "HTTP",
      title: "curl (OpenAI-совместимый API)",
      hint: `Голос по умолчанию ru: ${ruV}. model: silero | piper | rhvoice | tts-1.`,
      text: curl,
    },
    {
      id: "curl-ps",
      badge: "HTTP",
      title: "PowerShell (Windows)",
      hint: "Тот же эндпоинт /v1/audio/speech без curl.",
      text: curlPs,
    },
  ];
}

function lttsEnsureAgentsStyles() {
  if (document.getElementById("ltts-agents-styles")) return;
  const s = document.createElement("style");
  s.id = "ltts-agents-styles";
  s.textContent = `
.agents-panel { margin-top: 4px; }
.agents-panel .agents-intro { font-size: 14px; color: var(--muted); margin: 0 0 14px; line-height: 1.5; }
.agents-panel .agents-paths { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
.agents-panel .agents-tab { font-size: 12px; padding: 5px 10px; border-radius: 999px; border: 1px solid var(--border); background: var(--surface-2); color: var(--muted); cursor: pointer; font: inherit; }
.agents-panel .agents-tab.active { background: var(--accent-soft, var(--surface-2)); color: var(--accent-text, var(--accent)); border-color: var(--accent); }
.agents-panel .agents-head { display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
.agents-panel .agents-head h3 { margin: 0; font-size: 15px; font-weight: 600; }
.agents-panel .agents-hint { font-size: 13px; color: var(--faint, var(--muted)); margin: 0 0 10px; }
.agents-panel .agents-code-wrap { position: relative; }
.agents-panel pre.agents-code { margin: 0; padding: 14px 14px 40px; border-radius: var(--r, 12px); background: var(--surface-2); border: 1px solid var(--border); font: 12px/1.55 var(--mono, monospace); color: var(--text); overflow: auto; max-height: 320px; white-space: pre-wrap; word-break: break-word; }
.agents-panel .agents-copy { position: absolute; right: 8px; bottom: 8px; display: inline-flex; align-items: center; gap: 6px; padding: 6px 10px; border-radius: 8px; border: 1px solid var(--border); background: var(--surface); color: var(--muted); cursor: pointer; font-size: 12px; font-family: inherit; }
.agents-panel .agents-copy:hover { color: var(--text); border-color: var(--border-strong, var(--border)); }
.agents-panel .agents-copy.done { color: var(--ok, #15803d); }
details.agents .agents-panel { margin-top: 12px; }
details.agents .agents-panel pre.agents-code { background: var(--surface); }
`;
  document.head.appendChild(s);
}

async function lttsCopyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    try {
      return document.execCommand("copy");
    } finally {
      document.body.removeChild(ta);
    }
  }
}

/**
 * @param {HTMLElement} mount
 * @param {object} ctx — lttsAgentContextFromSettings или { serverUrl, defaultVoices, windows }
 * @param {{ onToast?: (msg: string) => void }} opts
 */
function lttsMountAgentsPanel(mount, ctx, opts = {}) {
  if (!mount) return;
  lttsEnsureAgentsStyles();
  const snippets = lttsBuildAgentSnippets(ctx);
  let active = snippets[0].id;

  const toast = opts.onToast || (() => {});

  function render() {
    const sn = snippets.find((x) => x.id === active) || snippets[0];
    mount.className = "agents-panel";
    mount.innerHTML = `
      <p class="agents-intro">Пока работает это окно, MCP доступен по <code>${(ctx.mcpHttpUrl || "").replace(/\/$/, "") || (ctx.serverUrl || "") + "/mcp"}</code> (вкладка MCP). Дальше: <strong>CLI</strong> <code>ltts say</code> и <strong>HTTP</strong> на <code>${ctx.serverUrl || location.origin}</code>.</p>
      <div class="agents-paths" role="tablist" aria-label="Варианты интеграции">
        ${snippets
          .map(
            (s) =>
              `<button type="button" class="agents-tab${s.id === active ? " active" : ""}" data-id="${s.id}" role="tab" aria-selected="${s.id === active}">${s.badge || "Copy"}</button>`
          )
          .join("")}
      </div>
      <div class="agents-head">
        <h3>${sn.title}</h3>
      </div>
      <p class="agents-hint">${sn.hint}</p>
      <div class="agents-code-wrap">
        <pre class="agents-code" id="agents-code-pre"></pre>
        <button type="button" class="agents-copy" id="agents-copy-btn">${lttsIcon("copy")}<span>Копировать</span></button>
      </div>`;
    mount.querySelector("#agents-code-pre").textContent = sn.text;
    mount.querySelectorAll(".agents-tab").forEach((btn) => {
      btn.onclick = () => {
        active = btn.dataset.id;
        render();
      };
    });
    const copyBtn = mount.querySelector("#agents-copy-btn");
    copyBtn.onclick = async () => {
      const ok = await lttsCopyToClipboard(sn.text);
      if (ok) {
        toast("Скопировано в буфер");
        copyBtn.classList.add("done");
        copyBtn.innerHTML = `${lttsIcon("check")}<span>Скопировано</span>`;
        lttsHydrateIcons(copyBtn);
        setTimeout(() => {
          copyBtn.classList.remove("done");
          copyBtn.innerHTML = `${lttsIcon("copy")}<span>Копировать</span>`;
          lttsHydrateIcons(copyBtn);
        }, 2000);
      } else toast("Не удалось скопировать");
    };
    lttsHydrateIcons(mount);
  }

  render();
}
