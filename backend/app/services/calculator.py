"""Cálculos deterministas de logística; nunca asignan importes no configurados."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from ..database import db
from ..models import Arbitro, EstadoCercano, Parametro, Partido, TarifaHospedaje, TarifaTraslado
from .travel import distancia_entre, medio_recomendado

DOS_DECIMALES = Decimal("0.01")


def _importe(valor: Decimal) -> float:
    return float(valor.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP))


def _requerir_tarifa(tipo: str, medio: str) -> Decimal:
    tarifa = TarifaTraslado.query.filter_by(tipo=tipo, medio=medio).first()
    if tarifa is None:
        raise ValueError(f"Falta configurar la tarifa de traslado {tipo}/{medio}.")
    return Decimal(str(tarifa.costo_base))


def _estados_son_cercanos(estado_a_id: int, estado_b_id: int) -> bool:
    menores, mayores = sorted((estado_a_id, estado_b_id))
    return EstadoCercano.query.filter_by(estado_a_id=menores, estado_b_id=mayores).first() is not None


def determinar_medio_externo(arbitro: Arbitro, partido: Partido) -> str:
    """Prioriza la distancia configurada; conserva la regla de estados si aún no hay matriz."""
    distancia = distancia_entre(arbitro.ciudad_origen_id, partido.ciudad_juego_id)
    if distancia:
        recomendado = medio_recomendado(distancia)
        return "taxi" if recomendado == "local" else recomendado
    origen = arbitro.ciudad_origen.estado_id
    destino = partido.ciudad_juego.estado_id
    return "taxi" if origen == destino or _estados_son_cercanos(origen, destino) else "avion"


def calcular_viaticos_asignacion(arbitro_id: int, partido_id: int, cantidad_noches: int = 1,
                                 cantidad_dias: int = 1, medio_transporte: str | None = None,
                                 viatico_por_dia: Decimal | float | str | None = None,
                                 hospedaje_total: Decimal | float | str | None = None) -> dict[str, float | bool | str]:
    """Devuelve el desglose de ida/vuelta aplicando exclusivamente tarifas cargadas."""
    if isinstance(cantidad_noches, bool) or not isinstance(cantidad_noches, int) or cantidad_noches < 0:
        raise ValueError("cantidad_noches debe ser un entero mayor o igual a cero.")
    if isinstance(cantidad_dias, bool) or not isinstance(cantidad_dias, int) or cantidad_dias < 1:
        raise ValueError("cantidad_dias debe ser un entero mayor o igual a uno.")
    arbitro = db.session.get(Arbitro, arbitro_id)
    partido = db.session.get(Partido, partido_id)
    if arbitro is None or partido is None:
        raise ValueError("El árbitro o el partido indicado no existe.")

    misma_ciudad = arbitro.ciudad_origen_id == partido.ciudad_juego_id
    interno = _requerir_tarifa("interno", "taxi") * 2  # llegada y regreso cancha/hotel
    externo = Decimal("0")
    estadia = Decimal("0")
    costo_hospedaje_por_noche = Decimal("0")
    medio_externo = None
    if not misma_ciudad:
        if medio_transporte is not None and medio_transporte not in {"taxi", "avion"}:
            raise ValueError("medio_transporte debe ser 'taxi' o 'avion'.")
        medio_externo = medio_transporte or determinar_medio_externo(arbitro, partido)
        externo = _requerir_tarifa("externo", medio_externo) * 2  # ida y vuelta
    if hospedaje_total is not None:
        try:
            estadia = Decimal(str(hospedaje_total))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise ValueError("hospedaje_total debe ser un importe numérico no negativo.") from error
        if not estadia.is_finite() or estadia < 0:
            raise ValueError("hospedaje_total debe ser un importe numérico no negativo.")
        costo_hospedaje_por_noche = estadia / cantidad_noches if cantidad_noches else Decimal("0")
    elif not misma_ciudad and cantidad_noches > 0:
        hotel = TarifaHospedaje.query.filter_by(ciudad_id=partido.ciudad_juego_id).first()
        if hotel is None:
            raise ValueError("Falta configurar la tarifa de hospedaje de la ciudad del partido.")
        costo_hospedaje_por_noche = Decimal(str(hotel.costo_noche))
        estadia = costo_hospedaje_por_noche * cantidad_noches
    parametro = db.session.get(Parametro, "viatico_por_dia")
    if parametro is None and viatico_por_dia is None:
        raise ValueError("Falta configurar el parámetro 'viatico_por_dia'.")
    importe_viatico = Decimal(str(viatico_por_dia if viatico_por_dia is not None else parametro.valor))
    if not importe_viatico.is_finite() or importe_viatico < 0:
        raise ValueError("viatico_por_dia debe ser un importe válido no negativo.")
    viaticos = importe_viatico * cantidad_dias
    total = externo + interno + estadia + viaticos
    return {"misma_ciudad": misma_ciudad, "medio_externo": medio_externo,
            "cantidad_noches": cantidad_noches, "cantidad_dias_viaticos": cantidad_dias,
            "costo_hospedaje_por_noche": _importe(costo_hospedaje_por_noche),
            "viatico_por_dia": _importe(importe_viatico),
            "costo_externo_por_trayecto": _importe(externo / 2),
            "costo_interno_por_trayecto": _importe(interno / 2),
            "costo_traslado_externo": _importe(externo), "costo_traslado_interno": _importe(interno),
            "costo_estadia": _importe(estadia), "costo_viaticos": _importe(viaticos),
            "costo_total": _importe(total)}
