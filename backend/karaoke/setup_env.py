"""Setup de primeiro uso: baixa e prepara o venv de IA na máquina do usuário.

Numa máquina limpa o app precisa: do binário `uv` (em data_dir()/bin), de um venv
Python 3.11 com torch/demucs/whisper/yt-dlp (config.ai_venv()) e dos modelos
(htdemucs e whisper small). Tudo é baixado aqui, com progresso:

    WS:  {"type": "setup", "pct", "step", "done", "error"}
    GET /api/setup/status  ->  {ready, running, pct, step, done, error, has3faixas}

Pesos das etapas: uv 5% · venv+python 10% · pip 60% · modelos 25%.
Também roda solto:  python -m karaoke.setup_env [--3faixas]
"""
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import threading
import urllib.request
import zipfile
from pathlib import Path

from . import config, jobs, ws

# Pacotes do venv de IA (espelha backend/requirements-ai.txt; embutido aqui para
# funcionar também no app empacotado, onde o arquivo não existe).
AI_PACKAGES = ["yt-dlp", "demucs", "openai-whisper", "stable-ts", "imageio-ffmpeg"]

LEAD_MODEL = "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt"
LEAD_CONFIG = "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956_config.yaml"
UVR_PREFIX = "https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models"
LEAD_MODEL_URL = f"{UVR_PREFIX}/{LEAD_MODEL}"
LEAD_CONFIG_URL = f"{UVR_PREFIX}/mdx_model_data/mdx_c_configs/{LEAD_CONFIG}"

_state = {"running": False, "pct": 0, "step": "", "done": False, "error": None}
_lock = threading.Lock()


def has3faixas():
    return config.ai_bin("audio-separator").is_file() and (config.models_dir() / LEAD_MODEL).is_file()


def status():
    with _lock:
        s = dict(_state)
    return {"ready": config.ai_ready(), "has3faixas": has3faixas(), **s}


def _emit(pct=None, step=None, done=None, error=None, running=None):
    with _lock:
        if pct is not None:
            _state["pct"] = round(pct, 1)
        if step is not None:
            _state["step"] = step
        if done is not None:
            _state["done"] = done
        if error is not None:
            _state["error"] = error
        if running is not None:
            _state["running"] = running
        msg = {"type": "setup", **_state}
    ws.broadcast(msg)


def _log_file():
    f = config.data_dir() / "setup.log"
    f.parent.mkdir(parents=True, exist_ok=True)
    return f


def _run(cmd, log, env=None, on_line=None):
    """Roda comando repassando a saída para log/arquivo; registra em jobs.running
    para o shutdown do app conseguir interromper o setup."""
    log("$ " + " ".join(str(c) for c in cmd))
    with open(_log_file(), "a", encoding="utf-8") as lf:
        p = subprocess.Popen([str(c) for c in cmd], stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, env=env,
                             **config.popen_kwargs())
        jobs.running.add(p)
        for line in p.stdout:
            line = line.rstrip()
            if line:
                log(line)
                lf.write(line + "\n")
                if on_line:
                    on_line(line)
        rc = p.wait()
        jobs.running.discard(p)
    if rc != 0:
        raise RuntimeError(f"comando falhou (código {rc}): {cmd[0]}")


