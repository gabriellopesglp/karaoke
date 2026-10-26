// Estado e ações da TV — porte da lógica global do app legado para stores.
//
// Diferenças de arquitetura em relação ao legado (mesmos comportamentos):
// - fila/jobs chegam por WS (eventos "queue"/"jobs") em vez de GET a cada 5s/1s;
//   edições locais da fila continuam indo por POST com debounce de 300 ms.
// - o progresso do alinhamento palavra-a-palavra chega pelo evento WS "align"
//   (sem polling de 2s do /api/words).
// - comandos do controle remoto chegam por DOIS caminhos — WS "command"
//   (instantâneo) e a resposta do heartbeat (fallback) — e são deduplicados
//   pelo campo "i" (seq global do servidor).

import { derived, get, writable } from "svelte/store";
import { apiJson, postJson } from "../shared/api.js";
import { connectWS } from "../shared/ws.js";
import { player } from "./player.js";
import { store } from "./util.js";
import { autoDetectOffset, fromWords, normalizeLines, parseLrc } from "./lrc.js";

// ---------------------------------------------------------------- básicos

export const isMac = ["localhost", "127.0.0.1", "::1", "[::1]"].includes(location.hostname);

// Cada dispositivo (Mac, tablet, celular) tem um sessionId único; o QR code
// do controle remoto aponta para /remote?session=<sessionId>.
export const sessionId =
  store.get("sessionId") ||
  (() => {
    const id = Math.random().toString(36).slice(2, 10);
    store.set("sessionId", id);
    return id;
  })();

export const library = writable([]);
export const queue = writable(store.get("queue", []));
export const jobs = writable([]);
export const ytResults = writable([]);
export const ytOpen = writable(false);
export const ytLoading = writable(false);
export const query = writable("");
export const artistOnly = writable(false);
export const backing = writable(false);

export const currentSong = writable(null); // espelho de player.song para a UI
export const ready = writable(false); // faixas carregadas (play/seek habilitados)
export const cover = writable(""); // URL da capa (fundo + header); "" = sem capa
export const stemsVersion = writable(0); // bump quando stems mudam (mixer)
export const pitch = writable(0);
export const origKey = writable(null);

export const lyr = writable({ lines: [], plain: null, mode: "linhas" });
export const lyrOffset = writable(0);
export const lyricScale = writable(store.get("lyricScale", 1));
export const darkenBg = writable(store.get("darkenBg") === true);
export const focusMode = writable(store.get("focusMode") === true);
export const wordSync = writable(false); // sempre abre com "Pintar" desligado
export const syncNote = writable("");
export const msg = writable({
  title: "Nenhuma música tocando",
  text: "Busque na biblioteca ou digite e aperte Enter para procurar no YouTube.",
  small: false,
});

export const drawer = writable(false);
export const immersive = writable(false);
export const lyricsOpen = writable(false);
export const shareOpen = writable(null); // null | "app" | "remote"
export const shareReset = writable(false); // reabrir o modal já com reset=1
export const settingsOpen = writable(false);
export const scoreEnabled = writable(false); // overlay de precisão/afinação
export const off = writable(false); // tela "Karaokê desligado"

// Toque na tela em idle: só acorda os controles (Lyrics consulta e limpa)
export const wokeByTouch = { value: false };

export function bumpStems() {
  stemsVersion.update((n) => n + 1);
}

export const byFolder = (f) => get(library).find((s) => s.folder === f);

// Fila filtrada (remove músicas apagadas da biblioteca) — para exibição
export const queueView = derived([queue, library], ([$q, $lib]) =>
  $q.filter((f) => !$lib.length || $lib.find((s) => s.folder === f)),
);

export function showMsg(title, text = "", small = false) {
  if (!title) msg.set(null);
  else msg.set({ title, text, small });
}

// ------------------------------------------------------- confirmação (modal)

