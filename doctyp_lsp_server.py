#!/usr/bin/env python3
"""
doctyp_lsp_server — Fase 1A de tinymist-implementation-plan.md: ciclo de vida del subproceso
`tinymist lsp`, gestionado por STDIO binario (framing LSP `Content-Length: N\\r\\n\\r\\n{json}`,
a diferencia de `doctyp_preview_server.py` que habla WebSocket con `tinymist preview`).

Un solo proceso por sesión de `doctyp web` (mismo criterio de "una instancia a la vez" que
`PreviewServer`, pero aquí el "recurso activo" es el *root* del workspace, no el documento -- ver
`cambiar_root()`): el `initialize` lo hace ESTE módulo una sola vez al arrancar; cambiar de
documento/plantilla activo reusa el mismo proceso vía `workspace/didChangeWorkspaceFolders`
(confirmado soportado por el binario real, `workspace.workspaceFolders.changeNotifications` en
`lsp-capabilities-0.15.2.json`, capturado en vivo -- paso 0 de la Fase 1).

El backend NO interpreta el protocolo JSON-RPC que fluye navegador↔tinymist salvo para lo que
gestiona directamente este módulo (`initialize`/`didChangeWorkspaceFolders`/`shutdown`, todo
"backend-owned", nunca visto por el navegador) -- el resto (allowlist de `executeCommand`,
respuestas locales a `workspace/configuration` etc.) lo decide el bridge en `doctyp_web.py`,
no este módulo, que solo sabe lanzar/hablar con el proceso.
"""
from __future__ import annotations
import json
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import doctyp as core
from doctyp_preview_binary import resolver_tinymist_utilizable

_TIMEOUT_INITIALIZE_S = 10.0
_TIMEOUT_PETICION_BACKEND_S = 5.0
_MAX_REINTENTOS = 3


class LspServerError(Exception):
    pass


def _leer_mensaje(stdout) -> bytes | None:
    """Framing LSP (snippet §3.4 del plan): cabeceras 'Content-Length: N' + \\r\\n\\r\\n + N
    bytes de JSON. `stdout` debe ser binario (Popen con text=False)."""
    largo = None
    while True:
        linea = stdout.readline()
        if not linea:
            return None  # el proceso cerró stdout
        if linea in (b"\r\n", b"\n"):
            break
        nombre, _, valor = linea.partition(b":")
        if nombre.strip().lower() == b"content-length":
            try:
                largo = int(valor.strip())
            except ValueError:
                return None
    if largo is None:
        return None
    return stdout.read(largo)


def _codificar_mensaje(datos: dict) -> bytes:
    payload = json.dumps(datos, ensure_ascii=False).encode("utf-8")
    return b"Content-Length: %d\r\n\r\n%s" % (len(payload), payload)


