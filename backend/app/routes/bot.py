"""Webhook autenticado para actualizar estados de viaje desde el bot."""

import hmac
import os
import re
import unicodedata
from datetime import datetime

from flask import Blueprint, jsonify, request

from ..database import db
from ..models import Arbitro, AsignacionPartido, Partido
from ..services.auditoria import registrar_cambio

bp = Blueprint("bot", __name__)


def _telefono_normalizado(valor) -> str:
    digitos = re.sub(r"\D", "", str(valor or ""))
    # Números locales venezolanos (0414...) y con código de país (+58414...)
    # comparten los últimos diez dígitos.
    return digitos[-10:] if len(digitos) >= 10 else digitos


def _normalizar_evento(valor) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or "").strip().lower())
    texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    return " ".join(texto.split())


def _parsear_minutos(valor):
    if isinstance(valor, bool):
        raise ValueError("minutos_retraso debe ser un entero no negativo.")
    try:
        numero = int(valor)
    except (TypeError, ValueError) as error:
        raise ValueError("minutos_retraso debe ser un entero no negativo.") from error
    if numero < 0 or (isinstance(valor, float) and not valor.is_integer()):
        raise ValueError("minutos_retraso debe ser un entero no negativo.")
    if isinstance(valor, str) and not re.fullmatch(r"\d+", valor.strip()):
        raise ValueError("minutos_retraso debe ser un entero no negativo.")
    return numero


@bp.post("/webhook")
def recibir_webhook():
    token_configurado = os.getenv("BOT_WEBHOOK_TOKEN", "").strip()
    token_recibido = request.headers.get("X-Bot-Token", "").strip()
    if not token_configurado:
        return jsonify({"error": "El webhook no está configurado."}), 503
    if not token_recibido or not hmac.compare_digest(token_recibido, token_configurado):
        return jsonify({"error": "Token de webhook inválido."}), 401

    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify({"error": "El cuerpo debe ser un objeto JSON."}), 400
    telefono = _telefono_normalizado(datos.get("telefono") or datos.get("phone"))
    if len(telefono) < 10:
        return jsonify({"error": "Incluye un teléfono válido del árbitro."}), 400

    nombres_evento = {
        "en camino": "En camino",
        "en cancha": "En estadio",
        "retraso": "Retraso",
    }
    evento_recibido = datos.get("evento") or datos.get("event")
    estado_nuevo = nombres_evento.get(_normalizar_evento(evento_recibido))
    if estado_nuevo is None:
        return jsonify({"error": "Evento no válido. Usa 'En camino', 'En cancha' o 'Retraso'."}), 400

    minutos_retraso = datos.get("minutos_retraso")
    if estado_nuevo == "Retraso":
        try:
            minutos_retraso = _parsear_minutos(minutos_retraso)
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
    elif minutos_retraso is not None:
        try:
            minutos_retraso = _parsear_minutos(minutos_retraso)
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

    arbitros = Arbitro.query.filter(Arbitro.telefono.isnot(None)).all()
    coincidencias = [arbitro for arbitro in arbitros if _telefono_normalizado(arbitro.telefono) == telefono]
    if not coincidencias:
        return jsonify({"error": "No se encontró un árbitro con ese teléfono."}), 404
    if len(coincidencias) > 1:
        return jsonify({"error": "El teléfono coincide con más de un árbitro; corrige el catálogo."}), 409
    arbitro = coincidencias[0]

    consulta = AsignacionPartido.query.join(Partido).filter(AsignacionPartido.arbitro_id == arbitro.id)
    if datos.get("asignacion_id") is not None:
        try:
            asignacion_id = int(datos["asignacion_id"])
        except (TypeError, ValueError):
            return jsonify({"error": "asignacion_id debe ser un entero."}), 400
        consulta = consulta.filter(AsignacionPartido.id == asignacion_id)
    elif datos.get("partido_id") is not None:
        try:
            partido_id = int(datos["partido_id"])
        except (TypeError, ValueError):
            return jsonify({"error": "partido_id debe ser un entero."}), 400
        consulta = consulta.filter(AsignacionPartido.partido_id == partido_id)
    else:
        consulta = consulta.filter(
            Partido.fecha_hora >= datetime.utcnow(),
            AsignacionPartido.estado_viaje != "Finalizado",
        )
    asignacion = consulta.order_by(Partido.fecha_hora.asc(), AsignacionPartido.id.asc()).first()
    if asignacion is None:
        return jsonify({"error": "No se encontró una asignación pendiente para el árbitro indicado."}), 404

    antes = {"estado_viaje": asignacion.estado_viaje, "minutos_retraso": None}
    asignacion.estado_viaje = estado_nuevo
    if estado_nuevo == "En camino":
        asignacion.fecha_salida = datetime.utcnow()
    elif estado_nuevo == "En estadio":
        asignacion.fecha_llegada_estadio = datetime.utcnow()
    despues = {
        "estado_viaje": estado_nuevo,
        "minutos_retraso": minutos_retraso if estado_nuevo == "Retraso" else None,
    }
    try:
        historial = registrar_cambio(
            "asignacion",
            asignacion.id,
            "ESTADO_BOT",
            antes=antes,
            despues=despues,
            origen="telegram",
        )
    except Exception:
        db.session.rollback()
        raise

    return jsonify({
        "mensaje": "Estado arbitral actualizado.",
        "arbitro_id": arbitro.id,
        "asignacion_id": asignacion.id,
        "estado_viaje": asignacion.estado_viaje,
        "evento_recibido": evento_recibido,
        "minutos_retraso": minutos_retraso if estado_nuevo == "Retraso" else None,
        "historial_id": historial.id,
    }), 200
