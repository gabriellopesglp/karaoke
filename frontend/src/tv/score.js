// Sessão de pontuação — compara a voz do microfone com a melodia da faixa de
// voz original e guarda a pontuação final da música.
//
// Regra: só as leituras em que o cantor realmente emitiu voz entram na conta —
// respirar ou ficar em silêncio não derruba mais a pontuação. Cada leitura soma
// de 0 a 1 conforme a distância da nota esperada (crédito parcial), comparando
// com todas as notas esperadas numa janela de ±0,2 s (o que absorve o portamento
// da gravação e o atraso do ataque). A melodia cantada em outra oitava vale
// igual. A pontuação são os pontos de 0 a 100 e só aparece no fim da música.

import { writable } from "svelte/store";
import { player } from "./player.js";
import { detectPitch, hzToMidi, pitchTrack } from "./pitch.js";

const FULL = 0.9; // semitons: até aqui a leitura vale 1 (acerto cheio)
const ZERO = 1.1; // semitons: daqui para cima não soma nada (1 semitom = 50%)
const WINDOW = 0.2; // s de notas esperadas consideradas em volta do instante
const SMOOTH = 3; // leituras usadas na mediana da voz (corta glitches)
const END_MARGIN = 1.5; // s antes do fim: parar aqui conta como fim da música
const FRAME_MS = 50; // 20 Hz

function blank() {
  return {
    error: "",
    hint: "",
    final: false, // música terminou: mostrar o resultado
    points: null, // 0–100 (null quando não houve voz para avaliar)
    total: 0, // leituras de voz avaliadas
  };
}

export const score = writable(blank());

// Cache da trilha de afinação por música (invalida se o áudio for recarregado).
const trackCache = new Map();

function vocalTrack() {
  const song = player.song;
  const voice = player.stems.find((s) => s.label.startsWith("Voz"));
  if (!song || !voice) return null;
  const hit = trackCache.get(song.folder);
  if (hit && hit.buffer === voice.buffer) return hit.track;
  const track = pitchTrack(voice.buffer);
  trackCache.set(song.folder, { buffer: voice.buffer, track });
  return track;
}

let session = null;
let starting = false;

function isAppleMobile() {
  const ua = navigator.userAgent || "";
  return /iPad|iPhone|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
}

function micUnavailableMessage() {
  if (!window.isSecureContext) {
    if (isAppleMobile()) {
      return "No iPad/iPhone, o Safari so libera o microfone em HTTPS. Pelo QR code na rede local o score nao consegue ouvir voce; use o app nativo no Mac para pontuar.";
    }
    return "Este navegador so libera o microfone em HTTPS ou no proprio computador. Neste acesso pela rede local, o score nao pode usar o microfone.";
  }
  return "Este navegador nao da acesso ao microfone.";
}

function micPermissionMessage() {
  if (isAppleMobile()) {
    return "Permissao do microfone negada. Autorize em Ajustes > Safari > Microfone e recarregue a pagina.";
  }
  return "Permissao do microfone negada. Autorize em Ajustes do Sistema > Privacidade e Seguranca > Microfone.";
}

export function stopScore() {
  if (session) {
    clearInterval(session.timer);
    try {
      session.analyser.disconnect();
      session.mute.disconnect();
      session.source.disconnect();
    } catch (e) {}
    session.stream.getTracks().forEach((t) => t.stop());
  }
  session = null;
  starting = false;
  score.set(blank());
}

export async function startScore() {
  if (session || starting) return;
  if (!player.song || !player.ctx || !player.stems.length) {
    score.set({ ...blank(), hint: "Escolha e toque uma música para pontuar." });
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    score.set({ ...blank(), error: micUnavailableMessage() });
    return;
  }
  starting = true;
  score.set({ ...blank(), hint: "Ativando o microfone…" });

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    });
  } catch (e) {
    starting = false;
    score.set({ ...blank(), error: micError(e) });
    return;
  }

  const ctx = player.ctx;
  try {
    await ctx.resume();
  } catch (e) {}

  const source = ctx.createMediaStreamSource(stream);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 2048;
  // O analisador precisa estar ligado ao destino para o grafo processar; o
  // ganho zero garante que o microfone não vire realimentação nos alto-falantes.
  const mute = ctx.createGain();
  mute.gain.value = 0;
  source.connect(analyser);
  analyser.connect(mute);
  mute.connect(ctx.destination);

  session = {
    stream,
    source,
    analyser,
    mute,
    frame: new Float32Array(analyser.fftSize),
    credits: 0, // soma dos créditos parciais
    total: 0,
    recent: [], // últimas leituras de voz (mediana)
    folder: player.song.folder,
    lastT: -1,
    playing: false,
    finished: false,
    track: vocalTrack(),
    timer: 0,
  };
  starting = false;

  if (!session.track) {
    const stream0 = session.stream;
    const analyser0 = session.analyser,
      mute0 = session.mute,
      source0 = session.source;
    session = null;
    try {
      analyser0.disconnect();
      mute0.disconnect();
      source0.disconnect();
    } catch (e) {}
    stream0.getTracks().forEach((t) => t.stop());
    score.set({ ...blank(), error: "Esta música não tem faixa de voz para comparar." });
    return;
  }

  score.set(blank());
  session.timer = setInterval(tick, FRAME_MS);
  tick();
}

