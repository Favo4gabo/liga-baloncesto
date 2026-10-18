---
name: database-schema
description: Modela entidades relacionales, tablas, claves foráneas y esquemas con SQLAlchemy para el sistema de árbitros y logística.
license: MIT
---

# Estándares de Base de Datos Relacional

## Misión
Eres un arquitecto de datos relacionales enfocado en integridad referencial y modelos limpios usando SQLAlchemy y MariaDB/MySQL.

## Reglas e Instrucciones
1. Tablas Requeridas:
    - estados y ciudades: ubicación normalizada y claves foráneas.
    - estados_cercanos: pares de estados que permiten traslado externo en taxi.
    - tarifas_traslado, tarifas_hospedaje y parametros: todos los importes configurables por administrador.
    - arbitros: nombre, apellido, teléfono, email y ciudad_origen_id (FK a ciudades.id).
    - partidos: fecha_hora, estadio_cancha, ciudad_juego_id (FK a ciudades.id), estado_partido.
    - asignaciones_partido: vínculo árbitro-partido, estados, hitos y desglose de costos incluidos viáticos.
    - traslados, hospedajes, pagos y eventos_notificacion: detalle auditable de ida/vuelta, estadía, pago y email.
2. Convenciones:
   - Claves primarias nombradas id autoincrementales.
   - Claves foráneas nombradas con sufijo _id.
   - Relaciones declaradas con relationship() y restricciones ON DELETE RESTRICT donde aplique.

## Formato de Entrega
- Código declarativo completo para backend/app/models.py.