// body: lista de parágrafos; cada parágrafo é uma lista de trechos {t, b(ool)}
export const confirm = writable(null); // {title, body, ok, danger, resolve}
export function confirmBox(opts) {
  return new Promise((resolve) => confirm.set({ ok: "Confirmar", ...opts, resolve }));
}
export function closeConfirm(answer) {
  const c = get(confirm);
  if (!c) return;
  confirm.set(null);
  c.resolve(answer);
}

// "Gera 3 faixas: …" (usado no toggle e no askSplit)
export const BACKING_BODY = [
  [
    { t: "Gera " },
    { t: "3 faixas", b: true },
    { t: ": voz principal, backing vocals e instrumental. É bem mais lento: leva uns " },
    { t: "2 minutos por minuto de música", b: true },
    { t: "." },
  ],
];

// ---------------------------------------------------------------- fila

let queueSaveTimer = null;
function pushQueueToServer() {
  clearTimeout(queueSaveTimer);
  queueSaveTimer = setTimeout(() => {
    postJson("/api/queue", { queue: get(queue) }).catch(() => {});
  }, 300);
}

// Toda mudança local da fila passa por aqui: atualiza, persiste e sincroniza
export function setQueue(next) {
  queue.set(next);
  store.set("queue", next);
  pushQueueToServer();
}

export function addToQueue(folder) {
  if (get(queue).includes(folder)) return;
  setQueue([...get(queue), folder]);
  if (!player.song) playNext(); // nada tocando: já começa
}

export function playNext() {
  const q = [...get(queue)];
  const folder = q.shift();
  setQueue(q);
  const song = folder && byFolder(folder);
  if (song) openSong(song);
  else if (q.length) playNext(); // pula itens que não existem mais
}

// As ações da UI da fila usam a PASTA como referência (a lista exibida é a
// filtrada queueView; pastas são únicas porque addToQueue deduplica).

export function removeFromQueue(folder) {
  setQueue(get(queue).filter((f) => f !== folder));
}

export function moveUpQueue(folder) {
  const q = [...get(queue)];
  const k = q.indexOf(folder);
  if (k <= 0) return;
  [q[k - 1], q[k]] = [q[k], q[k - 1]];
  setQueue(q);
}

export function reorderQueue(folder, beforeFolder) {
  const q = [...get(queue)];
  const from = q.indexOf(folder);
  if (from < 0) return;
  const [moved] = q.splice(from, 1);
  const to = q.indexOf(beforeFolder);
  q.splice(to < 0 ? q.length : to, 0, moved);
  setQueue(q);
}

export function clearQueue() {
  setQueue([]);
}

export function playFromQueue(folder) {
  setQueue(get(queue).filter((f) => f !== folder)); // tocar agora
  openSong(byFolder(folder));
}

// ------------------------------------------------------------- transporte

export function togglePlay() {
  if (!player.stems.length) return;
  player.playing ? player.pause() : player.play();
}

export function setPitch(semi) {
  player.setPitch(semi);
  pitch.set(player.pitch);
}
player.onKeyDetected = () => origKey.set(player.originalKey);

export function setStemVol(i, vol) {
  const s = player.stems[i];
  if (!s) return;
  s.vol = Math.max(0, Math.min(100, vol | 0));
  player.applyGain(s);
}

export function toggleStemMute(i) {
  const s = player.stems[i];
  if (!s) return;
  s.muted = !s.muted;
  player.applyGain(s);
}

// ------------------------------------------------------- offset e tamanho

export function nudge(d) {
  const v = Math.round((get(lyrOffset) + d) * 100) / 100;
  lyrOffset.set(v);
  if (player.song) store.set(`offset:${player.song.folder}`, v);
}

export function resetOffset() {
  lyrOffset.set(0);
  if (player.song) store.set(`offset:${player.song.folder}`, 0);
}

