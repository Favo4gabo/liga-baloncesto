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

const dateKey = (value) => value?.slice(0, 10)

export default function Calendario() {
  const [partidos, setPartidos] = useState([])
  const [arbitros, setArbitros] = useState([])
  const [fecha, setFecha] = useState('')
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')

  const cargarCalendario = () => Promise.all([fetch(`${API_URL}/partidos`), fetch(`${API_URL}/arbitros/`)]).then(async ([respuestaPartidos, respuestaArbitros]) => {
    if (!respuestaPartidos.ok || !respuestaArbitros.ok) throw new Error('No se pudo cargar el calendario.')
    setPartidos(await respuestaPartidos.json())
    setArbitros(await respuestaArbitros.json())
  })

  useEffect(() => {
    cargarCalendario()
      .catch(() => setError('No se pudo cargar el calendario. Verifica que el backend esté activo.'))
      .finally(() => setCargando(false))
  }, [])

  const partidosDia = useMemo(() => partidos.filter((partido) => dateKey(partido.fecha_hora) === fecha), [partidos, fecha])
  const fechaInicial = useMemo(() => partidos[0]?.fecha_hora ? new Date(partidos[0].fecha_hora) : new Date(), [partidos])
  const events = useMemo(() => partidos.map((partido) => ({
    id: String(partido.id),
    title: partido.estadio_cancha,
    start: partido.fecha_hora,
    classNames: [`match-${partido.estado_partido.toLowerCase().replaceAll(' ', '-')}`],
    extendedProps: { fecha: dateKey(partido.fecha_hora), arbitros: partido.asignaciones?.length || 0 },
  })), [partidos])

  const selectDate = (value) => setFecha(value)

  return <>
    <div className="page-heading calendar-heading">
      <div><h2>Calendario de partidos</h2><p>Selecciona un día para consultar sus sedes, árbitros y costos.</p></div>
    </div>
    {error ? <div className="error-notice">{error}</div> : cargando ? <div className="loading">Cargando calendario…</div> : (
      <div className="calendar-layout">
        <section className="calendar-card panel">
          <FullCalendar
            plugins={[dayGridPlugin, interactionPlugin, classicThemePlugin]}
            locale={esLocale}
            firstDay={1}
            initialView="dayGridMonth"
            initialDate={fechaInicial}
            headerToolbar={{ left: 'prev,next today', center: 'title', right: '' }}
            buttonText={{ today: 'Hoy' }}
            events={events}
            height="auto"
            dayMaxEvents={2}
            moreLinkText={(count) => `+${count} partidos`}
            dateClick={(info) => selectDate(info.dateStr)}
            eventClick={(info) => selectDate(info.event.extendedProps.fecha)}
            eventContent={(info) => <div className="calendar-event"><span>{info.timeText}</span><strong>{info.event.title}</strong><small>♙ {info.event.extendedProps.arbitros}/2 árbitros</small></div>}
          />
        </section>
        {fecha && <PanelDia fecha={fecha} partidos={partidosDia} arbitros={arbitros} onClose={() => setFecha('')} onAssigned={cargarCalendario} />}
      </div>
    )}
  </>
}
