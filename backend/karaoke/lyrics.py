"""Letras via LRCLIB (https://lrclib.net), com retry/backoff e cache em lyrics.json."""
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .library import audio_duration, safe_delete, safe_write, song_dir, song_info
from .metadata import sem_acento


def norm(s):
    return sem_acento(s or "")


def simplify(s):
    # "Evidências (Ao Vivo)" -> "Evidências": melhora a busca de letra
    return re.sub(r"\s*[\(\[].*?[\)\]]", "", s).strip()


def lrclib(path, params):
    url = f"https://lrclib.net/api/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "karaoke-local/1.0"})
    # Retry com backoff: tenta até 3 vezes com espera crescente (0.5s, 1s)
    delays = [0.5, 1.0]
    for attempt in range(len(delays) + 1):
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.load(r)
        except Exception:
            if attempt < len(delays):
                time.sleep(delays[attempt])
    return None


def lyrics(folder: str, refresh=False):
    d = song_dir(folder)
    cache = d / "lyrics.json"
    if cache.is_file() and not refresh:
        return json.loads(cache.read_text())

    song = song_info(d) or {}
    artist, track = song.get("artist", ""), song.get("track", folder)
    dur = audio_duration(d / "instrumental.mp3")

    found = None
    if artist and dur:
        found = lrclib("get", {"artist_name": artist, "track_name": track, "duration": round(dur)})
    if not found or not (found.get("syncedLyrics") or found.get("plainLyrics")):
        results = lrclib("search", {"track_name": simplify(track), "artist_name": artist}) or []
        if not results:
            results = lrclib("search", {"q": f"{artist} {simplify(track)}"}) or []
        # Prefere letra sincronizada com duração mais próxima do áudio
        results.sort(key=lambda r: (not r.get("syncedLyrics"),
                                    abs((r.get("duration") or 0) - (dur or 0))))
        found = results[0] if results else None

    return save_lyrics(d, found)


def save_lyrics(d: Path, found):
    data = {
        "id": (found or {}).get("id"),
        "synced": (found or {}).get("syncedLyrics"),
        "plain": (found or {}).get("plainLyrics"),
        "source": f"{found.get('artistName')} - {found.get('trackName')}" if found else None,
    }
    if data["synced"] or data["plain"]:
        safe_write(d / "lyrics.json", json.dumps(data, ensure_ascii=False, indent=2).encode())
        safe_delete(d / "words.json")  # letra nova: refaz o alinhamento
    return data


def lyrics_options(folder: str, q: str = ""):
    """Versões da letra no LRCLIB para o usuário escolher (sincronizadas e mais próximas da duração primeiro)."""
    d = song_dir(folder)
    song = song_info(d) or {}
    artist, track = song.get("artist", ""), song.get("track", folder)
    dur = audio_duration(d / "instrumental.mp3") or 0
    has_saved = (d / "lyrics.json").is_file()
    current = None
    current_source = None
    if has_saved:
        cur = json.loads((d / "lyrics.json").read_text())
        current = cur.get("id")
        current_source = cur.get("source")

    if q.strip():
        results = lrclib("search", {"q": q.strip()}) or []
    else:
        results = (lrclib("search", {"track_name": simplify(track), "artist_name": artist}) or []) + \
                  (lrclib("search", {"q": f"{artist} {simplify(track)}"}) or [])
    seen, out = set(), []
    for r in results:
        if r.get("id") in seen or not (r.get("syncedLyrics") or r.get("plainLyrics")):
            continue
        seen.add(r.get("id"))
        text = r.get("plainLyrics") or re.sub(r"\[[^\]]*\]", "", r.get("syncedLyrics") or "")
        preview = [l.strip() for l in text.splitlines() if l.strip()][:2]
        # marca como atual: por id, ou por fonte salva (artista - faixa), ou por faixa+artista+duração próximos
        src = f"{r.get('artistName')} - {r.get('trackName')}"
        by_id = r.get("id") == current and current is not None
        by_src = current_source and norm(src) == norm(current_source)
        by_meta = (norm(r.get("trackName") or "") == norm(track)
                   and norm(r.get("artistName") or "") == norm(artist)
                   and r.get("duration")
                   and abs((r.get("duration") or 0) - (dur or 0)) <= 3)
        is_current = by_id or ((by_src or by_meta) and not has_saved)
        out.append({
            "id": r.get("id"), "artist": r.get("artistName"), "track": r.get("trackName"),
            "album": r.get("albumName"), "duration": r.get("duration"),
            "synced": bool(r.get("syncedLyrics")), "preview": preview, "current": is_current,
        })
    out.sort(key=lambda r: (not r["current"], not r["synced"], abs((r["duration"] or 0) - dur)))
    return {"duration": dur, "options": out[:20]}


def choose_lyrics(folder: str, lyric_id: int):
    found = lrclib(f"get/{int(lyric_id)}", {})
    if not found:
        raise FileNotFoundError("letra")
    return save_lyrics(song_dir(folder), found)


def save_sync(folder: str, synced: str):
    """Salva os tempos ajustados da letra (mantendo id, plain e source originais)."""
    d = song_dir(folder)
    p = d / "lyrics.json"
    if not p.is_file():
        raise FileNotFoundError("letra")
    data = json.loads(p.read_text())
    data["synced"] = synced
    safe_write(p, json.dumps(data, ensure_ascii=False, indent=2).encode())
    # words.json fica desatualizado em relação aos novos tempos; remove para re-alinhar depois
    safe_delete(d / "words.json")
    return {"ok": True}