export function setLyricScale(v) {
  const s = Math.min(2, Math.max(0.6, Math.round(v * 10) / 10));
  lyricScale.set(s);
  store.set("lyricScale", s);
}

// --------------------------------------------------------------- toggles

export function toggleDarkenBg() {
  const v = !get(darkenBg);
  darkenBg.set(v);
  store.set("darkenBg", v);
}

export function toggleFocusMode() {
  const v = !get(focusMode);
  focusMode.set(v);
  store.set("focusMode", v);
}

export function toggleWordSync() {
  const v = !get(wordSync);
  wordSync.set(v);
  store.set("wordSync", v);
  if (player.song) {
    if (v) loadWords(player.song);
    else syncNote.set("");
  }
}

export function toggleScore() {
  const v = !get(scoreEnabled);
  scoreEnabled.set(v);
  // persiste no settings do backend (se falhar, ainda fica ligado na sessão)
  postJson("/api/settings", { score_enabled: v }).catch(() => {});
}

// ---------------------------------------------------------------- capa

export function applyCoverBg(folder, bust = false) {
  const url = `/media/${encodeURIComponent(folder)}/cover.jpg${bust ? `?v=${Date.now()}` : ""}`;
  const img = new Image();
  img.onload = () => cover.set(url);
  img.onerror = () => cover.set("");
  img.src = url;
}

export async function loadCover(song) {
  if (song.cover) return applyCoverBg(song.folder);
  // Música antiga sem capa: pede ao servidor para buscar na iTunes
  const ok = await postJson("/api/cover", { folder: song.folder })
    .then((d) => d.ok)
    .catch(() => false);
  if (ok && player.song?.folder === song.folder) applyCoverBg(song.folder);
}

// ---------------------------------------------------------------- letra

function setLyr(obj) {
  lyr.set({ ...obj, lines: normalizeLines(obj.lines || []) });
}

export async function loadWords(song) {
  const data = await apiJson(`/api/words?folder=${encodeURIComponent(song.folder)}`).catch(
    () => ({}),
  );
  if (player.song !== song) return;
  if (data.status === "pronto" && data.lines?.length) {
    setLyr({ lines: fromWords(data.lines), plain: null, mode: "palavras" });
    syncNote.set("");
    // Alinhamento palavra-por-palavra já tem tempos corretos: zera offset automático
    lyrOffset.set(0);
    store.set(`offset:${song.folder}`, 0);
  } else if (data.status === "alinhando") {
    syncNote.set(`sincronizando${data.pct ? ` ${data.pct}%` : ""}`);
    // Sem polling: o evento WS "align" atualiza o progresso e avisa o fim.
  } else {
    syncNote.set("");
  }
}

export async function loadLyrics(song, refresh = false) {
  syncNote.set("");
  lyr.set({ lines: [], plain: null, mode: "linhas" });
  const data = await apiJson(
    `/api/lyrics?folder=${encodeURIComponent(song.folder)}${refresh ? "&refresh=1" : ""}`,
  ).catch(() => ({}));
  if (player.song !== song) return;
  setLyr({
    lines: data.synced ? parseLrc(data.synced) : [],
    plain: data.plain,
    mode: "linhas",
  });
  if (!data.synced && !data.plain) {
    return showMsg(
      "Letra não encontrada",
      "A música toca normalmente. Use o botão de buscar a letra de novo, no rodapé.",
      true,
    );
  }
  if (get(wordSync)) loadWords(song);
}

// ---------------------------------------------------------------- músicas

