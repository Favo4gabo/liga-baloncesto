import TravelProgress from './TravelProgress.jsx'
import FormularioAsignacion from './FormularioAsignacion.jsx'

const textDate = (date) => new Intl.DateTimeFormat('es-ES', { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date(`${date}T12:00:00`))
const time = (value) => new Intl.DateTimeFormat('es-ES', { hour: '2-digit', minute: '2-digit' }).format(new Date(value))
const logisticsTime = (value) => value ? new Intl.DateTimeFormat('es-VE', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) : '—'

export default function PanelDia({ fecha, partidos, arbitros, onClose, onAssigned }) {
  if (!fecha) return <aside className="day-panel panel"><div className="day-panel-empty"><span>◫</span><h3>Selecciona un día</h3><p>Elige una fecha en el calendario para ver partidos, árbitros y trayectos.</p></div></aside>
  const asignaciones = partidos.flatMap((p) => p.asignaciones || [])
  return <aside className="day-panel panel"><header className="panel-header"><div><span className="eyebrow">OPERACIÓN DEL DÍA</span><h3>{textDate(fecha)}</h3></div><button className="icon-button" onClick={onClose} aria-label="Cerrar detalle">×</button></header><div className="day-panel-content">
    <div className="day-summary"><span><strong>{partidos.length}</strong> partidos</span><span><strong>{asignaciones.length}</strong> árbitros</span></div>
    {!partidos.length && <p className="empty-day">No hay partidos programados para este día.</p>}
    {partidos.map((partido) => <article className="day-match" key={partido.id}><div className="day-match-title"><time>{time(partido.fecha_hora)}</time><div><strong>{partido.estadio_cancha}</strong><small>{partido.ciudad_juego?.nombre}, {partido.ciudad_juego?.estado?.nombre}</small>{partido.ubicacion_cancha?.direccion && <small className="venue-location">⌖ {partido.ubicacion_cancha.direccion}</small>}</div></div><span className="badge-soft">{partido.estado_partido}</span>
      {partido.asignaciones?.length ? <div className="assignment-list">{partido.asignaciones.map((asignacion) => <div className="assignment-card" key={asignacion.id}><div className="assignment-name"><span className="referee-avatar">{asignacion.arbitro?.nombre?.[0]}{asignacion.arbitro?.apellido?.[0]}</span><div><strong>{asignacion.arbitro?.nombre} {asignacion.arbitro?.apellido}</strong><small>{asignacion.estado_viaje}</small></div></div><TravelProgress asignacion={asignacion} />{asignacion.plan_logistico && <div className="logistics-plan"><span>⌂ Ciudad sede: <strong>{logisticsTime(asignacion.plan_logistico.fecha_llegada_ciudad_recomendada)}</strong></span><span>◷ En cancha: <strong>{logisticsTime(asignacion.plan_logistico.fecha_llegada_estadio_recomendada)}</strong></span></div>}{asignacion.hospedaje && <small className="lodging">⌂ {asignacion.hospedaje.noches} noche(s){asignacion.hospedaje.hotel ? ` · ${asignacion.hospedaje.hotel}` : ''}</small>}</div>)}</div> : <p className="unassigned">Sin árbitros asignados</p>}<FormularioAsignacion partido={partido} arbitros={arbitros} onCreated={onAssigned} />
    </article>)}
  </div></aside>
}
