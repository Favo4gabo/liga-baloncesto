import { useEffect, useMemo, useState } from 'react'
import { API_URL } from '../App.jsx'

const formatDate = (value) => new Intl.DateTimeFormat('es-ES', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))

export default function Calendario() {
  const [partidos, setPartidos] = useState([]); const [fecha, setFecha] = useState(''); const [error, setError] = useState('')
  useEffect(() => { fetch(`${API_URL}/partidos`).then(async r => { if (!r.ok) throw new Error(); setPartidos(await r.json()) }).catch(() => setError('No se pudo cargar el calendario.')) }, [])
  const visibles = useMemo(() => fecha ? partidos.filter(p => p.fecha_hora?.slice(0, 10) === fecha) : partidos, [fecha, partidos])
  return <>
    <div className="page-heading"><div><h2>Calendario de partidos</h2><p>Selecciona una fecha para conocer las sedes y árbitros asignados.</p></div><input className="form-control" style={{ maxWidth: 180 }} type="date" value={fecha} onChange={e => setFecha(e.target.value)} /></div>
    {error ? <div className="error-notice">{error}</div> : <section className="panel"><header className="panel-header"><h3>{fecha ? `Partidos del ${fecha}` : 'Todos los partidos'}</h3><span className="badge-soft">{visibles.length} registros</span></header><div className="table-responsive"><table className="table data-table"><thead><tr><th>Fecha y hora</th><th>Estadio</th><th>Ciudad / Estado</th><th>Árbitros participantes</th><th>Estado</th></tr></thead><tbody>{visibles.map(p => <tr key={p.id}><td>{formatDate(p.fecha_hora)}</td><td className="match-name">{p.estadio_cancha}</td><td>{p.ciudad_juego ? `${p.ciudad_juego.nombre}, ${p.ciudad_juego.estado?.nombre || ''}` : '—'}</td><td>{p.asignaciones?.length ? p.asignaciones.map(a => `${a.arbitro?.nombre || ''} ${a.arbitro?.apellido || ''}`.trim()).join(', ') : 'Sin asignar'}</td><td><span className="badge-soft">{p.estado_partido}</span></td></tr>)}{!visibles.length && <tr><td colSpan="5" className="empty-cell">No hay partidos para esta selección.</td></tr>}</tbody></table></div></section>}
  </>
}
