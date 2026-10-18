"""Lectura en modo preview y confirmación humana de horarios."""

from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from ..authz import roles_required
from ..database import db
from ..models import Arbitro, Ciudad, Partido, UbicacionCancha
from ..services.asignaciones import AsignacionError, crear_asignacion
from ..services.auditoria import registrar_cambio
from ..services.schedule_extractor import extraer_horario_arbitro

bp = Blueprint("horarios", __name__)
EXTENSIONES_PERMITIDAS = {".xlsx", ".csv", ".png", ".jpg", ".jpeg"}
MAX_FILAS_CONFIRMACION = 250


@bp.post("/escanear")
def escanear_horario():
    archivo = request.files.get("file")
    if archivo is None or not archivo.filename:
        return jsonify({"error": "Adjunta un archivo en el campo 'file'."}), 400
    extension = "." + archivo.filename.rsplit(".", 1)[-1].lower() if "." in archivo.filename else ""
    if extension not in EXTENSIONES_PERMITIDAS:
        return jsonify({"error": "Formato no permitido. Usa Excel, CSV, PNG o JPG."}), 400
    try:
        contenido = archivo.read()
        if not contenido:
            return jsonify({"error": "El archivo está vacío."}), 400
        preview = extraer_horario_arbitro(contenido, archivo.filename)
        return jsonify(preview), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 422


def _entero_positivo(valor, campo):
    if isinstance(valor, bool):
        raise ValueError(f"{campo} debe ser un entero positivo.")
    try:
        numero = int(valor)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{campo} debe ser un entero positivo.") from error
    if numero <= 0 or str(numero) != str(valor).strip():
        raise ValueError(f"{campo} debe ser un entero positivo.")
    return numero


@bp.post("/confirmar")
@roles_required("super_admin", "admin")
def confirmar_horario():
    datos = request.get_json(silent=True)
    filas = datos.get("filas") if isinstance(datos, dict) else None
    if not isinstance(filas, list) or not filas:
        return jsonify({"error": "Envía una lista no vacía de filas revisadas."}), 400
    if len(filas) > MAX_FILAS_CONFIRMACION:
        return jsonify({"error": f"El máximo permitido es {MAX_FILAS_CONFIRMACION} filas por confirmación."}), 400

    registradas = []
    partidos_nuevos = 0
    asignaciones_nuevas = 0
    try:
        for indice, fila in enumerate(filas, start=1):
            if not isinstance(fila, dict):
                raise ValueError(f"La fila {indice} no tiene un formato válido.")
            try:
                fecha = datetime.strptime(f"{fila.get('fecha', '')} {fila.get('hora', '')}", "%Y-%m-%d %H:%M")
                arbitro_id = _entero_positivo(fila.get("arbitro_id"), "arbitro_id")
                cancha_id = _entero_positivo(fila.get("cancha_id"), "cancha_id")
            except ValueError as error:
                raise ValueError(f"Fila {indice}: {error}") from error

            arbitro = db.session.get(Arbitro, arbitro_id)
            cancha = db.session.get(UbicacionCancha, cancha_id)
            if arbitro is None or not arbitro.activo:
                raise ValueError(f"Fila {indice}: el árbitro seleccionado no existe o está inactivo.")
            if cancha is None:
                raise ValueError(f"Fila {indice}: la cancha seleccionada no existe.")

            ciudad_id = fila.get("ciudad_id")
            if ciudad_id in (None, ""):
                ciudad_id = cancha.ciudad_id
            else:
                ciudad_id = _entero_positivo(ciudad_id, "ciudad_id")
            if db.session.get(Ciudad, ciudad_id) is None:
                raise ValueError(f"Fila {indice}: la ciudad seleccionada no existe.")
            if ciudad_id != cancha.ciudad_id:
                raise ValueError(f"Fila {indice}: la ciudad debe coincidir con la ubicación de la cancha.")

            partido = Partido.query.filter_by(
                fecha_hora=fecha,
                estadio_cancha=cancha.nombre_cancha,
            ).order_by(Partido.id).first()
            creado = partido is None
            if creado:
                partido = Partido(
                    fecha_hora=fecha,
                    estadio_cancha=cancha.nombre_cancha,
                    ciudad_juego_id=cancha.ciudad_id,
                )
                db.session.add(partido)
                db.session.flush()
                registrar_cambio(
                    "partido",
                    partido.id,
                    "CREAR",
                    despues={
                        "fecha_hora": partido.fecha_hora.isoformat(),
                        "estadio_cancha": partido.estadio_cancha,
                        "ciudad_juego_id": partido.ciudad_juego_id,
                    },
                    origen="ocr",
                    commit=False,
                )
                partidos_nuevos += 1
            elif partido.ciudad_juego_id != cancha.ciudad_id:
                raise ValueError(f"Fila {indice}: existe un partido con esa fecha y cancha en otra ciudad.")

            opciones = {
                "arbitro_id": arbitro_id,
                "cantidad_noches": fila.get("cantidad_noches", 1),
                "cantidad_dias": fila.get("cantidad_dias", 1),
                "medio_transporte": fila.get("medio_transporte") or None,
            }
            try:
                asignacion = crear_asignacion(partido.id, opciones, commit=False)
            except AsignacionError as error:
                raise AsignacionError(f"Fila {indice}: {error}", error.status_code) from error
            registrar_cambio(
                "asignacion",
                asignacion.id,
                "CREAR",
                despues={
                    "partido_id": partido.id,
                    "arbitro_id": arbitro.id,
                    "estado_viaje": asignacion.estado_viaje,
                    "origen": "horario",
                },
                origen="ocr",
                commit=False,
            )

            registradas.append({
                "fila": indice,
                "partido_id": partido.id,
                "asignacion_id": asignacion.id,
                "arbitro_id": arbitro.id,
                "cancha_id": cancha.id,
                "partido_creado": creado,
            })
            asignaciones_nuevas += 1

        db.session.commit()
    except AsignacionError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), error.status_code
    except (ValueError, IntegrityError) as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 409 if isinstance(error, IntegrityError) else 400
    except Exception:
        db.session.rollback()
        raise

    return jsonify({
        "mensaje": "Horario confirmado y registrado en el calendario.",
        "partidos_nuevos": partidos_nuevos,
        "asignaciones_nuevas": asignaciones_nuevas,
        "registros": registradas,
    }), 201
