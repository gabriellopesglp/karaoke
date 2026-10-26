"""WebSocket /ws: broadcast de eventos JSON para todos os clientes conectados.

Cada conexão tem uma asyncio.Queue drenada por uma task do endpoint. As mutações
(fila, jobs, sessões, alinhamento) acontecem em threads worker, então o envio é
sempre agendado no loop principal com run_coroutine_threadsafe — _clients só é
tocado dentro do loop.

Eventos:
    {"type": "queue", "queue": [...]}                       a fila mudou
    {"type": "jobs", "jobs": [...]}                         um job mudou (throttle 500ms)
    {"type": "session", "session": sid, "state": {...}}     heartbeat da sessão
    {"type": "command", "session": sid, "command": {...}}   comando p/ a TV (com seq "i")
    {"type": "align", "folder": f, "pct": n, "step": s}     progresso do alinhamento
"""
import asyncio
import time

_loop = None
_clients = set()  # asyncio.Queue, uma por conexão (só mexida no loop principal)

JOBS_THROTTLE = 0.5  # o worker atualiza pct várias vezes por segundo; coalesce
_jobs_pending = None
_jobs_flush_handle = None
_jobs_last = 0.0


def attach(loop):
    """Registra o loop principal (chamado no startup do FastAPI)."""
    global _loop
    _loop = loop


def register():
    q = asyncio.Queue(maxsize=100)
    _clients.add(q)
    return q


def unregister(q):
    _clients.discard(q)


async def _fanout(msg):
    for q in list(_clients):
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            _clients.discard(q)  # cliente lento demais; desiste dele


def broadcast(msg):
    """Agenda o envio de msg para todos os clientes. Seguro chamar de qualquer thread."""
    loop = _loop
    if loop is not None:
        asyncio.run_coroutine_threadsafe(_fanout(msg), loop)


def broadcast_jobs(jobs_list):
    """Evento de jobs com throttle: manda na hora e, no máximo, um a cada JOBS_THROTTLE."""
    loop = _loop
    if loop is not None:
        asyncio.run_coroutine_threadsafe(_jobs_changed(jobs_list), loop)


async def _jobs_changed(jobs_list):
    global _jobs_pending, _jobs_flush_handle
    _jobs_pending = jobs_list
    if _jobs_flush_handle is None:
        delay = max(0.0, JOBS_THROTTLE - (time.monotonic() - _jobs_last))
        _jobs_flush_handle = _loop.call_later(delay, _flush_jobs)


def _flush_jobs():
    global _jobs_pending, _jobs_flush_handle, _jobs_last
    _jobs_flush_handle = None
    if _jobs_pending is not None:
        msg = {"type": "jobs", "jobs": _jobs_pending}
        _jobs_pending = None
        _jobs_last = time.monotonic()
        asyncio.ensure_future(_fanout(msg))
