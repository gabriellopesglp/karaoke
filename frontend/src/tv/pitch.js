// Detecção de afinação (frequência fundamental) para o score.
//
// Usa autocorrelação normalizada (estilo NSDF), que é robusta para voz cantada
// e barata o suficiente para rodar a ~20 Hz em tempo real. O contexto do app é
// karaokê, então precisamos da energia/afinação de uma voz monofônica e não de
// uma transcrição musical completa.

// Frequência (Hz) ↔ nota MIDI (pode ser fracionária: 69 = A4 = 440 Hz).
export const hzToMidi = (hz) => 69 + 12 * Math.log2(hz / 440);
export const midiToHz = (m) => 440 * 2 ** ((m - 69) / 12);

// Frequência fundamental de um quadro mono. Devolve 0 quando o quadro é
// silencioso ou não tem periodicidade clara (ruído, fala sussurrada).
// `step` amostra o sinal a cada N amostras para acelerar (usado no pré-cálculo).
export function detectPitch(frame, sampleRate, minHz = 70, maxHz = 1000, step = 1) {
  const n = frame.length;
  const minLag = Math.max(2, Math.floor(sampleRate / maxHz));
  const maxLag = Math.min(n - 2, Math.ceil(sampleRate / minHz));
  if (maxLag <= minLag) return 0;

  let energy = 0;
  for (let i = 0; i < n; i += step) energy += frame[i] * frame[i];
  if (Math.sqrt(energy / Math.ceil(n / step)) < 0.006) return 0; // silêncio

  const vals = new Float32Array(maxLag + 2);
  let maxVal = 0;
  for (let lag = minLag - 1; lag <= maxLag + 1; lag++) {
    let corr = 0,
      norm = 0;
    for (let i = 0; i + lag < n; i += step) {
      const a = frame[i],
        b = frame[i + lag];
      corr += a * b;
      norm += a * a + b * b;
    }
    vals[lag] = norm > 0 ? (2 * corr) / norm : 0;
    if (lag >= minLag && lag <= maxLag && vals[lag] > maxVal) maxVal = vals[lag];
  }
  // Clareza mínima: abaixo disso o "pico" é ruído e não afinação.
  if (maxVal < 0.5) return 0;

  // Escolhe o PRIMEIRO pico local que chega perto do máximo (e não o máximo
  // global): os múltiplos do período também correlacionam alto e escolher o
  // maior deles produziria o clássico erro de oitava.
  const thr = maxVal * 0.9;
  let bestLag = -1;
  for (let lag = minLag; lag <= maxLag; lag++) {
    if (vals[lag] >= thr && vals[lag] >= vals[lag - 1] && vals[lag] >= vals[lag + 1]) {
      bestLag = lag;
      break;
    }
  }
  if (bestLag < 0) return 0;

  // Interpolação parabólica do pico → precisão sub-amostra (menos de 1 centavo)
  const y0 = vals[bestLag - 1],
    y1 = vals[bestLag],
    y2 = vals[bestLag + 1];
  const d = y0 - 2 * y1 + y2;
  const shift = d !== 0 ? Math.max(-1, Math.min(1, (0.5 * (y0 - y2)) / d)) : 0;
  return sampleRate / (bestLag + shift);
}

// Reduz a taxa por média de blocos (passa-baixa simples). Acelera bastante o
// pré-cálculo da trilha, que roda sobre a música inteira.
function decimate(samples, factor) {
  if (factor <= 1) return samples;
  const n = Math.floor(samples.length / factor);
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    let s = 0;
    for (let k = 0; k < factor; k++) s += samples[i * factor + k];
    out[i] = s / factor;
  }
  return out;
}

// Trilha de afinação esperada de um stem (a melodia original cantada).
// Em cada quadro devolve o MIDI esperado; NaN onde não há voz.
export function pitchTrack(buf, { fps = 10, minHz = 70, maxHz = 900 } = {}) {
  const factor = Math.max(1, Math.round(buf.sampleRate / 11025));
  const sr = buf.sampleRate / factor;
  const data = decimate(buf.getChannelData(0), factor);
  const win = Math.max(256, Math.round((2 * sr) / minHz)); // ~2 períodos da nota mais grave
  const hop = Math.max(1, Math.round(sr / fps));
  const n = Math.max(0, Math.floor((data.length - win) / hop));
  const midi = new Float32Array(n).fill(NaN);
  const frame = new Float32Array(win);
  for (let f = 0; f < n; f++) {
    const off = f * hop;
    frame.set(data.subarray(off, off + win));
    const hz = detectPitch(frame, sr, minHz, maxHz);
    if (hz > 0) midi[f] = hzToMidi(hz);
  }
  return {
    fps,
    n,
    midi,
    at(t) {
      const f = Math.floor(t * fps);
      return f >= 0 && f < n ? midi[f] : NaN;
    },
  };
}
