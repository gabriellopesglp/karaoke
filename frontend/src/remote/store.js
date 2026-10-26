// Estado do controle remoto.
//
// Fontes de dados:
//   - REST /api/library, /api/session/state (carga inicial)
//   - WS /ws (snapshot de queue+jobs e eventos ao vivo: queue, jobs, session)
//
// UI otimista: cmd() aplica o efeito do comando no estado local ANTES da TV
// responder (guardado em `overrides` por ~800 ms). Quando o evento "session"
// da TV chega nesse intervalo, o campo alterado mantém o valor local — sem
// flicker. Depois da janela, o valor da TV prevalece (reconciliação).

import { derived, get, writable } from "svelte/store";
import { apiJson, getSession, postJson, sendCommand } from "../shared/api.js";
import { connectWS, wsStatus } from "../shared/ws.js";

export const session = getSession();

export const library = writable([]);
export const queue = writable([]);
export const jobs = writable([]);
export const conn = wsStatus; // "online" | "offline"

// Último estado da sessão vindo da TV (heartbeat ~2s via WS)
export const sessionRaw = writable(null);
// false quando /api/session/state responde 404 (TV fechada / sessão expirada)
export const sessionFound = writable(true);

// Índice da biblioteca por pasta (para capa/título dos itens da fila)
export const libByFolder = derived(library, ($lib) => new Map($lib.map((s) => [s.folder, s])));
export const libById = derived(library, ($lib) => new Map($lib.filter((s) => s.id).map((s) => [s.id, s])));
export const queueSet = derived(queue, ($q) => new Set($q));

// ---------------------------------------------------------------- toasts

export const toasts = writable([]);
let toastSeq = 0;
export function toast(text, kind = "ok") {
  const id = ++toastSeq;
  toasts.update((t) => [...t, { id, text, kind }]);
  setTimeout(() => toasts.update((t) => t.filter((x) => x.id !== id)), 2600);
}

// ------------------------------------------------- músicas deste aparelho
// Pastas que ESTE aparelho enfileirou (para o destaque "você adicionou").
const MY_KEY = "karaoke-myqueue";
function loadMine() {
  try {
    return new Set(JSON.parse(localStorage.getItem(MY_KEY) || "[]"));
  } catch (e) {
    return new Set();
  }
}
export const mine = writable(loadMine());
function saveMine(set) {
  try {
    localStorage.setItem(MY_KEY, JSON.stringify([...set]));
  } catch (e) {}
}
function pruneMine(q) {
  const inQ = new Set(q);
  mine.update((s) => {
    const n = new Set([...s].filter((f) => inQ.has(f)));
    if (n.size !== s.size) saveMine(n);
    return n;
  });
}

// ------------------------------------------------------- UI otimista

const OVERRIDE_MS = 800;
let overrides = {}; // campo -> { value, until }
const overridesTick = writable(0);

// Estado da sessão com os overrides ativos aplicados por cima
export const view = derived([sessionRaw, overridesTick], ([$raw]) => {
  if (!$raw) return null;
  const now = Date.now();
  const v = { ...$raw };
  for (const k of Object.keys(overrides)) {
    if (overrides[k].until > now) v[k] = overrides[k].value;
    else delete overrides[k];
  }
  return v;
});

function optimistic(patch) {
  const until = Date.now() + OVERRIDE_MS;
  for (const [k, val] of Object.entries(patch)) overrides[k] = { value: val, until };
  overridesTick.update((n) => n + 1);
}

// Envia comando para a TV; `patch` é o efeito otimista no estado local.
export function cmd(command, patch) {
  if (patch) optimistic(patch);
  if (!session) return Promise.resolve();
  return sendCommand(session, command).catch(() => toast("comando não chegou à TV", "err"));
}

// Enfileira uma música da biblioteca e marca como "deste aparelho"
export function enqueueSong(song) {
  mine.update((s) => {
    s.add(song.folder);
    saveMine(s);
    return s;
  });
  return cmd({ type: "enqueue", song }).then(() => toast("adicionada à fila"));
}

// -------------------------------------------------------- posição (seek)
// A TV manda `cur` a cada ~2s; entre heartbeats interpolamos no cliente
// para a barra de progresso andar suavemente.
export const tick = writable(0);
let lastEventAt = Date.now();
sessionRaw.subscribe(() => {
  lastEventAt = Date.now();
});
setInterval(() => tick.set(Date.now()), 500);

export const position = derived([view, tick], ([$v]) => {
  if (!$v) return { cur: 0, dur: 0 };
  const dur = $v.dur || 0;
  let cur = $v.cur || 0;
  if ($v.playing && dur) cur = Math.min(dur, cur + (Date.now() - lastEventAt) / 1000);
  return { cur, dur };
});

// ------------------------------------------------------- fila (remota)

// Substitui a fila inteira no servidor (POST /api/queue é "replace all").
// Otimista: a lista local muda já; o evento WS do próprio servidor confirma.
export async function pushQueue(next) {
  queue.set(next);
  try {
    await postJson("/api/queue", { queue: next });
  } catch (e) {
    toast("não foi possível atualizar a fila", "err");
    refreshQueue();
  }
}

export function removeAt(i) {
  const q = [...get(queue)];
  q.splice(i, 1);
  pushQueue(q);
}

export function moveAt(i, dir) {
  const q = [...get(queue)];
  const j = i + dir;
  if (j < 0 || j >= q.length) return;
  [q[i], q[j]] = [q[j], q[i]];
  pushQueue(q);
}

// ----------------------------------------------------------- bootstrap

export async function refreshLibrary() {
  try {
    library.set(await apiJson("/api/library"));
  } catch (e) {}
}

export async function refreshQueue() {
  try {
    queue.set(await apiJson("/api/queue"));
  } catch (e) {}
}

export async function refreshSessionState() {
  if (!session) {
    sessionFound.set(false);
    return;
  }
  try {
    const s = await apiJson(`/api/session/state?session=${encodeURIComponent(session)}`);
    sessionRaw.set(s);
    sessionFound.set(true);
  } catch (e) {
    if (e.status === 404) sessionFound.set(false);
  }
}

export function initRemote() {
  connectWS({
    queue: (m) => {
      queue.set(m.queue || []);
      pruneMine(m.queue || []);
    },
    jobs: (m) => jobs.set(m.jobs || []),
    session: (m) => {
      if (m.session === session) {
        sessionRaw.set(m.state);
        sessionFound.set(true);
      }
    },
  });
  refreshLibrary();
  refreshSessionState();
}

// Se a TV estiver fechada, tenta de novo a cada 5s até ela aparecer
setInterval(() => {
  if (!get(sessionFound) && session) refreshSessionState();
}, 5000);
