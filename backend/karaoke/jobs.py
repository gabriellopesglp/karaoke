"""Fila de processamento: download + separação de voz via karaoke.pipeline.

Um worker thread único roda um vídeo por vez (duas separações juntas
disputariam a GPU e ficariam mais lentas). O pipeline roda no venv de IA:

    python -m karaoke.pipeline get <id> <2faixas|3faixas>

com PYTHONPATH apontando para o diretório do backend. O stderr do filho traz o
progresso ("PCT n" e etapas "HH:MM:SS  mensagem") e é gravado em
config.data_dir()/jobs/<id>.log; o caminho da pasta pronta sai no stdout.
"""
import os
import queue
import re
import signal
import subprocess
import threading
import time
from pathlib import Path

from . import config, library, ws

heavy = threading.RLock()  # separação e alinhamento usam a GPU: um de cada vez
jobs = {}            # id -> {id, title, mode, status, step, pct, folder, error, t}
job_queue = queue.Queue()
jobs_lock = threading.Lock()
running = set()      # subprocessos em andamento (para encerrar ao desligar)

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")  # formato dos ids de vídeo do YouTube


def ai_env():
    """Env para subprocessos do venv de IA: PYTHONPATH = diretório do backend."""
    env = os.environ.copy()
    backend = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = str(backend) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    # PATH de reserva (Homebrew etc.): o app aberto pelo Finder não herda o PATH do shell.
    env["PATH"] = os.pathsep.join([p for p in (env.get("PATH", ""), config.extra_path()) if p])
    return env


def _broadcast():
    ws.broadcast_jobs(list_jobs())


def list_jobs():
    with jobs_lock:
        return [dict(j) for j in sorted(jobs.values(), key=lambda j: j["t"])]


def enqueue(vid, title, mode):
    if not VIDEO_ID.match(vid or ""):
        raise ValueError("id de vídeo inválido")  # evita nomes de arquivo como "../../x" no log
    with jobs_lock:
        if vid in jobs and jobs[vid]["status"] in ("na fila", "processando"):
            return jobs[vid]
        jobs[vid] = {"id": vid, "title": title, "mode": mode, "status": "na fila",
                     "step": "", "pct": 0, "folder": None, "error": None, "t": time.time()}
    job_queue.put(vid)
    _broadcast()
    return jobs[vid]


def clear_finished():
    with jobs_lock:
        for k in [k for k, j in jobs.items() if j["status"] in ("pronto", "erro")]:
            del jobs[k]
    _broadcast()


def progress_line(job, line):
    """Atualiza o job com uma linha do stderr do filho: "PCT 45" ou etapa
    ("19:04:58  2/3 separando voz x instrumental (Demucs)" -> "separando voz x instrumental")."""
    line = line.strip()
    if line.startswith("PCT "):
        try:
            job["pct"] = max(job["pct"], int(line[4:]))
        except ValueError:
            pass
    elif line and "▶" not in line:
        step = re.sub(r"^\d\d:\d\d:\d\d\s+(\d/\d\s+)?", "", line).strip()
        job["step"] = re.sub(r"\s*\(.*\)$", "", step)


def terminate_running():
    """Encerra os subprocessos (pipeline/alinhamento e seus filhos) ao desligar."""
    for p in list(running):
        try:
            if os.name == "posix":
                os.killpg(p.pid, signal.SIGTERM)
            else:
                p.terminate()
        except OSError:
            pass


def _post_process(folder):
    """Letra + sincronia palavra por palavra + capa em segundo plano; a música já pode tocar."""
    from . import covers, lyrics, words
    for fn in (lyrics.lyrics, words.align, covers.itunes_cover):
        try:
            fn(folder)
        except Exception:
            pass


def worker():
    while True:
        vid = job_queue.get()
        with jobs_lock:
            job = jobs.get(vid)
        if job is None:
            continue
        job["status"] = "processando"
        _broadcast()
        log = config.data_dir() / "jobs" / f"{vid}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with heavy, open(log, "w", encoding="utf-8") as err:
            # Grupo de processos próprio: ao desligar o servidor, encerra também demucs/yt-dlp
            p = subprocess.Popen(
                [str(config.ai_python()), "-m", "karaoke.pipeline", "get", vid, job["mode"]],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                env=ai_env(), **config.popen_kwargs())
            running.add(p)
            for line in p.stderr:
                err.write(line)
                err.flush()
                progress_line(job, line)
                _broadcast()
            p.wait()
            out = p.stdout.read().strip()
            running.discard(p)
        if p.returncode == 0 and out:
            folder = Path(out).name
            job.update(status="pronto", folder=folder, step="", pct=100)
            _broadcast()
            threading.Thread(target=_post_process, args=(folder,), daemon=True).start()
        else:
            tail = [l for l in log.read_text().splitlines() if l.strip()][-3:]
            job.update(status="erro", error=" / ".join(tail) or f"código {p.returncode}")
            _broadcast()


def start():
    threading.Thread(target=worker, daemon=True).start()


# ---------------------------------------------------------------- busca no YouTube

def yt_search(q):
    out = subprocess.run(
        [str(config.ai_python()), "-m", "karaoke.pipeline", "search", q],
        capture_output=True, text=True, timeout=90, env=ai_env()).stdout
    have = {s["id"] for s in library.library() if s.get("id")}
    results = []
    for line in out.splitlines():
        label, _, vid = line.rpartition("\t")
        if vid:
            title, _, channel = label.rpartition(" — ")
            results.append({"id": vid, "title": title or label, "channel": channel,
                            "downloaded": vid in have})
    return results
