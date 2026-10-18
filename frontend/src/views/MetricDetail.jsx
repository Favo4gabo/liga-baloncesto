import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { getCachedLeagueData, loadLeagueData } from '../services/leagueData.js'
import RefereeCount from '../components/RefereeCount.jsx'
import MonthPicker from '../components/MonthPicker.jsx'

const currentMonth = () => {
  const today = new Date()
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`
}
const money = (value) => Number(value || 0).toLocaleString('es-VE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const dateTime = (value) => value ? new Intl.DateTimeFormat('es-VE', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'

export default function MetricDetail() {
  const { pathname } = useLocation()
  const cachedData = getCachedLeagueData()
  const [arbitros, setArbitros] = useState(() => cachedData?.arbitros || [])
  const [partidos, setPartidos] = useState(() => cachedData?.partidos || [])
  const [mes, setMes] = useState(currentMonth)
  const [cargando, setCargando] = useState(!cachedData)
  const [error, setError] = useState('')
  const [selectedArbitroId, setSelectedArbitroId] = useState(null)

  useEffect(() => {
    let cancelled = false
    loadLeagueData({ refresh: Boolean(getCachedLeagueData()) })
      .then((data) => { if (!cancelled) { setArbitros(data.arbitros); setPartidos(data.partidos) } })
      .catch((err) => { if (!cancelled) setError(err.message) })
      .finally(() => { if (!cancelled) setCargando(false) })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!selectedArbitroId) return undefined
    const closeOnEscape = (event) => { if (event.key === 'Escape') setSelectedArbitroId(null) }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [selectedArbitroId])

  const tipo = pathname === '/arbitros' ? 'arbitros'
    : pathname === '/asignaciones' ? 'asignaciones' : 'partidos'
  const titulos = {
    arbitros: ['Árbitros y gastos mensuales', 'Gasto logístico de cada árbitro según los partidos del mes seleccionado.'],
    partidos: ['Partidos registrados', 'Sedes, fechas y nivel de asignación arbitral de cada partido.'],
    asignaciones: ['Asignaciones arbitrales', 'Árbitros convocados, estado de viaje, pago y costo logístico por partido.'],
  }

  const partidosDelMes = useMemo(() => partidos.filter((partido) => partido.fecha_hora?.slice(0, 7) === mes), [partidos, mes])
  const totalesPorArbitro = useMemo(() => {
    const totals = new Map(arbitros.map((arbitro) => [arbitro.id, {
      juegos: 0, externo: 0, interno: 0, estadia: 0, viaticos: 0, total: 0,
    }]))
    partidosDelMes.forEach((partido) => (partido.asignaciones || []).forEach((asignacion) => {
      const total = totals.get(asignacion.arbitro_id)
      if (!total) return
      total.juegos += 1
      total.externo += Number(asignacion.costo_traslado_externo || 0)
      total.interno += Number(asignacion.costo_traslado_interno || 0)
      total.estadia += Number(asignacion.costo_estadia || 0)
      total.viaticos += Number(asignacion.costo_viaticos || 0)
      total.total += Number(asignacion.costo_total || 0)
    }))
    return totals
  }, [arbitros, partidosDelMes])

  let filteredGames = partidos
  if (tipo === 'asignaciones') filteredGames = partidosDelMes

  const asignacionesDelMes = filteredGames.flatMap((partido) => (partido.asignaciones || []).map((asignacion) => ({ partido, asignacion })))
  const showMonth = tipo === 'arbitros' || tipo === 'asignaciones'
  const selectedArbitro = arbitros.find((arbitro) => arbitro.id === selectedArbitroId)
  const juegosDelArbitro = selectedArbitro ? partidosDelMes.flatMap((partido) => (partido.asignaciones || [])
    .filter((asignacion) => asignacion.arbitro_id === selectedArbitro.id)
    .map((asignacion) => ({ partido, asignacion }))) : []
  const gastoArbitroSeleccionado = juegosDelArbitro.reduce((total, item) => total + Number(item.asignacion.costo_total || 0), 0)

  return <>
    <div className="page-heading detail-page-heading">
      <div><Link className="back-link" to="/dashboard">← Volver al resumen</Link><h2>{titulos[tipo][0]}</h2><p>{titulos[tipo][1]}</p></div>
      {showMonth && <MonthPicker className="month-filter" label="Mes de los partidos" value={mes} onChange={setMes} />}
    </div>
    {error && <div className="error-notice">{error}</div>}
    {cargando ? <div className="loading">Cargando información…</div> : tipo === 'arbitros' ? (
      <section className="panel">
        <header className="panel-header"><h3>Árbitros registrados · {partidosDelMes.length} partidos en el mes</h3><span className="badge-soft">{arbitros.length} árbitros</span></header>
        <div className="table-responsive"><table className="table data-table cost-table"><thead><tr><th>Árbitro</th><th>Ciudad / estado de origen</th><th>Juegos</th><th>Transporte externo</th><th>Transporte interno</th><th>Estadía</th><th>Viáticos</th><th>Total del mes</th></tr></thead>
          <tbody>{arbitros.map((arbitro) => {
            const totals = totalesPorArbitro.get(arbitro.id)
            return <tr key={arbitro.id}><td><button className="referee-name-button" type="button" onClick={() => setSelectedArbitroId(arbitro.id)}>{arbitro.nombre} {arbitro.apellido}<small>Ver sus partidos</small></button></td><td>{arbitro.ciudad_origen?.nombre || '—'}{arbitro.ciudad_origen?.estado?.nombre ? `, ${arbitro.ciudad_origen.estado.nombre}` : ''}</td><td>{totals.juegos}</td><td>{money(totals.externo)}</td><td>{money(totals.interno)}</td><td>{money(totals.estadia)}</td><td>{money(totals.viaticos)}</td><td className="monthly-total">{money(totals.total)}</td></tr>
          })}{!arbitros.length && <tr><td colSpan="8" className="empty-cell">No hay árbitros registrados.</td></tr>}</tbody>
        </table></div>
        <p className="table-footnote">El gasto se agrupa por mes de la fecha del partido e incluye solo asignaciones registradas. Importes en la moneda de las tarifas cargadas.</p>
      </section>
    ) : tipo === 'asignaciones' ? (
      <section className="panel"><header className="panel-header"><h3>Asignaciones de {mes}</h3><span className="badge-soft">{asignacionesDelMes.length} árbitros asignados</span></header>
        <div className="table-responsive"><table className="table data-table"><thead><tr><th>Fecha / partido</th><th>Árbitro y origen</th><th>Asignación</th><th>Viaje</th><th>Total logístico</th></tr></thead><tbody>
           {asignacionesDelMes.map(({ partido, asignacion }) => <tr key={asignacion.id}><td>{dateTime(partido.fecha_hora)}<small className="table-subline">{partido.estadio_cancha} · {partido.ciudad_juego?.nombre}</small></td><td className="match-name">{asignacion.arbitro?.nombre} {asignacion.arbitro?.apellido}<small className="table-subline">{asignacion.arbitro?.ciudad_origen?.nombre}, {asignacion.arbitro?.ciudad_origen?.estado?.nombre}</small></td><td><RefereeCount assignments={partido.asignaciones || []} required={partido.arbitros_requeridos || 2} /></td><td><span className="badge-soft">{asignacion.estado_viaje}</span></td><td className="monthly-total">{money(asignacion.costo_total)}</td></tr>)}
          {!asignacionesDelMes.length && <tr><td colSpan="5" className="empty-cell">No hay asignaciones para este mes.</td></tr>}
        </tbody></table></div>
      </section>
    ) : (
      <section className="panel"><header className="panel-header"><h3>Todos los partidos</h3><span className="badge-soft">{filteredGames.length} partidos</span></header>
        <div className="table-responsive"><table className="table data-table"><thead><tr><th>Fecha y hora</th><th>Partido / cancha</th><th>Ciudad / estado</th><th>Árbitros asignados</th><th>Estado</th></tr></thead><tbody>
           {filteredGames.map((partido) => <tr key={partido.id}><td>{dateTime(partido.fecha_hora)}</td><td className="match-name">{partido.estadio_cancha}</td><td>{partido.ciudad_juego?.nombre}, {partido.ciudad_juego?.estado?.nombre}</td><td><RefereeCount assignments={partido.asignaciones || []} required={partido.arbitros_requeridos || 2} /></td><td><span className="badge-soft">{partido.estado_partido}</span></td></tr>)}
          {!filteredGames.length && <tr><td colSpan="5" className="empty-cell">No hay partidos en esta vista.</td></tr>}
        </tbody></table></div>
        <p className="table-footnote">Cada partido requiere dos árbitros. Un árbitro puede participar en más de un partido el mismo día o durante la semana.</p>
      </section>
    )}
    {selectedArbitro && <div className="referee-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelectedArbitroId(null) }}>
      <section className="referee-modal panel" role="dialog" aria-modal="true" aria-labelledby="referee-modal-title">
        <header className="panel-header referee-modal-header"><div><span className="eyebrow">AGENDA Y GASTOS · {mes}</span><h3 id="referee-modal-title">{selectedArbitro.nombre} {selectedArbitro.apellido}</h3></div><button className="icon-button" type="button" onClick={() => setSelectedArbitroId(null)} aria-label="Cerrar detalle">×</button></header>
        <div className="referee-modal-summary"><span>Origen <strong>{selectedArbitro.ciudad_origen?.nombre || '—'}{selectedArbitro.ciudad_origen?.estado?.nombre ? `, ${selectedArbitro.ciudad_origen.estado.nombre}` : ''}</strong></span><span>Partidos del mes <strong>{juegosDelArbitro.length}</strong></span><span className="monthly-total">Gasto total <strong>{money(gastoArbitroSeleccionado)}</strong></span></div>
        <div className="table-responsive"><table className="table data-table"><thead><tr><th>Fecha y hora</th><th>Estadio</th><th>Sede</th><th>Gasto total del juego</th></tr></thead><tbody>
          {juegosDelArbitro.map(({ partido, asignacion }) => <tr key={asignacion.id}><td>{dateTime(partido.fecha_hora)}</td><td className="match-name">{partido.estadio_cancha}</td><td>{partido.ciudad_juego?.nombre}, {partido.ciudad_juego?.estado?.nombre}</td><td className="monthly-total">{money(asignacion.costo_total)}</td></tr>)}
          {!juegosDelArbitro.length && <tr><td colSpan="4" className="empty-cell">Este árbitro no tiene juegos asignados en {mes}.</td></tr>}
        </tbody><tfoot><tr><th colSpan="3">Total de gastos del mes</th><th className="monthly-total">{money(gastoArbitroSeleccionado)}</th></tr></tfoot></table></div>
      </section>
    </div>}
  </>
}