def _download(url, dest, log, base, span):
    """Download com progresso real por Content-Length mapeado em [base, base+span]."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "karaoke-setup/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        total = int(r.headers.get("Content-Length") or 0)
        log(f"baixando {url} ({total / 1e6:.0f} MB)")
        got = 0
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                if total:
                    _emit(pct=base + span * got / total)
    tmp.replace(dest)


# ---------------------------------------------------------------- uv

def _uv_target():
    machine = platform.machine().lower()
    alvo = {
        ("darwin", "arm64"): "aarch64-apple-darwin",
        ("darwin", "x86_64"): "x86_64-apple-darwin",
        ("win32", "amd64"): "x86_64-pc-windows-msvc",
        ("linux", "x86_64"): "x86_64-unknown-linux-gnu",
        ("linux", "aarch64"): "aarch64-unknown-linux-gnu",
    }.get((sys.platform, machine))
    if not alvo:
        raise RuntimeError(f"plataforma sem build do uv: {sys.platform}/{machine}")
    return alvo


def _uv_bin():
    return config.data_dir() / "bin" / ("uv.exe" if sys.platform == "win32" else "uv")


def ensure_uv(log):
    uv = _uv_bin()
    if uv.is_file():
        return uv
    uv.parent.mkdir(parents=True, exist_ok=True)
    on_path = shutil.which("uv")
    if on_path:  # dev: copia do PATH em vez de baixar
        log(f"uv copiado de {on_path}")
        shutil.copy(on_path, uv)
        uv.chmod(0o755)
        return uv
    target = _uv_target()
    if sys.platform == "win32":
        url = f"https://github.com/astral-sh/uv/releases/latest/download/uv-{target}.zip"
        zip_path = uv.parent / "uv.zip"
        _download(url, zip_path, log, 0, 5)
        with zipfile.ZipFile(zip_path) as z:
            z.extract("uv.exe", uv.parent)
        zip_path.unlink()
    else:
        url = f"https://github.com/astral-sh/uv/releases/latest/download/uv-{target}.tar.gz"
        tgz = uv.parent / "uv.tar.gz"
        _download(url, tgz, log, 0, 5)
        with tarfile.open(tgz) as t:
            t.extract("uv", uv.parent)
        tgz.unlink()
        uv.chmod(0o755)
    return uv


# ---------------------------------------------------------------- etapas

def _pip_progress(base, span):
    """Converte marcos da saída do uv pip (Resolved/Downloaded/Installed) em pct."""
    def on_line(line):
        low = line.lower()
        if low.startswith("resolved"):
            _emit(pct=base + span * 0.1)
        elif "downloaded" in low or low.startswith("prepared"):
            _emit(pct=base + span * 0.7)
        elif low.startswith("installed"):
            _emit(pct=base + span)
    return on_line


def _install_packages(uv, packages, log, base, span, index_url=None):
    cmd = [uv, "pip", "install", "--python", config.ai_python()]
    if index_url:
        cmd += ["--index-url", index_url]
    cmd += list(packages)
    _run(cmd, log, on_line=_pip_progress(base, span))


def _install_torch(uv, log, base, span):
    # No Windows o torch tem que vir do índice CPU (senão puxa CUDA de vários GB);
    # no macOS o índice padrão do PyPI já é o build certo (MPS).
    index = "https://download.pytorch.org/whl/cpu" if sys.platform == "win32" else None
    _install_packages(uv, ["torch", "torchaudio"], log, base, span, index)


def _warm_models(log, base, span):
    """Baixa os modelos htdemucs e whisper small já no setup (sem esperar o 1º uso)."""
    half = span / 2
    whisper_pt = Path.home() / ".cache" / "whisper" / "small.pt"
    _emit(pct=base, step="baixando modelo de separação (Demucs htdemucs)")
    _run([config.ai_python(), "-c",
          "import demucs.pretrained; demucs.pretrained.get_model('htdemucs')"], log)
    _emit(pct=base + half)
    if whisper_pt.is_file():
        log("whisper small já existe em ~/.cache/whisper")
    else:
        _emit(step="baixando modelo Whisper small")
        _run([config.ai_python(), "-c",
              "import stable_whisper; stable_whisper.load_model('small')"], log)
    _emit(pct=base + span)


def install_extra3faixas(uv, log, base=0, span=100):
    """Separação voz principal x backing vocals: audio-separator + ckpt Mel-Roformer."""
    _emit(pct=base, step="instalando audio-separator")
    _install_packages(uv, ["audio-separator"], log, base, span * 0.4)
    config.models_dir().mkdir(parents=True, exist_ok=True)
    for name, url in ((LEAD_CONFIG, LEAD_CONFIG_URL), (LEAD_MODEL, LEAD_MODEL_URL)):
        dest = config.models_dir() / name
        if dest.is_file():
            log(f"{name} já existe")
            continue
        _emit(step=f"modelo 3 faixas: {name}")
        _download(url, dest, log, base + span * 0.4, span * 0.6)
    _emit(pct=base + span)


def _setup(log, extra3faixas=False):
    _emit(0, "preparando", done=False, error=None)
    # uv 5% · venv+python 10% · torch 30% · demais pacotes 30% · modelos 25%
    _emit(0, "baixando uv")
    uv = ensure_uv(log)
    _emit(5, "criando ambiente Python 3.11")
    _run([uv, "venv", "--python", "3.11", str(config.ai_venv())], log)
    _emit(15, "instalando torch")
    _install_torch(uv, log, 15, 30)
    _emit(45, "instalando demucs, whisper e yt-dlp")
    _install_packages(uv, AI_PACKAGES, log, 45, 30)
    _warm_models(log, 75, 25)
    if extra3faixas:
        install_extra3faixas(uv, log)
    _emit(100, "pronto", done=True)


# ---------------------------------------------------------------- gatilhos

def _spawn(alvo, *args):
    with _lock:
        if _state["running"]:
            return "setup já está em andamento"
        _state.update(running=True, pct=0, step="", done=False, error=None)
    def wrapper():
        try:
            alvo(*args)
        except Exception as e:
            _emit(step="", done=False, error=str(e))
        finally:
            _emit(running=False)
    threading.Thread(target=wrapper, daemon=True).start()
    return None


def start(extra3faixas=False):
    def log(m):
        print(m, file=sys.stderr, flush=True)
    return _spawn(_setup, log, extra3faixas)


def start_extra3faixas():
    if not config.ai_ready():
        return "o setup principal ainda não foi concluído"
    uv = _uv_bin()
    if not uv.is_file():
        return "uv não encontrado (rode o setup principal primeiro)"
    def log(m):
        print(m, file=sys.stderr, flush=True)
    return _spawn(install_extra3faixas, uv, log)


def update():
    """Atualiza componentes (yt-dlp) no venv de IA."""
    if not config.ai_ready():
        return "venv de IA não existe (rode o setup primeiro)"
    uv = _uv_bin()
    if not uv.is_file():
        return "uv não encontrado"
    def do(log):
        _emit(0, "atualizando yt-dlp", done=False, error=None)
        _install_packages(uv, ["-U", "yt-dlp"], log, 0, 100)
        _emit(100, "pronto", done=True)
    def log(m):
        print(m, file=sys.stderr, flush=True)
    return _spawn(do, log)


def main():
    extra = "--3faixas" in sys.argv
    def log(m):
        print(m, file=sys.stderr, flush=True)
    try:
        _setup(log, extra)
    except Exception as e:
        sys.exit(f"setup falhou: {e}")
    print("setup concluído", flush=True)


if __name__ == "__main__":
    main()
