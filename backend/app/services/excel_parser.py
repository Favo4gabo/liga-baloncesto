"""Importación atómica del libro maestro definido para la liga."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any, BinaryIO
import unicodedata

import pandas as pd

from ..database import db
from ..models import (Arbitro, Ciudad, Estado, EstadoCercano, Parametro, Partido,
                      TarifaHospedaje, TarifaTraslado)

HOJAS = {
    "Estados": {"nombre"}, "Ciudades": {"nombre", "estado"},
    "TarifasTraslado": {"tipo", "medio", "costo_base"},
    "TarifasHospedaje": {"ciudad", "costo_noche"}, "Parametros": {"clave", "valor"},
    "EstadosCercanos": {"estado_a", "estado_b"},
    "Arbitros": {"nombre", "apellido", "telefono", "email", "ciudad_origen"},
    "Partidos": {"fecha_hora", "estadio_cancha", "ciudad_juego"},
}


def _normalizar(valor: Any) -> str:
    texto = unicodedata.normalize("NFKD", str(valor).strip())
    return "".join(c for c in texto if not unicodedata.combining(c)).casefold()


def _vacio(valor: Any) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip()) or pd.isna(valor)


def _texto(valor: Any, campo: str, obligatorio: bool = True) -> str | None:
    if _vacio(valor):
        if obligatorio:
            raise ValueError(f"El campo '{campo}' es obligatorio.")
        return None
    return str(valor).strip()


def _decimal(valor: Any, campo: str) -> Decimal:
    try:
        numero = Decimal(str(_texto(valor, campo)))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"El campo '{campo}' debe ser numérico.") from error
    if not numero.is_finite() or numero < 0:
        raise ValueError(f"El campo '{campo}' debe ser un importe válido no negativo.")
    return numero


def _filas(libro: dict[str, pd.DataFrame], hoja: str) -> list[dict[str, Any]]:
    marco = libro[hoja].copy()
    columnas = [_normalizar(columna) for columna in marco.columns]
    if len(columnas) != len(set(columnas)):
        raise ValueError(f"La hoja '{hoja}' tiene cabeceras duplicadas.")
    faltantes = HOJAS[hoja] - set(columnas)
    if faltantes:
        raise ValueError(f"Faltan cabeceras en '{hoja}': {', '.join(sorted(faltantes))}.")
    marco.columns = columnas
    return [fila.to_dict() for _, fila in marco.dropna(how="all").iterrows()]


def _buscar(mapa: dict[str, Any], valor: Any, campo: str) -> Any:
    texto = _texto(valor, campo)
    registro = mapa.get(_normalizar(texto))
    if registro is None:
        raise ValueError(f"'{texto}' indicado en '{campo}' no existe.")
    return registro


def procesar_archivo_excel(archivo: bytes | bytearray | BinaryIO) -> dict[str, Any]:
    """Crea o actualiza los catálogos. Si una fila falla, no se guarda ninguna."""
    origen = BytesIO(archivo) if isinstance(archivo, (bytes, bytearray)) else archivo
    if hasattr(origen, "seek"):
        origen.seek(0)
    try:
        libro = pd.read_excel(origen, sheet_name=None, engine="openpyxl")
        faltantes = [nombre for nombre in HOJAS if nombre not in libro]
        if faltantes:
            raise ValueError("Faltan hojas requeridas: " + ", ".join(faltantes))
        datos = {hoja: _filas(libro, hoja) for hoja in HOJAS}
        resumen = {"estados": 0, "ciudades": 0, "tarifas_traslado": 0, "tarifas_hospedaje": 0,
                   "parametros": 0, "estados_cercanos": 0, "arbitros": 0, "partidos": 0}

        estados = {_normalizar(x.nombre): x for x in Estado.query.all()}
        for fila in datos["Estados"]:
            nombre = _texto(fila["nombre"], "nombre")
            estados.setdefault(_normalizar(nombre), Estado(nombre=nombre))
            if estados[_normalizar(nombre)] not in db.session:
                db.session.add(estados[_normalizar(nombre)])
            resumen["estados"] += 1
        db.session.flush()
        ciudades = {_normalizar(f"{x.nombre}|{x.estado.nombre}"): x for x in Ciudad.query.join(Estado).all()}
        for fila in datos["Ciudades"]:
            nombre, estado = _texto(fila["nombre"], "nombre"), _buscar(estados, fila["estado"], "estado")
            clave = _normalizar(f"{nombre}|{estado.nombre}")
            ciudad = ciudades.get(clave)
            if ciudad is None:
                ciudad = Ciudad(nombre=nombre, estado=estado); db.session.add(ciudad); ciudades[clave] = ciudad
            resumen["ciudades"] += 1
        db.session.flush()
        ciudades_nombre = {_normalizar(x.nombre): x for x in ciudades.values()}
        if len(ciudades_nombre) != len(ciudades):
            raise ValueError("Hay ciudades repetidas en distintos estados; use nombres de ciudad únicos en este Excel.")

        tarifas = {(x.tipo, x.medio): x for x in TarifaTraslado.query.all()}
        for fila in datos["TarifasTraslado"]:
            tipo, medio = _texto(fila["tipo"], "tipo").lower(), _texto(fila["medio"], "medio").lower()
            if tipo not in {"externo", "interno"} or medio not in {"avion", "taxi"}:
                raise ValueError("TarifasTraslado: tipo debe ser externo/interno y medio avion/taxi.")
            tarifa = tarifas.get((tipo, medio)) or TarifaTraslado(tipo=tipo, medio=medio)
            tarifa.costo_base = _decimal(fila["costo_base"], "costo_base"); db.session.add(tarifa)
            resumen["tarifas_traslado"] += 1
        for fila in datos["TarifasHospedaje"]:
            ciudad = _buscar(ciudades_nombre, fila["ciudad"], "ciudad")
            tarifa = TarifaHospedaje.query.filter_by(ciudad_id=ciudad.id).first() or TarifaHospedaje(ciudad=ciudad)
            tarifa.costo_noche = _decimal(fila["costo_noche"], "costo_noche"); db.session.add(tarifa)
            resumen["tarifas_hospedaje"] += 1
        for fila in datos["Parametros"]:
            clave = _texto(fila["clave"], "clave")
            parametro = db.session.get(Parametro, clave) or Parametro(clave=clave)
            parametro.valor = _decimal(fila["valor"], "valor"); db.session.add(parametro)
            resumen["parametros"] += 1
        for fila in datos["EstadosCercanos"]:
            a, b = _buscar(estados, fila["estado_a"], "estado_a"), _buscar(estados, fila["estado_b"], "estado_b")
            if a.id == b.id:
                raise ValueError("Un estado no puede declararse cercano a sí mismo.")
            menor, mayor = sorted((a.id, b.id))
            if not EstadoCercano.query.filter_by(estado_a_id=menor, estado_b_id=mayor).first():
                db.session.add(EstadoCercano(estado_a_id=menor, estado_b_id=mayor))
            resumen["estados_cercanos"] += 1
        for fila in datos["Arbitros"]:
            db.session.add(Arbitro(nombre=_texto(fila["nombre"], "nombre"), apellido=_texto(fila["apellido"], "apellido"),
                                  telefono=_texto(fila["telefono"], "telefono", False), email=_texto(fila["email"], "email", False),
                                  ciudad_origen=_buscar(ciudades_nombre, fila["ciudad_origen"], "ciudad_origen")))
            resumen["arbitros"] += 1
        for fila in datos["Partidos"]:
            fecha = pd.to_datetime(fila["fecha_hora"], errors="coerce")
            if pd.isna(fecha):
                raise ValueError("El campo 'fecha_hora' debe tener un formato válido.")
            db.session.add(Partido(fecha_hora=fecha.to_pydatetime(), estadio_cancha=_texto(fila["estadio_cancha"], "estadio_cancha"),
                                   ciudad_juego=_buscar(ciudades_nombre, fila["ciudad_juego"], "ciudad_juego")))
            resumen["partidos"] += 1
        db.session.commit()
        return {"status": "success", "insertados_o_actualizados": resumen}
    except Exception:
        db.session.rollback()
        raise
