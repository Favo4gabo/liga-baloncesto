"""Genera un libro Excel de ejemplo con la estructura que espera el importador.

Uso:
    python backend/scripts/generar_plantilla.py ruta/salida.xlsx
"""

from __future__ import annotations

import sys
from datetime import datetime

from openpyxl import Workbook


HOJAS: dict[str, list[list]] = {
    "Estados": [
        ["nombre"],
        ["Distrito Capital"],
        ["Miranda"],
        ["Carabobo"],
        ["Aragua"],
        ["Zulia"],
        ["Lara"],
        ["Anzoategui"],
        ["Merida"],
    ],
    "Ciudades": [
        ["nombre", "estado"],
        ["Caracas", "Distrito Capital"],
        ["Los Teques", "Miranda"],
        ["Valencia", "Carabobo"],
        ["Maracay", "Aragua"],
        ["Maracaibo", "Zulia"],
        ["Barquisimeto", "Lara"],
        ["Puerto La Cruz", "Anzoategui"],
        ["Merida", "Merida"],
    ],
    "TarifasTraslado": [
        ["tipo", "medio", "costo_base"],
        ["externo", "avion", 180.00],
        ["externo", "taxi", 85.00],
        ["interno", "taxi", 12.00],
    ],
    "TarifasHospedaje": [
        ["ciudad", "costo_noche"],
        ["Caracas", 45.00],
        ["Valencia", 38.00],
        ["Maracay", 35.00],
        ["Maracaibo", 42.00],
        ["Barquisimeto", 34.00],
        ["Puerto La Cruz", 36.00],
        ["Merida", 33.00],
        ["Los Teques", 40.00],
    ],
    "Parametros": [
        ["clave", "valor"],
        ["viatico_por_dia", 25.00],
    ],
    "EstadosCercanos": [
        ["estado_a", "estado_b"],
        ["Distrito Capital", "Miranda"],
        ["Carabobo", "Aragua"],
    ],
    "Arbitros": [
        ["nombre", "apellido", "telefono", "email", "ciudad_origen"],
        ["Luis", "Perez", "0414-1111111", "luis.perez@liga.local", "Caracas"],
        ["Jose", "Rodriguez", "0414-2222222", "jose.rodriguez@liga.local", "Valencia"],
        ["Maria", "Gonzalez", "0414-3333333", "maria.gonzalez@liga.local", "Maracay"],
        ["Pedro", "Martinez", "0414-4444444", "pedro.martinez@liga.local", "Maracaibo"],
        ["Ana", "Fernandez", "0414-5555555", "ana.fernandez@liga.local", "Barquisimeto"],
        ["Carlos", "Ramirez", "0414-6666666", "carlos.ramirez@liga.local", "Puerto La Cruz"],
        ["Jorge", "Sanchez", "0414-7777777", "jorge.sanchez@liga.local", "Merida"],
        ["Daniela", "Torres", "0414-8888888", "daniela.torres@liga.local", "Los Teques"],
    ],
    "Partidos": [
        ["fecha_hora", "estadio_cancha", "ciudad_juego"],
        [datetime(2026, 11, 5, 18, 0), "Gimnasio Cubierto de Caracas", "Caracas"],
        [datetime(2026, 11, 7, 19, 30), "Forum de Valencia", "Valencia"],
        [datetime(2026, 11, 9, 17, 0), "Coliseo El Limon", "Maracay"],
        [datetime(2026, 11, 14, 20, 0), "Palacio de Eventos Maracaibo", "Maracaibo"],
        [datetime(2026, 11, 16, 18, 30), "Domo Bolivariano", "Barquisimeto"],
        [datetime(2026, 11, 21, 19, 0), "Gimnasio Luis Ramos", "Puerto La Cruz"],
        [datetime(2026, 11, 23, 16, 0), "Cinco Águilas Blancas", "Merida"],
    ],
}


def generar(ruta: str) -> str:
    libro = Workbook()
    libro.remove(libro.active)
    for nombre, filas in HOJAS.items():
        hoja = libro.create_sheet(nombre)
        for fila in filas:
            hoja.append(fila)
    libro.save(ruta)
    return ruta


if __name__ == "__main__":
    destino = sys.argv[1] if len(sys.argv) > 1 else "plantilla_liga.xlsx"
    print(f"Plantilla generada en: {generar(destino)}")
