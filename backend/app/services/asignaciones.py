"""Creación de asignaciones y su detalle logístico asociado."""

from datetime import datetime

from sqlalchemy.exc import IntegrityError

from ..database import db
from ..models import (
    ARBITROS_POR_PARTIDO,
    Arbitro,
    AsignacionPartido,
    DetalleCostoAsignacion,
    Hospedaje,
    Pago,
    Partido,
    Traslado,
)
from .calculator import calcular_viaticos_asignacion
from .notifications import registrar_y_enviar_evento
from .travel import distancia_entre, planificar_logistica, ruta_aerea


class AsignacionError(Exception):
    """Error de negocio con el estado HTTP apropiado para la API."""

    def __init__(self, mensaje: str, status_code: int = 400):
        super().__init__(mensaje)
        self.status_code = status_code


def _fecha_hora(valor):
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise ValueError("fecha_hora debe estar en formato ISO 8601.") from error


def crear_asignacion(partido_id: int, datos: dict, commit: bool = True) -> AsignacionPartido:
    """Crea asignación, costos, traslados, hospedaje, pago y evento inicial.

    La función espera una sesión SQLAlchemy activa y confirma en una única
    transacción el conjunto completo de registros.
    """
    arbitro_id = datos.get("arbitro_id")
    if isinstance(arbitro_id, bool) or not isinstance(arbitro_id, int):
        raise AsignacionError("El campo 'arbitro_id' es obligatorio.")

    partido = db.session.get(Partido, partido_id)
    arbitro = db.session.get(Arbitro, arbitro_id)
    if partido is None or arbitro is None:
        raise AsignacionError("El partido o árbitro indicado no existe.", 404)
    if len(partido.asignaciones) >= ARBITROS_POR_PARTIDO:
        raise AsignacionError(
            f"Este partido ya tiene sus {ARBITROS_POR_PARTIDO} árbitros asignados.", 409
        )

    try:
        noches = datos.get("cantidad_noches", 1)
        dias = datos.get("cantidad_dias", 1)
        viaticos = calcular_viaticos_asignacion(
            arbitro_id,
            partido_id,
            noches,
            dias,
            datos.get("medio_transporte"),
            datos.get("viatico_por_dia"),
            datos.get("hospedaje_total"),
        )
        distancia = distancia_entre(arbitro.ciudad_origen_id, partido.ciudad_juego_id)
        medio = viaticos["medio_externo"] or "local"
        ruta = ruta_aerea(arbitro.ciudad_origen.estado_id, partido.ciudad_juego.estado_id) if medio == "avion" else None
        distancia_estimacion = ruta["distancia_aerea_km"] if ruta else distancia
        plan = planificar_logistica(
            partido.fecha_hora,
            distancia_estimacion,
            medio,
            not viaticos["misma_ciudad"],
        )
        salida = (
            _fecha_hora(datos["fecha_salida"])
            if datos.get("fecha_salida")
            else _fecha_hora(plan["fecha_salida_origen_recomendada"])
        )
        llegada_ciudad = (
            _fecha_hora(datos["fecha_llegada_ciudad"])
            if datos.get("fecha_llegada_ciudad")
            else (
                _fecha_hora(plan["fecha_llegada_ciudad_recomendada"])
                if plan["fecha_llegada_ciudad_recomendada"]
                else None
            )
        )
        if not viaticos["misma_ciudad"] and salida > _fecha_hora(plan["fecha_salida_origen_recomendada"]):
            raise ValueError("La salida debe permitir llegar a la ciudad sede al menos un día antes del partido.")

        asignacion = AsignacionPartido(
            partido_id=partido_id,
            arbitro_id=arbitro_id,
            costo_traslado_externo=viaticos["costo_traslado_externo"],
            costo_traslado_interno=viaticos["costo_traslado_interno"],
            costo_estadia=viaticos["costo_estadia"],
            costo_viaticos=viaticos["costo_viaticos"],
            costo_total=viaticos["costo_total"],
            fecha_salida=salida,
            fecha_llegada_ciudad=llegada_ciudad,
        )
        asignacion.detalle_costos = DetalleCostoAsignacion(
            cantidad_noches=viaticos["cantidad_noches"],
            costo_hospedaje_por_noche=viaticos["costo_hospedaje_por_noche"],
            cantidad_dias_viaticos=viaticos["cantidad_dias_viaticos"],
            viatico_por_dia=viaticos["viatico_por_dia"],
            costo_externo_por_trayecto=viaticos["costo_externo_por_trayecto"],
            costo_interno_por_trayecto=viaticos["costo_interno_por_trayecto"],
            medio_externo=viaticos["medio_externo"],
        )
        db.session.add(asignacion)
        db.session.flush()

        origen, sede = arbitro.ciudad_origen.nombre, partido.ciudad_juego.nombre
        costo_interno = viaticos["costo_traslado_interno"] / 2
        db.session.add_all([
            Traslado(asignacion=asignacion, sentido="ida", tipo="interno", medio="taxi",
                     origen="Hotel", destino=partido.estadio_cancha, costo=costo_interno),
            Traslado(asignacion=asignacion, sentido="vuelta", tipo="interno", medio="taxi",
                     origen=partido.estadio_cancha, destino="Hotel", costo=costo_interno),
        ])
        if not viaticos["misma_ciudad"]:
            costo_externo = viaticos["costo_traslado_externo"] / 2
            db.session.add_all([
                Traslado(asignacion=asignacion, sentido="ida", tipo="externo",
                         medio=viaticos["medio_externo"], origen=origen, destino=sede,
                         costo=costo_externo),
                Traslado(asignacion=asignacion, sentido="vuelta", tipo="externo",
                         medio=viaticos["medio_externo"], origen=sede, destino=origen,
                         costo=costo_externo),
                Hospedaje(
                    asignacion=asignacion,
                    noches=noches,
                    costo_noche=viaticos["costo_estadia"] / max(noches, 1),
                    costo_total=viaticos["costo_estadia"],
                ),
            ])
        db.session.add(Pago(asignacion=asignacion, monto_total=viaticos["costo_total"]))
        db.session.add(registrar_y_enviar_evento(asignacion, "Asignación creada"))
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return asignacion
    except (ValueError, IntegrityError) as error:
        db.session.rollback()
        if isinstance(error, IntegrityError):
            raise AsignacionError("No se pudo crear la asignación por una restricción de datos.") from error
        raise AsignacionError(str(error)) from error
    except Exception:
        db.session.rollback()
        raise


