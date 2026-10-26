"""Configurações do app persistidas em data_dir()/config.json.

Acessível tanto pelo backend quanto pelo pipeline (arquivo JSON simples).
"""
import json
import os
from pathlib import Path

from .config import data_dir

CONFIG_FILE = data_dir() / "config.json"
DEFAULTS = {
    "separation": "cpu",   # cpu | gpu | mvsep
    "mvsep_api_key": "",
    "mvsep_endpoint": "https://mvsep.com/api/separate",
    "score_enabled": False,
}


def _load() -> dict:
    if CONFIG_FILE.is_file():
        try:
            return {**DEFAULTS, **json.loads(CONFIG_FILE.read_text())}
        except Exception:
            pass
    return dict(DEFAULTS)


def get(key: str = None):
    cfg = _load()
    return cfg if key is None else cfg.get(key, DEFAULTS.get(key))


def set(values: dict) -> dict:
    cfg = _load()
    cfg.update(values)
    # só valores permitidos
    if cfg.get("separation") not in ("cpu", "gpu", "mvsep"):
        cfg["separation"] = "cpu"
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    safe_write(CONFIG_FILE, json.dumps(cfg, ensure_ascii=False, indent=2).encode())
    return cfg


def safe_write(path: Path, data: bytes):
    try:
        path.write_bytes(data)
    except Exception:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / path.name
            tmp.write_bytes(data)
            import shutil
            shutil.move(str(tmp), str(path))


def demucs_device() -> str:
    """Dispositivo usado pelo demucs com base na configuração."""
    engine = get("separation")
    if engine == "cpu":
        return "cpu"
    if engine == "gpu":
        # detecta a melhor opção disponível no venv de IA
        return _detect_gpu_device() or "cpu"
    return "cpu"


def _detect_gpu_device() -> str | None:
    import subprocess
    from . import config
    py = config.ai_python()
    if not py.is_file():
        return None
    try:
        out = subprocess.run(
            [str(py), "-I", "-c",
             "import torch,json; "
             "print(json.dumps({'cuda':torch.cuda.is_available(),'mps':getattr(torch.backends,'mps',None) is not None and torch.backends.mps.is_available()}))"],
            capture_output=True, text=True, timeout=30
        ).stdout.strip()
        info = json.loads(out)
        if info.get("mps"):
            return "mps"
        if info.get("cuda"):
            return "cuda"
    except Exception:
        pass
    return None
