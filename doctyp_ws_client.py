#!/usr/bin/env python3
"""
doctyp_ws_client — Plan 15 F2: cliente WebSocket mínimo (RFC 6455) sobre stdlib pura.

El proyecto no usa dependencias externas (CLAUDE.md §6) y Python stdlib no trae cliente
WebSocket, así que este módulo implementa lo mínimo necesario para mantener viva la conexión
persistente de `doctyp_web.py` al *control plane* de `tinymist preview` (ver
`doctyp_preview_server.py`, F2): handshake de upgrade HTTP→WS, envío/recepción de frames de
texto, frames de control (ping/pong/close), y reconexión no incluida aquí (vive en el llamador).

No implementa: fragmentación de mensajes (unnecesario para JSON/texto corto de este protocolo),
extensiones (compression), ni el lado servidor. Es un cliente de un solo propósito, no una
librería WebSocket de propósito general.
"""
from __future__ import annotations
import base64
import hashlib
import os
import socket
import struct
import threading
from dataclasses import dataclass, field
from typing import Callable

_GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"  # RFC 6455 §1.3, constante fija del protocolo

_OP_TEXT = 0x1
_OP_BINARY = 0x2
_OP_CLOSE = 0x8
_OP_PING = 0x9
_OP_PONG = 0xA


class WebSocketError(Exception):
    pass


def _leer_exacto(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise WebSocketError("conexión cerrada por el servidor mientras se leía un frame")
        buf.extend(chunk)
    return bytes(buf)


def _handshake(sock: socket.socket, host: str, port: int, path: str, origin: str) -> None:
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    peticion = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"Origin: {origin}\r\n"
        f"\r\n"
    ).encode("ascii")
    sock.sendall(peticion)

    # Leer la respuesta HTTP línea por línea hasta \r\n\r\n (headers caben en pocos KB).
    resp = bytearray()
    while b"\r\n\r\n" not in resp:
        chunk = sock.recv(4096)
        if not chunk:
            raise WebSocketError("conexión cerrada durante el handshake")
        resp.extend(chunk)
        if len(resp) > 65536:
            raise WebSocketError("respuesta de handshake excede el tamaño razonable")

    cabecera = resp.split(b"\r\n\r\n", 1)[0].decode("iso-8859-1", errors="replace")
    lineas = cabecera.split("\r\n")
    if not lineas or " 101 " not in lineas[0]:
        raise WebSocketError(f"handshake rechazado: {lineas[0] if lineas else '(sin respuesta)'}")

    esperado = base64.b64encode(hashlib.sha1((key + _GUID.decode()).encode()).digest()).decode()
    accept_recibido = None
    for linea in lineas[1:]:
        if ":" not in linea:
            continue
        nombre, _, valor = linea.partition(":")
        if nombre.strip().lower() == "sec-websocket-accept":
            accept_recibido = valor.strip()
    if accept_recibido != esperado:
        raise WebSocketError("Sec-WebSocket-Accept no coincide (handshake inválido)")


def _codificar_frame(opcode: int, payload: bytes) -> bytes:
    """Codifica un frame saliente (cliente→servidor: SIEMPRE enmascarado, RFC 6455 §5.3)."""
    fin_y_opcode = 0x80 | opcode  # FIN=1, un solo frame (sin fragmentación)
    longitud = len(payload)
    if longitud < 126:
        cabecera = struct.pack("!BB", fin_y_opcode, 0x80 | longitud)
    elif longitud < 65536:
        cabecera = struct.pack("!BBH", fin_y_opcode, 0x80 | 126, longitud)
    else:
        cabecera = struct.pack("!BBQ", fin_y_opcode, 0x80 | 127, longitud)
    mascara = os.urandom(4)
    payload_enmascarado = bytes(b ^ mascara[i % 4] for i, b in enumerate(payload))
    return cabecera + mascara + payload_enmascarado


