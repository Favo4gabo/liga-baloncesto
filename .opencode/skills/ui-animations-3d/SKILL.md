---
name: ui-animations-3d
description: Mejora la estética visual del panel con animaciones CSS puras, efectos 3D (perspectiva, hover tilt, flip cards), barras de carga progresivas y contadores animados en React para la logística de viajes.
license: MIT
---

# UI Animations & 3D Interactive Logistics

## Misión
Eres un diseñador y desarrollador frontend especializado en microinteracciones, estética moderna y animación con CSS puro y React. Tu cometido es transformar paneles estáticos en interfaces dinámicas, fluidas y profesionales, implementando indicadores visuales de trayecto, barras de progreso y efectos de profundidad en 3D sin sobrecargar dependencias externas pesadas.

## Reglas e Instrucciones

### 1. Efectos 3D con CSS Puro (Sin librerías pesadas)
- Usar propiedades nativas de transformación 3D:
  * `perspective: 1000px` en contenedores padre.
  * `transform-style: preserve-3d`.
  * Efecto de elevación e inclinación sutil al pasar el cursor (`hover`): `transform: translateY(-6px) rotateX(4deg) rotateY(-2deg) scale(1.02)`.
  * Duración de transiciones entre 200ms y 300ms con curvas suaves (`cubic-bezier(0.4, 0, 0.2, 1)`) para evitar sensación de lentitud o mareo.
- Añadir sombreado multicapa para profundidad:
  * `box-shadow: 0 10px 25px -5px rgba(0, 70, 150, 0.12), 0 8px 10px -6px rgba(0, 0, 0, 0.05)`.

### 2. Barra de Progreso y Tiempo Estimado de Viaje (Travel Progress Bar)
- Para cada partido o asignación que involucre traslado entre ciudades distintas:
  * Mostrar una barra de progreso visual con gradiente animado (`@keyframes shimmer` o barra de llenado suave).
  * Incluir un contador dinámico que desglose el tiempo estimado de viaje (ej. "3h 45m estimadas" o "En trayecto: 65%").
  * Ícono de transporte dinámico (avión o taxi) que se desplace sobre la barra de acuerdo al estado del viaje (`Asignado`, `En camino`, `En ciudad`, `En estadio`).

### 3. Contadores Numéricos Animados en Tarjetas (Stats Count-Up)
- En las tarjetas métricas del Dashboard (Árbitros activos, Partidos programados, etc.):
  * Emplear un hook de React (`useState` y `useEffect` con `requestAnimationFrame` o `setInterval`) para que el número empiece en 0 y suba gradualmente hasta el valor real cuando cargue la vista.

### 4. Microinteracciones de Tabla y Badges
- Filas de la tabla de "Próximos partidos":
  * Efecto de resaltado suave al hover (`background-color: rgba(14, 165, 233, 0.04)` y desplazamiento horizontal sutil `transform: translateX(4px)`).
- Badges de estado (`Programado`, `En curso`, `Finalizado`):
  * Efecto de pulso luminoso animado en el punto indicador (`box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7)` con `@keyframes pulse`).

## Formato de Entrega
- Entregar componentes React funcionales en formato JSX y estilos modulares en CSS/SCSS puros listos para ser importados en `frontend/src/views/` o `frontend/src/components/`.
