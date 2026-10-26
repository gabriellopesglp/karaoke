// WebSocket /ws com reconexão automática (backoff exponencial).
//
// O servidor manda um snapshot inicial (queue + jobs) e depois eventos de
// broadcast (queue, jobs, session, align). A autenticação do WS é pelo cookie
// "karaoke" que o servidor grava ao entregar /remote com o token do QR code;
// se o servidor fechar com código 4403, o cookie não vale mais e o usuário
// precisa se reconectar pela tela de /remote.
//
// Uso: connectWS({ queue: fn, jobs: fn, session: fn }) — cada handler recebe
// a mensagem JSON já parseada do seu tipo.

import { writable } from "svelte/store";

// "online" | "offline" (offline = caiu e vai tentar de novo)
export const wsStatus = writable("offline");

let sock = null;
let attempt = 0;
let timer = null;
let handlers = {};

export function connectWS(h) {
  handlers = h || {};
  open();
}

function open() {
  clearTimeout(timer);
  const proto = location.protocol === "https:" ? "wss" : "ws";
  try {
    sock = new WebSocket(`${proto}://${location.host}/ws`);
  } catch (e) {
    schedule();
    return;
  }
  sock.onopen = () => {
    attempt = 0;
    wsStatus.set("online");
  };
  sock.onmessage = (ev) => {
    let msg;
    try {
      msg = JSON.parse(ev.data);
    } catch (e) {
      return;
    }
    const fn = handlers[msg.type];
    if (fn) fn(msg);
  };
  sock.onclose = (ev) => {
    wsStatus.set("offline");
    sock = null;
    if (ev.code === 4403) {
      // sem acesso: reapresenta a tela de reconexão
      location.replace("/remote");
      return;
    }
    schedule();
  };
  sock.onerror = () => {
    try {
      sock.close();
    } catch (e) {}
  };
}

function schedule() {
  clearTimeout(timer);
  // 1s, 1.6s, 2.6s, ... até no máximo 10s entre tentativas
  const delay = Math.min(10000, 1000 * Math.pow(1.6, attempt++));
  timer = setTimeout(open, delay);
  // Muitas falhas seguidas: navegadores nem sempre entregam o código 4403 do
  // fechamento (a rejeição do handshake vira um close genérico). Confere se o
  // cookie usado pelo WS ainda vale — este fetch vai SEM o cabeçalho de token
  // de propósito, para testar exatamente o mesmo acesso que o WS tem.
  if (attempt === 8) {
    fetch("/api/ping").then((r) => {
      if (r.status === 403) location.replace("/remote");
    }).catch(() => {});
  }
}

// Ao voltar para a aba/tela, reconecta na hora se estiver caído
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && !sock) {
    attempt = 0;
    open();
  }
});
