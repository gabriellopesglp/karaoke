"""Caminhos do app, multiplataforma e só com stdlib.

Este módulo é importado tanto pelo backend (venv leve) quanto pelo pipeline
(venv de IA), então não pode depender de nada além da stdlib.

Overrides por variável de ambiente:
    KARAOKE_DATA_DIR  pasta de dados do app (venv de IA, modelos, token, fila)
    KARAOKE_LIB_DIR   biblioteca de músicas (padrão: ~/Music/karaoke)
    KARAOKE_AI_VENV   venv de IA existente (desenvolvimento)
"""
import os
import shutil
import sys
from pathlib import Path

APP_NAME = "karaoke"


def data_dir() -> Path:
    """Pasta de dados gerenciada pelo app (venv de IA, modelos, queue.json, token)."""
    if os.environ.get("KARAOKE_DATA_DIR"):
        return Path(os.environ["KARAOKE_DATA_DIR"])
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME


def lib_dir() -> Path:
    """Biblioteca de músicas processadas. Reutiliza ~/Music/karaoke existente."""
    if os.environ.get("KARAOKE_LIB_DIR") or os.environ.get("KARAOKE_DIR"):
        return Path(os.environ.get("KARAOKE_LIB_DIR") or os.environ["KARAOKE_DIR"])
    return Path.home() / "Music" / APP_NAME


def models_dir() -> Path:
    return data_dir() / "models"


def ai_venv() -> Path:
    """Venv com as dependências de IA (torch, demucs, whisper, yt-dlp)."""
    if os.environ.get("KARAOKE_AI_VENV"):
        return Path(os.environ["KARAOKE_AI_VENV"])
    default = data_dir() / "ai-venv"
    if default.exists():
        return default
    # Reaproveita o venv do app antigo (~/.local/share/karaoke/venv) quando ele
    # já existe: reinstalar o ambiente de IA levaria vários GB.
    fallback_venv = Path.home() / ".local" / "share" / APP_NAME / "venv"
    return fallback_venv if fallback_venv.exists() else default


def _venv_bin() -> Path:
    v = ai_venv()
    return v / ("Scripts" if sys.platform == "win32" else "bin")


def ai_python() -> Path:
    name = "python.exe" if sys.platform == "win32" else "python"
    return _venv_bin() / name


def ai_bin(name: str) -> Path:
    """Executável dentro do venv de IA (yt-dlp, demucs, audio-separator)."""
    if sys.platform == "win32":
        name += ".exe"
    return _venv_bin() / name


def ai_ready() -> bool:
    return ai_python().is_file() and ai_bin("yt-dlp").is_file()


def bin_dirs() -> list[str]:
    """Pastas comuns de binários do sistema (Homebrew e afins)."""
    dirs = ["/opt/homebrew/bin", "/usr/local/bin"] if sys.platform == "darwin" else []
    return dirs + ["/usr/bin", "/bin", "/usr/sbin", "/sbin"]


def extra_path() -> str:
    """PATH de reserva para subprocessos.

    O app aberto pelo Finder herda um ambiente mínimo, sem o PATH do shell, e
    assim yt-dlp/demucs não encontram o ffmpeg do Homebrew.
    """
    return os.pathsep.join(bin_dirs())


def ffmpeg() -> str | None:
    """ffmpeg do imageio-ffmpeg (venv de IA), do PATH ou das pastas padrão."""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe:
            return exe
    except Exception:
        pass
    found = shutil.which("ffmpeg")
    if found:
        return found
    for d in bin_dirs():
        cand = Path(d) / "ffmpeg"
        if cand.is_file():
            return str(cand)
    return None


def popen_kwargs() -> dict:
    """Grupo de processos próprio para o backend conseguir encerrar a árvore."""
    if os.name == "posix":
        return {"start_new_session": True}
    return {"creationflags": getattr(__import__("subprocess"), "CREATE_NEW_PROCESS_GROUP", 0)}
