"""Ponto de entrada do app de Mac: sobe o servidor e abre a interface.

    python -m karaoke.app [porta]

Se já houver um servidor do app rodando na porta, apenas abre a janela de novo
(evita duas instâncias disputando a mesma porta). Roda no venv leve do backend.
"""
import json
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

from . import server

PORT = 8765
LOADING_HTML = """<!doctype html><meta charset="utf-8"><title>Karaokê</title>
<body style="margin:0;background:#0a0a0a;color:#eceef5;font:16px -apple-system,system-ui,sans-serif;display:grid;place-items:center;min-height:100vh">
  <div style="text-align:center">
    <div style="font-size:18px;font-weight:700">Abrindo Karaokê…</div>
    <div style="margin-top:8px;color:#9a9a9a">Preparando a interface nativa</div>
  </div>
</body>"""
ERROR_HTML = """<!doctype html><meta charset="utf-8"><title>Karaokê</title>
<body style="margin:0;background:#0a0a0a;color:#eceef5;font:16px -apple-system,system-ui,sans-serif;display:grid;place-items:center;min-height:100vh;padding:24px">
  <div style="max-width:420px;text-align:center">
    <div style="font-size:18px;font-weight:700">Não foi possível abrir o Karaokê</div>
    <div style="margin-top:8px;color:#9a9a9a">O servidor local demorou para responder.</div>
  </div>
</body>"""


def is_running(port):
    """True se o backend novo já responde na porta (não confunde com o legado)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1) as r:
            return json.load(r).get("app") == "karaoke-fastapi"
    except Exception:
        return False


def port_available(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def choose_port(port, explicit=False):
    if is_running(port) or explicit or port_available(port):
        return port
    for candidate in range(port + 1, port + 20):
        if port_available(candidate):
            return candidate
    return port


def wait_until_running(port, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_running(port):
            return True
        time.sleep(0.3)
    return False


def open_browser_when_ready(port, timeout=60):
    if wait_until_running(port, timeout):
        webbrowser.open(f"http://localhost:{port}/")


def stop_local_server(port):
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/shutdown",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=2).read()
    except Exception:
        pass


def open_native_window(port, shutdown_on_close=False):
    import webview

    url = f"http://127.0.0.1:{port}/"
    window = webview.create_window(
        "Karaokê",
        html=LOADING_HTML,
        width=1440,
        height=900,
        min_size=(1100, 700),
        text_select=True,
    )

    def load():
        if wait_until_running(port, 60):
            window.load_url(url)
        else:
            window.load_html(ERROR_HTML)

    webview.start(load, gui="cocoa", debug=False)
    if shutdown_on_close:
        stop_local_server(port)


def run_server(port):
    old_argv = sys.argv[:]
    try:
        sys.argv = [sys.argv[0], str(port)]
        server.main()
    finally:
        sys.argv = old_argv


def main():
    explicit = len(sys.argv) > 1
    requested = int(sys.argv[1]) if explicit else PORT
    port = choose_port(requested, explicit=explicit)
    started_server = False
    if not is_running(port):
        threading.Thread(target=run_server, args=(port,), daemon=True).start()
        started_server = True
    try:
        open_native_window(port, shutdown_on_close=started_server)
    except Exception:
        if started_server:
            threading.Thread(target=open_browser_when_ready, args=(port,), daemon=True).start()
            while True:
                time.sleep(3600)
        else:
            webbrowser.open(f"http://localhost:{port}/")


if __name__ == "__main__":
    main()