export async function openSong(song, { at = 0, autoplay = true } = {}) {
  if (!song) return;
  drawer.set(false);
  currentSong.set(song);
  ready.set(false);
  showMsg("Carregando faixas…", "");
  lyrOffset.set(store.get(`offset:${song.folder}`, 0));
  setPitch(store.get(`pitch:${song.folder}`, 0));
  loadCover(song);
  const lyricsDone = loadLyrics(song);
  if (!(await player.load(song))) return;
  showMsg(null);
  bumpStems();
  ready.set(true);
  await lyricsDone;
  // Só aplica offset automático se não houver alinhamento palavra-por-palavra
  // e não houver offset manual salvo (diferente de 0)
  if (get(lyr).mode === "linhas" && get(lyrOffset) === 0) {
    const offAuto = autoDetectOffset(player.voice, get(lyr).lines);
    if (offAuto != null) {
      lyrOffset.set(offAuto);
      store.set(`offset:${song.folder}`, offAuto);
    }
  }
  player.offset = at;
  if (autoplay) player.play();
}

export async function reloadCurrent() {
  const song = byFolder(player.song.folder),
    t = player.now(),
    was = player.playing;
  if (!song) return;
  await openSong(song, { at: t, autoplay: was });
}

export async function deleteSong(song) {
  if (!song) return;
  const ok = await confirmBox({
    title: `Deletar “${song.track}”?`,
    body: [
      [
        { t: "A música " },
        { t: `${song.artist} — ${song.track}`, b: true },
        {
          t: " será removida da biblioteca. As faixas de áudio, a letra e a capa são apagadas do disco.",
        },
      ],
    ],
    ok: "Deletar",
    danger: true,
  });
  if (!ok) return;
  const wasPlaying = player.song?.folder === song.folder;
  await postJson("/api/delete", { folder: song.folder }).catch(() => {});
  if (wasPlaying) {
    player.stop();
    player.song = null;
    player.stems = [];
    ready.set(false);
    bumpStems();
    currentSong.set(null);
    cover.set("");
    showMsg(
      "Nenhuma música tocando",
      "Busque na biblioteca ou digite e aperte Enter para procurar no YouTube.",
    );
  }
  setQueue(get(queue).filter((f) => f !== song.folder));
  await refreshLibrary();
}

// Separar backing de uma música já baixada (2faixas → 3faixas)
export async function askSplit(song) {
  if (!song) return;
  const ok = await confirmBox({
    title: `Separar backing de “${song.track}”?`,
    body: [...BACKING_BODY, [{ t: "A música continua disponível enquanto processa." }]],
    ok: "Separar",
  });
  if (!ok) return;
  jobs.update((js) => [
    ...js.filter((j) => j.id !== song.id),
    { id: song.id, title: song.track, status: "na fila", pct: 0 },
  ]);
  const lists = document.querySelector(".lists");
  if (lists) lists.scrollTop = 0;
  postJson("/api/process", {
    id: song.id,
    title: `${song.track} · backing vocals`,
    mode: "3faixas",
  }).catch(() => {});
}

// --------------------------------------------------------------- YouTube

let pendingOpen = null; // id do vídeo a abrir quando terminar de processar

export async function searchYT() {
  const q = get(query).trim();
  if (!q) return;
  ytOpen.set(true);
  ytLoading.set(true);
  ytResults.set([]);
  try {
    ytResults.set(await apiJson(`/api/search?q=${encodeURIComponent(q)}`));
  } catch (e) {
    ytResults.set([]);
  }
  ytLoading.set(false);
}

export function backToLibrary() {
  query.set("");
  ytResults.set([]);
  ytOpen.set(false);
  const lists = document.querySelector(".lists");
  if (lists) lists.scrollTop = 0;
}

export async function clickYt(r) {
  const song = r.downloaded && get(library).find((s) => s.id === r.id);
  if (song) {
    backToLibrary();
    return openSong(song);
  }
  pendingOpen = r.id;
  // Mostra a música na biblioteca já como "processando", antes da resposta do servidor
  jobs.update((js) => [
    ...js.filter((j) => j.id !== r.id),
    { id: r.id, title: r.title, status: "na fila", pct: 0 },
  ]);
  backToLibrary();
  await postJson("/api/process", {
    id: r.id,
    title: r.title,
    mode: get(backing) ? "3faixas" : "2faixas",
  }).catch(() => {});
}

