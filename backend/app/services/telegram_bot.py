"""Bot de Telegram para reportes de viaje y gastos de árbitros."""

from __future__ import annotations

import os
import re
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation

import requests
from sqlalchemy import or_

from ..database import db
from ..models import (
    Arbitro,
    AsignacionPartido,
    GastoExtra,
    Pago,
    Partido,
    TelegramVinculacion,
)
from .auditoria import registrar_cambio


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
MENU = [["🚗 En camino", "⏰ Reportar retraso"], ["🏟 Llegué a instalación", "💸 Reportar gasto"], ["📅 Mis asignaciones", "❓ Ayuda"]]


def _post(metodo: str, payload: dict, timeout: int = 25) -> dict:
    respuesta = requests.post(f"{BASE_URL}/{metodo}", json=payload, timeout=timeout)
    respuesta.raise_for_status()
    datos = respuesta.json()
    if not datos.get("ok"):
        raise RuntimeError(f"Telegram rechazó {metodo}: {datos.get('description', 'error desconocido')}")
    return datos.get("result", {})


def _mensaje(chat_id, texto: str, **opciones):
    return _post("sendMessage", {"chat_id": chat_id, "text": texto, **opciones})


def _teclado_menu() -> dict:
    return {"keyboard": MENU, "resize_keyboard": True, "is_persistent": True}


def _telefono(valor) -> str:
    digitos = re.sub(r"\D", "", str(valor or ""))
    return digitos[-10:] if len(digitos) >= 10 else digitos


def _admins() -> set[str]:
    return {valor.strip() for valor in os.getenv("TELEGRAM_ADMIN_IDS", "").split(",") if valor.strip()}


def _vinculacion(user_id) -> TelegramVinculacion | None:
    return TelegramVinculacion.query.filter_by(telegram_user_id=str(user_id)).first()


def _vincular_contacto(message: dict) -> None:
    user = message.get("from", {})
    contact = message.get("contact", {})
    chat_id = message["chat"]["id"]
    if str(contact.get("user_id")) != str(user.get("id")):
        _mensaje(chat_id, "Por seguridad, comparte tu propio contacto usando el botón de Telegram.")
        return
    telefono = _telefono(contact.get("phone_number"))
    arbitros = [
        arbitro for arbitro in Arbitro.query.filter_by(activo=True).all()
        if _telefono(arbitro.telefono) == telefono and telefono
    ]
    if not arbitros:
        _mensaje(chat_id, "No encontré un árbitro activo con ese teléfono. Contacta al administrador para actualizar tu ficha.")
        return
    if len(arbitros) > 1:
        _mensaje(chat_id, "Ese teléfono aparece más de una vez en el catálogo. El administrador debe corregirlo antes de vincular la cuenta.")
        return
    arbitro = arbitros[0]
    existente_user = TelegramVinculacion.query.filter_by(telegram_user_id=str(user["id"])).first()
    existente_arbitro = TelegramVinculacion.query.filter_by(arbitro_id=arbitro.id).first()
    if existente_user and existente_user.arbitro_id != arbitro.id:
        _mensaje(chat_id, "Esta cuenta ya está vinculada a otro árbitro. Contacta al administrador.")
        return
    if existente_arbitro and existente_arbitro.telegram_user_id != str(user["id"]):
        _mensaje(chat_id, "Este árbitro ya tiene una cuenta de Telegram vinculada. Contacta al administrador.")
        return
    vinculacion = existente_user or existente_arbitro or TelegramVinculacion(
        arbitro_id=arbitro.id,
        telegram_user_id=str(user["id"]),
        chat_id=str(chat_id),
    )
    vinculacion.arbitro_id = arbitro.id
    vinculacion.telegram_user_id = str(user["id"])
    vinculacion.chat_id = str(chat_id)
    db.session.add(vinculacion)
    db.session.commit()
    _mensaje(chat_id, f"¡Listo, {arbitro.nombre}! Tu cuenta quedó vinculada. Usa el menú para reportar tu viaje.", reply_markup=_teclado_menu())


def _asignaciones(arbitro_id: int) -> list[AsignacionPartido]:
    ahora = datetime.utcnow()
    return (
        AsignacionPartido.query.join(Partido)
        .filter(
            AsignacionPartido.arbitro_id == arbitro_id,
            AsignacionPartido.estado_viaje != "Finalizado",
            or_(Partido.fecha_hora >= ahora, AsignacionPartido.estado_viaje.in_(("En camino", "Retraso", "En estadio"))),
        )
        .order_by(Partido.fecha_hora.asc(), AsignacionPartido.id.asc())
        .limit(10)
        .all()
    )


