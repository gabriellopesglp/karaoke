"""Monta o nome padrão "Artista - Música" a partir dos metadados do yt-dlp."""
import json
import re
import unicodedata

# Penduricalhos comuns em títulos do YouTube. "(Ao Vivo)" fica, pois diferencia a versão.
RUIDO = re.compile(
    r"\s*[\(\[][^\)\]]*\b(official|oficial|clipe|video|vídeo|audio|áudio|lyrics?|letra|"
    r"remaster(ed)?|hd|hq|4k|visualizer)\b[^\)\]]*[\)\]]",
    re.I,
)
# Sufixos soltos comuns no YouTube: "Lyrics", "Official Video", "Audio", etc.
RUIDO_FINAL = re.compile(
    r"(?:\s*[-–—:|]\s*|\s+)"
    r"(?:official(?:\s+music)?\s+video|official\s+video|official\s+audio|official|"
    r"oficial(?:\s+video|\s+áudio)?|oficial|"
    r"lyric\s+video|video\s+lyrics?|lyrics?|letra|audio|áudio|"
    r"video|vídeo|visualizer|remaster(?:ed)?|hd|hq|4k)"
    r"(?:\s+(?:video|vídeo|audio|áudio))?\s*$",
    re.I,
)
RUIDO_PURO = re.compile(
    r"^(?:official(?:\s+music)?\s+video|official\s+video|official\s+audio|official|"
    r"oficial(?:\s+video|\s+áudio)?|oficial|"
    r"lyric\s+video|video\s+lyrics?|lyrics?|letra|audio|áudio|"
    r"video|vídeo|visualizer|remaster(?:ed)?|hd|hq|4k)"
    r"(?:\s+(?:video|vídeo|audio|áudio))?\s*$",
    re.I,
)
CANAL_RUIDO = re.compile(r"\s*(-\s*topic|vevo|oficial|official)\s*$", re.I)
SEP = re.compile(r"\s+[-–—]\s+")


def limpa(s):
    s = RUIDO.sub("", s)
    # Alguns vídeos vêm sem parênteses: "Ain't It Fun Lyrics".
    while True:
        out = RUIDO_FINAL.sub("", s)
        if out == s:
            break
        s = out
    if so_ruido(s):
        s = ""
    s = re.sub(r"\s{2,}", " ", s).strip(" -–—|")
    return s.replace("/", "-").replace(":", " -").translate(str.maketrans("", "", '"?*<>|\\'))


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).casefold()


def so_ruido(s):
    return bool(RUIDO_PURO.match((s or "").strip()))


def partes_nome(track, artist, title, channel):
    na = lambda v: not v or v == "NA"
    if not na(track) and not na(artist):
        # "artist" pode vir com vários nomes separados por vírgula; o primeiro é o principal
        musica, artista = track, artist.split(",")[0]
        # O YouTube Music às vezes perde acentos no artista ("Legiao Urbana"); o canal costuma estar certo
        canal = CANAL_RUIDO.sub("", channel or "")
        if canal != artista and sem_acento(canal) == sem_acento(artista):
            artista = canal
    elif len(partes := SEP.split(title, maxsplit=1)) == 2 and not so_ruido(partes[1]):
        artista, musica = partes
    else:
        musica, artista = title, CANAL_RUIDO.sub("", channel or "")
    return limpa(artista), limpa(musica)


def nome(*campos):
    artista, musica = partes_nome(*campos)
    return f"{artista} - {musica}" if artista else musica


def info_json(track, artist, title, channel) -> str:
    artista, musica = partes_nome(track, artist, title, channel)
    return json.dumps(
        {"artist": artista, "track": musica, "name": nome(track, artist, title, channel)},
        ensure_ascii=False,
    )
