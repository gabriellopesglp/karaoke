"""Sessões de controle remoto.

Cada dispositivo que toca música tem um sessionId. O servidor guarda o estado
da sessão (música, volumes, foco, etc.) e uma fila de comandos enviados pelo
controle remoto (outro dispositivo que escaneou o QR code da sessão).
"""
import threading
import time

from . import ws

sessions = {}
sessions_lock = threading.Lock()
SESSION_TTL = 300  # segundos sem heartbeat antes de esquecer a sessão
_seq = 0  # seq global dos comandos (dedupe TV WS × heartbeat)


def session_heartbeat(session_id, state):
    with sessions_lock:
        sessions[session_id] = {
            "state": state,
            "commands": sessions.get(session_id, {}).get("commands", []),
            "last": time.time(),
        }
        # limpa sessões expiradas
        now = time.time()
        for k in [k for k, v in sessions.items() if now - v["last"] > SESSION_TTL]:
            del sessions[k]
    ws.broadcast({"type": "session", "session": session_id, "state": state})


def session_get(session_id):
    with sessions_lock:
        s = sessions.get(session_id)
        return s["state"] if s else None


def session_poll_commands(session_id):
    """A sessão controlada pega os comandos pendentes (e limpa a fila)."""
    with sessions_lock:
        s = sessions.get(session_id)
        if not s:
            return []
        cmds = s["commands"]
        s["commands"] = []
        return cmds


def session_send_command(session_id, command):
    """O controle remoto envia um comando para a sessão.

    Cada comando ganha um seq "i": a TV o recebe na hora pelo WS (evento
    "command") e de novo na resposta do heartbeat — executa uma única vez,
    deduplicando pelo "i"."""
    global _seq
    with sessions_lock:
        s = sessions.get(session_id)
        if not s:
            return False
        _seq += 1
        cmd = {**command, "i": _seq}
        s["commands"].append(cmd)
    ws.broadcast({"type": "command", "session": session_id, "command": cmd})
    return True
