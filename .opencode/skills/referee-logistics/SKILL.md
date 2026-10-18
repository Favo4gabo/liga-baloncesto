---
name: referee-logistics
description: Calcula costos de viaje, traslados externos e internos, noches de hotel, viáticos y asignaciones de árbitros de baloncesto.
license: MIT
---

# Reglas de Logística y Presupuesto Arbitral

## Misión
Eres un analista de operaciones y logística deportiva encargado de calcular de forma determinista y sin inventar cifras los viáticos de los árbitros designados a cada partido.

## Reglas e Instrucciones
1. Lógica de Traslado:
   - Si ciudad_origen_id del árbitro es IGUAL a la ciudad_juego_id del partido:
     * costo_traslado_externo = 0.
     * costo_estadia = 0.
      * costo_traslado_interno = dos tarifas internas (ida y vuelta a la cancha).
   - Si las ciudades son DIFERENTES:
      * costo_traslado_externo = dos tarifas (ida y vuelta); taxi si los estados son iguales o están configurados como cercanos, avión en los demás casos.
     * costo_estadia = costo_hotel_noche * cantidad_noches.
     * costo_traslado_interno = tarifa fija hotel-cancha.
2. Sumatoria:
   - costo_total = costo_traslado_externo + costo_traslado_interno + costo_estadia.
3. Estados Permitidos:
    - Estado de viaje: Asignado, Confirmado, En camino, En ciudad, En estadio, Finalizado.
   - Estado de pago: Pendiente, Pagado.

## Formato de Entrega
- Funciones modulares puras en Python dentro de backend/app/services/calculator.py, con tipado estricto y manejo de excepciones.
