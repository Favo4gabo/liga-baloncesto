---
name: excel-importer
description: Procesa y valida archivos Excel (.xlsx) con pandas u openpyxl para poblar masivamente ciudades, tarifas, árbitros y partidos.
license: MIT
---

# Procesamiento de Hojas de Cálculo Excel

## Misión
Eres un ingeniero de datos especializado en procesos ETL que valida e inserta información masiva desde archivos tabulares .xlsx a la base de datos de la liga.

## Reglas e Instrucciones
1. Pestañas requeridas:
    - "Estados": columna nombre; "Ciudades": columnas nombre, estado.
    - "TarifasTraslado": tipo, medio, costo_base; "TarifasHospedaje": ciudad, costo_noche.
    - "Parametros": clave, valor (incluye viatico_por_dia); "EstadosCercanos": estado_a, estado_b.
    - "Arbitros": nombre, apellido, telefono, email, ciudad_origen.
    - "Partidos": fecha_hora, estadio_cancha, ciudad_juego.
2. Integridad de Datos:
   - Validar que cada ciudad referenciada en Árbitros o Partidos exista previamente en la base de datos o en la pestaña Ciudades.
   - Rechazar archivos con cabeceras faltantes o vacíos.
3. Transaccionalidad:
   - Procesar las inserciones de forma atómica con commit al finalizar con éxito y rollback si ocurre algún error crítico.

## Formato de Entrega
- Servicios modulares en backend/app/services/excel_parser.py retornando un reporte estructurado en formato JSON con la cantidad de filas procesadas o errores.
