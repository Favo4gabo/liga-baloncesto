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
        ["Amazonas"], ["Anzoátegui"], ["Apure"], ["Aragua"], ["Barinas"], ["Bolívar"],
        ["Carabobo"], ["Cojedes"], ["Delta Amacuro"], ["Falcón"], ["Guárico"], ["La Guaira"],
        ["Lara"], ["Mérida"], ["Miranda"], ["Monagas"], ["Nueva Esparta"], ["Portuguesa"],
        ["Sucre"], ["Táchira"], ["Trujillo"], ["Yaracuy"], ["Zulia"],
        ["Distrito Capital"],
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
    "DistanciasCiudades": [
        ["ciudad_origen", "ciudad_destino", "distancia_km"],
        ["Caracas", "Los Teques", 28], ["Caracas", "Valencia", 160], ["Caracas", "Maracay", 110],
        ["Caracas", "Maracaibo", 700], ["Caracas", "Barquisimeto", 350], ["Caracas", "Puerto La Cruz", 320],
        ["Caracas", "Merida", 680], ["Valencia", "Maracay", 70], ["Valencia", "Maracaibo", 540],
        ["Valencia", "Barquisimeto", 190], ["Valencia", "Puerto La Cruz", 410], ["Valencia", "Merida", 530],
        ["Maracay", "Maracaibo", 620], ["Maracay", "Barquisimeto", 270], ["Maracay", "Puerto La Cruz", 390],
        ["Maracay", "Merida", 610], ["Maracaibo", "Barquisimeto", 310], ["Maracaibo", "Puerto La Cruz", 980],
        ["Maracaibo", "Merida", 420], ["Barquisimeto", "Puerto La Cruz", 590], ["Barquisimeto", "Merida", 330],
        ["Puerto La Cruz", "Merida", 760], ["Los Teques", "Valencia", 140], ["Los Teques", "Maracay", 95],
    ],
    "UbicacionesCancha": [
        ["estadio_cancha", "ciudad", "direccion", "latitud", "longitud"],
        ["Gimnasio Cubierto de Caracas", "Caracas", "Parque Naciones Unidas", 10.4806, -66.9113],
        ["Forum de Valencia", "Valencia", "Naguanagua, Carabobo", 10.2182, -68.0106],
        ["Coliseo El Limon", "Maracay", "El Limón, Aragua", 10.3062, -67.6323],
        ["Palacio de Eventos Maracaibo", "Maracaibo", "Avenida Guajira", 10.7090, -71.6320],
        ["Domo Bolivariano", "Barquisimeto", "Avenida Libertador", 10.0623, -69.3234],
        ["Gimnasio Luis Ramos", "Puerto La Cruz", "Avenida Municipal", 10.2069, -64.6347],
        ["Cinco Águilas Blancas", "Merida", "Avenida Las Américas", 8.5897, -71.1510],
    ],
    "Aeropuertos": [
        ["estado", "ciudad_sede", "nombre", "codigo_iata", "latitud", "longitud"],
        ["La Guaira", "Maiquetía / Caracas", 'Aeropuerto Internacional de Maiquetía "Simón Bolívar"', "MIQ", 10.6012, -66.9912],
        ["Zulia", "Maracaibo", 'Aeropuerto Internacional "La Chinita"', "MAR", 10.5582, -71.7279],
        ["Carabobo", "Valencia", 'Aeropuerto Internacional "Arturo Michelena"', "VLN", 10.1497, -67.9284],
        ["Lara", "Barquisimeto", 'Aeropuerto Internacional "Jacinto Lara"', "BRM", 10.0427, -69.3586],
        ["Nueva Esparta", "Porlamar / Isla de Margarita", 'Aeropuerto Internacional del Caribe "Santiago Mariño"', "PMV", 10.9126, -63.9666],
        ["Anzoátegui", "Barcelona / Puerto La Cruz", 'Aeropuerto Internacional "General José Antonio Anzoátegui"', "BLA", 10.1071, -64.6892],
        ["Bolívar", "Ciudad Guayana / Puerto Ordaz", 'Aeropuerto Internacional "Manuel Carlos Piar"', "PZO", 8.2885, -62.7604],
        ["Táchira", "Santo Domingo del Táchira / San Cristóbal", 'Aeropuerto "Mayor Buenaventura Vivas Guerrero"', "STD", 7.5654, -72.0351],
        ["Táchira", "San Antonio del Táchira", 'Aeropuerto Internacional "Juan Vicente Gómez"', "SVZ", 7.8408, -72.4397],
        ["Falcón", "Las Piedras / Punto Fijo", 'Aeropuerto Internacional "Josefa Camejo"', "LSP", 11.7808, -70.1515],
        ["Mérida", "El Vigía", 'Aeropuerto Internacional "Juan Pablo Pérez Alfonzo"', "VIG", 8.6241, -71.6727],
        ["Mérida", "Mérida", 'Aeropuerto Nacional "Alberto Carnevalli"', "MRD", 8.5821, -71.1610],
        ["Monagas", "Maturín", 'Aeropuerto Internacional "General José Tadeo Monagas"', "MUN", 9.7545, -63.1474],
        ["Sucre", "Cumaná", 'Aeropuerto Internacional "Antonio José de Sucre"', "CUM", 10.4503, -64.1305],
        ["Amazonas", "Puerto Ayacucho", 'Aeropuerto Nacional "Cacique Aramare"', "PYH", 5.6199, -67.6061],
        ["Barinas", "Barinas", 'Aeropuerto Nacional "Luisa Cáceres de Arismendi"', "BNS", 8.6195, -70.2142],
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