@dataclass
class LspServer:
    """Una instancia = un proceso `tinymist lsp` vivo, con el `root` de workspace actual.
    `on_message` recibe TODO mensaje del servidor que no sea la respuesta a una petición
    "backend-owned" (ver `_ids_pendientes`): notificaciones (`publishDiagnostics`, etc.) y
    peticiones server→client (`workspace/configuration`, ...) -- el bridge de `doctyp_web.py`
    decide qué hacer con cada una, este módulo solo las entrega tal cual."""

    root: Path
    font_dir: Path | None = None

    on_message: Callable[[dict], None] | None = field(default=None, init=False, repr=False)

    _proc: subprocess.Popen | None = field(default=None, init=False, repr=False)
    _lector: threading.Thread | None = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _lock_escritura: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    _siguiente_id_backend: int = field(default=-1, init=False, repr=False)
    # Ids de peticiones "backend-owned" (initialize/didChangeWorkspaceFolders/shutdown) usan
    # enteros NEGATIVOS -- el navegador (LSP client convencional) siempre empieza en 1 y sube,
    # así que este espacio de ids nunca colisiona con el suyo aunque ambos hablen con el mismo
    # proceso stdin/stdout. Ver cabecera del módulo: initialize/shutdown ocurren antes/después
    # de que haya tráfico del navegador, pero se namespacean igual por correctitud.
    _pendientes: dict[int, dict] = field(default_factory=dict, init=False, repr=False)
    _eventos_pendientes: dict[int, threading.Event] = field(default_factory=dict, init=False, repr=False)

    capabilities: dict | None = field(default=None, init=False, repr=False)
    server_info: dict | None = field(default=None, init=False, repr=False)
    _detenido_manualmente: bool = field(default=False, init=False, repr=False)
    _generacion: int = field(default=0, init=False, repr=False)

    def _tinymist_path(self) -> Path:
        resuelto = resolver_tinymist_utilizable()
        if resuelto is None:
            raise LspServerError("tinymist no disponible (ver aviso previo de doctyp_preview_binary).")
        return resuelto[0]

    def start(self) -> None:
        self._detenido_manualmente = False
        tinymist = self._tinymist_path()
        cmd = [str(tinymist), "lsp"]
        with self._lock:
            self._generacion += 1
            generacion = self._generacion
        self._proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            bufsize=0,  # binario, sin buffering -- a diferencia del Popen de texto de preview
        )
        self._lector = threading.Thread(target=self._bucle_lectura, args=(generacion,), daemon=True)
        self._lector.start()
        self._initialize()

    def _bucle_lectura(self, generacion: int) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        try:
            while True:
                crudo = _leer_mensaje(proc.stdout)
                if crudo is None:
                    break
                try:
                    datos = json.loads(crudo.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                self._despachar(datos)
        except OSError:
            pass
        if not self._detenido_manualmente and generacion == self._generacion:
            core._warn("tinymist lsp terminó inesperadamente (stdout cerrado).")

    def _despachar(self, datos: dict) -> None:
        id_ = datos.get("id")
        if isinstance(id_, int) and id_ < 0 and id_ in self._eventos_pendientes:
            self._pendientes[id_] = datos
            self._eventos_pendientes[id_].set()
            return
        if self.on_message:
            self.on_message(datos)

    def _escribir(self, datos: dict) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise LspServerError("proceso LSP no está corriendo")
        with self._lock_escritura:
            self._proc.stdin.write(_codificar_mensaje(datos))
            self._proc.stdin.flush()  # sin flush hay buffering => latencia (nota del plan §3.4)

    def enviar_crudo(self, payload: bytes) -> None:
        """Reenvía tal cual un mensaje ya serializado del navegador (el bridge de doctyp_web.py
        ya decidió que corresponde reenviarlo -- ver allowlist de executeCommand)."""
        if self._proc is None or self._proc.stdin is None:
            raise LspServerError("proceso LSP no está corriendo")
        with self._lock_escritura:
            self._proc.stdin.write(b"Content-Length: %d\r\n\r\n" % len(payload) + payload)
            self._proc.stdin.flush()

    def _peticion_backend(self, metodo: str, params: dict, timeout: float = _TIMEOUT_PETICION_BACKEND_S) -> dict:
        with self._lock:
            id_ = self._siguiente_id_backend
            self._siguiente_id_backend -= 1
        evento = threading.Event()
        self._eventos_pendientes[id_] = evento
        try:
            self._escribir({"jsonrpc": "2.0", "id": id_, "method": metodo, "params": params})
            if not evento.wait(timeout):
                raise LspServerError(f"sin respuesta de '{metodo}' tras {timeout}s")
            respuesta = self._pendientes.pop(id_)
            if "error" in respuesta:
                raise LspServerError(f"'{metodo}' devolvió error: {respuesta['error']}")
            return respuesta.get("result") or {}
        finally:
            self._eventos_pendientes.pop(id_, None)
            self._pendientes.pop(id_, None)

    def _notificacion(self, metodo: str, params: dict) -> None:
        self._escribir({"jsonrpc": "2.0", "method": metodo, "params": params})

    def ejecutar_comando(self, comando: str, argumentos: list, timeout: float = 30.0) -> dict:
        """Fase 1D (exportadores rápidos, D5): invoca workspace/executeCommand desde el propio
        backend (no desde el navegador) -- mismo mecanismo que _peticion_backend (ids negativos,
        sin colisión con los del navegador). Público (sin guión bajo): a diferencia de
        initialize/shutdown, esto lo llama doctyp_web.py directamente, no solo este módulo."""
        return self._peticion_backend("workspace/executeCommand", {
            "command": comando, "arguments": argumentos,
        }, timeout=timeout)

    def _initialize(self) -> None:
        # initializationOptions: Fase 1A punto 6 del plan -- configurado desde el backend
        # (única fuente de verdad, mismo criterio que settings.json). No confirmado en vivo
        # contra el schema real de tinymist todavía (paso 0 solo capturó ServerCapabilities,
        # no probó initializationOptions); si el servidor las ignora silenciosamente no rompe
        # nada (initialize solo falla si el JSON es inválido, no por claves desconocidas).
        opciones: dict = {
            "formatterMode": "typstyle",
            "semanticTokens": "enable",
            # NOTA (Fase 1D, investigación en vivo): "exportPdf": "never" NO bloquea la
            # invocación manual de tinymist.exportPdf vía executeCommand (se probó quitándola
            # y el error era idéntico) -- el bug real de "output path is relative" era que
            # arguments[0] debe ser una ruta plana, NO un URI file://. Se deja sin este campo:
            # no se confirmó que exista en el schema real (paso 0 no lo capturó, era una
            # suposición) y omitirlo no mostró efecto adverso alguno en las pruebas.
        }
        if self.font_dir is not None and self.font_dir.is_dir():
            opciones["fontPaths"] = [str(self.font_dir)]

        resultado = self._peticion_backend("initialize", {
            "processId": None,
            "rootUri": self.root.as_uri(),
            "workspaceFolders": [{"uri": self.root.as_uri(), "name": self.root.name}],
            "capabilities": {
                "textDocument": {
                    "synchronization": {"didSave": True},
                    "completion": {"completionItem": {"snippetSupport": True}},
                    "hover": {"contentFormat": ["markdown", "plaintext"]},
                    "signatureHelp": {},
                    "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
                    "definition": {}, "references": {}, "documentHighlight": {},
                    "codeAction": {}, "rename": {"prepareSupport": True},
                    "formatting": {}, "foldingRange": {}, "selectionRange": {},
                    "documentLink": {}, "documentColor": {}, "publishDiagnostics": {},
                    "semanticTokens": {
                        "requests": {"full": {"delta": True}},
                        "tokenTypes": [], "tokenModifiers": [], "formats": ["relative"],
                    },
                    "inlayHint": {}, "codeLens": {},
                },
                "workspace": {
                    "symbol": {}, "executeCommand": {}, "workspaceFolders": True,
                    "configuration": True, "didChangeConfiguration": {},
                    "didChangeWorkspaceFolders": True,
                },
                "window": {"workDoneProgress": True},
            },
            "initializationOptions": opciones,
        }, timeout=_TIMEOUT_INITIALIZE_S)
        self.capabilities = resultado.get("capabilities", {})
        self.server_info = resultado.get("serverInfo")
        self._notificacion("initialized", {})

    def cambiar_root(self, nuevo_root: Path) -> None:
        """Reusa el mismo proceso al cambiar de documento/plantilla activo -- confirmado
        soportado (workspace.workspaceFolders.changeNotifications=true en las capabilities
        reales capturadas en el paso 0). Si `nuevo_root` ya es el root vigente, no hace nada."""
        if nuevo_root.resolve() == self.root.resolve():
            return
        anterior = self.root
        self._notificacion("workspace/didChangeWorkspaceFolders", {
            "event": {
                "added": [{"uri": nuevo_root.as_uri(), "name": nuevo_root.name}],
                "removed": [{"uri": anterior.as_uri(), "name": anterior.name}],
            }
        })
        self.root = nuevo_root

    def stop(self) -> None:
        with self._lock:
            self._detenido_manualmente = True
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._peticion_backend("shutdown", {}, timeout=2.0)
                self._notificacion("exit", {})
            except (LspServerError, OSError):
                pass
            try:
                self._proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
        self._proc = None

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None
