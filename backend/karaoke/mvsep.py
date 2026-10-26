"""Integração com MVSep (separação online via API).

A API real do MVSep é privada e requer chave. Este módulo implementa o fluxo
comum: envia o áudio, espera o job terminar e baixa os stems. Os nomes de
campos/endpoints são configuráveis porque o schema público não foi localizado.

Ajuste em settings.py/config.json:
    mvsep_endpoint  URL base (padrão: https://mvsep.com/api/separate)
    mvsep_api_key   chave do usuário
"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from . import settings


class MVSepError(RuntimeError):
    pass


def _request(url, data=None, headers=None, method=None, files=None):
    """Faz uma requisição HTTP simples."""
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        raise MVSepError(f"HTTP {e.code}: {body}")


def separate(src: Path, tmp: Path, progress=None):
    """Separa src em voz/instrumental usando MVSep.

    Retorna (vocal_wav_path, no_vocals_wav_path). Os arquivos são salvos em tmp.
    progress(msg, pct) é chamado ocasionalmente.
    """
    cfg = settings.get()
    key = cfg.get("mvsep_api_key", "")
    endpoint = cfg.get("mvsep_endpoint", "https://mvsep.com/api/separate")
    if not key:
        raise MVSepError("Chave de API do MVSep não configurada (Menu de configurações).")

    # Schema guess: POST multipart com arquivo + api_key.
    # Se a API real usar nomes diferentes, ajuste aqui ou torne configurável.
    boundary = "----KaraokeMVSepBoundary"
    parts = []
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="api_key"\r\n\r\n{key}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="stems"\r\n\r\n2\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{src.name}"\r\nContent-Type: audio/mpeg\r\n\r\n'.encode())
    parts.append(src.read_bytes())
    parts.append(f'\r\n--{boundary}--\r\n'.encode())
    body = b"".join(parts)

    if progress:
        progress("enviando áudio para o MVSep", 15)
    try:
        resp = _request(endpoint, data=body, headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "karaoke-local/1.0",
        }, method="POST")
    except Exception as e:
        raise MVSepError(f"Falha ao enviar para o MVSep: {e}") from e

    try:
        data = json.loads(resp)
    except json.JSONDecodeError:
        raise MVSepError(f"Resposta inesperada do MVSep: {resp[:300]!r}")

    # Guess do polling: job_id + status URL.
    job_id = data.get("job_id") or data.get("id")
    if not job_id:
        raise MVSepError(f"Resposta do MVSep não contém job_id: {data}")

    status_url = data.get("status_url") or f"{endpoint}/status/{job_id}"
    for attempt in range(180):  # até ~15 min
        if progress and attempt % 10 == 0:
            progress(f"aguardando o MVSep processar ({attempt//6} min)", 20 + min(50, attempt))
        time.sleep(5)
        try:
            status = json.loads(_request(status_url, headers={"User-Agent": "karaoke-local/1.0"}))
        except Exception as e:
            raise MVSepError(f"Erro ao consultar status: {e}") from e
        if status.get("status") == "done" or status.get("state") == "done":
            result = status.get("result") or status
            break
        if status.get("status") == "error" or status.get("state") == "error":
            raise MVSepError(f"Erro no MVSep: {status.get('error', 'desconhecido')}")
    else:
        raise MVSepError("Tempo esgotado aguardando o MVSep.")

    # Guess dos links de download.
    urls = result if isinstance(result, list) else result.get("urls") or result.get("files") or []
    vocals_url = None
    instr_url = None
    for u in urls:
        url = u if isinstance(u, str) else u.get("url")
        name = (u.get("name") if isinstance(u, dict) else url)
        if url and name:
            nl = name.lower()
            if "vocal" in nl or "vocals" in nl:
                vocals_url = url
            elif "instr" in nl or "no_vocals" in nl or "instrumental" in nl or "other" in nl:
                instr_url = url
    if not vocals_url or not instr_url:
        raise MVSepError(f"Não foi possível identificar os links dos stems: {result}")

    if progress:
        progress("baixando stems do MVSep", 80)
    vocal_path = tmp / "mvsep_vocals.wav"
    instr_path = tmp / "mvsep_instrumental.wav"
    try:
        vocal_path.write_bytes(_request(vocals_url))
        instr_path.write_bytes(_request(instr_url))
    except Exception as e:
        raise MVSepError(f"Falha ao baixar stems: {e}") from e

    return vocal_path, instr_path
