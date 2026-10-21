(function (global) {
  const DEFAULT_PAGE = "#010102";

  function normalizeHex(raw) {
    let s = String(raw || DEFAULT_PAGE).trim();
    if (!s.startsWith("#")) s = "#" + s;
    if (s.length === 4) s = "#" + [...s.slice(1)].map((c) => c + c).join("");
    if (s.length !== 7) return DEFAULT_PAGE;
    const n = parseInt(s.slice(1), 16);
    if (Number.isNaN(n)) return DEFAULT_PAGE;
    return s.toLowerCase();
  }

  function hexToRgb(hex) {
    const h = normalizeHex(hex);
    return [
      parseInt(h.slice(1, 3), 16),
      parseInt(h.slice(3, 5), 16),
      parseInt(h.slice(5, 7), 16),
    ];
  }

  function parseChromaLayout(L) {
    const layout = L && typeof L === "object" ? L : {};
    const enabled = !!layout.chroma_enabled;
    const keyHex = enabled ? normalizeHex(layout.chroma_color) : DEFAULT_PAGE;
    const tolerance = Math.max(
      0,
      Math.min(64, Number(layout.chroma_tolerance) || 16),
    );
    return {
      enabled,
      pageHex: DEFAULT_PAGE,
      keyHex,
      keyRgb: hexToRgb(keyHex),
      tolerance,
    };
  }

  function effectivePageChroma(_L) {
    return DEFAULT_PAGE;
  }

  function isChromaPixel(r, g, b, rgb, tolerance) {
    return (
      Math.abs(r - rgb[0]) <= tolerance &&
      Math.abs(g - rgb[1]) <= tolerance &&
      Math.abs(b - rgb[2]) <= tolerance
    );
  }

  function chromaKeyImageData(imageData, rgb, tolerance) {
    const d = imageData.data;
    for (let i = 0; i < d.length; i += 4) {
      if (isChromaPixel(d[i], d[i + 1], d[i + 2], rgb, tolerance)) {
        d[i + 3] = 0;
      }
    }
    return imageData;
  }

  function chromaKeyRect(ctx, x, y, w, h, rgb, tolerance) {
    if (w <= 0 || h <= 0) return;
    const imageData = ctx.getImageData(x, y, w, h);
    chromaKeyImageData(imageData, rgb, tolerance);
    ctx.putImageData(imageData, x, y);
  }

  function chromaKeyLayoutRect(ctx, x, y, w, h, layout) {
    const c = parseChromaLayout(layout);
    if (!c.enabled) return;
    chromaKeyRect(ctx, x, y, w, h, c.keyRgb, c.tolerance);
  }

  function applyPageBackground(layout, previewMode) {
    const hex = previewMode ? "transparent" : DEFAULT_PAGE;
    const els = [document.documentElement, document.body];
    const drag = document.getElementById("dragpad");
    if (drag) els.push(drag);
    for (const el of els) {
      if (!el) continue;
      el.style.backgroundColor = hex;
      el.style.background = hex;
    }
  }

  global.AvatarChroma = {
    DEFAULT_PAGE,
    normalizeHex,
    hexToRgb,
    parseChromaLayout,
    effectivePageChroma,
    isChromaPixel,
    chromaKeyImageData,
    chromaKeyRect,
    chromaKeyLayoutRect,
    applyPageBackground,
  };
})(typeof window !== "undefined" ? window : globalThis);
