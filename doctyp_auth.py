#!/usr/bin/env python3
"""
doctyp_auth — Login básico (Etapa 20 de PLAN-V4.md): usuarios = autores (ver doctyp_db.py),
hash de password con scrypt (stdlib, hashlib), sesiones por cookie httpOnly.

Bootstrap (PLAN-V4.md §4, decidido con el usuario 2026-07-17):
  1. Sin usuarios en la BD -> la SPA muestra un formulario de alta del primer usuario
     (admin) en vez del login. `bootstrap_estado()` distingue este caso.
  2. Un solo usuario y sin password (típico tras `doctyp migrate`: el autor migrado no
     tenía credenciales, modo mono-usuario) -> el login lo detecta por email y permite
     fijar la password directo, sin token de invitación (no hay nadie más a quien pedírsela).

No requiere paquetes externos (hashlib.scrypt es stdlib desde Python 3.6 con OpenSSL 1.1+).
"""
from __future__ import annotations
import datetime, hashlib, hmac, os, secrets

import doctyp_db as db

SESSION_COOKIE = "doctyp_session"
SESSION_TTL_HORAS = 24 * 14  # 14 días

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1
_SCRYPT_SALT_LEN = 16
_SCRYPT_DKLEN = 32


class AuthError(Exception):
    def __init__(self, status: int, mensaje: str):
        self.status = status
        self.mensaje = mensaje


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SCRYPT_SALT_LEN)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N,
                              r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${derived.hex()}"


def verificar_password(password: str, hash_almacenado: str) -> bool:
    try:
        algo, n, r, p, salt_hex, derived_hex = hash_almacenado.split("$")
        if algo != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        esperado = bytes.fromhex(derived_hex)
    except (ValueError, AttributeError):
        return False
    real = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p),
                           dklen=len(esperado))
    return hmac.compare_digest(real, esperado)


def _hash_token(token: str) -> str:
    # Las sesiones no necesitan derivar una clave lenta (scrypt) -- son secretos aleatorios
    # de alta entropía generados por el servidor, no passwords elegidas por humanos. SHA-256
    # basta para no guardar el token en claro en la BD.
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def bootstrap_estado() -> dict:
    """Estado de arranque para que la SPA decida qué pantalla mostrar (PLAN-V4.md §4):
    - sin_usuarios: True -> formulario de alta del primer usuario (admin).
    - usuario_unico_sin_password: {id, email, nombre} -> login debe ofrecer "crear tu
      contraseña" para ese usuario sin pedir la password todavía.
    """
    usuarios = db.listar_usuarios()
    if not usuarios:
        return {"sin_usuarios": True, "usuario_unico_sin_password": None}
    if len(usuarios) == 1 and not usuarios[0].get("password_hash"):
        u = usuarios[0]
        return {
            "sin_usuarios": False,
            "usuario_unico_sin_password": {"id": u["id"], "email": u["email"], "nombre": u["nombre"]},
        }
    return {"sin_usuarios": False, "usuario_unico_sin_password": None}


def crear_primer_usuario(email: str, nombre: str, password: str) -> dict:
    """Alta del primer usuario del sistema (caso 1 del bootstrap). Falla si ya hay alguno --
    evita que este endpoint se use para colarse como admin en una instalación ya poblada."""
    email = (email or "").strip().lower()
    nombre = (nombre or "").strip()
    if not email or "@" not in email:
        raise AuthError(400, "email inválido")
    if not nombre:
        raise AuthError(400, "el nombre es obligatorio")
    if not password or len(password) < 8:
        raise AuthError(400, "la contraseña debe tener al menos 8 caracteres")
    if db.contar_usuarios() > 0:
        raise AuthError(409, "ya existe al menos un usuario; usa el login normal")
    return db.crear_usuario(email, nombre, hash_password(password))


def fijar_password_primer_login(user_id: str, password: str) -> None:
    """Caso 2 del bootstrap: el único usuario del sistema fija su password en su primer
    login, sin token de invitación (PLAN-V4.md §4 -- no hay otro usuario que se la envíe)."""
    if not password or len(password) < 8:
        raise AuthError(400, "la contraseña debe tener al menos 8 caracteres")
    usuarios = db.listar_usuarios()
    if len(usuarios) != 1 or usuarios[0]["id"] != user_id or usuarios[0].get("password_hash"):
        raise AuthError(409, "esta vía solo aplica cuando hay un único usuario sin contraseña")
    db.fijar_password(user_id, hash_password(password))


# ── Rate limit simple en memoria (por IP) ──────────────────────────────────────────────────
_intentos: dict[str, list[float]] = {}
_RATE_LIMIT_VENTANA_S = 60
_RATE_LIMIT_MAX = 8


def _rate_limit_ok(ip: str) -> bool:
    import time
    ahora = time.time()
    ventana = _intentos.setdefault(ip, [])
    ventana[:] = [t for t in ventana if ahora - t < _RATE_LIMIT_VENTANA_S]
    if len(ventana) >= _RATE_LIMIT_MAX:
        return False
    ventana.append(ahora)
    return True


def login(email: str, password: str, ip: str, user_agent: str) -> tuple[dict, str]:
    if not _rate_limit_ok(ip):
        raise AuthError(429, "demasiados intentos; espera un momento")
    email = (email or "").strip().lower()
    usuario = db.obtener_usuario_por_email(email)
    if usuario is None or not usuario.get("password_hash"):
        raise AuthError(401, "email o contraseña incorrectos")
    if not verificar_password(password, usuario["password_hash"]):
        raise AuthError(401, "email o contraseña incorrectos")
    if not usuario.get("activo", 1):
        raise AuthError(403, "usuario inactivo")

    token = secrets.token_urlsafe(32)
    expira = (datetime.datetime.now() + datetime.timedelta(hours=SESSION_TTL_HORAS)).isoformat(timespec="seconds")
    db.crear_sesion(usuario["id"], _hash_token(token), expira, ip=ip, user_agent=user_agent)
    return usuario, token


def logout(token: str) -> None:
    if token:
        db.eliminar_sesion(_hash_token(token))


def usuario_de_sesion(token: str | None) -> dict | None:
    if not token:
        return None
    sesion = db.obtener_sesion_por_token_hash(_hash_token(token))
    if sesion is None:
        return None
    if sesion["expires_at"] < datetime.datetime.now().isoformat(timespec="seconds"):
        db.eliminar_sesion(_hash_token(token))
        return None
    return db.obtener_usuario(sesion["user_id"])


def usuario_publico(usuario: dict) -> dict:
    """Vista del usuario segura para exponer a la SPA (nunca password_hash)."""
    return {"id": usuario["id"], "email": usuario["email"], "nombre": usuario["nombre"],
            "cargo": usuario.get("cargo") or "", "correo": usuario.get("correo") or ""}
