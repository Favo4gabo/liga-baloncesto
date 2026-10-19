"""Catálogo geográfico mínimo para que una base nueva pueda operar."""

import unicodedata

from ..database import db
from ..models import Ciudad, Estado


# Capitales de los estados y Distrito Capital; no se insertan árbitros, canchas
# ni partidos ficticios. Se pueden ampliar luego importando el libro maestro.
CAPITALES_VENEZUELA = (
    ("Amazonas", "Puerto Ayacucho"),
    ("Anzoátegui", "Barcelona"),
    ("Apure", "San Fernando de Apure"),
    ("Aragua", "Maracay"),
    ("Barinas", "Barinas"),
    ("Bolívar", "Ciudad Bolívar"),
    ("Carabobo", "Valencia"),
    ("Cojedes", "San Carlos"),
    ("Delta Amacuro", "Tucupita"),
    ("Falcón", "Coro"),
    ("Guárico", "San Juan de los Morros"),
    ("La Guaira", "La Guaira"),
    ("Lara", "Barquisimeto"),
    ("Mérida", "Mérida"),
    ("Miranda", "Los Teques"),
    ("Monagas", "Maturín"),
    ("Nueva Esparta", "La Asunción"),
    ("Portuguesa", "Guanare"),
    ("Sucre", "Cumaná"),
    ("Táchira", "San Cristóbal"),
    ("Trujillo", "Trujillo"),
    ("Yaracuy", "San Felipe"),
    ("Zulia", "Maracaibo"),
    ("Distrito Capital", "Caracas"),
    # Sede habitual de la liga, además de Barcelona que es la capital del estado.
    ("Anzoátegui", "Puerto La Cruz"),
)


def _clave(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", str(texto or "").strip().casefold())
    return "".join(caracter for caracter in normalizado if not unicodedata.combining(caracter))


def asegurar_catalogo_geografico() -> tuple[int, int]:
    """Agrega estados/capitales faltantes, sin borrar ni reemplazar registros."""
    estados = {_clave(estado.nombre): estado for estado in Estado.query.all()}
    nuevos_estados = 0
    for nombre_estado, _ in CAPITALES_VENEZUELA:
        clave = _clave(nombre_estado)
        if clave not in estados:
            estado = Estado(nombre=nombre_estado)
            db.session.add(estado)
            estados[clave] = estado
            nuevos_estados += 1
    if nuevos_estados:
        db.session.flush()

    ciudades = {
        (_clave(ciudad.nombre), _clave(ciudad.estado.nombre)): ciudad
        for ciudad in Ciudad.query.join(Estado).all()
    }
    nuevas_ciudades = 0
    for nombre_estado, nombre_ciudad in CAPITALES_VENEZUELA:
        estado = estados[_clave(nombre_estado)]
        clave = (_clave(nombre_ciudad), _clave(estado.nombre))
        if clave not in ciudades:
            ciudad = Ciudad(nombre=nombre_ciudad, estado=estado)
            db.session.add(ciudad)
            ciudades[clave] = ciudad
            nuevas_ciudades += 1

    if nuevos_estados or nuevas_ciudades:
        db.session.commit()
    return nuevos_estados, nuevas_ciudades
