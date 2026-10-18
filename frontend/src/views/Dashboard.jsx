import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { API_URL } from '../App.jsx'

const empty = { arbitros: [], partidos: [] }
const dateText = (value) => value ? new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'

export default function Dashboard() {
  const [data, setData] = useState(empty)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([fetch(`${API_URL}/arbitros/`), fetch(`${API_URL}/partidos`)])
      .then(async ([arbitros, partidos]) => {
        if (!arbitros.ok || !partidos.ok) throw new Error('No fue posible consultar la información del sistema.')
        setData({ arbitros: await arbitros.json(), partidos: await partidos.json() })
      }).catch((err) => setError(err.message))
  }, [])

  const programados = data.partidos.filter((p) => p.estado_partido === 'Programado')
  const asignaciones = data.partidos.reduce((total, partido) => total + (partido.asignaciones?.length || 0), 0)
  const cards = [
    ['♙', data.arbitros.filter((a) => a.activo).length, 'Árbitros activos'],
    ['◫', data.partidos.length, 'Partidos registrados'],
    ['◷', programados.length, 'Partidos programados'],
    ['✓', asignaciones, 'Asignaciones realizadas'],
  ]

  return <>
    <div className="page-heading"><div><h2>Resumen de la liga</h2><p>Consulta rápidamente la actividad y logística arbitral.</p></div></div>
    {error && <div className="error-notice">{error} Verifica que el backend esté activo.</div>}
    <section className="metrics-grid">{cards.map(([icon, value, label]) => <article className="metric-card" key={label}><span className="metric-icon">{icon}</span><strong className="metric-value">{value}</strong><span className="metric-label">{label}</span></article>)}</section>
    <section className="panel">
      <header className="panel-header"><h3>Próximos partidos</h3><Link to="/calendario">Ver calendario completo →</Link></header>
      <div className="table-responsive"><table className="table data-table"><thead><tr><th>Fecha y hora</th><th>Cancha / estadio</th><th>Ciudad sede</th><th>Árbitros</th><th>Estado</th></tr></thead>
        <tbody>{data.partidos.slice(0, 6).map((p) => <tr key={p.id}><td>{dateText(p.fecha_hora)}</td><td className="match-name">{p.estadio_cancha}</td><td>{p.ciudad_juego?.nombre || '—'}</td><td>{p.asignaciones?.length || 0}</td><td><span className="badge-soft">{p.estado_partido}</span></td></tr>)}{!data.partidos.length && <tr><td colSpan="5" className="empty-cell">Aún no hay partidos. Importa el libro Excel para comenzar.</td></tr>}</tbody>
      </table></div>
    </section>
  </>
}