function micError(e) {
  if (e?.name === "NotAllowedError" || e?.name === "SecurityError")
    return micPermissionMessage();
  if (e?.name === "NotFoundError") return "Nenhum microfone encontrado.";
  if (e?.name === "NotReadableError") return "O microfone está em uso por outro app.";
  return `Não foi possível acessar o microfone. ${e?.message || ""}`.trim();
}

// Diferença entre a voz e a nota esperada trazida para ±6 semitons: assim a
// mesma melodia cantada uma ou mais oitavas acima/abaixo continua valendo.
function interval(cur, ref) {
  let d = (((cur - ref) % 12) + 12) % 12;
  if (d > 6) d -= 12;
  return d;
}

// Crédito parcial de uma leitura: cheio até FULL semitons, caindo até ZERO.
function credit(d) {
  const a = Math.abs(d);
  if (a <= FULL) return 1;
  if (a >= ZERO) return 0;
  return (ZERO - a) / (ZERO - FULL);
}

// Melhor crédito entre as notas esperadas na janela em volta de `t`: o cantor
// original desliza entre as notas e o ataque da voz atrasa, então comparar só
// com o instante exato reprovava quem estava cantando certo.
function bestCredit(track, t, shift, cur) {
  const f0 = Math.max(0, Math.floor((t - WINDOW) * track.fps));
  const f1 = Math.min(track.n - 1, Math.ceil((t + WINDOW) * track.fps));
  let best = 0;
  for (let f = f0; f <= f1; f++) {
    const m = track.midi[f];
    if (Number.isNaN(m)) continue;
    best = Math.max(best, credit(interval(cur, m + shift)));
    if (best === 1) break;
  }
  return best;
}

// Mediana das últimas leituras: um quadro isolado de vibrato ou erro de oitava
// deixa de virar erro.
function smooth(s, midi) {
  s.recent.push(midi);
  if (s.recent.length > SMOOTH) s.recent.shift();
  const a = [...s.recent].sort((x, y) => x - y);
  return a[a.length >> 1];
}

function finish(s) {
  s.finished = true;
  s.lastT = -1;
  const pct = s.total ? (s.credits / s.total) * 100 : 0;
  score.set({
    ...blank(),
    final: true,
    points: s.total ? Math.min(100, Math.round(pct)) : null,
    total: s.total,
  });
}

function tick() {
  const s = session;
  if (!s) return;
  const song = player.song;

  // Troca de música: recomeça a pontuação e some com o resultado anterior
  if (!song || song.folder !== s.folder) {
    s.folder = song ? song.folder : null;
    s.credits = s.total = 0;
    s.recent = [];
    s.lastT = -1;
    s.finished = false;
    s.track = vocalTrack();
    if (!s.track) return;
  }
  if (!player.playing) {
    s.playing = false;
    // Parou no fim da faixa: música terminou, guarda o resultado.
    if (!s.finished && player.duration && s.lastT >= player.duration - END_MARGIN) finish(s);
    return;
  }
  if (!s.playing) {
    s.playing = true;
    // Começou a tocar: zera uma tentativa anterior e tira o resultado da tela.
    if (s.finished) {
      s.finished = false;
      s.credits = s.total = 0;
      s.recent = [];
      s.lastT = -1;
    }
    score.set(blank());
  }

  const t = player.now();
  if (s.lastT >= 0 && t + 1 < s.lastT) {
    s.credits = s.total = 0; // voltou no tempo / recomeçou: zera o placar
    s.recent = [];
    s.lastT = -1;
    return;
  }
  s.lastT = t;

  if (Number.isNaN(s.track.at(t))) return; // sem voz na música agora: não pontua

  s.analyser.getFloatTimeDomainData(s.frame);
  const hz = detectPitch(s.frame, player.ctx.sampleRate, 70, 1200);
  if (hz <= 0) return; // o cantor não emitiu voz: leitura fora da conta

  const cur = smooth(s, hzToMidi(hz));
  s.total++;
  // A referência acompanha o tom escolhido (o áudio é desafinado junto)
  s.credits += bestCredit(s.track, t, player.pitch || 0, cur);
}
