#!/usr/bin/env python3
"""
doctyp_ws_server — Fase 1A de tinymist-implementation-plan.md: lado SERVIDOR de un WebSocket
mínimo (RFC 6455) sobre stdlib pura, espejo de `doctyp_ws_client.py` (Plan 15 F2, lado
cliente). Usado por `GET /api/lsp` en `doctyp_web.py` para exponer un puente WS crudo
navegador↔`tinymist lsp` sobre el mismo `http.server`/puerto que sirve el resto de la API — sin
dependencias externas (CLAUDE.md §6), sin un servidor WS de propósito general aparte.

A diferencia del cliente (Plan 15 F2, mensajes JSON cortos de control), este lado SÍ necesita:
- Aceptar frames ENMASCARADOS de entrada (el navegador enmascara siempre, RFC 6455 §5.1) y
  enviar SIN máscara (el servidor nunca enmascara).
- Reensamblar fragmentación de entrada (FIN=0 + frames de continuación opcode 0x0): las
  respuestas de `completion`/`semanticTokens` del LSP pueden superar cientos de KB, y aunque el
  envío propio no fragmenta (la longitud extendida de 64 bits ya cubre payloads grandes en un
  solo frame), un cliente remoto podría fragmentar su entrada -- H5 del plan pide soportarlo.
"""
from __future__ import annotations
import base64
import hashlib
import struct
import threading
from dataclasses import dataclass, field
from typing import BinaryIO

_GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"  # RFC 6455 §1.3, misma constante que el cliente

_OP_CONTINUATION = 0x0
_OP_TEXT = 0x1
_OP_BINARY = 0x2
_OP_CLOSE = 0x8
_OP_PING = 0x9
_OP_PONG = 0xA

_MAX_PAYLOAD = 64 * 1024 * 1024  # cota de cordura (64 MB) contra un cliente malicioso/roto


class WebSocketServerError(Exception):
    pass


def es_peticion_upgrade(headers) -> bool:
    """`headers`: `self.headers` de un `BaseHTTPRequestHandler` (email.message.Message)."""
    upgrade = (headers.get("Upgrade") or "").strip().lower()
    connection = (headers.get("Connection") or "").lower()
    return upgrade == "websocket" and "upgrade" in connection


def realizar_handshake(headers, wfile: BinaryIO) -> bool:
    """Valida las cabeceras de upgrade y responde 101 con Sec-WebSocket-Accept (RFC 6455 §4.2).
    Devuelve True si el handshake se completó (el llamador debe pasar a modo framing sobre el
    mismo socket); False si las cabeceras no calzan (el llamador debe responder error HTTP
    normal, la conexión sigue siendo HTTP)."""
    key = headers.get("Sec-WebSocket-Key")
    version = headers.get("Sec-WebSocket-Version")
    if not key or version != "13":
        return False
    accept = base64.b64encode(hashlib.sha1((key + _GUID.decode()).encode()).digest()).decode()
    respuesta = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept}\r\n"
        "\r\n"
    ).encode("ascii")
    wfile.write(respuesta)
    wfile.flush()
    return True


