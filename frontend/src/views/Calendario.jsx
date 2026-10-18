import { useEffect, useMemo, useState } from 'react'
import FullCalendar from '@fullcalendar/react'
import dayGridPlugin from '@fullcalendar/react/daygrid'
import interactionPlugin from '@fullcalendar/react/interaction'
import classicThemePlugin from '@fullcalendar/react/themes/classic'
import esLocale from '@fullcalendar/react/locales/es'
import '@fullcalendar/react/skeleton.css'
import '@fullcalendar/react/themes/classic/theme.css'
import '@fullcalendar/react/themes/classic/palette.css'
import PanelDia from '../components/PanelDia.jsx'
import { getCachedLeagueData, loadLeagueData } from '../services/leagueData.js'

const dateKey = (value) => value?.slice(0, 10)

export default function Calendario() {
  const cachedData = getCachedLeagueData()
  const [partidos, setPartidos] = useState(() => cachedData?.partidos || [])
  const [arbitros, setArbitros] = useState(() => cachedData?.arbitros || [])
  const [fecha, setFecha] = useState('')
  const [cargando, setCargando] = useState(!cachedData)
  const [error, setError] = useState('')

  const aplicarDatos = (datos) => { setPartidos(datos.partidos); setArbitros(datos.arbitros) }
  const cargarCalendario = () => loadLeagueData({ refresh: true }).then(aplicarDatos)

  useEffect(() => {
    let cancelled = false
    loadLeagueData({ refresh: Boolean(getCachedLeagueData()) })
      .then((datos) => { if (!cancelled) aplicarDatos(datos) })
      .catch(() => setError('No se pudo cargar el calendario. Verifica que el backend esté activo.'))
      .finally(() => { if (!cancelled) setCargando(false) })
    return () => { cancelled = true }
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
    {error && <div className="error-notice">{error}</div>}
    {cargando ? <div className="loading">Cargando calendario…</div> : (
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
