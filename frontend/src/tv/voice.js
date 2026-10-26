// Atividade da voz — porte do voiceActivity do legado.
//
// O LRCLIB só dá o início de cada linha. Para o preenchimento amarelo
// acompanhar o canto, medimos na faixa de voz isolada quando há voz, em
// quadros de ~23 ms, e acumulamos (integral cumulativa consultável por tempo).

export function voiceActivity(buf) {
  const hop = 1024,
    n = Math.floor(buf.length / hop),
    fps = buf.sampleRate / hop;
  const chans = [...Array(buf.numberOfChannels)].map((_, c) => buf.getChannelData(c));
  const rms = new Float32Array(n);
  for (let f = 0; f < n; f++) {
    let sum = 0;
    for (const ch of chans)
      for (let k = f * hop, e = k + hop; k < e; k += 2) sum += ch[k] * ch[k];
    rms[f] = Math.sqrt(sum / ((chans.length * hop) / 2));
  }
  // Limiar adaptativo: separa silêncio de voz usando a distribuição do RMS.
  // median ≈ nível de silêncio, p90 ≈ nível típico de voz.
  const sorted = Float32Array.from(rms).sort();
  const silenceLevel = sorted[Math.floor(n * 0.5)];
  const voiceLevel = sorted[Math.floor(n * 0.9)];
  const thr = Math.max(0.006, silenceLevel + (voiceLevel - silenceLevel) * 0.3);
  const voiced = rms.map((v) => (v > thr ? 1 : 0));
  // Fecha buracos curtos (consoantes, respiros rápidos) para o preenchimento
  // não "travar". 80ms cobre consoantes sem fundir linhas separadas por silêncio.
  const rawVoiced = Float32Array.from(voiced);
  const gap = Math.round(0.08 * fps);
  for (let f = 0, last = -1; f < n; f++) {
    if (voiced[f]) {
      if (last >= 0 && f - last <= gap) voiced.fill(1, last, f);
      last = f;
    }
  }
  const cum = new Float32Array(n + 1);
  for (let f = 0; f < n; f++) cum[f + 1] = cum[f] + voiced[f];

  return {
    fps,
    n,
    rms,
    voiced,
    rawVoiced,
    silenceLevel,
    voiceLevel,
    at: (t) => cum[Math.min(n, Math.max(0, Math.floor(t * fps)))] / fps,
  };
}
