import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../services/api.js'

const emptyReferee = { nombre: '', apellido: '', telefono: '', email: '', ciudad_origen_id: '' }
const emptyVenue = { nombre_cancha: '', ciudad_id: '', direccion: '', latitud: '', longitud: '' }
const historyDate = (value) => value ? new Intl.DateTimeFormat('es-VE', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'

export default function Administracion() {
  const [tab, setTab] = useState('arbitros')
  const [ciudades, setCiudades] = useState([])
  const [arbitros, setArbitros] = useState([])
  const [canchas, setCanchas] = useState([])
  const [historial, setHistorial] = useState([])
  const [historyError, setHistoryError] = useState('')
  const [referee, setReferee] = useState(emptyReferee)
  const [venue, setVenue] = useState(emptyVenue)
  const [editingRefereeId, setEditingRefereeId] = useState(null)
  const [editingVenueId, setEditingVenueId] = useState(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    const responses = await Promise.all([
      apiFetch('/catalogos/ciudades'),
      apiFetch('/arbitros/'),
      apiFetch('/catalogos/canchas'),
    ])
    if (!responses.every((response) => response.ok)) throw new Error('No se pudieron cargar los catálogos y árbitros.')
    const [cities, refs, venues] = await Promise.all(responses.map((response) => response.json()))
    setCiudades(cities)
    setArbitros(refs)
    setCanchas(venues)
    try {
      const historyResponse = await apiFetch('/historial?per_page=10')
      if (!historyResponse.ok) throw new Error(`El backend respondió HTTP ${historyResponse.status} al consultar el historial.`)
      const changes = await historyResponse.json()
      setHistorial(changes.items || [])
      setHistoryError('')
    } catch (err) {
      setHistoryError(`${err.message} Reinicia el backend para sincronizar sus rutas.`)
    }
  }, [])

  useEffect(() => {
    load().catch((err) => setError(err.message)).finally(() => setLoading(false))
  }, [load])

  const cityLabel = (item) => `${item?.nombre || 'Ciudad desconocida'} · ${item?.estado?.nombre || 'Sin estado'}`

  async function send(url, method, data) {
    const response = await apiFetch(`/${url}`, {
      method,
      headers: { 'Content-Type': 'application/json' },
      ...(data ? { body: JSON.stringify(data) } : {}),
    })
    const json = await response.json()
    if (!response.ok) {
      const conflict = json.partidos_en_conflicto?.length
        ? ` Partidos asociados: ${json.partidos_en_conflicto.map((partido) => `#${partido.id} (${historyDate(partido.fecha_hora)})`).join(', ')}.`
        : ''
      throw new Error(`${json.error || 'La operación no se pudo completar.'}${conflict}`)
    }
    return json
  }

  async function submit(event, type) {
    event.preventDefault()
    setMessage('')
    setError('')
    const isReferee = type === 'arbitros'
    const editingId = isReferee ? editingRefereeId : editingVenueId
    const url = isReferee
      ? `arbitros/${editingId || ''}`
      : `catalogos/canchas${editingId ? `/${editingId}` : ''}`
    const data = isReferee
      ? { ...referee, ciudad_origen_id: Number(referee.ciudad_origen_id) }
      : {
          ...venue,
          ciudad_id: Number(venue.ciudad_id),
          latitud: venue.latitud || null,
          longitud: venue.longitud || null,
        }
    try {
      await send(url, editingId ? 'PUT' : 'POST', data)
      setMessage(`${isReferee ? 'Árbitro' : 'Cancha'} ${editingId ? 'actualizado' : 'registrado'} correctamente.`)
      if (isReferee) { setReferee(emptyReferee); setEditingRefereeId(null) }
      else { setVenue(emptyVenue); setEditingVenueId(null) }
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  function editReferee(item) {
    setTab('arbitros')
    setEditingRefereeId(item.id)
    setReferee({
      nombre: item.nombre,
      apellido: item.apellido,
      telefono: item.telefono || '',
      email: item.email || '',
      ciudad_origen_id: String(item.ciudad_origen_id),
    })
    setMessage('')
    setError('')
  }

  function editVenue(item) {
    setTab('canchas')
    setEditingVenueId(item.id)
    setVenue({
      nombre_cancha: item.nombre_cancha,
      ciudad_id: String(item.ciudad_id),
      direccion: item.direccion || '',
      latitud: item.latitud ?? '',
      longitud: item.longitud ?? '',
    })
    setMessage('')
    setError('')
  }

  async function setRefereeActive(item, activo) {
    setMessage('')
    setError('')
    try {
      const result = activo
        ? await send(`arbitros/${item.id}`, 'PUT', { activo: true })
        : await send(`arbitros/${item.id}`, 'DELETE')
      setMessage(result.mensaje || `Árbitro ${activo ? 'reactivado' : 'desactivado'}; se conservó su historial.`)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  async function deleteVenue(item) {
    if (!window.confirm(`¿Eliminar la cancha "${item.nombre_cancha}"? Esta operación no se puede deshacer.`)) return
    setMessage('')
    setError('')
    try {
      const result = await send(`catalogos/canchas/${item.id}`, 'DELETE')
      setMessage(result.mensaje || 'Cancha eliminada.')
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  function cancelEdit(type) {
    if (type === 'arbitros') { setReferee(emptyReferee); setEditingRefereeId(null) }
    else { setVenue(emptyVenue); setEditingVenueId(null) }
  }

  const tabs = [['arbitros', '♙ Árbitros', arbitros.length], ['canchas', '⌖ Canchas', canchas.length]]

  return <>
    <div className="page-heading"><div><h2>Administración de la liga</h2><p>Gestiona los árbitros y las sedes. Las ciudades existentes se mantienen como catálogo de referencia.</p></div></div>
    {error && <div className="error-notice" role="alert">{error}</div>}
    {message && <div className="success-notice" role="status">✓ {message}</div>}
    <div className="admin-tabs">{tabs.map(([id, label, count]) => <button key={id} className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>{label} <span>{count}</span></button>)}</div>
    {loading ? <div className="loading">Cargando administración…</div> : <div className="admin-layout">
      {tab === 'arbitros' && <>
        <section className="panel admin-form-card">
          <header className="panel-header"><h3>{editingRefereeId ? 'Editar árbitro' : 'Nuevo árbitro'}</h3><span className="badge-soft">Perfil operativo</span></header>
          <form className="admin-form" onSubmit={(event) => submit(event, 'arbitros')}>
            <div className="admin-form-row">
              <label>Nombre<input required maxLength="80" value={referee.nombre} onChange={(e) => setReferee({ ...referee, nombre: e.target.value })} /></label>
              <label>Apellido<input required maxLength="80" value={referee.apellido} onChange={(e) => setReferee({ ...referee, apellido: e.target.value })} /></label>
            </div>
            <label>Ciudad y estado de origen<select required value={referee.ciudad_origen_id} onChange={(e) => setReferee({ ...referee, ciudad_origen_id: e.target.value })}><option value="">Selecciona ciudad / estado</option>{ciudades.map((item) => <option value={item.id} key={item.id}>{cityLabel(item)}</option>)}</select></label>
            <div className="admin-form-row">
              <label>Teléfono<input maxLength="30" value={referee.telefono} onChange={(e) => setReferee({ ...referee, telefono: e.target.value })} placeholder="0412-0000000" /></label>
              <label>Correo<input type="email" maxLength="150" value={referee.email} onChange={(e) => setReferee({ ...referee, email: e.target.value })} placeholder="nombre@liga.ve" /></label>
            </div>
            <div className="admin-actions">
              <button className="btn-primary-custom">{editingRefereeId ? 'Guardar cambios' : 'Guardar árbitro'}</button>
              {editingRefereeId && <button type="button" className="admin-secondary-button" onClick={() => cancelEdit('arbitros')}>Cancelar</button>}
            </div>
          </form>
        </section>
        <section className="panel admin-list">
          <header className="panel-header"><h3>Árbitros registrados</h3></header>
          {arbitros.map((ref) => <article key={ref.id} className="admin-list-item">
            <span className="referee-avatar">{ref.nombre[0]}{ref.apellido[0]}</span>
            <div><strong>{ref.nombre} {ref.apellido}</strong><small>⌖ {cityLabel(ref.ciudad_origen)}</small></div>
            <span className={ref.activo ? 'availability-dot active' : 'availability-dot'}>{ref.activo ? 'Activo' : 'Inactivo'}</span>
            <div className="admin-row-actions">
              <button type="button" className="admin-action-button" onClick={() => editReferee(ref)}>Editar</button>
              <button type="button" className="admin-action-button" onClick={() => setRefereeActive(ref, !ref.activo)}>{ref.activo ? 'Desactivar' : 'Reactivar'}</button>
            </div>
          </article>)}
          {!arbitros.length && <p className="empty-cell">No hay árbitros registrados.</p>}
        </section>
      </>}

      {tab === 'canchas' && <>
        <section className="panel admin-form-card">
          <header className="panel-header"><h3>{editingVenueId ? 'Editar cancha' : 'Nueva cancha'}</h3><span className="badge-soft">Sede venezolana</span></header>
          <form className="admin-form" onSubmit={(event) => submit(event, 'canchas')}>
            <label>Nombre de la cancha / estadio<input required maxLength="150" value={venue.nombre_cancha} onChange={(e) => setVenue({ ...venue, nombre_cancha: e.target.value })} placeholder="Gimnasio o domo" /></label>
            <label>Ciudad y estado<select required value={venue.ciudad_id} onChange={(e) => setVenue({ ...venue, ciudad_id: e.target.value })}><option value="">Selecciona ciudad / estado</option>{ciudades.map((item) => <option value={item.id} key={item.id}>{cityLabel(item)}</option>)}</select></label>
            <label>Dirección<input maxLength="250" value={venue.direccion} onChange={(e) => setVenue({ ...venue, direccion: e.target.value })} placeholder="Avenida, sector o referencia" /></label>
            <div className="admin-form-row">
              <label>Latitud<input type="number" step="any" value={venue.latitud} onChange={(e) => setVenue({ ...venue, latitud: e.target.value })} placeholder="10.4806" /></label>
              <label>Longitud<input type="number" step="any" value={venue.longitud} onChange={(e) => setVenue({ ...venue, longitud: e.target.value })} placeholder="-66.9113" /></label>
            </div>
            <div className="admin-actions">
              <button className="btn-primary-custom">{editingVenueId ? 'Guardar cambios' : 'Guardar cancha'}</button>
              {editingVenueId && <button type="button" className="admin-secondary-button" onClick={() => cancelEdit('canchas')}>Cancelar</button>}
            </div>
          </form>
        </section>
        <section className="panel admin-list">
          <header className="panel-header"><h3>Canchas y ubicaciones</h3></header>
          {canchas.map((cancha) => <article key={cancha.id} className="admin-list-item venue-list-item">
            <span className="venue-icon">⌖</span>
            <div><strong>{cancha.nombre_cancha}</strong><small>{cityLabel(cancha.ciudad)}{cancha.direccion ? ` · ${cancha.direccion}` : ''}</small></div>
            {cancha.latitud && <a target="_blank" rel="noreferrer" href={`https://www.google.com/maps?q=${cancha.latitud},${cancha.longitud}`}>Mapa ↗</a>}
            <div className="admin-row-actions">
              <button type="button" className="admin-action-button" onClick={() => editVenue(cancha)}>Editar</button>
              <button type="button" className="admin-action-button danger" onClick={() => deleteVenue(cancha)}>Eliminar</button>
            </div>
          </article>)}
          {!canchas.length && <p className="empty-cell">No hay canchas registradas.</p>}
        </section>
      </>}
    </div>}

    <section className="panel admin-history">
      <header className="panel-header"><div><h3>Historial de cambios</h3><small>Actividad administrativa reciente con valores anteriores y nuevos.</small>{!historyError && <span className="history-connection-status">Conectado · {historial.length} recientes</span>}</div><button type="button" className="admin-action-button" onClick={() => load().catch((err) => setError(err.message))}>Actualizar</button></header>
      {historyError && <div className="history-load-warning" role="alert">{historyError}</div>}
      {historial.length ? <div className="admin-history-list">{historial.map((change) => <article className="admin-history-item" key={change.id}>
        <div className="admin-history-heading"><strong>{change.accion} · {change.entidad} #{change.entidad_id}</strong><time>{historyDate(change.fecha)}</time></div>
        <small>Origen: {change.origen}</small>
        <div className="admin-history-diff"><span><b>Antes:</b> {JSON.stringify(change.antes ?? {})}</span><span><b>Después:</b> {JSON.stringify(change.despues ?? {})}</span></div>
      </article>)}</div> : !historyError && <p className="empty-cell">El historial está conectado. Los cambios registrados a partir de ahora aparecerán aquí.</p>}
    </section>
  </>
}
