// Player Web Audio multi-stem — porte fiel do player do app legado.
//
// Todos os stems de uma música são baixados (/media/<pasta>/<arquivo>) e
// decodificados; cada um tem um GainNode (curva (vol/100)², mute) ligado a um
// master GainNode → DynamicsCompressor → destination. O pitch usa `detune`
// (100 cents = 1 semitom, ±12). O início dos sources é sincronizado
// (currentTime + 0.05) e play/pause/seek usam fades de 0.4s no master para
// evitar cliques. O objeto é mutável; a UI acompanha via stores espelho
// (ver store.js).

import { api } from "../shared/api.js";
import { store } from "./util.js";
import { voiceActivity } from "./voice.js";
import { detectKey } from "./keydetect.js";

export const player = {
  ctx: null,
  stems: [],
  sources: [],
  playing: false,
  offset: 0,
  startedAt: 0,
  duration: 0,
  song: null,
  loadId: 0,
  pitch: 0, // semitons (−12 a +12)
  originalKey: null, // {tonic:0-11, mode:'major'|'minor', name, fullName}
  volume: 1, // volume master (0–1)
  voice: null, // atividade de voz do stem "Voz…" (preenchimento da letra)
  onKeyDetected: null, // callback quando a detecção de tom termina (store.js)

  now() {
    return this.playing ? this.ctx.currentTime - this.startedAt : this.offset;
  },

  async load(song) {
    this.stop();
    this.ctx ??= new AudioContext();
    // Cadeia master: masterGain → compressor → destination.
    // O compressor evita clipping quando vários stems estão no máximo.
    if (!this.masterGain) {
      this.masterGain = this.ctx.createGain();
      this.compressor = this.ctx.createDynamicsCompressor();
      this.compressor.threshold.value = -10;
      this.compressor.knee.value = 24;
      this.compressor.ratio.value = 4;
      this.compressor.attack.value = 0.003;
      this.compressor.release.value = 0.25;
      this.masterGain.connect(this.compressor);
      this.compressor.connect(this.ctx.destination);
    }
    const myLoad = ++this.loadId;
    this.song = song;
    this.stems = [];
    this.offset = 0;
    this.duration = 0;
    const buffers = await Promise.all(
      song.stems.map((s) =>
        api(`/media/${encodeURIComponent(song.folder)}/${encodeURIComponent(s.file)}`)
          .then((r) => r.arrayBuffer())
          .then((b) => this.ctx.decodeAudioData(b)),
      ),
    );
    if (myLoad !== this.loadId) return false; // trocou de música no meio do carregamento
    this.stems = song.stems.map((s, i) => {
      const gain = this.ctx.createGain();
      gain.connect(this.masterGain);
      const saved = store.get(`stem:${s.label}`, { vol: 100, muted: false });
      return { ...s, buffer: buffers[i], gain, vol: saved.vol, muted: saved.muted };
    });
    this.stems.forEach((s) => this.applyGain(s));
    this.duration = Math.max(...buffers.map((b) => b.duration));
    const voice = this.stems.find((s) => s.label.startsWith("Voz"));
    this.voice = voice ? voiceActivity(voice.buffer) : null;
    // Detecção do tom musical (em background, não trava a UI)
    this.originalKey = null;
    setTimeout(() => {
      try {
        this.originalKey = detectKey(this.stems);
        this.onKeyDetected?.();
      } catch (e) {}
    }, 200);
    return true;
  },

  applyGain(s) {
    const v = s.muted ? 0 : (s.vol / 100) ** 2; // curva quadrática soa mais natural
    s.gain.gain.setTargetAtTime(v, this.ctx.currentTime, 0.02);
    store.set(`stem:${s.label}`, { vol: s.vol, muted: s.muted });
  },

  play() {
    if (!this.stems.length) return;
    if (this.offset >= this.duration - 0.05) this.offset = 0;
    this.ctx.resume();
    const t0 = this.ctx.currentTime + 0.05;
    this.sources = this.stems.map((s) => {
      const src = this.ctx.createBufferSource();
      src.buffer = s.buffer;
      src.detune.value = this.pitch * 100; // 100 cents = 1 semitom
      src.connect(s.gain);
      src.start(t0, this.offset);
      return src;
    });
    // Fade in no master para evitar clique/pop
    if (this.masterGain) {
      this.masterGain.gain.cancelScheduledValues(t0);
      this.masterGain.gain.setValueAtTime(0.0001, t0);
      this.masterGain.gain.exponentialRampToValueAtTime(Math.max(0.0001, this.volume), t0 + 0.4);
    }
    this.startedAt = t0 - this.offset;
    this.playing = true;
  },

  pause() {
    if (!this.playing) return;
    this.offset = this.now();
    this.stop(true);
  },

  stop(pauseOnly = false) {
    const now = this.ctx ? this.ctx.currentTime : 0;
    const srcs = this.sources;
    this.sources = [];
    this.playing = false;
    // Fade out no master (0.4s) antes de parar as fontes
    if (this.masterGain && srcs.length) {
      const g = this.masterGain.gain;
      g.cancelScheduledValues(now);
      g.setValueAtTime(Math.max(0.0001, g.value), now);
      g.exponentialRampToValueAtTime(0.0001, now + 0.4);
      setTimeout(() => {
        srcs.forEach((s) => {
          try {
            s.stop();
          } catch (e) {}
        });
      }, 420);
    } else {
      srcs.forEach((s) => {
        try {
          s.stop();
        } catch (e) {}
      });
    }
  },

  seek(t) {
    const was = this.playing;
    this.stop();
    this.offset = Math.min(Math.max(0, t), this.duration);
    if (was) this.play();
  },

  setPitch(semi) {
    this.pitch = Math.max(-12, Math.min(12, semi));
    // Aplica imediatamente nas fontes que estão tocando
    if (this.sources) {
      for (const src of this.sources) src.detune.value = this.pitch * 100;
    }
    if (this.song) store.set(`pitch:${this.song.folder}`, this.pitch);
    return this.pitch;
  },

  setVolume(v) {
    this.volume = Math.max(0, Math.min(1, v));
    if (this.masterGain) {
      const now = this.ctx.currentTime;
      this.masterGain.gain.cancelScheduledValues(now);
      this.masterGain.gain.setTargetAtTime(Math.max(0.0001, this.volume), now, 0.05);
    }
    return this.volume;
  },
};
