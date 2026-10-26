"""Capa do álbum via iTunes Search API, salva como cover.jpg na pasta da música."""
import json
import urllib.parse
import urllib.request

from .library import safe_write, song_dir, song_info
from .metadata import sem_acento


def norm(s):
    return sem_acento(s or "")


def itunes_search(artist: str, track: str, limit=8):
    """Busca resultados na iTunes Search API e retorna a lista bruta."""
    term = urllib.parse.quote(f"{artist} {track}")
    url = f"https://itunes.apple.com/search?term={term}&entity=song&limit={limit}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "karaoke-local/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r).get("results") or []
    except Exception:
        return []


def download_cover(url: str) -> bytes | None:
    """Baixa uma imagem de capa e retorna os bytes (ou None)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "karaoke-local/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read()
    except Exception:
        return None


def itunes_cover(folder: str, force=False, cover_url=None):
    """Busca a capa do álbum na iTunes Search API e salva cover.jpg na pasta da música.
    Se cover_url for passado, baixa essa capa específica (escolhida pelo usuário)."""
    d = song_dir(folder)
    if (d / "cover.jpg").is_file() and not force and not cover_url:
        return True
    if not cover_url:
        song = song_info(d) or {}
        artist, track = song.get("artist", ""), song.get("track", folder)
        if not artist or not track:
            return False
        results = itunes_search(artist, track)
        if not results:
            return False
        na, nt = norm(artist), norm(track)
        results.sort(key=lambda r: (
            norm(r.get("artistName", "")) != na,
            norm(r.get("trackName", "")) != nt,
        ))
        cover_url = results[0].get("artworkUrl100")
        if not cover_url:
            return False
    # 100x100bb -> 600x600bb para qualidade melhor
    cover_url = cover_url.replace("100x100bb", "600x600bb")
    blob = download_cover(cover_url)
    if not blob:
        return False
    return safe_write(d / "cover.jpg", blob)


def refresh_cover(folder: str, cover_url=None):
    return itunes_cover(folder, force=True, cover_url=cover_url)


def cover_options(folder: str, q: str = ""):
    """Opções de capa na iTunes para o usuário escolher (ordenadas por match)."""
    d = song_dir(folder)
    song = song_info(d) or {}
    artist, track = song.get("artist", ""), song.get("track", folder)
    if q.strip():
        results = itunes_search(q, "", limit=12)
    else:
        results = itunes_search(artist, track, limit=12)
    na, nt = norm(artist), norm(track)
    out = []
    seen = set()
    for r in results:
        art = r.get("artworkUrl100")
        if not art or art in seen:
            continue
        seen.add(art)
        out.append({
            "artist": r.get("artistName"),
            "track": r.get("trackName"),
            "album": r.get("collectionName"),
            "url": art.replace("100x100bb", "600x600bb"),
            "thumb": art,
            "match": (norm(r.get("artistName", "")) == na) and (norm(r.get("trackName", "")) == nt),
        })
    out.sort(key=lambda o: (not o["match"],))
    return {"options": out[:12]}