def reemplazar_arbitro_asignacion(asignacion_id: int, arbitro_id: int) -> AsignacionPartido:
    """Recrea una asignación con otro árbitro para mantener costos y rutas coherentes."""
    asignacion = db.session.get(AsignacionPartido, asignacion_id)
    arbitro = db.session.get(Arbitro, arbitro_id)
    if asignacion is None or arbitro is None:
        raise AsignacionError("La asignación o árbitro indicado no existe.", 404)
    if asignacion.arbitro_id == arbitro_id:
        return asignacion
    if not arbitro.activo:
        raise AsignacionError("No se puede asignar un árbitro inactivo.", 400)
    if any(
        otra.id != asignacion.id and otra.arbitro_id == arbitro_id
        for otra in asignacion.partido.asignaciones
    ):
        raise AsignacionError("Ese árbitro ya está asignado a este partido.", 409)
    if asignacion.gastos_reales or asignacion.gastos_extra:
        raise AsignacionError("No se puede cambiar el árbitro después de registrar gastos reales o extras; conserva el historial y realiza una nueva asignación.", 409)

    detalle = asignacion.detalle_costos
    datos = {
        "arbitro_id": arbitro_id,
        "cantidad_noches": detalle.cantidad_noches if detalle else 1,
        "cantidad_dias": detalle.cantidad_dias_viaticos if detalle else 1,
        "medio_transporte": detalle.medio_externo if detalle else None,
        "viatico_por_dia": detalle.viatico_por_dia if detalle else None,
    }
    partido_id = asignacion.partido_id
    db.session.delete(asignacion)
    db.session.flush()
    return crear_asignacion(partido_id, datos)