def _leer_frame(sock: socket.socket) -> tuple[int, bytes]:
    """Lee un frame entrante (servidor→cliente: nunca enmascarado). No maneja fragmentación
    (los mensajes de este protocolo son pequeños: JSON de control o el binario del render)."""
    primeros_dos = _leer_exacto(sock, 2)
    b0, b1 = primeros_dos[0], primeros_dos[1]
    opcode = b0 & 0x0F
    longitud = b1 & 0x7F
    if longitud == 126:
        longitud = struct.unpack("!H", _leer_exacto(sock, 2))[0]
    elif longitud == 127:
        longitud = struct.unpack("!Q", _leer_exacto(sock, 8))[0]
    # b1 & 0x80 indicaría máscara -- servidores no enmascaran (RFC 6455 §5.1), se ignora si viene.
    payload = _leer_exacto(sock, longitud) if longitud else b""
    return opcode, payload


@dataclass
class WebSocketClient:
    """Cliente WS de un solo hilo de lectura en background. `on_message`/`on_close` se llaman
    desde ese hilo -- el llamador debe ser thread-safe si actualiza estado compartido."""

    host: str
    port: int
    path: str = "/"
    origin: str | None = None
    on_message: Callable[[bytes, bool], None] | None = None  # (payload, es_binario)
    on_close: Callable[[], None] | None = None

    _sock: socket.socket | None = field(default=None, init=False, repr=False)
    _hilo: threading.Thread | None = field(default=None, init=False, repr=False)
    _lock_envio: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _cerrado: bool = field(default=False, init=False, repr=False)

    def conectar(self, timeout: float = 5.0) -> None:
        sock = socket.create_connection((self.host, self.port), timeout=timeout)
        sock.settimeout(None)  # una vez conectado, el hilo de lectura bloquea indefinidamente
        origin = self.origin or f"http://{self.host}:{self.port}"
        _handshake(sock, self.host, self.port, self.path, origin)
        self._sock = sock
        self._cerrado = False
        self._hilo = threading.Thread(target=self._bucle_lectura, daemon=True)
        self._hilo.start()

    def _bucle_lectura(self) -> None:
        try:
            while not self._cerrado:
                opcode, payload = _leer_frame(self._sock)
                if opcode == _OP_TEXT:
                    if self.on_message:
                        self.on_message(payload, False)
                elif opcode == _OP_BINARY:
                    if self.on_message:
                        self.on_message(payload, True)
                elif opcode == _OP_PING:
                    self._enviar_frame(_OP_PONG, payload)
                elif opcode == _OP_CLOSE:
                    break
                # PONG y otros opcodes de control se ignoran silenciosamente.
        except (WebSocketError, OSError):
            pass
        finally:
            self._cerrado = True
            if self.on_close:
                self.on_close()

    def _enviar_frame(self, opcode: int, payload: bytes) -> None:
        if self._sock is None or self._cerrado:
            raise WebSocketError("intento de enviar sobre un socket cerrado o no conectado")
        with self._lock_envio:
            self._sock.sendall(_codificar_frame(opcode, payload))

    def enviar_texto(self, texto: str) -> None:
        self._enviar_frame(_OP_TEXT, texto.encode("utf-8"))

    def enviar_datos(self, payload: bytes, es_binario: bool) -> None:
        """Reenvía bytes crudos preservando el opcode (texto/binario) -- para relays "tontos"
        que no interpretan el contenido, a diferencia de enviar_texto() (ver el proxy del data
        plane de tinymist preview en doctyp_web.py)."""
        self._enviar_frame(_OP_BINARY if es_binario else _OP_TEXT, payload)

    def cerrar(self) -> None:
        if self._cerrado or self._sock is None:
            return
        self._cerrado = True
        try:
            self._enviar_frame(_OP_CLOSE, b"")
        except (WebSocketError, OSError):
            pass
        try:
            self._sock.close()
        except OSError:
            pass

    @property
    def conectado(self) -> bool:
        return not self._cerrado and self._sock is not None
