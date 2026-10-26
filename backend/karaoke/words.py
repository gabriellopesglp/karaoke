"""Alinhamento palavra por palavra: orquestra `python -m karaoke.align` no venv de IA.

align.py (stable-whisper) roda no venv de IA; aqui ficam o acompanhamento de
progresso (protocolo "PCT n" no stderr), o retry quando a letra muda no meio do
alinhamento, a validação do words.json e a lógica do endpoint /api/words.
"""
import json
import subprocess
import threading

from . import config, jobs, library, ws

aligning = set()       # pastas sendo alinhadas agora
align_progress = {}    # folder -> {"pct": 0, "step": ""}
align_retry = {}       # folder -> tentativa atual (evita loop infinito)
align_lock = threading.Lock()


def align(folder: str, is_retry=False):
    """Gera words.json (tempo de cada palavra) com alinhamento forçado do Whisper."""
    d = library.song_dir(folder)
    with align_lock:
        if not is_retry:
            if folder in aligning or (d / "words.json").is_file() or not (d / "lyrics.json").is_file():
                return
        aligning.add(folder)
        align_progress[folder] = {"pct": 0, "step": "iniciando"}
    ws.broadcast({"type": "align", "folder": folder, "pct": 0, "step": "iniciando"})
    try:
        with jobs.heavy:
            # Registra o tempo de modificação da letra no início do alinhamento.
            # Se a letra mudar durante (usuário escolheu outra versão), o
            # words.json gerado fica obsoleto e precisa ser refeito.
            lyrics_mtime = (d / "lyrics.json").stat().st_mtime if (d / "lyrics.json").is_file() else 0
            p = subprocess.Popen(
                [str(config.ai_python()), "-m", "karaoke.align", str(d)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                env=jobs.ai_env(), **config.popen_kwargs())
            jobs.running.add(p)
            # Lê o stderr linha por linha para acompanhar o progresso
            for line in p.stderr:
                line = line.strip()
                prog = align_progress.get(folder)
                if prog is None:
                    break
                if line.startswith("PCT "):
                    try:
                        prog["pct"] = max(prog["pct"], int(line[4:]))
                    except ValueError:
                        pass
                elif line:
                    prog["step"] = line
                ws.broadcast({"type": "align", "folder": folder,
                              "pct": prog["pct"], "step": prog["step"]})
            p.wait()
            jobs.running.discard(p)
            # Se a letra mudou durante o alinhamento, o words.json está obsoleto.
            # Apaga e refaz o alinhamento (com limite de tentativas).
            nova_mtime = (d / "lyrics.json").stat().st_mtime if (d / "lyrics.json").is_file() else 0
            if nova_mtime > lyrics_mtime:
                tentativa = align_retry.get(folder, 0) + 1
                align_retry[folder] = tentativa
                if tentativa <= 3:
                    library.safe_delete(d / "words.json")
                    align(folder, is_retry=True)
                align_retry.pop(folder, None)
    finally:
        with align_lock:
            aligning.discard(folder)
            align_progress.pop(folder, None)
        ws.broadcast({"type": "align", "folder": folder, "pct": 100, "step": ""})


def validate_words(lines, duration=None):
    """Valida e corrige os tempos do words.json.
    - tempos não negativos
    - s <= e em cada palavra
    - palavras em ordem crescente dentro da linha
    - linhas em ordem crescente
    - tempos dentro da duração da música (se conhecida)
    Retorna a lista corrigida (ou a original se tudo ok)."""
    if not isinstance(lines, list):
        return []
    fixed = []
    prev_end = 0.0
    for line in lines:
        if not isinstance(line, dict):
            continue
        words = line.get("words") or []
        wlist = []
        prev_w = 0.0
        for w in words:
            if not isinstance(w, dict):
                continue
            s = max(0.0, float(w.get("s", 0) or 0))
            e = max(s, float(w.get("e", s) or s))
            # garante ordem dentro da linha
            if s < prev_w:
                s = prev_w
                e = max(s, e)
            if duration is not None:
                s = min(s, duration)
                e = min(e, duration)
            wlist.append({"w": w.get("w", ""), "s": round(s, 3), "e": round(e, 3)})
            prev_w = e
        if wlist:
            t = max(prev_end, wlist[0]["s"])
            end = max(t, wlist[-1]["e"])
            if duration is not None:
                t = min(t, duration)
                end = min(end, duration)
            fixed.append({"t": round(t, 3), "end": round(end, 3), "words": wlist})
            prev_end = end
    return fixed


def words(folder: str):
    d = library.song_dir(folder)
    if (d / "words.json").is_file():
        try:
            raw = json.loads((d / "words.json").read_text())
        except ValueError:
            raw = []
        # Valida os tempos antes de devolver (evita travar o frontend)
        dur = library.audio_duration(d / "instrumental.mp3")
        return {"status": "pronto", "lines": validate_words(raw, dur)}
    if folder in aligning:
        prog = align_progress.get(folder, {"pct": 0, "step": ""})
        return {"status": "alinhando", "pct": prog["pct"], "step": prog["step"]}
    if (d / "lyrics.json").is_file():
        threading.Thread(target=align, args=(folder,), daemon=True).start()
        return {"status": "alinhando", "pct": 0, "step": "iniciando"}
    return {"status": "sem letra"}
