#!/usr/bin/env python3
"""
doctyp_preview_server — Plan 15 F2: ciclo de vida del subproceso `tinymist preview`.

Lanza y supervisa `tinymist preview` como servidor de vista previa para UN documento a la vez
(el mismo modelo que `doctyp compile`: un `.typ` con su `root`). Mantiene una conexión
WebSocket PERSISTENTE al *control plane* del subproceso desde este mismo proceso Python (no
desde el navegador) -- decisión confirmada con el usuario tras el hallazgo de F0: si esa
conexión se cierra, `tinymist preview` se autoapaga por completo
("EditorActor: editor disconnected" -> "shutting down whole program"), así que sobrevivir a
recargas de página del frontend requiere que el dueño de esa conexión sea el backend, no el
navegador.

Solo se usa `tinymist preview` como servidor standalone de renderizado -- nunca como LSP ni
herramienta de edición (ver `plan 15.md` §0).
"""
from __future__ import annotations
import json
import os
import re
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import doctyp as core
from doctyp_preview_binary import resolver_tinymist_utilizable
from doctyp_ws_client import WebSocketClient, WebSocketError

# Etapa 18 (Docker/VPS, ver DESPLIEGUE.md): el data plane (lo único que habla directo el
# navegador) necesita un puerto FIJO y conocido de antemano para que Traefik pueda enrutarle
# un subdominio propio (doctyp-preview.<dominio>) -- un puerto aleatorio por proceso, como
# tenía la Etapa 15/16 (pensada para navegador+proceso en el mismo host), no se puede mapear a
# una regla de Traefik fija. DOCTYP_PREVIEW_DATA_PORT fija ese puerto (default 37800, arbitrario
# pero estable); DOCTYP_PREVIEW_BIND fija la interfaz (default 127.0.0.1 fuera de Docker, tal
# cual antes; 0.0.0.0 en el contenedor -- Traefik le llega por la red `proxy`, no localhost).
# El control plane (solo lo habla este proceso Python, nunca el navegador) sigue siendo
# 127.0.0.1 con puerto aleatorio -- no necesita ser alcanzable desde fuera del contenedor.
_DATA_PLANE_PORT_DEFAULT = 37800


def _puerto_data_plane_fijo() -> int:
    return int(os.environ.get("DOCTYP_PREVIEW_DATA_PORT", _DATA_PLANE_PORT_DEFAULT))


def _bind_data_plane() -> str:
    return os.environ.get("DOCTYP_PREVIEW_BIND", "127.0.0.1")


def _url_publica_data_plane() -> str:
    """URL que se le manda al navegador para el <iframe> de TinymistPreview.vue. Por defecto
    (sin DOCTYP_PREVIEW_PUBLIC_URL) sigue siendo http://127.0.0.1:<puerto>/, el caso de
    desarrollo local donde navegador y proceso comparten host (sin cambios de comportamiento
    fuera de Docker). En producción (VPS, ver DESPLIEGUE.md) se fija al subdominio dedicado
    que Traefik enruta directo al puerto fijo del data plane -- doctyp_web.py no proxea nada
    de esto, es un router de Traefik aparte apuntando al mismo contenedor/puerto."""
    override = os.environ.get("DOCTYP_PREVIEW_PUBLIC_URL")
    if override:
        return override.rstrip("/") + "/"
    return f"http://127.0.0.1:{_puerto_data_plane_fijo()}/"

# Ver plan15_notas.md §6: tinymist hace `.unwrap()` sobre el bind del socket y aborta (SIGABRT)
# si el puerto ya está ocupado -- no maneja el conflicto con gracia. Sin --data-plane-host/
# --control-plane-host, tinymist usa un rango "por defecto" que NO es realmente aleatorio: se
# confirmó en la práctica (dos instancias lanzadas casi simultáneamente) que ambas intentan
# los MISMOS puertos por defecto y la segunda choca con el mismo panic. La mitigación real es
# sondear puertos libres nosotros mismos (bind a puerto 0, que el SO garantiza libre en ese
# instante, cerrar, y pasarlo explícito) -- ver _puerto_libre() más abajo. Sigue existiendo una
# ventana de carrera teórica entre "cerrar nuestro socket de sondeo" y "que tinymist bindee ese
# puerto", pero es mucho más angosta que confiar en la asignación por defecto del binario.
_RE_DATA_PLANE = re.compile(r"Data plane server listening on:\s*([\w.\-]+):(\d+)")
_RE_CONTROL_PLANE = re.compile(r"Control panel server listening on:\s*([\w.\-]+):(\d+)")
_RE_COMPILE_ERROR = re.compile(r"compilation failed", re.IGNORECASE)

