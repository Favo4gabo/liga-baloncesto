import { Fragment } from 'react'

const dayKey = (value) => value.toISOString().slice(0, 10)
const addDays = (date, amount) => { const copy = new Date(`${date}T12:00:00`); copy.setDate(copy.getDate() + amount); return copy }

export default function TimelineArbitros({ partidos, fechaInicio, onSelectDate }) {
  const days = Array.from({ length: 14 }, (_, i) => dayKey(addDays(fechaInicio, i)))
  const rows = new Map()
  partidos.forEach((partido) => (partido.asignaciones || []).forEach((asignacion) => { if (asignacion.arbitro) { const current = rows.get(asignacion.arbitro.id) || { arbitro: asignacion.arbitro, viajes: [] }; current.viajes.push({ ...asignacion, partido }); rows.set(asignacion.arbitro.id, current) } }))
  return <section className="timeline panel"><header className="panel-header"><div><h3>Agenda de árbitros</h3><small>Próximos 14 días desde la fecha seleccionada</small></div></header><div className="timeline-scroll"><div className="timeline-grid" style={{ gridTemplateColumns: `175px repeat(${days.length}, minmax(54px, 1fr))` }}><div className="timeline-name timeline-head">Árbitro</div>{days.map((day) => <button className="timeline-head" onClick={() => onSelectDate(day)} key={day}>{new Intl.DateTimeFormat('es-ES', { weekday: 'short', day: 'numeric' }).format(new Date(`${day}T12:00:00`))}</button>)}
    {!rows.size && <div className="timeline-empty">Aún no hay asignaciones. Cuando se asignen árbitros, sus trayectos aparecerán aquí.</div>}
    {[...rows.values()].map(({ arbitro, viajes }) => <Fragment key={arbitro.id}><div className="timeline-name">{arbitro.nombre} {arbitro.apellido}</div>{days.map((day) => { const viaje = viajes.find((item) => item.partido.fecha_hora.slice(0, 10) === day); return <div className="timeline-cell" key={`${arbitro.id}-${day}`}>{viaje && <button className="timeline-trip" onClick={() => onSelectDate(day)} title={`${viaje.partido.estadio_cancha} · ${viaje.estado_viaje}`}>{viaje.estado_viaje === 'En camino' ? '✈' : '●'}</button>}</div> })}</Fragment>)}
  </div></div></section>
}