def _selector_asignaciones(chat_id, arbitro_id: int, accion: str) -> None:
    asignaciones = _asignaciones(arbitro_id)
    if not asignaciones:
        _mensaje(chat_id, "No tienes asignaciones pendientes o próximas registradas.", reply_markup=_teclado_menu())
        return
    botones = []
    for asignacion in asignaciones:
        partido = asignacion.partido
        fecha = partido.fecha_hora.strftime("%d/%m %H:%M")
        etiqueta = f"{fecha} · {partido.estadio_cancha} · {partido.ciudad_juego.nombre}"
        botones.append([{"text": etiqueta[:60], "callback_data": f"sel:{accion}:{asignacion.id}"}])
    _mensaje(chat_id, "Selecciona el partido al que corresponde el reporte:", reply_markup={"inline_keyboard": botones})


def _actualizar_estado(asignacion: AsignacionPartido, estado: str, detalles: dict | None = None, commit: bool = True) -> None:
    antes = {"estado_viaje": asignacion.estado_viaje}
    asignacion.estado_viaje = estado
    ahora = datetime.utcnow()
    if estado == "En camino":
        antes["fecha_salida"] = asignacion.fecha_salida.isoformat() if asignacion.fecha_salida else None
        asignacion.fecha_salida = ahora
    elif estado == "En estadio":
        antes["fecha_llegada_estadio"] = asignacion.fecha_llegada_estadio.isoformat() if asignacion.fecha_llegada_estadio else None
        asignacion.fecha_llegada_estadio = ahora
    despues = {"estado_viaje": estado, **(detalles or {})}
    if estado == "En camino":
        despues["fecha_salida"] = ahora.isoformat()
    elif estado == "En estadio":
        despues["fecha_llegada_estadio"] = ahora.isoformat()
    registrar_cambio(
        "asignacion", asignacion.id, "REPORTE_TELEGRAM",
        antes=antes, despues=despues, origen="telegram", commit=False,
    )
    if commit:
        db.session.commit()


def _reporte_gasto(vinculo: TelegramVinculacion, mensaje: dict, asignacion: AsignacionPartido) -> bool:
    contenido = mensaje.get("text") or mensaje.get("caption") or ""
    partes = [parte.strip() for parte in contenido.split("|", 2)]
    if len(partes) < 2:
        _mensaje(vinculo.chat_id, "Formato: monto | concepto | detalle (ejemplo: 12,50 | taxi | traslado adicional).")
        return False
    try:
        monto = Decimal(partes[0].replace("$", "").replace(" ", "").replace(",", "."))
    except InvalidOperation:
        _mensaje(vinculo.chat_id, "No reconocí el monto. Envíalo así: 12,50 | taxi | traslado adicional.")
        return False
    if not monto.is_finite() or monto <= 0 or monto > Decimal("1000000"):
        _mensaje(vinculo.chat_id, "El monto debe ser mayor que cero y menor o igual a 1.000.000 USD.")
        return False
    fotos = mensaje.get("photo") or []
    recibo_id = fotos[-1].get("file_id") if fotos else None
    gasto = GastoExtra(
        asignacion_id=asignacion.id,
        arbitro_id=vinculo.arbitro_id,
        monto=monto,
        concepto=partes[1][:80],
        descripcion=partes[2][:500] if len(partes) > 2 else None,
        telegram_file_id=recibo_id,
    )
    db.session.add(gasto)
    db.session.flush()
    registrar_cambio(
        "gasto_extra", gasto.id, "REPORTAR",
        despues={"asignacion_id": asignacion.id, "monto": str(monto), "moneda": "USD", "concepto": gasto.concepto, "estado": "Pendiente"},
        origen="telegram", commit=False,
    )
    vinculo.accion_pendiente = None
    vinculo.asignacion_pendiente_id = None
    db.session.commit()
    _mensaje(vinculo.chat_id, f"Gasto #{gasto.id} guardado por ${monto:.2f} USD y enviado a revisión. No se sumará al total hasta ser aprobado.", reply_markup=_teclado_menu())
    _avisar_admins(gasto)
    return True


