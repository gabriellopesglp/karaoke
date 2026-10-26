// Formatação de tempo, offset da letra e tom.

// 75 -> "1:15"
export function fmtTime(s) {
  s = Math.max(0, Math.floor(s || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

// 0.05 -> "+0,05 s" (pt-BR); -0.1 -> "-0,10 s"; 0 -> "0,00 s"
export function fmtOffset(v) {
  const n = Number(v || 0);
  return (n > 0 ? "+" : "") + n.toFixed(2).replace(".", ",") + " s";
}

const KEY_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

// Tom exibido no controle. Com o tom original da música (keyOrig) mostra
// "C→D"; sem ele, mostra os semitons ("+2", "-1", "0").
export function fmtPitch(pitch, keyOrig) {
  const p = pitch || 0;
  if (keyOrig != null) {
    const now = (((12 - keyOrig + p) % 12) + 12) % 12;
    return p ? `${KEY_NAMES[keyOrig]} → ${KEY_NAMES[now]}` : KEY_NAMES[keyOrig];
  }
  return p > 0 ? `+${p}` : String(p);
}
