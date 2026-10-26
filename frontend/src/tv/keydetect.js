// Detecção do tom musical — porte do keydetect do legado.
// FFT radix-2 + STFT (janela 4096, hop 2048, Hann, primeiros 90s do mix) →
// cromagrama de 12 classes → correlação com perfis de Krumhansl-Schmuckler.

export const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

// Perfis de Krumhansl-Schmuckler para dó maior e lá menor.
const KS_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88];
const KS_MINOR = [6.33, 2.68, 3.52, 5.38, 2.6, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17];

// FFT radix-2 (in-place, Cooley-Tukey). re[] e im[] são modificados.
function fft(re, im) {
  const n = re.length;
  if (n <= 1) return;
  // bit-reversal permutation
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) {
      [re[i], re[j]] = [re[j], re[i]];
      [im[i], im[j]] = [im[j], im[i]];
    }
  }
  for (let len = 2; len <= n; len <<= 1) {
    const ang = (-2 * Math.PI) / len;
    const wRe = Math.cos(ang),
      wIm = Math.sin(ang);
    for (let i = 0; i < n; i += len) {
      let curRe = 1,
        curIm = 0;
      for (let k = 0; k < len / 2; k++) {
        const uRe = re[i + k],
          uIm = im[i + k];
        const vRe = re[i + k + len / 2] * curRe - im[i + k + len / 2] * curIm;
        const vIm = re[i + k + len / 2] * curIm + im[i + k + len / 2] * curRe;
        re[i + k] = uRe + vRe;
        im[i + k] = uIm + vIm;
        re[i + k + len / 2] = uRe - vRe;
        im[i + k + len / 2] = uIm - vIm;
        const nRe = curRe * wRe - curIm * wIm;
        curIm = curRe * wIm + curIm * wRe;
        curRe = nRe;
      }
    }
  }
}

// Detecta o tom da música combinando todos os stems.
// Retorna {tonic: 0-11, mode: 'major'|'minor', name: 'C', fullName: 'C maior'}
export function detectKey(stems) {
  if (!stems || !stems.length) return null;

  // 1. Mistura todos os stems em um sinal mono (primeiro canal de cada stem).
  const sr = stems[0].buffer.sampleRate;
  const maxLen = Math.max(...stems.map((s) => s.buffer.length));
  // Processa só os primeiros ~90s (o tom raramente muda no meio da música)
  const len = Math.min(maxLen, Math.floor(90 * sr));
  const mono = new Float32Array(len);
  for (const s of stems) {
    const ch = s.buffer.getChannelData(0);
    for (let i = 0; i < len && i < ch.length; i++) mono[i] += ch[i];
  }

  // 2. STFT com janela de 4096, hop 2048 → cromagrama de 12 classes de altura.
  const win = 4096,
    hop = 2048;
  const nFrames = Math.floor((len - win) / hop);
  const chroma = new Float32Array(12);
  const re = new Float32Array(win);
  const im = new Float32Array(win);
  // Pré-computa a classe de altura (0-11) de cada bin de frequência
  const binToPitch = new Int32Array(win / 2);
  for (let b = 1; b < win / 2; b++) {
    const freq = (b * sr) / win;
    const midi = 12 * Math.log2(freq / 440) + 69;
    binToPitch[b] = ((Math.round(midi) % 12) + 12) % 12;
  }

  for (let f = 0; f < nFrames; f++) {
    const off = f * hop;
    for (let i = 0; i < win; i++) {
      const x = mono[off + i] || 0;
      // Janela de Hann para reduzir vazamento espectral
      const w = 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / (win - 1));
      re[i] = x * w;
      im[i] = 0;
    }
    fft(re, im);
    for (let b = 1; b < win / 2; b++) {
      const mag = Math.sqrt(re[b] * re[b] + im[b] * im[b]);
      if (mag > 0.001) chroma[binToPitch[b]] += mag;
    }
  }

  // 3. Normaliza o cromagrama
  const sum = chroma.reduce((a, b) => a + b, 0);
  if (sum < 1) return null; // áudio quase silencioso
  for (let i = 0; i < 12; i++) chroma[i] /= sum;

  // 4. Correlação com os 24 perfis (12 maior + 12 menor)
  let bestTonic = 0,
    bestMode = "major",
    bestScore = -Infinity;
  for (let t = 0; t < 12; t++) {
    let sMajor = 0,
      sMinor = 0;
    for (let i = 0; i < 12; i++) {
      const pc = (i + t) % 12;
      sMajor += chroma[pc] * KS_MAJOR[i];
      sMinor += chroma[pc] * KS_MINOR[i];
    }
    if (sMajor > bestScore) {
      bestScore = sMajor;
      bestTonic = t;
      bestMode = "major";
    }
    if (sMinor > bestScore) {
      bestScore = sMinor;
      bestTonic = t;
      bestMode = "minor";
    }
  }

  return {
    tonic: bestTonic,
    mode: bestMode,
    name: NOTE_NAMES[bestTonic],
    fullName: NOTE_NAMES[bestTonic] + (bestMode === "major" ? " maior" : " menor"),
  };
}

// Converte um tom (original) + deslocamento em semitons para o tom resultante.
export function shiftedKey(orig, semi) {
  if (!orig) return null;
  const t = (((orig.tonic + semi) % 12) + 12) % 12;
  return {
    tonic: t,
    mode: orig.mode,
    name: NOTE_NAMES[t],
    fullName: NOTE_NAMES[t] + (orig.mode === "major" ? " maior" : " menor"),
  };
}