export async function refreshLibrary() {
  try {
    library.set(await apiJson("/api/library"));
  } catch (e) {}
}

export async function clearFinishedJobs() {
  await postJson("/api/jobs/clear", {}).catch(() => {});
}

// -------------------------------------------------- sessão de controle remoto

function sessionState() {
  return {
    song: player.song
      ? { artist: player.song.artist, track: player.song.track, folder: player.song.folder }
      : null,
    playing: player.playing,
    pitch: player.pitch || 0,
    keyOrig: player.song ? (player.song.capo ? 12 - (player.song.capo % 12) : null) : null,
    volume: player.volume,
    cur: player.now ? player.now() : 0,
    dur: player.duration || 0,
    stems: player.stems.map((s) => ({ label: s.label, vol: s.vol, muted: s.muted })),
    bg: get(darkenBg),
    focus: get(focusMode),
    paint: get(wordSync),
    score: get(scoreEnabled),
    offset: get(lyrOffset) || 0,
    size: get(lyricScale) || 1,
  };
}

export function execRemoteCmd(cmd) {
  switch (cmd.type) {
    case "play":
      togglePlay();
      break;
    case "prev":
      // reinicia a música atual (não há fila de "anterior")
      if (player.playing) {
        player.stop();
        player.offset = 0;
        player.play();
      } else {
        player.offset = 0;
      }
      break;
    case "next":
      playNext();
      break;
    case "stemVol":
      setStemVol(cmd.index, cmd.vol);
      bumpStems();
      break;
    case "stemMute":
      toggleStemMute(cmd.index);
      bumpStems();
      break;
    case "toggle":
      if (cmd.key === "bg") toggleDarkenBg();
      else if (cmd.key === "focus") toggleFocusMode();
      else if (cmd.key === "paint") toggleWordSync();
      else if (cmd.key === "score") toggleScore();
      break;
    case "enqueue":
      if (cmd.song && cmd.song.folder) addToQueue(cmd.song.folder);
      break;
    case "lyricsOffset":
      nudge(cmd.delta || 0);
      break;
    case "lyricsResetOffset":
      resetOffset();
      break;
    case "seek":
      if (player.duration && cmd.t != null) player.seek(cmd.t);
      break;
    case "pitch":
      setPitch(cmd.semi | 0);
      break;
    case "fontSize":
      setLyricScale(cmd.scale);
      break;
  }
}

// Dedupe: o mesmo comando chega pelo WS e pela resposta do heartbeat
const seenCmds = new Set();
function execCmdOnce(cmd) {
  if (!cmd) return;
  if (cmd.i == null) return execRemoteCmd(cmd); // sem seq: executa sempre
  if (seenCmds.has(cmd.i)) return;
  seenCmds.add(cmd.i);
  if (seenCmds.size > 500) seenCmds.delete(seenCmds.values().next().value); // cap
  execRemoteCmd(cmd);
}

async function sessionLoop() {
  try {
    const r = await postJson("/api/session/heartbeat", {
      session: sessionId,
      state: sessionState(),
    });
    for (const cmd of r.commands || []) execCmdOnce(cmd);
  } catch (e) {}
}

// --------------------------------------------------------------- jobs (WS)

let prevJobStatus = null; // Map id->status; o primeiro snapshot é a linha de base

async function onJobs(list) {
  const before = prevJobStatus;
  prevJobStatus = new Map(list.map((j) => [j.id, j.status]));
  jobs.set(list);
  if (!before) return;
  const finished = list.filter((j) => j.status === "pronto" && before.get(j.id) !== "pronto");
  if (!finished.length) return;
  await refreshLibrary();
  ytResults.update((rs) => {
    rs.forEach((r) => {
      if (finished.some((j) => j.id === r.id)) r.downloaded = true;
    });
    return rs;
  });
  // A música aberta foi reprocessada (ex.: backing separado): recarrega no mesmo ponto
  const cur =
    player.song && finished.find((j) => j.folder === player.song.folder && j.id !== pendingOpen);
  if (cur) reloadCurrent();
  const open = finished.find((j) => j.id === pendingOpen);
  if (open) {
    pendingOpen = null;
    const s = byFolder(open.folder);
    if (s && player.playing) addToQueue(s.folder);
    else if (s) openSong(s);
  }
}

