// Parse da letra — porte do lrc do legado.
//
// Dois modos:
// - "palavras": words.json (alinhamento com Whisper) dá o tempo de cada palavra
// - "linhas": só o início de cada linha (LRCLIB); o preenchimento segue a
//   atividade da voz (ver Lyrics.svelte)

export const GAP = { text: "♪ ♪ ♪", gap: true };

// Detecta marcadores de dueto no início da linha:
// [Male], [Female], [M], [F], [男], [女], [Homem], [Mulher], [Ele], [Ela]…
export function detectDuet(text) {
  const m = text.match(/^\s*\[(?:male|m|homem|ele|男|masc|masculino)\s*:?\]/i);
  if (m) return "male";
  const f = text.match(/^\s*\[(?:female|f|mulher|ela|女|fem|feminino)\s*:?\]/i);
  if (f) return "female";
  return null;
}

const DUET_MARK = /^\s*\[(?:male|female|homem|mulher|ele|ela|男|女|masc|fem|masculino|feminino|m|f)\s*:?\]\s*/i;

export function parseLrc(text) {
  const out = [];
  for (const raw of text.split("\n")) {
    const tags = [...raw.matchAll(/\[(\d+):(\d+(?:\.\d+)?)\]/g)];
    // Detecta dueto ANTES de remover os marcadores
    const duet = detectDuet(raw);
    let words = raw.replace(/\[[^\]]*\]/g, "").trim();
    // Remove o marcador de dueto do texto exibido
    words = words.replace(DUET_MARK, "").trim();
    for (const m of tags) out.push({ t: +m[1] * 60 + +m[2], text: words, duet });
  }
  out.sort((a, b) => a.t - b.t);
  // Linhas vazias viram "♪" (intervalos instrumentais)
  return out.map((l) => (l.text ? l : { ...GAP, t: l.t }));
}

export function fromWords(lines) {
  const out = [];
  lines.forEach((l, i) => {
    out.push({
      t: l.t,
      end: l.end,
      text: l.words.map((w) => w.w).join(" "),
      words: l.words,
    });
    const next = lines[i + 1];
    if (next && next.t - l.end > 6) out.push({ ...GAP, t: l.end + 0.6 }); // solo / intervalo longo
  });
  return out;
}

// Prepara as linhas para render: insere "♪ ♪ ♪" no início quando a primeira
// linha começa depois de 3s (intro instrumental).
export function normalizeLines(lines) {
  const ls = [...lines];
  if (ls.length && ls[0].t > 3 && !ls[0].gap) ls.unshift({ ...GAP, t: 0 });
  return ls;
}

// Detecta o offset da letra analisando apenas os primeiros 30s de áudio:
// acha o primeiro onset de voz e compara com o timestamp da primeira linha do
// LRC. Retorna o offset global (a ser aplicado a todas as linhas) ou null.
export function autoDetectOffset(voice, lines) {
  if (!voice || !lines.length) return null;
  // Primeira linha com texto real (ignora marcadores instrumentais ♪ e vazias)
  const firstLine = lines.find((l) => l.text && l.text.trim() && !/^[♪♫\s]+$/.test(l.text));
  if (!firstLine) return null;
  // Acha o primeiro início de voz nos primeiros 30s
  const maxFrames = Math.min(voice.n, Math.floor(30 * voice.fps));
  const minRun = Math.round(0.15 * voice.fps); // 150ms de voz contínua
  let onset = -1;
  for (let f = 0; f < maxFrames - minRun; f++) {
    if (voice.voiced[f]) {
      let ok = true;
      for (let k = 0; k < minRun; k++) {
        if (!voice.voiced[f + k]) {
          ok = false;
          break;
        }
      }
      if (ok) {
        onset = f / voice.fps;
        break;
      }
    }
  }
  if (onset < 0) return null;
  return Math.round((onset - firstLine.t) * 100) / 100;
}