_TIMEOUT_ARRANQUE_S = 8.0
_MAX_REINTENTOS = 3


class PreviewServerError(Exception):
    pass


def _puerto_libre() -> int:
    """Pide al SO un puerto TCP libre en 127.0.0.1 (bind a puerto 0) y lo libera de inmediato.
    Punto de entrada único al bindear en localhost (mismo mecanismo que usa el resto de doctyp
    -- ver §6 de doctyp_web.py, aunque ese usa el puerto pedido por el usuario, no autodetección)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@dataclass
class PreviewServer:
    """Una instancia = un documento en preview. Cambiar de documento activo reinicia el
    subproceso (tinymist preview fija el entrypoint al lanzar; no se encontró en F0 un comando
    de cambio de archivo en caliente sin relanzar)."""

    main_typ: Path
    root: Path
    font_dir: Path | None = None
    # `doctyp web --verbose`: reenvía en vivo la salida de `tinymist preview` (por defecto solo
    # se guarda en log_lines, en memoria, y nunca llega a `docker compose logs` -- ver doctyp_web.py).
    verbose: bool = False

    _proc: subprocess.Popen | None = field(default=None, init=False, repr=False)
    _ctl: WebSocketClient | None = field(default=None, init=False, repr=False)
    _lector_stdout: threading.Thread | None = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    data_plane_host: str | None = field(default=None, init=False)
    data_plane_port: int | None = field(default=None, init=False)
    control_plane_host: str | None = field(default=None, init=False)
    control_plane_port: int | None = field(default=None, init=False)

    log_lines: list[str] = field(default_factory=list, init=False, repr=False)
    _reintentos_hechos: int = field(default=0, init=False, repr=False)
    _detenido_manualmente: bool = field(default=False, init=False, repr=False)
    _reiniciando: bool = field(default=False, init=False, repr=False)
    # Número de "generación" del proceso/conexión actual. La caída de un proceso la notan dos
    # hilos independientes (lector de stdout y cliente WS) que pueden disparar con segundos de
    # diferencia -- el callback de cierre del WS viejo debe poder reconocer que ya no es la
    # generación vigente (el reinicio ya ocurrió por la otra vía) y no relanzar de nuevo.
    _generacion: int = field(default=0, init=False, repr=False)

    # Callbacks opcionales para que doctyp_web.py reaccione a eventos del control plane sin
    # que este módulo conozca la API HTTP/SSE del backend.
    on_editor_scroll_to: object = field(default=None, init=False, repr=False)  # Callable[[dict]]
    on_compile_status: object = field(default=None, init=False, repr=False)  # Callable[[str]]

    def start(self) -> None:
        # `self._lock` NO es reentrante: no debe tomarse aquí "por fuera" -- _lanzar_proceso()
        # ya adquiere el lock puntualmente para el contador de generación, y arrancar/esperar
        # puertos/conectar el WS puede tardar varios segundos (nada de eso debe bloquear otras
        # operaciones sobre la instancia mientras tanto, como is_running o stop()).
        self._detenido_manualmente = False
        self._lanzar_proceso()
        self._esperar_puertos_anunciados()
        self._conectar_control_plane()

    def _tinymist_path(self) -> Path:
        resuelto = resolver_tinymist_utilizable()
        if resuelto is None:
            raise PreviewServerError("tinymist no disponible (ver aviso previo de doctyp_preview_binary).")
        return resuelto[0]

    def _lanzar_proceso(self) -> None:
        tinymist = self._tinymist_path()
        bind_data = _bind_data_plane()
        puerto_data = _puerto_data_plane_fijo()
        puerto_control = _puerto_libre()  # solo lo habla este proceso -- sigue siendo interno
        cmd = [
            str(tinymist), "preview",
            "--root", str(self.root),
            "--data-plane-host", f"{bind_data}:{puerto_data}",
            "--control-plane-host", f"127.0.0.1:{puerto_control}",
            "--no-open",
            "--verbose",
        ]
        if self.font_dir is not None and self.font_dir.is_dir():
            cmd += ["--font-path", str(self.font_dir)]
        cmd.append(str(self.main_typ))

        self.log_lines.clear()
        # Se fijan de antemano (no se espera a que tinymist los anuncie por stdout) porque
        # nosotros elegimos los puertos -- _esperar_puertos_anunciados() igual confirma que el
        # proceso los adoptó realmente, por si el binario cambiara de comportamiento.
        # data_plane_host queda en 127.0.0.1 aunque el bind real sea 0.0.0.0 (Docker): es el
        # host que usa la conexión INTERNA control-plane->data-plane (cabecera Origin, más
        # abajo), no la URL pública -- esa la arma info() por separado (ver _url_publica()).
        self.data_plane_host, self.data_plane_port = "127.0.0.1", puerto_data
        self.control_plane_host, self.control_plane_port = "127.0.0.1", puerto_control
        with self._lock:
            self._generacion += 1
            generacion_de_este_lanzamiento = self._generacion
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self._lector_stdout = threading.Thread(
            target=self._leer_stdout, args=(generacion_de_este_lanzamiento,), daemon=True,
        )
        self._lector_stdout.start()

    def _leer_stdout(self, generacion: int) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        for linea in proc.stdout:
            limpia = linea.rstrip("\n")
            self.log_lines.append(limpia)
            if len(self.log_lines) > 500:
                del self.log_lines[:250]  # cap simple: no crecer sin límite en sesiones largas
            if self.verbose:
                print(f"  [tinymist preview: {self.main_typ.name}] {limpia}", flush=True)
        # El stdout se cerró: el proceso terminó. Si no fue un stop() manual Y esta lectura sigue
        # siendo la de la generación vigente (no un reinicio ya en curso por otra vía), es una
        # caída real que hay que atender.
        if not self._detenido_manualmente and generacion == self._generacion:
            self._on_proceso_caido()

    def _esperar_puertos_anunciados(self) -> None:
        """Los puertos ya se fijaron en _lanzar_proceso() (los elegimos nosotros); acá solo se
        confirma, leyendo el log, que el proceso realmente los adoptó y arrancó bien -- si el
        binario cambiara de comportamiento y los ignorara, esto lo detectaría igual porque el
        log anunciaría puertos distintos a los pedidos (se acepta cualquiera de los dos como
        señal de arranque exitoso; lo crítico es que arrancó, no cuál puerto exacto usó)."""
        limite = time.monotonic() + _TIMEOUT_ARRANQUE_S
        while time.monotonic() < limite:
            anuncio_data = anuncio_control = False
            for linea in list(self.log_lines):
                if _RE_DATA_PLANE.search(linea):
                    anuncio_data = True
                if _RE_CONTROL_PLANE.search(linea):
                    anuncio_control = True
            if anuncio_data and anuncio_control:
                return
            if self._proc is not None and self._proc.poll() is not None:
                raise PreviewServerError(
                    "tinymist preview terminó antes de anunciar sus puertos:\n"
                    + "\n".join(self.log_lines[-20:])
                )
            time.sleep(0.1)
        raise PreviewServerError(
            f"tinymist preview no anunció sus puertos en {_TIMEOUT_ARRANQUE_S}s:\n"
            + "\n".join(self.log_lines[-20:])
        )

    def _conectar_control_plane(self) -> None:
        generacion_de_esta_conexion = self._generacion
        origin = f"http://{self.data_plane_host}:{self.data_plane_port}"
        cliente = WebSocketClient(
            host=self.control_plane_host,
            port=self.control_plane_port,
            path="/",
            origin=origin,
            on_message=self._on_control_message,
            on_close=lambda: self._on_control_plane_cerrado(generacion_de_esta_conexion),
        )
        cliente.conectar()
        self._ctl = cliente

    def _on_control_message(self, payload: bytes, es_binario: bool) -> None:
        if es_binario:
            return
        try:
            data = json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        evento = data.get("event")
        if evento == "editorScrollTo" and self.on_editor_scroll_to:
            self.on_editor_scroll_to(data)
        elif evento == "compileStatus" and self.on_compile_status:
            self.on_compile_status(data.get("kind", ""))

    def _on_control_plane_cerrado(self, generacion: int) -> None:
        # Confirmado en F0: si esta conexión se cierra, tinymist preview se autoapaga solo. No
        # hace falta matarlo explícitamente aquí, pero si fue una caída inesperada (no un stop()
        # nuestro) intentamos reiniciar con reintentos -- salvo que ya no seamos la generación
        # vigente (el reinicio ya ocurrió por la otra vía, ver _leer_stdout).
        if not self._detenido_manualmente and generacion == self._generacion:
            self._on_proceso_caido()

    def _on_proceso_caido(self) -> None:
        # La misma caída la observan DOS hilos independientes en paralelo: el lector de stdout
        # (ve que el proceso terminó) y el cliente WS (ve que el control plane se cerró). Sin
        # esta guarda, ambos intentan reiniciar a la vez y el segundo choca contra el primer
        # relanzamiento a medio construir (ConnectionRefusedError). `_reiniciando` hace que solo
        # el primero en llegar dispare el reinicio real; el lock protege la lectura+escritura de
        # esa bandera, pero se libera ANTES de reintentar (lanzar+esperar+conectar puede tardar
        # segundos y no debe bloquear otras operaciones sobre la instancia). El check de
        # generación (arriba, en los llamadores) cubre el caso en que el hilo lento notifica
        # después de que el reinicio ya haya completado por la otra vía.
        with self._lock:
            if self._detenido_manualmente or self._reiniciando:
                return
            if self._reintentos_hechos >= _MAX_REINTENTOS:
                core._warn(
                    f"tinymist preview cayó {_MAX_REINTENTOS} veces seguidas para "
                    f"'{self.main_typ.name}'; se deja de reintentar. Revisa el log con "
                    "doctyp web --verbose."
                )
                return
            self._reiniciando = True
            self._reintentos_hechos += 1
            intento_actual = self._reintentos_hechos

        core._warn(
            f"tinymist preview terminó inesperadamente (reintento "
            f"{intento_actual}/{_MAX_REINTENTOS})..."
        )
        backoff = 0.5 * (2 ** (intento_actual - 1))
        time.sleep(backoff)
        try:
            self._lanzar_proceso()
            self._esperar_puertos_anunciados()
            self._conectar_control_plane()
            with self._lock:
                self._reintentos_hechos = 0  # arrancó bien, resetea el contador
        except PreviewServerError as e:
            core._warn(f"reintento de tinymist preview falló: {e}")
        finally:
            with self._lock:
                self._reiniciando = False

    def send_panel_scroll_to(self, filepath: str, line: int, character: int) -> None:
        """Editor→preview: salto explícito (F6). No garantiza un `jump` visible -- confirmado
        en F0 que el servidor lo ignora en silencio si la posición no cae en un span resoluble
        (p. ej. exactamente sobre el "=" de un heading); eso es comportamiento esperado, no error."""
        if self._ctl is None or not self._ctl.conectado:
            raise PreviewServerError("control plane no conectado")
        msg = {"event": "panelScrollTo", "filepath": filepath, "line": line, "character": character}
        self._ctl.enviar_texto(json.dumps(msg))

    def send_update_memory_files(self, files: dict[str, str]) -> None:
        """F6: contenido no guardado -- recompila en memoria sin tocar el archivo en disco
        (verificado en F0)."""
        if self._ctl is None or not self._ctl.conectado:
            raise PreviewServerError("control plane no conectado")
        msg = {"event": "updateMemoryFiles", "files": files}
        self._ctl.enviar_texto(json.dumps(msg))

    def stop(self) -> None:
        with self._lock:
            self._detenido_manualmente = True
            if self._ctl is not None:
                self._ctl.cerrar()
                self._ctl = None
            if self._proc is not None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                    self._proc.wait(timeout=2.0)
                self._proc = None

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def info(self) -> dict:
        """Para el endpoint /api/preview/info (F2, punto 2 del plan)."""
        return {
            "enabled": self.is_running,
            "static_url": _url_publica_data_plane() if self.data_plane_port else None,
            # No hay endpoint WS directo expuesto al frontend por diseño (F0 §5): el frontend
            # no se conecta él mismo al control plane, así que no se publica su URL aquí.
        }