def _avisar_admins(gasto: GastoExtra) -> None:
    partido = gasto.asignacion.partido
    arbitro = gasto.arbitro
    texto = (
        f"Gasto extra pendiente #{gasto.id}\n"
        f"Árbitro: {arbitro.nombre} {arbitro.apellido}\n"
        f"Partido: {partido.fecha_hora:%d/%m/%Y %H:%M} · {partido.estadio_cancha}\n"
        f"Monto: ${gasto.monto:.2f} USD · {gasto.concepto}\n"
        f"Detalle: {gasto.descripcion or '—'}\n"
        f"Comprobante adjunto: {'sí' if gasto.telegram_file_id else 'no'}"
    )
    keyboard = {"inline_keyboard": [[
        {"text": "Aprobar", "callback_data": f"gasto:aprobar:{gasto.id}"},
        {"text": "Rechazar", "callback_data": f"gasto:rechazar:{gasto.id}"},
    ]]}
    for admin_id in _admins():
        try:
            if gasto.telegram_file_id:
                _post("sendPhoto", {"chat_id": admin_id, "photo": gasto.telegram_file_id, "caption": texto[:1000], "reply_markup": keyboard})
            else:
                _mensaje(admin_id, texto, reply_markup=keyboard)
        except requests.RequestException:
            continue


def _listar_gastos_pendientes(chat_id) -> None:
    gastos = GastoExtra.query.filter_by(estado="Pendiente").order_by(GastoExtra.reportado_en.asc()).limit(25).all()
    if not gastos:
        _mensaje(chat_id, "No hay gastos pendientes de revisión.", reply_markup=_teclado_menu())
        return
    for gasto in gastos:
        partido = gasto.asignacion.partido
        texto = (
            f"Gasto pendiente #{gasto.id}\n{gasto.arbitro.nombre} {gasto.arbitro.apellido}\n"
            f"{partido.fecha_hora:%d/%m/%Y %H:%M} · {partido.estadio_cancha}\n"
            f"${gasto.monto:.2f} USD · {gasto.concepto}\n{gasto.descripcion or ''}"
        )
        markup = {"inline_keyboard": [[
            {"text": "Aprobar", "callback_data": f"gasto:aprobar:{gasto.id}"},
            {"text": "Rechazar", "callback_data": f"gasto:rechazar:{gasto.id}"},
        ]]}
        if gasto.telegram_file_id:
            _post("sendPhoto", {"chat_id": chat_id, "photo": gasto.telegram_file_id, "caption": texto[:1000], "reply_markup": markup})
        else:
            _mensaje(chat_id, texto, reply_markup=markup)


def _revisar_gasto(gasto_id: int, aprobado: bool, admin_id: str) -> str:
    gasto = db.session.get(GastoExtra, gasto_id)
    if gasto is None:
        return "No encontré ese gasto."
    if gasto.estado != "Pendiente":
        return f"El gasto #{gasto.id} ya fue revisado: {gasto.estado.lower()}."
    asignacion = gasto.asignacion
    antes = {"estado": gasto.estado, "costo_total": float(asignacion.costo_total)}
    gasto.estado = "Aprobado" if aprobado else "Rechazado"
    gasto.revisado_en = datetime.utcnow()
    gasto.revisado_por_telegram_id = admin_id
    if aprobado:
        asignacion.costo_total = Decimal(str(asignacion.costo_total)) + Decimal(str(gasto.monto))
        pago = Pago.query.filter_by(asignacion_id=asignacion.id).first()
        if pago:
            pago.monto_total = Decimal(str(pago.monto_total)) + Decimal(str(gasto.monto))
    registrar_cambio(
        "gasto_extra", gasto.id, "REVISAR",
        antes=antes,
        despues={"estado": gasto.estado, "costo_total": float(asignacion.costo_total), "revisado_por_telegram_id": admin_id},
        origen="telegram_admin", commit=False,
    )
    db.session.commit()
    return f"Gasto #{gasto.id} {'aprobado y sumado al total' if aprobado else 'rechazado'} correctamente."


