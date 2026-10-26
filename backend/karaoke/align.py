"""Sincroniza a letra palavra por palavra (alinhamento forçado com Whisper).

Roda DENTRO do venv de IA (stable-whisper, torch), chamado pelo backend:

    python -m karaoke.align "<pasta da música>" [modelo]

Usa a faixa de voz isolada e a letra do LRCLIB (lyrics.json) da pasta da música e grava
words.json: [{"t": início da linha, "end": fim, "words": [{"w": "palavra", "s": início, "e": fim}, ...]}, ...]

Progresso no stderr: linhas "PCT n" e etapas em texto puro.
"""
import json
import re
import sys
import time
from pathlib import Path


def log(msg):
    """Escreve no stderr (o servidor lê para mostrar progresso)."""
    print(msg, file=sys.stderr, flush=True)


def main():
    import stable_whisper
    import whisper

    pasta = Path(sys.argv[1])
    modelo = sys.argv[2] if len(sys.argv) > 2 else "small"

    letra = json.loads((pasta / "lyrics.json").read_text())
    voz = next(p for p in (pasta / "voz.mp3", pasta / "voz principal.mp3") if p.is_file())

    # Linhas da letra (com tempos do LRC, se disponível)
    lrc_tempos = []  # tempo de início de cada linha (None se não houver)
    linhas = []
    if letra.get("synced"):
        for l in letra["synced"].splitlines():
            m = re.search(r"\[(\d+):(\d+(?:\.\d+)?)\]", l)
            t = (int(m.group(1)) * 60 + float(m.group(2))) if m else None
            texto = re.sub(r"\[[^\]]*\]", "", l).strip()
            if texto:
                linhas.append(texto)
                lrc_tempos.append(t)
    else:
        for l in (letra.get("plain") or "").splitlines():
            if l.strip():
                linhas.append(l.strip())
                lrc_tempos.append(None)
    if not linhas:
        sys.exit("sem letra")

    # Estima a duração de cada linha a partir dos tempos do LRC:
    # fim da linha = início da próxima (ou início + duração média para a última)
    duracao_media = 3.0  # fallback
    tempos_lrc_validos = [t for t in lrc_tempos if t is not None]
    if len(tempos_lrc_validos) >= 2:
        diffs = [tempos_lrc_validos[i+1] - tempos_lrc_validos[i]
                 for i in range(len(tempos_lrc_validos)-1)
                 if 0 < tempos_lrc_validos[i+1] - tempos_lrc_validos[i] < 30]
        if diffs:
            duracao_media = sum(diffs) / len(diffs)

    log("PCT 5")
    log("carregando modelo")
    model = stable_whisper.load_model(modelo)

    # Idioma: o Whisper ouve 30 s de voz a partir do primeiro verso (português, inglês, ...)
    log("PCT 15")
    log("carregando áudio")
    audio = whisper.load_audio(str(voz))
    tempos = [int(m[1]) * 60 + float(m[2]) for m in re.finditer(r"\[(\d+):(\d+(?:\.\d+)?)\]", letra.get("synced") or "")]
    ini = int(max(0, (tempos[0] if tempos else 30) - 1) * whisper.audio.SAMPLE_RATE)
    trecho = whisper.pad_or_trim(audio[ini:])
    mel = whisper.log_mel_spectrogram(trecho, model.dims.n_mels).to(model.device)
    _, probs = model.detect_language(mel)
    idioma = max(probs, key=probs.get)
    log("PCT 30")
    log(f"idioma detectado: {idioma}")

    # Alinha a letra inteira de uma vez (sem original_split, que falha em frases repetidas).
    # O Whisper encontra onde cada palavra é cantada no áudio; depois mapeamos de volta
    # para as linhas originais da letra.
    log("PCT 35")
    log(f"alinhando {len(linhas)} linhas")
    t0 = time.time()
    res = model.align(audio, "\n".join(linhas), language=idioma, original_split=False)
    log("PCT 90")
    log(f"alinhamento concluído em {time.time()-t0:.1f}s")

    # Mapeia as palavras alinhadas de volta para as linhas originais da letra.
    # Cada linha é uma sequência de palavras; achamos a melhor correspondência
    # no fluxo contínuo de palavras do Whisper.
    todas_palavras = [w for seg in res.segments for w in seg.words if w.word.strip()]
    out = []
    idx = 0  # posição atual em todas_palavras
    for i_linha, linha in enumerate(linhas):
        palavras_linha = [p for p in re.split(r"\s+", linha.strip()) if p]
        if not palavras_linha:
            continue
        linha_words = []
        best_start = len(todas_palavras)
        for tentativa in range(min(20, len(todas_palavras) - idx)):
            pos = idx + tentativa
            if pos >= len(todas_palavras):
                break
            w_whisper = re.sub(r"[^\w]", "", todas_palavras[pos].word.lower())
            w_letra = re.sub(r"[^\w]", "", palavras_linha[0].lower())
            if w_whisper == w_letra or (w_whisper and w_letra and
                                        (w_whisper.startswith(w_letra) or w_letra.startswith(w_whisper))):
                best_start = pos
                break
        if best_start < len(todas_palavras):
            idx = best_start
            i = 0
            while i < len(palavras_linha) and idx < len(todas_palavras):
                w_whisper = re.sub(r"[^\w]", "", todas_palavras[idx].word.lower())
                w_letra = re.sub(r"[^\w]", "", palavras_linha[i].lower())
                if w_whisper == w_letra or (w_whisper and w_letra and
                                            (w_whisper.startswith(w_letra) or w_letra.startswith(w_whisper))):
                    linha_words.append({"w": todas_palavras[idx].word.strip(),
                                        "s": round(todas_palavras[idx].start, 3),
                                        "e": round(todas_palavras[idx].end, 3)})
                    i += 1
                idx += 1
        if linha_words:
            out.append({"t": linha_words[0]["s"], "end": linha_words[-1]["e"],
                        "words": linha_words, "i_lrc": i_linha})

    # Fallback: se o mapeamento falhou muito (menos de 60% das linhas), usa os segmentos
    # originais do Whisper.
    if len(out) < len(linhas) * 0.6:
        out = []
        for i_linha, seg in enumerate(res.segments):
            palavras = [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)}
                        for w in seg.words if w.word.strip()]
            if palavras:
                out.append({"t": palavras[0]["s"], "end": palavras[-1]["e"],
                            "words": palavras, "i_lrc": i_linha})

    # Re-escalona as palavras usando os tempos do LRC como âncoras.
    # O Whisper pode errar o posicionamento global (ex.: colocar "oh" no fim do interlúdio),
    # mas a estrutura RELATIVA das palavras dentro da linha costuma ser boa. Então usamos
    # o tempo do LRC para definir o início da linha e re-escalonamos as palavras para
    # caber dentro da janela [t_ini_lrc, t_fim_lrc].
    def rescale_line(entry, t_ini, t_fim):
        words = entry["words"]
        # Verifica anomalias: gaps > 2s entre palavras, ou palavra com duração > 5s.
        # Se houver, o Whisper provavelmente errou o posicionamento; redistribui uniformemente.
        tem_anomalia = (
            any(words[i+1]["s"] - words[i]["e"] > 2.0 for i in range(len(words) - 1)) or
            any(w["e"] - w["s"] > 5.0 for w in words)
        )
        if tem_anomalia or len(words) == 1:
            # Distribuição uniforme
            n = len(words)
            passo = (t_fim - t_ini) / n
            for i, w in enumerate(words):
                w["s"] = round(t_ini + i * passo, 3)
                w["e"] = round(t_ini + (i + 1) * passo, 3)
        else:
            # Mantém a proporção original do Whisper (boa quando não há anomalias)
            s0 = words[0]["s"]
            e0 = words[-1]["e"]
            span = e0 - s0
            dur = t_fim - t_ini
            for w in words:
                if span > 0:
                    w["s"] = round(t_ini + (w["s"] - s0) / span * dur, 3)
                    w["e"] = round(t_ini + (w["e"] - s0) / span * dur, 3)
                else:
                    w["s"] = round(t_ini, 3)
                    w["e"] = round(t_fim, 3)
        entry["t"] = words[0]["s"]
        entry["end"] = words[-1]["e"]

    tem_lrc = any(t is not None for t in lrc_tempos)
    if tem_lrc:
        for entry in out:
            i = entry["i_lrc"]
            t_ini = lrc_tempos[i]
            if t_ini is None:
                continue
            # Fim da linha = início da próxima linha com tempo, ou início + duração média
            t_fim = None
            for j in range(i + 1, len(lrc_tempos)):
                if lrc_tempos[j] is not None:
                    t_fim = lrc_tempos[j]
                    break
            if t_fim is None:
                t_fim = t_ini + duracao_media
            # Evita esticar linhas curtas em gaps grandes (interlúdios).
            # Se a próxima linha do LRC estiver muito além do fim detectado pelo Whisper,
            # usa o fim do Whisper + margem em vez do tempo do LRC.
            fim_whisper = entry["words"][-1]["e"]
            if t_fim - fim_whisper > 4.0:
                t_fim = fim_whisper + 1.0
            # Não deixa a linha ser menor que 1.5s
            if t_fim - t_ini < 1.5:
                t_fim = t_ini + 1.5
            rescale_line(entry, t_ini, t_fim)

    # Remove o campo auxiliar i_lrc
    for entry in out:
        entry.pop("i_lrc", None)

    log("PCT 95")
    log("salvando words.json")
    (pasta / "words.json").write_bytes(json.dumps(out, ensure_ascii=False).encode())
    log("PCT 100")
    print(f"{idioma}: {len(out)} linhas, {sum(len(l['words']) for l in out)} palavras")


if __name__ == "__main__":
    main()
