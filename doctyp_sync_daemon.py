#!/usr/bin/env python3
"""
doctyp_sync_daemon — proceso en segundo plano que reintenta `doctyp_sync.sincronizar_todo()`
cada 5 segundos (`doctyp _sync-daemon`, comando interno, ver doctyp.py: cmd_sync_daemon).

Es el primer proceso del proyecto pensado para sobrevivir a la invocación de CLI que lo lanzó
(o al gestor de servicios del sistema operativo que lo supervisa -- systemd --user en Linux,
LaunchAgent en macOS, Task Scheduler en Windows, ver `init`/`init.ps1`). `doctyp sync`/`doctyp
login` lo relanzan solos si detectan que no está vivo (auto-sanación vía pidfile).

Stdlib puro, sin dependencias externas (mismo principio que doctyp_sync.py) -- `ctypes` solo
se importa dentro de las ramas específicas de Windows para que el módulo importe limpio en
POSIX.
"""
from __future__ import annotations
import datetime
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import doctyp as core
import doctyp_sync as sync

INTERVALO_SEGUNDOS = 5.0


# ── Rutas de estado (junto a settings.json, no XDG) ─────────────────────────────────────────

def _estado_dir() -> Path:
    """Carpeta donde viven pidfile/log del daemon: la MISMA carpeta que settings.json
    (core.registro_path(core.SCRIPT_DIR).parent), no un directorio XDG de estado -- el
    proyecto ya decidió que settings.json no usa convenciones XDG (a diferencia de
    docs_root(), que sí resuelve Documentos por SO); el daemon es un detalle de esa misma
    instalación, no un segundo esquema de ubicación de archivos."""
    return core.registro_path(core.SCRIPT_DIR).parent


def pid_path() -> Path:
    return _estado_dir() / "sync_daemon.pid"


def log_path() -> Path:
    return _estado_dir() / "sync_daemon.log"


# ── Liveness cruzada ─────────────────────────────────────────────────────────────────────────

def _pid_vivo(pid: int) -> bool:
    """¿Existe un proceso con este PID? En POSIX, os.kill(pid, 0) es el probe estándar (no
    manda ninguna señal real). Windows no tiene esa semántica vía os.kill -- se usa
    OpenProcess de kernel32 (ctypes, stdlib) en su lugar."""
    if sys.platform.startswith("win"):
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # existe pero es de otro usuario -- igual cuenta como "vivo"
    return True


# ── Pidfile ──────────────────────────────────────────────────────────────────────────────────

def leer_pid() -> int | None:
    p = pid_path()
    if not p.exists():
        return None
    try:
        return int(p.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def _escribir_pid(pid: int) -> None:
    core._escribir_texto_atomico(pid_path(), str(pid))


def _borrar_pid() -> None:
    pid_path().unlink(missing_ok=True)


def daemon_vivo() -> int | None:
    """PID vivo del daemon, o None. Efecto secundario: si el pidfile apunta a un PID que ya no
    existe (caída, kill -9, reinicio sin cierre limpio), lo borra -- así el próximo chequeo no
    vuelve a toparse con el mismo archivo obsoleto."""
    pid = leer_pid()
    if pid is None:
        return None
    if _pid_vivo(pid):
        return pid
    _borrar_pid()
    return None


# ── Un tick ──────────────────────────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    linea = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(linea, flush=True)


def _asegurar_carpetas() -> None:
    """core.docs_root()/docs_root_org() ya crean carpetas, pero solo de forma reactiva dentro
    de un round-trip de red exitoso -- acá se llaman sin red, incondicionalmente, para que la
    carpeta de Documentos exista desde el primer tick (incluso antes de cualquier login) y la
    de cada org exista aunque la red falle. Sin lógica de mkdir nueva: pura reutilización."""
    core.docs_root()
    sesion = sync.sesion_activa()
    if sesion:
        for slug in (sesion.get("orgs") or []):
            core.docs_root_org(slug)


def un_tick() -> None:
    """Nunca lanza -- un tick que falla no debe matar el loop; se reintenta en el siguiente."""
    try:
        _asegurar_carpetas()
        if sync.sesion_activa() is None:
            return  # sin sesión: nada que sincronizar, la carpeta base ya quedó asegurada
        orgs = sync.sincronizar_todo()
        _log(f"sincronizado: {len(orgs)} organización(es)")
    except sync.SyncError as e:
        _log(f"advertencia: sync falló ({e}); reintento en el próximo tick")
    except Exception as e:  # noqa: BLE001 - nunca dejar que un tick mate el loop
        _log(f"error inesperado en tick: {e!r}")


# ── El loop ──────────────────────────────────────────────────────────────────────────────────

_debe_parar = False


def _manejar_senal(signum, frame):
    global _debe_parar
    _debe_parar = True


def ejecutar_foreground(intervalo: float = INTERVALO_SEGUNDOS) -> None:
    """Entrypoint de 'doctyp _sync-daemon' -- bloqueante, en primer plano. Igual si lo invoca
    systemd/launchd/Task Scheduler directamente, o si lo lanzó 'doctyp sync'/'doctyp login'
    como proceso desprendido (ver lanzar_en_segundo_plano): el bucle no necesita saber cuál de
    los dos es -- siempre se autoregistra en el pidfile al partir y lo limpia al salir."""
    _escribir_pid(os.getpid())
    signal.signal(signal.SIGTERM, _manejar_senal)
    signal.signal(signal.SIGINT, _manejar_senal)
    _log(f"daemon iniciado (pid={os.getpid()}, intervalo={intervalo}s)")
    try:
        while not _debe_parar:
            un_tick()
            time.sleep(intervalo)
    finally:
        _borrar_pid()
        _log("daemon detenido")


# ── Lanzar desprendido / detener (usado por cmd_sync/cmd_login/cmd_logout) ──────────────────

def lanzar_en_segundo_plano() -> int:
    """Lanza 'doctyp _sync-daemon' como proceso desprendido de la terminal/proceso actual. NO
    es lo que ejecutan systemd/launchd/Task Scheduler (esos invocan ejecutar_foreground()
    directamente, en primer plano, y son ellos quienes supervisan/capturan la salida -- ver
    init/init.ps1); esto es solo para el autoarranque bajo demanda desde la CLI."""
    cmd = [sys.executable, str(core.SCRIPT_DIR / "doctyp.py"), "_sync-daemon"]
    logfile = open(log_path(), "ab")
    if sys.platform.startswith("win"):
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        proc = subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL, stdout=logfile, stderr=subprocess.STDOUT,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP, close_fds=True,
        )
    else:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL, stdout=logfile, stderr=subprocess.STDOUT,
            start_new_session=True, close_fds=True,
        )
    return proc.pid


def asegurar_daemon_en_marcha() -> tuple[int, bool]:
    """Devuelve (pid, ya_estaba_activo). Si no hay daemon vivo, lo lanza y espera brevemente
    (hasta ~2s) a que se autoregistre en el pidfile antes de devolver el control -- acotado,
    para que 'doctyp sync'/'doctyp login' nunca se cuelguen esperando indefinidamente."""
    pid = daemon_vivo()
    if pid is not None:
        return pid, True
    lanzar_en_segundo_plano()
    for _ in range(20):
        time.sleep(0.1)
        pid = daemon_vivo()
        if pid is not None:
            return pid, False
    return -1, False


def detener_daemon() -> bool:
    pid = daemon_vivo()
    if pid is None:
        return False
    if sys.platform.startswith("win"):
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    _borrar_pid()
    return True
