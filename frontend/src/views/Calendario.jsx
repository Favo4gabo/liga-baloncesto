import { useEffect, useMemo, useState } from 'react'
import FullCalendar from '@fullcalendar/react'
import dayGridPlugin from '@fullcalendar/react/daygrid'
import interactionPlugin from '@fullcalendar/react/interaction'
import classicThemePlugin from '@fullcalendar/react/themes/classic'
import esLocale from '@fullcalendar/react/locales/es'
import '@fullcalendar/react/skeleton.css'
import '@fullcalendar/react/themes/classic/theme.css'
import '@fullcalendar/react/themes/classic/palette.css'
import { API_URL } from '../App.jsx'
import PanelDia from '../components/PanelDia.jsx'
import TimelineArbitros from '../components/TimelineArbitros.jsx'
import TravelProgress from '../components/TravelProgress.jsx'

const dateKey = (value) => value?.slice(0, 10)

export default function Calendario() {
  const [partidos, setPartidos] = useState([])
  const [arbitros, setArbitros] = useState([])
  const [fecha, setFecha] = useState('')
  const [cargando, setCargando] = useState(true)
  const [vista, setVista] = useState('mes')
  const [error, setError] = useState('')

  const cargarCalendario = () => Promise.all([fetch(`${API_URL}/partidos`), fetch(`${API_URL}/arbitros/`)]).then(async ([respuestaPartidos, respuestaArbitros]) => { if (!respuestaPartidos.ok || !respuestaArbitros.ok) throw new Error(); setPartidos(await respuestaPartidos.json()); setArbitros(await respuestaArbitros.json()) })
  useEffect(() => { cargarCalendario().catch(() => setError('No se pudo cargar el calendario. Verifica que el backend esté activo.')).finally(() => setCargando(false)) }, [])
  const partidosDia = useMemo(() => partidos.filter((partido) => dateKey(partido.fecha_hora) === fecha), [partidos, fecha])
  const fechaInicial = useMemo(() => (partidos[0]?.fecha_hora ? new Date(partidos[0].fecha_hora) : new Date()), [partidos])
  const events = useMemo(() => partidos.map((partido) => ({ id: String(partido.id), title: partido.estadio_cancha, start: partido.fecha_hora, classNames: [`match-${partido.estado_partido.toLowerCase().replaceAll(' ', '-')}`], extendedProps: { fecha: dateKey(partido.fecha_hora), arbitros: partido.asignaciones?.length || 0 } })), [partidos])
  const selectDate = (value) => { setFecha(value); setVista('mes') }

  return <>
    <div className="page-heading calendar-heading"><div><h2>Calendario de partidos</h2><p>Planifica las sedes, asignaciones y trayectos de árbitros de forma visual.</p></div><div className="calendar-view-switch" role="group" aria-label="Vista del calendario"><button className={vista === 'mes' ? 'active' : ''} onClick={() => setVista('mes')}>Mes</button><button className={vista === 'timeline' ? 'active' : ''} onClick={() => setVista('timeline')}>Agenda de árbitros</button></div></div>
    {error ? <div className="error-notice">{error}</div> : <>
      {vista === 'mes' ? (cargando ? <div className="loading">Cargando calendario…</div> : <div className="calendar-layout"><section className="calendar-card panel"><FullCalendar plugins={[dayGridPlugin, interactionPlugin, classicThemePlugin]} locale={esLocale} firstDay={1} initialView="dayGridMonth" initialDate={fechaInicial} headerToolbar={{ left: 'prev,next today', center: 'title', right: '' }} buttonText={{ today: 'Hoy' }} events={events} height="auto" dayMaxEvents={2} moreLinkText={(count) => `+${count} partidos`} dateClick={(info) => selectDate(info.dateStr)} eventClick={(info) => selectDate(info.event.extendedProps.fecha)} eventContent={(info) => <div className="calendar-event"><span>{info.timeText}</span><strong>{info.event.title}</strong><small>♙ {info.event.extendedProps.arbitros} árbitros</small></div>} /></section><PanelDia fecha={fecha} partidos={partidosDia} arbitros={arbitros} onClose={() => setFecha('')} onAssigned={cargarCalendario} /></div>) : <TimelineArbitros partidos={partidos} fechaInicio={dateKey(fechaInicial.toISOString())} onSelectDate={selectDate} />}
      <section className="panel calendar-table"><header className="panel-header"><h3>{fecha ? `Partidos del ${fecha}` : 'Todos los partidos'}</h3><span className="badge-soft">{fecha ? partidosDia.length : partidos.length} registros</span></header><div className="table-responsive"><table className="table data-table"><thead><tr><th>Fecha y hora</th><th>Estadio</th><th>Ciudad / Estado</th><th>Árbitros y trayecto</th><th>Estado</th></tr></thead><tbody>{(fecha ? partidosDia : partidos).map((partido) => <tr key={partido.id}><td>{new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(partido.fecha_hora))}</td><td className="match-name">{partido.estadio_cancha}</td><td>{partido.ciudad_juego ? `${partido.ciudad_juego.nombre}, ${partido.ciudad_juego.estado?.nombre || ''}` : '—'}</td><td>{partido.asignaciones?.length ? partido.asignaciones.map((asignacion) => <div className="table-assignment" key={asignacion.id}><strong>{asignacion.arbitro?.nombre} {asignacion.arbitro?.apellido}</strong><TravelProgress asignacion={asignacion} /></div>) : 'Sin asignar'}</td><td><span className="badge-soft status-badge">{partido.estado_partido}</span></td></tr>)}{!(fecha ? partidosDia : partidos).length && <tr><td colSpan="5" className="empty-cell">No hay partidos para esta selección.</td></tr>}</tbody></table></div></section>
    </>}
  </>
}