def _leer_exacto(rfile: BinaryIO, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = rfile.read(n - len(buf))
        if not chunk:
            raise WebSocketServerError("conexión cerrada por el cliente mientras se leía un frame")
        buf.extend(chunk)
    return bytes(buf)


def _leer_frame_crudo(rfile: BinaryIO) -> tuple[int, bool, bytes]:
    """Lee UN frame de entrada (siempre enmascarado -- RFC 6455 §5.1, se cierra si no lo está).
    Devuelve (opcode, fin, payload_desenmascarado)."""
    b0, b1 = _leer_exacto(rfile, 2)
    fin = bool(b0 & 0x80)
    opcode = b0 & 0x0F
    enmascarado = bool(b1 & 0x80)
    longitud = b1 & 0x7F
    if longitud == 126:
        longitud = struct.unpack("!H", _leer_exacto(rfile, 2))[0]
    elif longitud == 127:
        longitud = struct.unpack("!Q", _leer_exacto(rfile, 8))[0]
    if longitud > _MAX_PAYLOAD:
        raise WebSocketServerError(f"frame de {longitud} bytes excede la cota de {_MAX_PAYLOAD}")
    if not enmascarado:
        raise WebSocketServerError("frame de cliente sin máscara (viola RFC 6455 §5.1)")
    mascara = _leer_exacto(rfile, 4)
    crudo = _leer_exacto(rfile, longitud) if longitud else b""
    payload = bytes(b ^ mascara[i % 4] for i, b in enumerate(crudo))
    return opcode, fin, payload


def _codificar_frame(opcode: int, payload: bytes) -> bytes:
    """Codifica un frame saliente (servidor→cliente: SIN máscara, RFC 6455 §5.1). Sin
    fragmentar -- la longitud extendida de 64 bits ya cubre payloads grandes en un solo frame."""
    fin_y_opcode = 0x80 | opcode
    longitud = len(payload)
    if longitud < 126:
        cabecera = struct.pack("!BB", fin_y_opcode, longitud)
    elif longitud < 65536:
        cabecera = struct.pack("!BBH", fin_y_opcode, 126, longitud)
    else:
        cabecera = struct.pack("!BBQ", fin_y_opcode, 127, longitud)
    return cabecera + payload


@dataclass
class WebSocketServerConnection:
    """Envuelve el socket ya "hijackeado" de un `BaseHTTPRequestHandler` tras el handshake.
    Un hilo por conexión (el propio hilo del handler HTTP, `ThreadingHTTPServer`) -- no hace
    falta un hilo de lectura en background aparte como en el cliente, porque el llamador
    (`doctyp_web.py`) ya bloquea ese hilo en un bucle de lectura dedicado a esta conexión."""

    rfile: BinaryIO
    wfile: BinaryIO
    _lock_envio: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _cerrado: bool = field(default=False, init=False, repr=False)

    def leer_mensaje(self) -> tuple[int, bytes] | None:
        """Lee UN mensaje completo (reensamblando fragmentación si hace falta). Devuelve
        (opcode, payload) con opcode en {TEXT, BINARY} para mensajes de datos -- ping/pong se
        responden/ignoran acá mismo, sin exponerlos al llamador. None si el cliente cerró."""
        fragmentos: list[bytes] = []
        opcode_mensaje: int | None = None
        while True:
            try:
                opcode, fin, payload = _leer_frame_crudo(self.rfile)
            except WebSocketServerError:
                return None
            if opcode == _OP_CONTINUATION:
                if opcode_mensaje is None:
                    raise WebSocketServerError("frame de continuación sin mensaje fragmentado abierto")
                fragmentos.append(payload)
            elif opcode in (_OP_TEXT, _OP_BINARY):
                if opcode_mensaje is not None:
                    raise WebSocketServerError("nuevo mensaje de datos con uno fragmentado sin cerrar")
                opcode_mensaje = opcode
                fragmentos.append(payload)
            elif opcode == _OP_PING:
                self._enviar_frame(_OP_PONG, payload)
                continue
            elif opcode == _OP_PONG:
                continue
            elif opcode == _OP_CLOSE:
                self._responder_close(payload)
                return None
            else:
                continue  # opcode reservado/desconocido: se ignora, no rompe la conexión

            if fin:
                return opcode_mensaje, b"".join(fragmentos)
            # FIN=0 en un frame de datos/continuación: sigue esperando más continuación.

    def _enviar_frame(self, opcode: int, payload: bytes) -> None:
        if self._cerrado:
            return
        with self._lock_envio:
            try:
                self.wfile.write(_codificar_frame(opcode, payload))
                self.wfile.flush()
            except OSError:
                self._cerrado = True

    def enviar_texto(self, texto: str) -> None:
        self._enviar_frame(_OP_TEXT, texto.encode("utf-8"))

    def _responder_close(self, payload: bytes) -> None:
        if self._cerrado:
            return
        self._cerrado = True
        try:
            self._enviar_frame(_OP_CLOSE, payload[:2])  # eco del código de cierre, sin razón
        except OSError:
            pass

    def cerrar(self) -> None:
        if self._cerrado:
            return
        self._enviar_frame(_OP_CLOSE, b"")
        self._cerrado = True

    @property
    def cerrado(self) -> bool:
        return self._cerrado
