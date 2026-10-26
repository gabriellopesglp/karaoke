"""Biblioteca de músicas e fila compartilhada.

Escaneia config.lib_dir() montando a ficha de cada pasta (info.json + stems),
mede a duração dos áudios com mutagen (cache no info.json, chave "duration:<nome>")
e persiste a fila em config.data_dir()/queue.json para todos os dispositivos
verem a mesma.
"""
import json
import locale
import shutil
import threading
from pathlib import Path

from . import config, ws
from .metadata import limpa

# Faixas reconhecidas, na ordem em que aparecem no mixer.
STEMS = [
    ("voz.mp3", "Voz"),
    ("voz principal.mp3", "Voz principal"),
    ("backing vocals.mp3", "Backing vocals"),
    ("instrumental.mp3", "Instrumental"),
]


def safe_write(path: Path, data: bytes) -> bool:
    """Escreve bytes em path, criando a pasta se preciso (escrita direta, sem hacks)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return True
    except OSError:
        return False


def safe_delete(path: Path) -> bool:
    try:
        path.unlink(missing_ok=True)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------- biblioteca

def song_info(folder: Path):
    stems = [{"file": f, "label": label} for f, label in STEMS if (folder / f).is_file()]
    if not any(s["file"] == "instrumental.mp3" for s in stems):
        return None  # pasta incompleta (processamento antigo ou interrompido)
    info = {}
    if (folder / "info.json").is_file():
        try:
            info = json.loads((folder / "info.json").read_text())
        except ValueError:
            pass
    artist, _, track = folder.name.partition(" - ")
    info_artist = limpa(info.get("artist", ""))
    info_track = limpa(info.get("track", ""))
    if (info_artist and info_artist != info.get("artist")) or (info_track and info_track != info.get("track")):
        info["artist"] = info_artist
        info["track"] = info_track
        safe_write((folder / "info.json"), json.dumps(info, ensure_ascii=False, indent=2).encode())
    return {
        "folder": folder.name,
        "artist": info_artist or (artist if track else ""),
        "track": info_track or (track or folder.name),
        "id": info.get("id"),
        "stems": stems,
        "cover": (folder / "cover.jpg").is_file(),
        "added": folder.stat().st_mtime,
    }


def library():
    lib = config.lib_dir()
    lib.mkdir(parents=True, exist_ok=True)
    songs = [s for d in lib.iterdir() if d.is_dir() and (s := song_info(d))]
    try:
        locale.setlocale(locale.LC_ALL, "pt_BR.UTF-8")
    except locale.Error:
        pass
    return sorted(songs, key=lambda s: locale.strxfrm(s["track"].lower()))


def song_dir(folder: str) -> Path:
    lib = config.lib_dir()
    d = (lib / folder).resolve()
    if d.parent != lib.resolve() or not d.is_dir():
        raise FileNotFoundError(folder)
    return d


def delete_song(folder: str):
    shutil.rmtree(song_dir(folder))


def audio_duration(path: Path):
    """Retorna a duração do áudio em segundos (mutagen).
    Cacheia o valor no info.json da pasta para não reabrir o arquivo toda vez."""
    folder = path.parent
    info_path = folder / "info.json"
    info = {}
    if info_path.is_file():
        try:
            info = json.loads(info_path.read_text())
        except ValueError:
            info = {}
    # Chave por nome do arquivo (instrumental.mp3, voz.mp3, etc.)
    cache_key = f"duration:{path.name}"
    cached = info.get(cache_key)
    if isinstance(cached, (int, float)) and cached > 0:
        return float(cached)
    try:
        from mutagen.mp3 import MP3
        dur = float(MP3(str(path)).info.length)
        if dur > 0:
            info[cache_key] = dur
            safe_write(info_path, json.dumps(info, ensure_ascii=False, indent=2).encode())
            return dur
    except Exception:
        pass
    return None


# ---------------------------------------------------------------- fila compartilhada
queue_lock = threading.Lock()


def get_queue():
    f = config.data_dir() / "queue.json"
    if f.is_file():
        try:
            return json.loads(f.read_text())
        except ValueError:
            pass
    return []


def save_queue(items):
    with queue_lock:
        ok = safe_write(config.data_dir() / "queue.json",
                        json.dumps(items, ensure_ascii=False).encode())
    if ok:
        ws.broadcast({"type": "queue", "queue": items})
    return ok
