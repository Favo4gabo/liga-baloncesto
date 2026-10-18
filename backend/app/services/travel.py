"""Estimación de duración, llegada y progreso para trayectos arbitrales."""

from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt

from ..models import Aeropuerto, DistanciaCiudad


def distancia_entre(ciudad_origen_id: int, ciudad_destino_id: int) -> float:
    """Devuelve la distancia cargada sin importar el sentido; 0 para misma ciudad."""
    if ciudad_origen_id == ciudad_destino_id:
        return 0.0
    distancia = DistanciaCiudad.query.filter(
        ((DistanciaCiudad.ciudad_origen_id == ciudad_origen_id) & (DistanciaCiudad.ciudad_destino_id == ciudad_destino_id)) |
        ((DistanciaCiudad.ciudad_origen_id == ciudad_destino_id) & (DistanciaCiudad.ciudad_destino_id == ciudad_origen_id))
    ).first()
    return float(distancia.distancia_km) if distancia else 0.0


def medio_recomendado(distancia_km: float) -> str:
    if distancia_km <= 40:
        return "local"
    if distancia_km <= 350:
        return "taxi"
    return "avion"


def _distancia_haversine(latitud_a: float, longitud_a: float, latitud_b: float, longitud_b: float) -> float:
    """Distancia de gran círculo entre dos aeropuertos, en kilómetros."""
    radio_tierra_km = 6371.0
    d_latitud, d_longitud = radians(latitud_b - latitud_a), radians(longitud_b - longitud_a)
    valor = sin(d_latitud / 2) ** 2 + cos(radians(latitud_a)) * cos(radians(latitud_b)) * sin(d_longitud / 2) ** 2
    return round(2 * radio_tierra_km * asin(sqrt(valor)), 1)


def ruta_aerea(estado_origen_id: int, estado_destino_id: int) -> dict | None:
    """Selecciona el aeropuerto principal por estado y calcula su distancia aérea."""
    if estado_origen_id == estado_destino_id:
        return None
    origen = Aeropuerto.query.filter_by(estado_id=estado_origen_id, principal=True).first() or Aeropuerto.query.filter_by(estado_id=estado_origen_id).first()
    destino = Aeropuerto.query.filter_by(estado_id=estado_destino_id, principal=True).first() or Aeropuerto.query.filter_by(estado_id=estado_destino_id).first()
    if origen is None or destino is None:
        return None
    distancia = _distancia_haversine(float(origen.latitud), float(origen.longitud), float(destino.latitud), float(destino.longitud))
    return {"distancia_aerea_km": distancia, "origen": origen.to_dict(), "destino": destino.to_dict()}


def calcular_tiempo_traslado(distancia_km: float, tipo_transporte: str, fecha_salida: datetime | None = None) -> dict:
    """Aplica T=distancia/velocidad más la logística fija de cada transporte."""
    distancia_km = max(float(distancia_km or 0), 0)
    tipo = (tipo_transporte or medio_recomendado(distancia_km)).lower()
    recomendado = medio_recomendado(distancia_km)
    if tipo == "avion":
        horas_estimadas, velocidad, margen = (distancia_km / 550.0) + 2.0, 550, 2.0
    elif distancia_km <= 40:
        tipo, horas_estimadas, velocidad, margen = "local", (distancia_km / 35.0) + 0.25, 35, 0.25
    else:
        tipo, horas_estimadas, velocidad, margen = "taxi", (distancia_km / 75.0) + 0.5, 75, 0.5

    minutos_totales = max(1, round(horas_estimadas * 60))
    llegada = fecha_salida + timedelta(minutes=minutos_totales) if fecha_salida else None
    ahora = datetime.utcnow()
    if not fecha_salida:
        progreso = 0
    elif ahora >= llegada:
        progreso = 100
    elif ahora <= fecha_salida:
        progreso = 0
    else:
        progreso = min(100, round((ahora - fecha_salida).total_seconds() / (llegada - fecha_salida).total_seconds() * 100))
    horas, minutos = divmod(minutos_totales, 60)
    return {"distancia_km": distancia_km, "tipo_transporte": tipo, "tipo_recomendado": recomendado,
            "velocidad_kmh": velocidad, "margen_logistico_minutos": round(margen * 60),
            "minutos_totales": minutos_totales, "duracion_estimada_texto": f"{horas}h {minutos:02d}m" if horas else f"{minutos}m",
            "fecha_llegada_estimada": llegada.isoformat() if llegada else None, "porcentaje_progreso": progreso}


def planificar_logistica(fecha_partido: datetime, distancia_km: float, tipo_transporte: str,
                          requiere_hospedaje: bool) -> dict:
    """Plan operativo: sede un día antes y presencia en cancha 30 min antes del juego."""
    traslado = calcular_tiempo_traslado(distancia_km, tipo_transporte)
    llegada_estadio = fecha_partido - timedelta(minutes=30)
    traslado_local_minutos = 15
    salida_hotel = llegada_estadio - timedelta(minutes=traslado_local_minutos)
    if requiere_hospedaje:
        llegada_ciudad = fecha_partido - timedelta(days=1)
        salida_origen = llegada_ciudad - timedelta(minutes=traslado["minutos_totales"])
    else:
        llegada_ciudad = None
        salida_origen = salida_hotel
    return {"requiere_hospedaje": requiere_hospedaje,
            "fecha_salida_origen_recomendada": salida_origen.isoformat(),
            "fecha_llegada_ciudad_recomendada": llegada_ciudad.isoformat() if llegada_ciudad else None,
            "fecha_salida_hotel_recomendada": salida_hotel.isoformat(),
            "fecha_llegada_estadio_recomendada": llegada_estadio.isoformat(),
            "margen_antes_partido_minutos": 30,
            "traslado_hotel_cancha_minutos": traslado_local_minutos}
