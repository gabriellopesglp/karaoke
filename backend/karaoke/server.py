"""Servidor local do Karaokê (FastAPI).

Serve a interface de TV (index.html), o controle remoto (remote.html), a biblioteca
em config.lib_dir() e a fila de processamento (jobs.py). Escuta na rede local para
celular/tablet abrirem pelo QR code: no próprio computador não pede nada; de outros
aparelhos exige a chave que vai no QR code (depois do primeiro acesso ela fica num
cookie).

    python -m karaoke.server [porta]
"""
import asyncio
import json
import mimetypes
import os
import secrets
import socket
import sys
import threading
import time
import urllib.parse
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import (config, covers, jobs, library, lyrics, sessions, settings,
               setup_env, words as words_mod, ws)

# Build do frontend novo (Vite → backend/karaoke/static).
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Página do primeiro uso (instala o ambiente de IA no Mac).
SETUP_PAGE = Path(__file__).resolve().parent / "setup_page.html"


def remote_html():
    """HTML do controle remoto gerado pelo frontend novo."""
    return (STATIC_DIR / "remote.html").read_bytes()


def index_html():
    """HTML da TV gerado pelo frontend novo."""
    return (STATIC_DIR / "index.html").read_bytes()

PORT = 8765  # ajustado em main()


# ---------------------------------------------------------------- acesso pela rede (QR code)

def get_token(new=False):
    f = config.data_dir() / "token"
    if new or not f.is_file():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(secrets.token_urlsafe(18))
        f.chmod(0o600)
    return f.read_text().strip()


def lan_ip():
    # Descobre o IP na rede Wi-Fi (UDP "connect" não envia nenhum pacote)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def host_kind(headers):
    """'local', 'lan' ou None. Bloqueia "DNS rebinding": um site malicioso apontando o próprio
    domínio para 127.0.0.1 chegaria aqui com outro nome no cabeçalho Host."""
    host = (headers.get("host") or "").lower()
    if host in (f"localhost:{PORT}", f"127.0.0.1:{PORT}", f"[::1]:{PORT}"):
        return "local"
    if host == f"{lan_ip()}:{PORT}":
        return "lan"
    return None


def is_local(client_ip, kind):
    return client_ip in ("127.0.0.1", "::1") and kind == "local"


def cross_site(headers):
    """Pedido disparado por outro site aberto no navegador (ex.: página maliciosa)."""
    if headers.get("sec-fetch-site") in ("cross-site", "same-site"):
        return True
    origin = headers.get("origin")
    return bool(origin) and origin != f"http://{headers.get('host')}"