// ------------------------------------------------------------- tick (rAF)

export const frame = writable({ t: 0, playing: false, duration: 0 });
const tickFns = new Set();
export function onTick(fn) {
  tickFns.add(fn);
  return () => tickFns.delete(fn);
}

function startTick() {
  const tick = () => {
    if (player.stems.length) {
      let t = player.now();
      if (player.playing && t >= player.duration) {
        player.pause();
        player.offset = 0;
        t = 0;
        if (get(queue).length) playNext();
      }
      frame.set({ t, playing: player.playing, duration: player.duration });
      for (const fn of tickFns) fn(t);
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

// --------------------------------------------------------------- desligar

export async function shutdown() {
  const busy = get(jobs).filter((j) => j.status === "processando" || j.status === "na fila");
  const body = [];
  if (busy.length) {
    body.push([
      {
        t:
          busy.length === 1
            ? "Uma música está sendo processada"
            : `${busy.length} músicas estão sendo processadas`,
        b: true,
      },
      { t: busy.length > 1 ? " e serão interrompidas." : " e será interrompida." },
    ]);
  }
  body.push([
    { t: "Celulares e tablets conectados também param de funcionar. Para abrir de novo, use o atalho " },
    { t: "Karaoke Player", b: true },
    { t: "." },
  ]);
  const ok = await confirmBox({
    title: "Desligar o karaokê?",
    body,
    ok: "Desligar",
    danger: true,
  });
  if (!ok) return;
  player.pause();
  await postJson("/api/shutdown", {}).catch(() => {});
  off.set(true);
}

// ---------------------------------------------------------------- init

export async function loadSettings() {
  try {
    const cfg = await apiJson("/api/settings");
    scoreEnabled.set(cfg.score_enabled === true);
  } catch (e) {
    // offline ou ainda não tem settings — defaults
  }
}

export function initTV() {
  // Semântica do legado na carga inicial: o GET /api/queue só sobrescreve a
  // fila local se o servidor tiver itens. Os eventos WS "queue" (incluindo o
  // snapshot inicial, que chegaria vazio) só reconciliam DEPOIS dessa carga.
  let queueReady = false;
  loadSettings();
  connectWS({
    queue: (m) => {
      if (!queueReady) return;
      const remote = m.queue || [];
      // Reconcilia: outro dispositivo pode ter mudado a fila
      if (JSON.stringify(remote) !== JSON.stringify(get(queue))) {
        queue.set(remote);
        store.set("queue", remote);
      }
    },
    jobs: (m) => onJobs(m.jobs || []),
    align: (m) => {
      // Progresso do alinhamento palavra-a-palavra da música atual
      const song = player.song;
      if (!song || m.folder !== song.folder || !get(wordSync)) return;
      if (m.pct >= 100) loadWords(song); // terminou: busca o words.json pronto
      else syncNote.set(`sincronizando${m.pct ? ` ${m.pct}%` : ""}`);
    },
    command: (m) => {
      if (m.session === sessionId) execCmdOnce(m.command);
    },
  });
  refreshLibrary();
  // Fila inicial do servidor (sobrescreve a local se houver)
  apiJson("/api/queue")
    .then((remote) => {
      if (Array.isArray(remote) && remote.length) {
        queue.set(remote);
        store.set("queue", remote);
      }
    })
    .catch(() => {})
    .finally(() => {
      queueReady = true;
    });
  sessionLoop();
  setInterval(sessionLoop, 2000);
  startTick();
}
