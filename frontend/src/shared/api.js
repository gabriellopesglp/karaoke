// Cliente REST do Karaokê.
//
// Autenticação: o QR code da TV abre /remote?session=X&t=TOKEN. O token fica
// salvo no aparelho (localStorage) e vai no cabeçalho X-Karaoke-Token — assim
// funciona mesmo em navegador que bloqueia cookie de terceiros. Qualquer 403
// significa "chave trocada no Mac": volta para /remote, que mostra a tela de
// reconexão (colar URL / escanear de novo).

const TOKEN_KEY = "karaoke-token";
const SESSION_KEY = "karaoke-session";

export function captureAuth() {
  const params = new URLSearchParams(location.search);
  const t = params.get("t");
  const s = params.get("session");
  try {
    if (t) localStorage.setItem(TOKEN_KEY, t);
    if (s) localStorage.setItem(SESSION_KEY, s);
  } catch (e) {}
  // Tira o token da barra de endereço (continua salvo no aparelho)
  if (t) {
    const clean = new URLSearchParams();
    const sid = s || getSession();
    if (sid) clean.set("session", sid);
    history.replaceState(null, "", clean.toString() ? `/remote?${clean}` : "/remote");
  }
}

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch (e) {
    return null;
  }
}

export function getSession() {
  const fromUrl = new URLSearchParams(location.search).get("session");
  if (fromUrl) return fromUrl;
  try {
    return localStorage.getItem(SESSION_KEY);
  } catch (e) {
    return null;
  }
}

export async function api(path, opts = {}) {
  const token = getToken();
  const headers = { ...(opts.headers || {}) };
  if (token) headers["X-Karaoke-Token"] = token;
  const r = await fetch(path, { ...opts, headers });
  // skipAuthRedirect: o modal de compartilhar prefere mostrar o erro na caixa
  // (paridade com o authFetch legado, que não redirecionava em /api/share)
  if (r.status === 403 && !opts.skipAuthRedirect) {
    // chave inválida/trocada: /remote sem chave válida mostra a tela de reconexão
    location.replace(location.pathname);
    throw new Error("auth");
  }
  return r;
}

export async function apiJson(path, opts = {}) {
  const r = await api(path, opts);
  if (!r.ok) {
    const err = new Error(`HTTP ${r.status}`);
    err.status = r.status;
    try {
      err.detail = (await r.json()).error;
    } catch (e) {}
    throw err;
  }
  return r.json();
}

export function postJson(path, body) {
  return apiJson(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// Envia um comando para a sessão da TV (ver sessions.py / execRemoteCmd da TV)
export function sendCommand(session, command) {
  return postJson("/api/session/command", { session, command });
}
