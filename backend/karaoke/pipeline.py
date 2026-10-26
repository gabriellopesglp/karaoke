"""Pipeline de download e separação de voz do app novo.

Roda DENTRO do venv de IA (torch, demucs, yt-dlp), chamado pelo backend:

    python -m karaoke.pipeline search <termo>   -> "Título — Canal<TAB>id" por linha
    python -m karaoke.pipeline info <id>        -> JSON {artist, track, name}
    python -m karaoke.pipeline get <id> [2faixas|3faixas]
        2faixas : voz + instrumental (Demucs htdemucs)
        3faixas : voz principal + backing vocals + instrumental
                  (Mel-Roformer Karaoke + Demucs; requer o extra de IA)

Progresso no stderr: linhas "PCT n" e etapas "HH:MM:SS  mensagem".
O caminho final da pasta da música vai para o stdout.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import config, settings
from .metadata import info_json

LEAD_MODEL = "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt"
# overlap 2 + fp16: ~1,9x mais rápido que o padrão, diferença inaudível (-47 dB)
LEAD_OPTS = ["--mdxc_overlap", "2", "--use_native_fp16"]

VIDEO_URL = "https://www.youtube.com/watch?v={}"


def separate_2stems(src, tmp, work):
    """Separa src em voz.mp3 + instrumental.mp3 usando o motor configurado."""
    engine = settings.get("separation")
    if engine == "mvsep":
        from . import mvsep
        try:
            vocals, no_vocals = mvsep.separate(src, tmp, progress=lambda s, p: (step(s), progress(p)))
        except mvsep.MVSepError as e:
            step(f"MVSep falhou: {e}; usando Demucs CPU como fallback")
            engine = "cpu"
    if engine != "mvsep":
        device = settings.demucs_device()
        cmd = [str(config.ai_bin("demucs")), "-n", "htdemucs", "--two-stems=vocals",
               "-o", str(tmp / "demucs"), str(src)]
        if device != "cpu":
            cmd.extend(["-d", device])
        rc = run(cmd, track=(10, 85))
        if rc != 0:
            sys.exit(f"demucs falhou (código {rc})")
        vocals = tmp / "demucs" / "htdemucs" / "original" / "vocals.wav"
        no_vocals = tmp / "demucs" / "htdemucs" / "original" / "no_vocals.wav"

    step("3/3 convertendo para MP3")
    progress(95)
    mp3(vocals, work / "voz.mp3")
    mp3(no_vocals, work / "instrumental.mp3")


def step(msg):
    print(f"{time.strftime('%H:%M:%S')}  {msg}", file=sys.stderr, flush=True)


def progress(n):
    print(f"PCT {int(n)}", file=sys.stderr, flush=True)


def _pump_stderr(proc, on_line):
    """Lê stderr do filho tratando \\r (barras tqdm) como quebra de linha."""
    buf = b""
    while True:
        chunk = proc.stderr.read1(4096) if hasattr(proc.stderr, "read1") else proc.stderr.read(4096)
        if not chunk:
            break
        buf += chunk
        *parts, buf = re.split(rb"[\r\n]", buf)
        for p in parts:
            if p:
                on_line(p.decode("utf-8", "replace"))
    if buf:
        on_line(buf.decode("utf-8", "replace"))


def run(cmd, log_lines=None, track=None, env=None):
    """Roda comando repassando o stderr.

    track=(base, span): converte porcentagens tqdm ("NN%|") do stderr em
    "PCT base+pct*span/100". Sem track, as linhas vão para o stderr como etapas.
    Retorna o returncode.
    """
    pct_re = re.compile(r"(\d+)%\|")

    def on_line(line):
        if track:
            m = pct_re.search(line)
            if m:
                progress(track[0] + int(m.group(1)) * track[1] / 100)
        else:
            if log_lines is not None:
                log_lines.append(line)
            print(line, file=sys.stderr, flush=True)

    proc = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        env=env, **config.popen_kwargs(),
    )
    _pump_stderr(proc, on_line)
    return proc.wait()


def yt(*args):
    """yt-dlp com as proteções de sempre; se o YouTube pedir verificação de bot,
    tenta de novo com os cookies do Chrome."""
    base = [str(config.ai_bin("yt-dlp")), "--no-warnings"]
    # --ffmpeg-location: o app aberto pelo Finder não tem o ffmpeg no PATH.
    ff = config.ffmpeg()
    if ff:
        base += ["--ffmpeg-location", str(Path(ff).parent)]
    r = subprocess.run([*base, *args], capture_output=True, text=True)
    if r.returncode == 0:
        return r.stdout
    r = subprocess.run([*base, "--cookies-from-browser", "chrome", *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        # Erro legível no log do job (antes o motivo real ficava escondido).
        tail = [l for l in (r.stderr or r.stdout or "").splitlines() if l.strip()]
        sys.exit(f"yt-dlp falhou: {tail[-1] if tail else f'código {r.returncode}'}")
    return r.stdout


def download(url, out_template):
    yt("-q", "--retries", "10", "--retry-sleep", "fragment:exp=1:120",
       "-f", "bestaudio[ext=m4a]/bestaudio/best", "-x", "--audio-format", "mp3",
       "--audio-quality", "5", "-o", out_template, url)


def mp3(src, dst):
    ff = config.ffmpeg()
    if not ff:
        raise RuntimeError("ffmpeg não encontrado")
    subprocess.run([ff, "-v", "error", "-y", "-i", str(src), "-codec:a", "libmp3lame",
                    "-q:a", "5", str(dst)], check=True)


def cmd_search(query):
    out = yt(f"ytsearch10:{query}", "--flat-playlist",
             "--print", "%(title)s — %(channel)s\t%(id)s")
    print(out, end="")


def cmd_info(vid):
    out = yt("--print", "%(track)s", "--print", "%(artist)s",
             "--print", "%(title)s", "--print", "%(channel)s", VIDEO_URL.format(vid))
    meta = (out.splitlines() + ["NA"] * 4)[:4]
    print(info_json(*meta))


def cmd_get(vid, mode="2faixas"):
    if mode not in ("2faixas", "3faixas"):
        sys.exit(f"modo inválido: {mode}")
    info = json.loads(cmd_info_capture(vid))
    title = info["name"]
    dest = config.lib_dir() / title

    with tempfile.TemporaryDirectory(prefix="karaoke-") as tmp:
        tmp = Path(tmp)
        work = tmp / title
        work.mkdir()

        # info.json: usado pela interface (artista/música para a letra, id para saber o que já foi baixado)
        (work / "info.json").write_text(
            json.dumps({**info, "id": vid, "mode": mode}, ensure_ascii=False, indent=2))

        src = work / "original.mp3"

        step(f"▶ {title} ({vid}) [{mode}]")
        step("1/3 download"); progress(2)
        if not src.is_file() or src.stat().st_size == 0:
            download(VIDEO_URL.format(vid), str(work / "original.%(ext)s"))
        progress(10)

        if mode == "2faixas":
            step("2/3 separando voz x instrumental")
            separate_2stems(src, tmp, work)

        else:  # 3faixas
            step("2/3 separando voz principal (Mel-Roformer, demorado)")
            rc = run([str(config.ai_bin("audio-separator")), str(src), "-m", LEAD_MODEL,
                      *LEAD_OPTS, "--model_file_dir", str(config.models_dir()),
                      "--output_dir", str(tmp / "lead"), "--output_format", "WAV"],
                     track=(10, 65))
            if rc != 0:
                sys.exit(f"audio-separator falhou (código {rc})")
            leads = list((tmp / "lead").glob("*(Vocals)*.wav"))
            restos = list((tmp / "lead").glob("*(Instrumental)*.wav"))
            if not leads or not restos:
                sys.exit("audio-separator não gerou as faixas esperadas")
            shutil.move(str(leads[0]), tmp / "lead.wav")
            shutil.move(str(restos[0]), tmp / "resto.wav")

            step("   separando backing vocals x instrumental (Demucs)")
            device = settings.demucs_device()
            cmd = [str(config.ai_bin("demucs")), "-n", "htdemucs", "--two-stems=vocals",
                   "-o", str(tmp / "demucs"), str(tmp / "resto.wav")]
            if device != "cpu":
                cmd.extend(["-d", device])
            rc = run(cmd, track=(75, 20))
            if rc != 0:
                sys.exit(f"demucs falhou (código {rc})")

            step("3/3 convertendo para MP3"); progress(95)
            mp3(tmp / "lead.wav", work / "voz principal.mp3")
            mp3(tmp / "demucs" / "htdemucs" / "resto" / "vocals.wav", work / "backing vocals.mp3")
            mp3(tmp / "demucs" / "htdemucs" / "resto" / "no_vocals.wav", work / "instrumental.mp3")

        # Apaga a pasta de destino antes para evitar sobras de um modo anterior
        # (ex: voz.mp3 de 2faixas ao reprocessar em 3faixas).
        step("movendo para a biblioteca"); progress(97)
        config.lib_dir().mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(work), str(dest))

    progress(100)
    step(f"✔ pronto: {dest}")
    print(dest)


def cmd_info_capture(vid):
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_info(vid)
    return buf.getvalue().strip()


USAGE = "uso: python -m karaoke.pipeline search <termo> | info <id> | get <id> [2faixas|3faixas]"


def main(argv=None):
    args = argv or sys.argv[1:]
    # PATH de reserva: garante ffmpeg/ffprobe para yt-dlp, demucs e
    # audio-separator mesmo quando o app foi aberto pelo Finder.
    os.environ["PATH"] = os.pathsep.join(
        [p for p in (os.environ.get("PATH", ""), config.extra_path()) if p])
    if not args:
        sys.exit(USAGE)
    cmd, rest = args[0], args[1:]
    if cmd == "search":
        cmd_search(" ".join(rest))
    elif cmd == "info":
        cmd_info(rest[0])
    elif cmd == "get":
        cmd_get(rest[0], rest[1] if len(rest) > 1 else "2faixas")
    else:
        sys.exit(USAGE)


if __name__ == "__main__":
    main()
