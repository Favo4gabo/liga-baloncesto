import { useEffect, useMemo, useState } from 'react'

function progressAt(asignacion) {
  const viaje = asignacion.tiempo_traslado
  if (!viaje?.fecha_llegada_estimada || !asignacion.fecha_salida) return viaje?.porcentaje_progreso || 0
  const start = new Date(asignacion.fecha_salida).getTime()
  const end = new Date(viaje.fecha_llegada_estimada).getTime()
  if (Date.now() <= start) return 0
  if (Date.now() >= end) return 100
  return Math.round(((Date.now() - start) / (end - start)) * 100)
}

const transportLabel = { avion: 'Vuelo comercial', taxi: 'Traslado terrestre', local: 'Movilización local' }
const transportIcon = { avion: '✈', taxi: '🚕', local: '⌁' }

export default function TravelProgress({ asignacion, compact = false }) {
  const viaje = asignacion.tiempo_traslado
  const [progreso, setProgreso] = useState(() => progressAt(asignacion))
  const externo = asignacion.traslados?.find((t) => t.tipo === 'externo' && t.sentido === 'ida')
  const tipo = viaje?.tipo_transporte || externo?.medio || 'local'
  const rutaAerea = viaje?.ruta_aerea
  const estadoViaje = asignacion.estado_viaje || 'Asignado'
  const estadoClase = estadoViaje.toLowerCase().replaceAll(' ', '-')

  useEffect(() => { const update = () => setProgreso(progressAt(asignacion)); update(); const timer = setInterval(update, 30000); return () => clearInterval(timer) }, [asignacion])
  const salida = useMemo(() => asignacion.fecha_salida ? new Intl.DateTimeFormat('es-ES', { hour: '2-digit', minute: '2-digit' }).format(new Date(asignacion.fecha_salida)) : null, [asignacion.fecha_salida])
  const llegada = useMemo(() => viaje?.fecha_llegada_estimada ? new Intl.DateTimeFormat('es-ES', { hour: '2-digit', minute: '2-digit' }).format(new Date(viaje.fecha_llegada_estimada)) : null, [viaje?.fecha_llegada_estimada])

  if (!viaje && !externo) return <div className="travel-local-state"><span className="travel-local">Sin traslado interurbano</span><span className={`travel-status-badge ${estadoClase}`}>{estadoViaje}</span></div>
  return <div className={`travel-progress ${compact ? 'travel-progress-compact' : ''}`}>
    <div className="travel-progress-meta"><span>{transportIcon[tipo]} {transportLabel[tipo]}</span><strong>{viaje?.duracion_estimada_texto || 'Pendiente'} · {progreso}%</strong><span className={`travel-status-badge ${estadoClase}`}>{estadoViaje}</span></div>
    {!compact && <div className="travel-distance"><span>{viaje?.distancia_km ? `${viaje.distancia_km} km${rutaAerea ? ' aéreos' : ''}` : 'Distancia pendiente'}</span><span>{viaje?.velocidad_kmh ? `${viaje.velocidad_kmh} km/h + ${viaje.margen_logistico_minutos} min logística` : ''}</span></div>}
    {!compact && rutaAerea && <div className="airport-route"><span>{rutaAerea.origen.codigo_iata}</span><i>✈</i><span>{rutaAerea.destino.codigo_iata}</span><small>{rutaAerea.origen.ciudad_sede} → {rutaAerea.destino.ciudad_sede}</small></div>}
    <div className="travel-track" aria-label={`Progreso estimado de traslado: ${progreso}%`}><span className="travel-fill" style={{ width: `${progreso}%` }} /><span className="travel-vehicle" style={{ left: `${Math.max(5, Math.min(progreso, 96))}%` }}>{transportIcon[tipo]}</span></div>
    {!compact && (salida || llegada) && <div className="travel-times"><span>Salida {salida || 'por definir'}</span><span>Llegada estimada {llegada || 'por definir'}</span></div>}
  </div>
}