def _manejar_callback(callback: dict) -> None:
    user_id = str(callback.get("from", {}).get("id", ""))
    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    data = callback.get("data", "")
    _post("answerCallbackQuery", {"callback_query_id": callback["id"]})
    partes = data.split(":")
    if partes[0] == "gasto" and len(partes) == 3:
        if user_id not in _admins():
            _mensaje(chat_id, "Solo un administrador autorizado puede revisar gastos.")
            return
        try:
            texto = _revisar_gasto(int(partes[2]), partes[1] == "aprobar", user_id)
        except Exception:
            db.session.rollback()
            _mensaje(chat_id, "No se pudo completar la revisión. Intenta de nuevo o consulta los registros.")
            return
        _mensaje(chat_id, texto, reply_markup=_teclado_menu())
        return
    if partes[0] != "sel" or len(partes) != 3:
        return
    vinculo = _vinculacion(user_id)
    if not vinculo:
        _mensaje(chat_id, "Primero vincula tu cuenta con /start.")
        return
    try:
        asignacion_id = int(partes[2])
    except ValueError:
        return
    asignacion = AsignacionPartido.query.filter_by(id=asignacion_id, arbitro_id=vinculo.arbitro_id).first()
    if not asignacion:
        _mensaje(chat_id, "La asignación seleccionada no te pertenece o ya no está disponible.")
        return
    accion = partes[1]
    if accion == "ver":
        partido = asignacion.partido
        _mensaje(
            chat_id,
            f"Asignación #{asignacion.id}\n{partido.fecha_hora:%d/%m/%Y %H:%M}\n{partido.estadio_cancha} · {partido.ciudad_juego.nombre}\nEstado: {asignacion.estado_viaje}",
            reply_markup=_teclado_menu(),
        )
    elif accion == "en_camino":
        _actualizar_estado(asignacion, "En camino")
        _mensaje(chat_id, "Registré que vas en camino. ¡Buen viaje!", reply_markup=_teclado_menu())
    elif accion == "llegada":
        _actualizar_estado(asignacion, "En estadio")
        _mensaje(chat_id, "Llegada a la instalación registrada. ¡Gracias!", reply_markup=_teclado_menu())
    elif accion == "retraso":
        vinculo.accion_pendiente = "retraso"
        vinculo.asignacion_pendiente_id = asignacion.id
        db.session.commit()
        _mensaje(chat_id, "Indica minutos estimados y motivo, separados por |. Ejemplo: 20 | tráfico, llego 18:40.")
    elif accion == "gasto":
        vinculo.accion_pendiente = "gasto"
        vinculo.asignacion_pendiente_id = asignacion.id
        db.session.commit()
        _mensaje(chat_id, "Indica monto | concepto | detalle. Ejemplo: 12,50 | taxi | traslado extra al estadio. También puedes adjuntar una foto con ese texto como descripción.")


def _procesar_texto_pendiente(vinculo: TelegramVinculacion, message: dict) -> bool:
    if not vinculo.accion_pendiente:
        return False
    asignacion = db.session.get(AsignacionPartido, vinculo.asignacion_pendiente_id)
    if not asignacion or asignacion.arbitro_id != vinculo.arbitro_id:
        vinculo.accion_pendiente = None
        vinculo.asignacion_pendiente_id = None
        db.session.commit()
        _mensaje(vinculo.chat_id, "La asignación ya no está disponible. Elige otra desde el menú.", reply_markup=_teclado_menu())
        return True
    if vinculo.accion_pendiente == "retraso":
        contenido = (message.get("text") or "").strip()
        partes = contenido.split("|", 1)
        try:
            minutos = int(partes[0].strip())
            if minutos < 0 or minutos > 10080:
                raise ValueError
        except ValueError:
            _mensaje(vinculo.chat_id, "Escribe minutos como número y opcionalmente | motivo. Ejemplo: 20 | tráfico.")
            return True
        motivo = partes[1].strip()[:300] if len(partes) > 1 else ""
        vinculo.accion_pendiente = None
        vinculo.asignacion_pendiente_id = None
        _actualizar_estado(asignacion, "Retraso", {"minutos_retraso": minutos, "motivo": motivo}, commit=False)
        db.session.commit()
        _mensaje(vinculo.chat_id, f"Retraso de {minutos} minutos registrado." + (f" Motivo: {motivo}" if motivo else ""), reply_markup=_teclado_menu())
        return True
    if vinculo.accion_pendiente == "gasto" and (message.get("text") or message.get("caption")):
        _reporte_gasto(vinculo, message, asignacion)
        return True
    if vinculo.accion_pendiente == "gasto" and message.get("photo"):
        _mensaje(vinculo.chat_id, "Añade el texto del gasto como descripción de la foto: monto | concepto | detalle.")
        return True
    _mensaje(vinculo.chat_id, "No entendí ese reporte. Envía el formato que te indiqué o usa /cancel.")
    return True


