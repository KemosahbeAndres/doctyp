#!/usr/bin/env python3
"""
doctyp_tray — icono de bandeja del sistema para doctyp_sync_daemon.py (Fedora/KDE Plasma,
pedido explícito del usuario 2026-07-21). El daemon posee el icono directamente (mismo
proceso, sin IPC): este módulo solo encapsula lo específico de Qt para no acoplar
doctyp_sync.py/doctyp_sync_daemon.py a PySide6.

Es la ÚNICA dependencia Python fuera de stdlib del proyecto (todo lo demás -- doctyp_sync.py,
doctyp_ws_client.py, etc. -- es deliberadamente stdlib puro). Por eso todo acá está detrás de
un guard de disponibilidad de tres capas (import, sesión gráfica, soporte real del escritorio)
que el llamador debe consultar ANTES de intentar nada gráfico -- si algo falta, el daemon cae
al loop headless de siempre, sin icono pero sincronizando igual.
"""
from __future__ import annotations
import datetime
import os
from typing import Callable

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
    _PYSIDE_DISPONIBLE = True
except ImportError:
    _PYSIDE_DISPONIBLE = False


def pyside_disponible() -> bool:
    return _PYSIDE_DISPONIBLE


def sesion_grafica_disponible() -> bool:
    """DISPLAY (X11) o WAYLAND_DISPLAY -- ninguno de los dos seteado casi siempre significa que
    no hay compositor al que conectarse (ej. systemd --user arrancado antes de la sesión
    gráfica, o sin heredar el entorno de sesión). Evita que Qt aborte el proceso al intentar
    crear QApplication sin display."""
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def disponible() -> bool:
    """Chequeo barato (sin crear ningún objeto Qt) -- lo que consulta el daemon antes de
    decidir si intenta la rama gráfica."""
    return _PYSIDE_DISPONIBLE and sesion_grafica_disponible()


def _tamano_legible(bytes_: int) -> str:
    valor = float(bytes_)
    for unidad in ("B", "KB", "MB", "GB"):
        if valor < 1024 or unidad == "GB":
            return f"{valor:.0f} {unidad}" if unidad == "B" else f"{valor:.1f} {unidad}"
        valor /= 1024
    return f"{valor:.1f} GB"


if _PYSIDE_DISPONIBLE:

    def _icono_generado() -> QIcon:
        """Glifo simple dibujado en runtime -- sin asset binario nuevo en el repo. Un cuadrado
        redondeado azul con una 'd' blanca, reconocible a tamaño de bandeja (16-24px reales,
        se dibuja a 64px y Qt lo reescala)."""
        tam = 64
        pixmap = QPixmap(tam, tam)
        pixmap.fill(Qt.GlobalColor.transparent)
        pintor = QPainter(pixmap)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        pintor.setBrush(QColor("#2a5fa5"))
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.drawRoundedRect(4, 4, tam - 8, tam - 8, 14, 14)
        fuente = pintor.font()
        fuente.setBold(True)
        fuente.setPixelSize(38)
        pintor.setFont(fuente)
        pintor.setPen(QColor("white"))
        pintor.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "d")
        pintor.end()
        return QIcon(pixmap)

    class DoctypTrayIcon(QSystemTrayIcon):
        """Estado en memoria (sesión, último evento de sync, último resultado de tick) que se
        vuelca a texto plano en el tooltip cada vez que cambia -- no hay nada que leer del
        exterior, el proceso que lo actualiza es el mismo que lo muestra."""

        def __init__(self, on_sincronizar_ahora: Callable[[], None] | None = None, parent=None):
            super().__init__(_icono_generado(), parent)
            self._usuario: str | None = None
            self._ultimo_evento: dict | None = None
            self._ultimo_tick: tuple[bool, str | None, datetime.datetime] | None = None
            self._on_sincronizar_ahora = on_sincronizar_ahora

            menu = QMenu()
            accion_sync = QAction("Sincronizar ahora", menu)
            accion_sync.triggered.connect(self._disparar_sync_manual)
            menu.addAction(accion_sync)
            menu.addSeparator()
            accion_salir = QAction("Salir", menu)
            accion_salir.triggered.connect(self._salir)
            menu.addAction(accion_salir)
            self.setContextMenu(menu)

            self._actualizar_tooltip()

        def _disparar_sync_manual(self) -> None:
            if self._on_sincronizar_ahora is not None:
                self._on_sincronizar_ahora()

        def _salir(self) -> None:
            app = QApplication.instance()
            if app is not None:
                app.quit()

        def actualizar_sesion(self, email: str | None) -> None:
            self._usuario = email
            self._actualizar_tooltip()

        def actualizar_evento_sync(self, evento: dict) -> None:
            """`evento` viene tal cual de doctyp_sync._notificar: tipo, slug, nombre, accion,
            archivo, tamano, cuando."""
            self._ultimo_evento = evento
            self._actualizar_tooltip()

        def actualizar_estado_tick(self, ok: bool, detalle: str | None = None) -> None:
            self._ultimo_tick = (ok, detalle, datetime.datetime.now())
            self._actualizar_tooltip()

        def _actualizar_tooltip(self) -> None:
            lineas = ["doctyp — sincronización en segundo plano", ""]
            lineas.append(f"Usuario: {self._usuario or 'sin sesión'}")

            lineas.append("")
            if self._ultimo_evento is not None:
                e = self._ultimo_evento
                accion = "subido" if e["accion"] == "subida" else "bajado"
                lineas.append(f"Último sincronizado ({accion}):")
                lineas.append(f"  {e['tipo']}: {e['nombre']}")
                lineas.append(f"  {e['archivo']} — {_tamano_legible(e['tamano'])}")
                lineas.append(f"  {e['cuando'].strftime('%d-%m-%Y %H:%M:%S')}")
            else:
                lineas.append("Sin sincronizaciones todavía.")

            if self._ultimo_tick is not None:
                ok, detalle, cuando = self._ultimo_tick
                estado = "OK" if ok else f"error ({detalle})"
                lineas.append("")
                lineas.append(f"Último intento: {estado} — {cuando.strftime('%H:%M:%S')}")

            self.setToolTip("\n".join(lineas))


def iniciar(on_sincronizar_ahora: Callable[[], None] | None = None):
    """Intenta levantar QApplication + el icono. Devuelve (app, icono) si el escritorio
    soporta bandeja de sistema, o (None, None) si no (ej. algunos GNOME sin la extensión
    AppIndicator/KStatusNotifierItem) -- el llamador cae al loop headless en ese caso, sin
    tratarlo como error."""
    if not disponible():
        return None, None
    app = QApplication.instance() or QApplication([])
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None, None
    icono = DoctypTrayIcon(on_sincronizar_ahora=on_sincronizar_ahora)
    icono.show()
    return app, icono
