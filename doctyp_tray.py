#!/usr/bin/env python3
"""
doctyp_tray — icono de bandeja del sistema para doctyp_sync_daemon.py (Fedora/KDE Plasma,
pedido explícito del usuario 2026-07-21, extendido 2026-07-22 con cambio de usuario/cerrar
sesión). El daemon posee el icono directamente (mismo proceso, sin IPC): este módulo solo
encapsula lo específico de Qt para no acoplar doctyp_sync.py/doctyp_sync_daemon.py a PySide6.

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
    from PySide6.QtWidgets import (
        QApplication, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMenu,
        QSystemTrayIcon, QVBoxLayout,
    )
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


def motivo_no_disponible() -> str:
    """Explicación legible de por qué disponible() dio False -- string vacío si sí está
    disponible. Solo para logging (doctyp_sync_daemon._loop_con_bandeja): sin esto, la caída al
    modo headless era silenciosa -- ni error ni aviso, el usuario no tenía forma de saber si el
    icono simplemente no aplicaba en su sistema o si algo estaba roto."""
    if not _PYSIDE_DISPONIBLE:
        return ("PySide6 no está instalado -- instálalo con "
                "'python3 -m pip install --user PySide6-Essentials' (o vuelve a correr 'init')")
    if not sesion_grafica_disponible():
        return "sin sesión gráfica (ni DISPLAY ni WAYLAND_DISPLAY están seteados en el entorno)"
    return ""


def _tamano_legible(bytes_: int) -> str:
    valor = float(bytes_)
    for unidad in ("B", "KB", "MB", "GB"):
        if valor < 1024 or unidad == "GB":
            return f"{valor:.0f} {unidad}" if unidad == "B" else f"{valor:.1f} {unidad}"
        valor /= 1024
    return f"{valor:.1f} GB"


def _resumen_evento(evento: dict | None) -> str:
    """Una línea con lo esencial de un evento de sync (ver doctyp_sync._notificar: tipo, slug,
    nombre, accion, archivo, tamano, cuando) -- compartida entre el tooltip y el ítem de menú,
    para no mantener el mismo formato en dos lugares."""
    if evento is None:
        return "sin sincronizaciones todavía"
    accion = "subido" if evento["accion"] == "subida" else "bajado"
    return (f"{evento['tipo']} {evento['nombre']} ({accion}, {_tamano_legible(evento['tamano'])}) "
            f"— {evento['cuando'].strftime('%d-%m-%Y %H:%M:%S')}")


if _PYSIDE_DISPONIBLE:

    def _icono_generado() -> QIcon:
        """Glifo simple dibujado en runtime -- sin asset binario nuevo en el repo. Un cuadrado
        redondeado azul con una 'D' blanca, reconocible a tamaño de bandeja (16-24px reales,
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
        pintor.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "D")
        pintor.end()
        return QIcon(pixmap)

    class _DialogoLogin(QDialog):
        """Formulario de login (correo + contraseña) usado tanto por 'Otro usuario…' (correo
        vacío) como por un clic sobre un correo ya conocido (correo prellenado) -- en AMBOS
        casos se vuelve a pedir la contraseña, nunca hay un cambio de cuenta sin ella (decisión
        explícita del usuario). `on_login(email, password) -> (ok, detalle)` hace el trabajo de
        red/sesión (vive en doctyp_sync_daemon.py); acá solo se maneja la UI y el bloqueo
        mientras esa llamada está en curso."""

        def __init__(self, on_login: Callable[[str, str], tuple[bool, str | None]],
                     correo_prellenado: str | None = None, parent=None):
            super().__init__(parent)
            self.setWindowTitle("doctyp — Iniciar sesión")
            self._on_login = on_login

            self._campo_correo = QLineEdit(correo_prellenado or "")
            self._campo_password = QLineEdit()
            self._campo_password.setEchoMode(QLineEdit.EchoMode.Password)

            form = QFormLayout()
            form.addRow("Correo:", self._campo_correo)
            form.addRow("Contraseña:", self._campo_password)

            self._etiqueta_error = QLabel("")
            self._etiqueta_error.setStyleSheet("color: #c0392b;")
            self._etiqueta_error.setWordWrap(True)
            self._etiqueta_error.setVisible(False)

            botones = QDialogButtonBox()
            self._boton_entrar = botones.addButton("Entrar", QDialogButtonBox.ButtonRole.AcceptRole)
            botones.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
            botones.accepted.connect(self._intentar_login)
            botones.rejected.connect(self.reject)

            layout = QVBoxLayout(self)
            layout.addLayout(form)
            layout.addWidget(self._etiqueta_error)
            layout.addWidget(botones)

            if correo_prellenado:
                self._campo_password.setFocus()
            else:
                self._campo_correo.setFocus()

        def _intentar_login(self) -> None:
            email = self._campo_correo.text().strip()
            password = self._campo_password.text()
            if not email or not password:
                self._mostrar_error("El correo y la contraseña son obligatorios.")
                return
            self._boton_entrar.setEnabled(False)
            self.setCursor(Qt.CursorShape.WaitCursor)
            try:
                ok, detalle = self._on_login(email, password)
            finally:
                self._boton_entrar.setEnabled(True)
                self.unsetCursor()
            if ok:
                self.accept()
            else:
                self._mostrar_error(detalle or "No se pudo iniciar sesión.")

        def _mostrar_error(self, texto: str) -> None:
            self._etiqueta_error.setText(texto)
            self._etiqueta_error.setVisible(True)

    class DoctypTrayIcon(QSystemTrayIcon):
        """Estado en memoria (sesión, último evento de sync, último resultado de tick) que se
        vuelca a texto plano en el tooltip y en el menú cada vez que cambia -- no hay nada que
        leer del exterior, el proceso que lo actualiza es el mismo que lo muestra."""

        def __init__(self,
                     on_sincronizar_ahora: Callable[[], None] | None = None,
                     on_login: Callable[[str, str], tuple[bool, str | None]] | None = None,
                     on_listar_usuarios: Callable[[], list[str]] | None = None,
                     on_cerrar_sesion: Callable[[], None] | None = None,
                     parent=None):
            super().__init__(_icono_generado(), parent)
            self._usuario: str | None = None
            self._ultimo_evento: dict | None = None
            self._ultimo_tick: tuple[bool, str | None, datetime.datetime] | None = None
            self._on_sincronizar_ahora = on_sincronizar_ahora
            self._on_login = on_login
            self._on_listar_usuarios = on_listar_usuarios
            self._on_cerrar_sesion = on_cerrar_sesion

            menu = QMenu()
            self._accion_usuario = QAction("Usuario: sin sesión", menu)
            self._accion_usuario.setEnabled(False)
            menu.addAction(self._accion_usuario)
            self._accion_estado_sync = QAction("Última sync: sin sincronizaciones todavía", menu)
            self._accion_estado_sync.setEnabled(False)
            menu.addAction(self._accion_estado_sync)
            menu.addSeparator()

            accion_sync = QAction("Sincronizar ahora", menu)
            accion_sync.triggered.connect(self._disparar_sync_manual)
            menu.addAction(accion_sync)

            self._menu_usuarios = QMenu("Cambiar de usuario", menu)
            self._menu_usuarios.aboutToShow.connect(self._reconstruir_menu_usuarios)
            menu.addMenu(self._menu_usuarios)
            menu.addSeparator()

            accion_cerrar = QAction("Cerrar sesión", menu)
            accion_cerrar.triggered.connect(self._disparar_cerrar_sesion)
            menu.addAction(accion_cerrar)
            self.setContextMenu(menu)

            self._actualizar_estado_ui()

        def _disparar_sync_manual(self) -> None:
            if self._on_sincronizar_ahora is not None:
                self._on_sincronizar_ahora()

        def _disparar_cerrar_sesion(self) -> None:
            if self._on_cerrar_sesion is not None:
                self._on_cerrar_sesion()
            else:
                self._salir()  # sin callback (ej. uso standalone) -- al menos no queda colgado

        def _salir(self) -> None:
            app = QApplication.instance()
            if app is not None:
                app.quit()

        def _reconstruir_menu_usuarios(self) -> None:
            """Se llama justo antes de mostrar el submenú (aboutToShow) -- siempre con la lista
            de correos conocidos al día, sin tener que refrescarlo manualmente cada vez que se
            loguea alguien nuevo."""
            self._menu_usuarios.clear()
            accion_otro = QAction("Otro usuario…", self._menu_usuarios)
            accion_otro.triggered.connect(lambda: self._abrir_dialogo_login(None))
            self._menu_usuarios.addAction(accion_otro)

            correos = [c for c in (self._on_listar_usuarios() if self._on_listar_usuarios else [])
                       if c != self._usuario]
            if correos:
                self._menu_usuarios.addSeparator()
                for correo in correos:
                    accion = QAction(correo, self._menu_usuarios)
                    accion.triggered.connect(lambda checked=False, c=correo: self._abrir_dialogo_login(c))
                    self._menu_usuarios.addAction(accion)

        def _abrir_dialogo_login(self, correo_prellenado: str | None) -> None:
            if self._on_login is None:
                return
            dialogo = _DialogoLogin(self._on_login, correo_prellenado, parent=None)
            dialogo.exec()

        def actualizar_sesion(self, email: str | None) -> None:
            self._usuario = email
            self._actualizar_estado_ui()

        def actualizar_evento_sync(self, evento: dict) -> None:
            """`evento` viene tal cual de doctyp_sync._notificar: tipo, slug, nombre, accion,
            archivo, tamano, cuando."""
            self._ultimo_evento = evento
            self._actualizar_estado_ui()

        def actualizar_estado_tick(self, ok: bool, detalle: str | None = None) -> None:
            self._ultimo_tick = (ok, detalle, datetime.datetime.now())
            self._actualizar_estado_ui()

        def _actualizar_estado_ui(self) -> None:
            usuario_texto = self._usuario or "sin sesión"
            resumen_sync = _resumen_evento(self._ultimo_evento)

            self._accion_usuario.setText(f"Usuario: {usuario_texto}")
            self._accion_estado_sync.setText(f"Última sync: {resumen_sync}")

            lineas = ["doctyp — sincronización en segundo plano", "",
                      f"Usuario: {usuario_texto}", "", f"Último sincronizado: {resumen_sync}"]
            if self._ultimo_tick is not None:
                ok, detalle, cuando = self._ultimo_tick
                estado = "OK" if ok else f"error ({detalle})"
                lineas.append("")
                lineas.append(f"Último intento: {estado} — {cuando.strftime('%H:%M:%S')}")
            self.setToolTip("\n".join(lineas))


def iniciar(on_sincronizar_ahora: Callable[[], None] | None = None,
            on_login: Callable[[str, str], tuple[bool, str | None]] | None = None,
            on_listar_usuarios: Callable[[], list[str]] | None = None,
            on_cerrar_sesion: Callable[[], None] | None = None):
    """Intenta levantar QApplication + el icono. Devuelve (app, icono) si el escritorio
    soporta bandeja de sistema, o (None, None) si no (ej. algunos GNOME sin la extensión
    AppIndicator/KStatusNotifierItem) -- el llamador cae al loop headless en ese caso, sin
    tratarlo como error."""
    if not disponible():
        return None, None
    app = QApplication.instance() or QApplication([])
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None, None
    icono = DoctypTrayIcon(on_sincronizar_ahora=on_sincronizar_ahora, on_login=on_login,
                            on_listar_usuarios=on_listar_usuarios,
                            on_cerrar_sesion=on_cerrar_sesion)
    icono.show()
    return app, icono