def has_cookie(headers):
    # Chave no cookie ou no cabeçalho X-Karaoke-Token (para navegadores que bloqueiam cookies)
    token = get_token()
    if secrets.compare_digest(headers.get("x-karaoke-token") or "", token):
        return True
    for part in (headers.get("cookie") or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == "karaoke" and secrets.compare_digest(v, token):
            return True
    return False


def share_info(session_id=None):
    import qrcode
    import qrcode.image.svg
    ip = lan_ip()
    if not ip:
        return {"error": "O Mac não está conectado a uma rede."}
    # Se session_id for fornecido, o QR aponta para a página de controle remoto
    # daquela sessão específica. Senão, aponta para o app completo.
    if session_id:
        url = f"http://{ip}:{PORT}/remote?session={session_id}&t={get_token()}"
    else:
        url = f"http://{ip}:{PORT}/?t={get_token()}"
    svg = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    return {"url": url, "address": f"http://{ip}:{PORT}", "svg": svg.to_string(encoding="unicode")}


DENIED = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Karaokê</title><body style="background:#0e0f15;color:#eceef5;font:16px -apple-system,system-ui,sans-serif;
display:grid;place-items:center;min-height:100vh;margin:0;text-align:center;padding:24px">
<div style="max-width:360px;width:100%">
<svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="#ffc94a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7"/></svg>
<h2>Acesso pelo QR code</h2>
<p id="msg" style="color:#8b90a6">No Mac, clique em <b>Abrir no celular ou tablet</b> e escaneie o QR code com este aparelho.</p>

<!-- Campo para colar a URL do QR — sempre disponível, funciona em HTTP -->
<div id="pasteBox" style="margin:16px 0">
  <input id="tokenIn" placeholder="cole aqui a URL do QR code" style="width:100%;box-sizing:border-box;padding:12px 14px;border-radius:10px;border:1px solid #3a3a3a;background:#1c1c1c;color:#eceef5;font-size:15px;text-align:center" />
  <p style="color:#6b7088;font-size:13px;margin:8px 0 0">Abra a Câmera do iPad, aponte para o QR, toque na notificação e <b>Copiar</b>. Depois cole aqui.</p>
</div>

<p>
<button id="retry" style="display:none;background:#e1e622;color:#1a1405;border:0;border-radius:8px;padding:10px 20px;font-weight:700;cursor:pointer;margin:4px">Tentar de novo</button>
<button id="scanBtn" style="display:none;background:#2a2a2a;color:#eceef5;border:1px solid #444;border-radius:8px;padding:10px 20px;font-weight:700;cursor:pointer;margin:4px">Escanear com a câmera</button>
</p>
<video id="cam" playsinline muted autoplay style="display:none;width:100%;max-width:280px;border-radius:12px;margin-top:12px"></video>
<p id="camErr" style="color:#ff6b6b;font-size:14px;display:none"></p>
</div>
<script>
(function(){
  var msg = document.getElementById("msg");
  var retry = document.getElementById("retry");
  var scanBtn = document.getElementById("scanBtn");
  var cam = document.getElementById("cam");
  var camErr = document.getElementById("camErr");
  var tokenIn = document.getElementById("tokenIn");
  var stream = null, detector = null, scanning = false;

  function go(t){
    var m = String(t).match(/[?&]t=([^&]+)/);
    var tok = m ? decodeURIComponent(m[1]) : t.trim();
    if(!tok) return;
    localStorage.setItem("karaoke-token", tok);
    sessionStorage.removeItem("tried-token");
    location.replace((location.pathname === "/remote" ? "/remote?" : "/?") + "t=" + encodeURIComponent(tok));
  }

  function tryStored(){
    try{
      var t = localStorage.getItem("karaoke-token");
      if(t){
        if(sessionStorage.getItem("tried-token")){
          msg.textContent = "A chave deste aparelho foi alterada no Mac. Cole a nova URL do QR abaixo ou toque em Tentar de novo.";
          retry.style.display = "inline-block";
          return;
        }
        sessionStorage.setItem("tried-token","1");
        location.replace((location.pathname === "/remote" ? "/remote?" : "/?") + "t=" + encodeURIComponent(t));
      }
    }catch(e){}
  }

  retry.onclick = function(){ sessionStorage.removeItem("tried-token"); tryStored(); };

  // Campo de colar — sempre funciona, mesmo em HTTP
  tokenIn.addEventListener("paste", function(){ setTimeout(function(){ go(tokenIn.value); }, 50); });
  tokenIn.addEventListener("change", function(){ go(tokenIn.value); });
  tokenIn.addEventListener("keydown", function(e){ if(e.key === "Enter") go(tokenIn.value); });

  // Câmera só funciona em contexto seguro (HTTPS ou localhost)
  if(window.isSecureContext && navigator.mediaDevices && navigator.mediaDevices.getUserMedia){
    scanBtn.style.display = "inline-block";
  }

  scanBtn.onclick = async function(){
    if(scanning){ stopCam(); return; }
    scanBtn.textContent = "Parar";
    camErr.style.display = "none";
    try{
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false
      });
      cam.srcObject = stream;
      cam.style.display = "block";
      await cam.play();
      scanning = true;
      if("BarcodeDetector" in window){
        detector = new BarcodeDetector({formats:["qr_code"]});
        (function loop(){
          if(!scanning) return;
          detector.detect(cam).then(function(codes){
            if(codes && codes[0]){ go(codes[0].rawValue); return; }
            requestAnimationFrame(loop);
          }).catch(function(){ requestAnimationFrame(loop); });
        })();
      } else {
        camErr.textContent = "Este navegador não lê QR automaticamente. Use o campo acima para colar a URL.";
        camErr.style.display = "block";
      }
    }catch(e){
      var m = "Não foi possível acessar a câmera.";
      if(e.name === "NotAllowedError"){
        m = "Permissão da câmera negada. Permita o acesso em Ajustes > Safari > Câmera, ou use o campo acima para colar a URL.";
      } else if(e.name === "NotFoundError"){
        m = "Nenhuma câmera encontrada. Use o campo acima para colar a URL.";
      } else if(e.name === "NotReadableError"){
        m = "A câmera está em uso por outro app. Feche outros apps ou cole a URL no campo acima.";
      } else {
        m += " " + e.message + ". Use o campo acima para colar a URL.";
      }
      camErr.textContent = m;
      camErr.style.display = "block";
      scanBtn.textContent = "Escanear com a câmera";
    }
  };

  function stopCam(){
    scanning = false;
    if(stream){ stream.getTracks().forEach(function(t){ t.stop(); }); stream = null; }
    cam.style.display = "none";
    scanBtn.textContent = "Escanear com a câmera";
  }

  tryStored();
})();</script>"""


# ---------------------------------------------------------------- app e middleware

@asynccontextmanager
async def lifespan(app):
    ws.attach(asyncio.get_running_loop())
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


class AuthMiddleware:
    """Porta das verificações do Handler legado: DNS-rebinding (421), pedidos
    cross-site (403) e a chave do QR code para acesso pela rede local."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            # lifespan e outros scopes passam direto (sem headers para inspecionar)
            return await self.app(scope, receive, send)

        headers = Headers(scope=scope)
        kind = host_kind(headers)
        client = (scope.get("client") or ("", 0))[0]

        if scope["type"] == "websocket":
            if kind is None or (not is_local(client, kind) and not has_cookie(headers)):
                await send({"type": "websocket.close", "code": 4403})
                return
            return await self.app(scope, receive, send)

        path = scope["path"]

        async def reply(resp):
            await resp(scope, receive, send)

        if kind is None:
            return await reply(JSONResponse({"error": "endereço não reconhecido"}, status_code=421))

        if scope["method"] == "GET":
            if path != "/" and cross_site(headers):
                return await reply(JSONResponse({"error": "pedido de outro site"}, status_code=403))
            if not is_local(client, kind) and not has_cookie(headers):
                qs = urllib.parse.parse_qs(scope["query_string"].decode())
                token_ok = secrets.compare_digest(qs.get("t", [""])[0], get_token())
                if path in ("/", "/remote") and token_ok:
                    # Chave do QR code válida: entrega a página e guarda a chave em cookie
                    # (a página também guarda no aparelho e tira a chave da barra de endereço)
                    body = remote_html() if path == "/remote" else index_html()
                    return await reply(Response(
                        body, media_type="text/html; charset=utf-8", headers={
                            "Set-Cookie": f"karaoke={get_token()}; Max-Age=31536000; Path=/; HttpOnly; SameSite=Lax",
                        }))
                return await reply(Response(DENIED.encode(), media_type="text/html; charset=utf-8",
                                            status_code=403))
        else:
            if cross_site(headers):
                return await reply(JSONResponse({"error": "pedido de outro site"}, status_code=403))
            if not is_local(client, kind) and not has_cookie(headers):
                return await reply(JSONResponse({"error": "sem acesso"}, status_code=403))
            # Limite de tamanho do corpo (1MB) para evitar abuso
            if int(headers.get("content-length") or 0) > 1024 * 1024:
                return await reply(JSONResponse({"error": "corpo muito grande (máx 1MB)"},
                                                status_code=413))

        scope["karaoke_local"] = is_local(client, kind)

        async def send_with_cache(message):
            if message["type"] == "http.response.start":
                h = MutableHeaders(raw=message.setdefault("headers", []))
                if "cache-control" not in h:
                    h["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_with_cache)


app.add_middleware(AuthMiddleware)


@app.exception_handler(FileNotFoundError)
async def _not_found(request, exc):
    return JSONResponse({"error": "não encontrado"}, status_code=404)


@app.exception_handler(StarletteHTTPException)
async def _http_exc(request, exc):
    msg = "não encontrado" if exc.status_code == 404 else str(exc.detail)
    return JSONResponse({"error": msg}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def _validation_exc(request, exc):
    return JSONResponse({"error": "parâmetros inválidos"}, status_code=400)


@app.exception_handler(Exception)
async def _server_exc(request, exc):
    return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------- páginas e API (GET)

@app.get("/")
def index():
    # Primeiro uso: sem o ambiente de IA, manda instalar antes de abrir a TV.
    if not config.ai_ready():
        return RedirectResponse("/setup", status_code=303)
    return Response(index_html(), media_type="text/html; charset=utf-8")


@app.get("/setup")
def setup_page():
    return Response(SETUP_PAGE.read_bytes(), media_type="text/html; charset=utf-8")


@app.get("/remote")
def remote():
    return Response(remote_html(), media_type="text/html; charset=utf-8")


@app.get("/assets/{path:path}")
def static_assets(path: str):
    # Assets do build do frontend novo (nomes com hash: cache longo/imutável)
    base = (STATIC_DIR / "assets").resolve()
    f = (base / path).resolve()
    if base not in f.parents or not f.is_file():
        raise FileNotFoundError(path)
    ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
    return FileResponse(f, media_type=ctype,
                        headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.get("/api/ping")
def ping():
    # 'app' identifica o backend novo; o desktop app usa isso para não confundir
    # com um servidor legado na mesma porta.
    return {"ok": True, "app": "karaoke-fastapi"}


@app.get("/api/setup/status")
def setup_status():
    return setup_env.status()


@app.post("/api/setup/start")
def setup_start(body: dict | None = Body(None)):
    body = body or {}
    error = setup_env.start(bool(body.get("extra3faixas")))
    if error:
        return JSONResponse({"error": error}, status_code=409)
    return {"ok": True}


@app.get("/api/library")
def get_library():
    return library.library()


@app.get("/api/queue")
def get_queue():
    return library.get_queue()


@app.get("/api/search")
def search(q: str = ""):
    return jobs.yt_search(q)


@app.get("/api/jobs")
def get_jobs():
    return jobs.list_jobs()


@app.get("/api/words")
def get_words(folder: str):
    return words_mod.words(folder)


@app.get("/api/session/state")
def session_state(session: str = ""):
    state = sessions.session_get(session)
    if state is None:
        return JSONResponse({"error": "sessão não encontrada"}, status_code=404)
    return state


@app.get("/api/lyrics/options")
def get_lyrics_options(folder: str, q: str = ""):
    return lyrics.lyrics_options(folder, q)


@app.get("/api/cover/options")
def get_cover_options(folder: str, q: str = ""):
    return covers.cover_options(folder, q)


@app.get("/api/lyrics")
def get_lyrics(folder: str, refresh: str = ""):
    return lyrics.lyrics(folder, refresh == "1")


@app.get("/api/share")
def share(session: str = "", reset: str = ""):
    if reset == "1":
        get_token(new=True)  # desconecta os aparelhos que já tinham acesso
    # session opcional: se fornecido, gera QR do controle remoto da sessão
    return share_info(session or None)


@app.get("/api/settings")
def get_settings():
    cfg = settings.get()
    # nunca expõe a chave de API completa para a rede
    masked = cfg.copy()
    if masked.get("mvsep_api_key"):
        masked["mvsep_api_key"] = masked["mvsep_api_key"][:4] + "****"
    return masked


@app.post("/api/settings")
def post_settings(body: dict | None = Body(None)):
    body = body or {}
    allowed = {"separation", "mvsep_api_key", "mvsep_endpoint", "score_enabled"}
    updates = {k: v for k, v in body.items() if k in allowed}
    return settings.set(updates)


@app.get("/api/settings/gpu")
def gpu_available():
    return {"device": settings.demucs_device(), "available": settings._detect_gpu_device()}


ALLOWED_MEDIA = {f for f, _ in library.STEMS} | {"cover.jpg"}


@app.get("/media/{folder}/{name}")
def media(folder: str, name: str):
    if name not in ALLOWED_MEDIA:
        raise FileNotFoundError("arquivo")
    f = library.song_dir(folder) / name
    if not f.is_file():
        raise FileNotFoundError(name)
    ctype = "image/jpeg" if name == "cover.jpg" else "audio/mpeg"
    return FileResponse(f, media_type=ctype, headers={"Cache-Control": "public, max-age=3600"})


# ---------------------------------------------------------------- API (POST)

@app.post("/api/process")
def process(body: dict | None = Body(None)):
    body = body or {}
    mode = "3faixas" if body.get("mode") == "3faixas" else "2faixas"
    try:
        return jobs.enqueue(body.get("id"), body.get("title", body.get("id")), mode)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/api/lyrics/choose")
def lyrics_choose(body: dict | None = Body(None)):
    body = body or {}
    try:
        return lyrics.choose_lyrics(body["folder"], body["id"])
    except (FileNotFoundError, ValueError, KeyError, TypeError):
        return JSONResponse({"error": "letra não encontrada"}, status_code=404)


@app.post("/api/lyrics/sync")
def lyrics_sync(body: dict | None = Body(None)):
    body = body or {}
    try:
        return lyrics.save_sync(body["folder"], body.get("synced", ""))
    except FileNotFoundError:
        return JSONResponse({"error": "letra não encontrada"}, status_code=404)


@app.post("/api/cover")
def cover(body: dict | None = Body(None)):
    body = body or {}
    try:
        return {"ok": covers.refresh_cover(body["folder"], body.get("url"))}
    except FileNotFoundError:
        return JSONResponse({"error": "não encontrado"}, status_code=404)


@app.post("/api/delete")
def delete(body: dict | None = Body(None)):
    body = body or {}
    try:
        library.delete_song(body["folder"])
        return {"ok": True}
    except FileNotFoundError:
        return JSONResponse({"error": "não encontrado"}, status_code=404)


def _shutdown_server():
    time.sleep(0.3)  # deixa a resposta chegar ao navegador
    jobs.terminate_running()
    server = getattr(app.state, "uvicorn", None)
    if server is not None:
        server.should_exit = True


@app.post("/api/shutdown")
def shutdown(request: Request):
    if not request.scope.get("karaoke_local"):
        return JSONResponse({"error": "só no Mac"}, status_code=403)
    threading.Thread(target=_shutdown_server, daemon=True).start()
    return {"ok": True}


@app.post("/api/jobs/clear")
def jobs_clear():
    jobs.clear_finished()
    return {"ok": True}


@app.post("/api/queue")
def save_queue(body: dict | None = Body(None)):
    body = body or {}
    # body.queue deve ser uma lista de objetos (as músicas da fila)
    items = body.get("queue")
    if not isinstance(items, list):
        return JSONResponse({"error": "queue deve ser uma lista"}, status_code=400)
    library.save_queue(items)
    return {"ok": True}


# ---- sessões de controle remoto ----

@app.post("/api/session/heartbeat")
def session_heartbeat(body: dict | None = Body(None)):
    body = body or {}
    sid = body.get("session")
    if not sid:
        return JSONResponse({"error": "session é obrigatório"}, status_code=400)
    sessions.session_heartbeat(sid, body.get("state", {}))
    # devolve os comandos pendentes para a sessão controlada executar
    return {"commands": sessions.session_poll_commands(sid)}


@app.post("/api/session/command")
def session_command(body: dict | None = Body(None)):
    body = body or {}
    sid = body.get("session")
    if not sid:
        return JSONResponse({"error": "session é obrigatório"}, status_code=400)
    if not sessions.session_send_command(sid, body.get("command", {})):
        return JSONResponse({"error": "sessão não encontrada"}, status_code=404)
    return {"ok": True}


# ---------------------------------------------------------------- WebSocket

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    q = ws.register()
    # estado inicial: fila e jobs atuais
    await websocket.send_text(json.dumps({"type": "queue", "queue": library.get_queue()},
                                         ensure_ascii=False))
    await websocket.send_text(json.dumps({"type": "jobs", "jobs": jobs.list_jobs()},
                                         ensure_ascii=False))

    async def sender():
        while True:
            msg = await q.get()
            await websocket.send_text(json.dumps(msg, ensure_ascii=False))

    task = asyncio.create_task(sender())
    try:
        while True:
            await websocket.receive_text()  # cliente não manda nada; só detecta desconexão
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        task.cancel()
        ws.unregister(q)


# ---------------------------------------------------------------- entrypoint

def main():
    global PORT
    PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    jobs.start()
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="warning"))
    app.state.uvicorn = server
    print(f"Karaokê em http://localhost:{PORT} (rede: http://{lan_ip()}:{PORT})", flush=True)
    server.run()
    print("Karaokê desligado", flush=True)


if __name__ == "__main__":
    main()