def _procesar_mensaje(message: dict) -> None:
    chat_id = message.get("chat", {}).get("id")
    user = message.get("from", {})
    user_id = str(user.get("id", ""))
    texto = (message.get("text") or "").strip()
    if texto.startswith("/start"):
        if _vinculacion(user_id):
            _mensaje(chat_id, "Ya estás vinculado. Usa el menú para reportar tu viaje o un gasto.", reply_markup=_teclado_menu())
        else:
            keyboard = {"keyboard": [[{"text": "Compartir mi teléfono para vincular", "request_contact": True}]], "resize_keyboard": True, "one_time_keyboard": True}
            _mensaje(chat_id, "Bienvenido al asistente de árbitros. Comparte tu propio teléfono registrado en la liga para verificar tu cuenta.", reply_markup=keyboard)
        return
    if texto == "/mi_id":
        _mensaje(chat_id, f"Tu ID de Telegram es {user_id}. El administrador puede usarlo para habilitar revisiones.")
        return
    if texto == "/pendientes" and user_id in _admins():
        _listar_gastos_pendientes(chat_id)
        return
    if texto.startswith("/cancel"):
        vinculo = _vinculacion(user_id)
        if vinculo:
            vinculo.accion_pendiente = None
            vinculo.asignacion_pendiente_id = None
            db.session.commit()
        _mensaje(chat_id, "Operación cancelada.", reply_markup=_teclado_menu())
        return
    if message.get("contact"):
        _vincular_contacto(message)
        return
    vinculo = _vinculacion(user_id)
    if not vinculo:
        _mensaje(chat_id, "Primero vincula tu cuenta con /start.")
        return
    if _procesar_texto_pendiente(vinculo, message):
        return
    opciones = {
        "🚗 en camino": ("en_camino", "en camino"),
        "⏰ reportar retraso": ("retraso", "reportar retraso"),
        "🏟 llegué a instalación": ("llegada", "llegué a instalación"),
        "💸 reportar gasto": ("gasto", "reportar gasto"),
        "📅 mis asignaciones": ("ver", "mis asignaciones"),
    }
    elegido = opciones.get(texto.casefold())
    if elegido:
        _selector_asignaciones(chat_id, vinculo.arbitro_id, elegido[0])
    elif texto in {"❓ ayuda", "/help"}:
        _mensaje(chat_id, "Usa los botones del menú. Los retrasos piden minutos y motivo; los gastos se guardan pendientes de aprobación.", reply_markup=_teclado_menu())
    elif message.get("photo"):
        _mensaje(chat_id, "Para enviar un comprobante, inicia primero Reportar gasto, selecciona el partido y luego adjunta la foto con monto | concepto | detalle.")
    else:
        _mensaje(chat_id, "No reconocí la opción. Usa los botones del menú.", reply_markup=_teclado_menu())


def procesar_update(update: dict) -> None:
    if "callback_query" in update:
        _manejar_callback(update["callback_query"])
    elif "message" in update:
        _procesar_mensaje(update["message"])


def run_polling() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("Configura TELEGRAM_BOT_TOKEN en .env antes de iniciar el bot.")
    print("Bot de Telegram iniciado en modo polling.", flush=True)
    offset = None
    while True:
        try:
            parametros = {"timeout": 25, "allowed_updates": ["message", "callback_query"]}
            if offset is not None:
                parametros["offset"] = offset
            respuesta = requests.get(f"{BASE_URL}/getUpdates", params=parametros, timeout=35)
            respuesta.raise_for_status()
            datos = respuesta.json()
            if not datos.get("ok"):
                raise RuntimeError(datos.get("description", "getUpdates falló"))
            for update in datos.get("result", []):
                offset = update["update_id"] + 1
                try:
                    procesar_update(update)
                except Exception as error:
                    db.session.rollback()
                    print(f"No se pudo procesar update {update.get('update_id')}: {error}", flush=True)
                finally:
                    db.session.remove()
        except (requests.RequestException, RuntimeError) as error:
            print(f"Telegram no disponible: {error}", flush=True)
            time.sleep(5)
