import { useState } from 'react'
import { apiFetch } from '../services/api.js'
import { useAuth } from '../context/AuthContext.jsx'
import FormularioAsignacion from './FormularioAsignacion.jsx'
import CostBreakdown from './CostBreakdown.jsx'

const textDate = (date) => new Intl.DateTimeFormat('es-ES', { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date(`${date}T12:00:00`))
const time = (value) => new Intl.DateTimeFormat('es-ES', { hour: '2-digit', minute: '2-digit' }).format(new Date(value))
const amount = (value) => Number(value || 0).toLocaleString('es-VE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

export default function PanelDia({ fecha, partidos, arbitros, onClose, onAssigned }) {
  const { user } = useAuth()
  const canEditAssignments = ['super_admin', 'admin'].includes(user.rol)
  const [editingId, setEditingId] = useState(null)
  const [selectedReferee, setSelectedReferee] = useState('')
  const [editError, setEditError] = useState('')
  const [savingEdit, setSavingEdit] = useState(false)
  const asignaciones = partidos.flatMap((partido) => partido.asignaciones || [])
  const totalDia = asignaciones.reduce((total, asignacion) => total + Number(asignacion.costo_total || 0), 0)

  return (
    <section className="day-panel panel" aria-live="polite">
      <header className="panel-header day-panel-header">
        <div><span className="eyebrow">DETALLE DEL DÍA</span><h3>{textDate(fecha)}</h3></div>
        <button className="icon-button" onClick={onClose} aria-label="Cerrar detalle">×</button>
      </header>
      <div className="day-panel-content">
        <div className="day-summary">
          <span><strong>{partidos.length}</strong> partidos</span>
          <span><strong>{asignaciones.length}</strong> árbitros asignados</span>
          <span className="day-summary-total">Gastos logísticos <strong>{amount(totalDia)}</strong></span>
        </div>
        {!partidos.length && <p className="empty-day">No hay partidos programados para este día.</p>}
        <div className="day-matches-grid">
          {partidos.map((partido) => (
            <article className="day-match" key={partido.id}>
              <div className="day-match-heading">
                <div className="day-match-title">
                  <time>{time(partido.fecha_hora)}</time>
                  <div>
                    <strong>{partido.estadio_cancha}</strong>
                    <small>{partido.ciudad_juego?.nombre}, {partido.ciudad_juego?.estado?.nombre}</small>
                    {partido.ubicacion_cancha?.direccion && <small className="venue-location">⌖ {partido.ubicacion_cancha.direccion}</small>}
                  </div>
                </div>
                <span className="badge-soft">{partido.estado_partido}</span>
              </div>
              <small className={`required-referees ${partido.asignaciones?.length === 2 ? 'complete' : ''}`}>
                Árbitros asignados: {partido.asignaciones?.length || 0}/2
              </small>
              {partido.asignaciones?.length ? (
                <div className="assignment-list">
                  {partido.asignaciones.map((asignacion) => {
                    const trasladoExterno = asignacion.traslados?.find((traslado) => traslado.tipo === 'externo' && traslado.sentido === 'ida')
                    return (
                      <div className="assignment-card" key={asignacion.id}>
                        <div className="assignment-name">
                          <span className="referee-avatar">{asignacion.arbitro?.nombre?.[0]}{asignacion.arbitro?.apellido?.[0]}</span>
                          <div className="referee-hover" title={`Árbitro asignado: ${asignacion.arbitro?.nombre} ${asignacion.arbitro?.apellido}`}>
                            <strong>{asignacion.arbitro?.nombre} {asignacion.arbitro?.apellido}</strong>
                            <small>Viaje: <span className={`travel-status-badge ${(asignacion.estado_viaje || '').toLowerCase().replaceAll(' ', '-')}`}>{asignacion.estado_viaje}</span></small>
                          </div>
                        </div>
                        {canEditAssignments && editingId === asignacion.id ? (
                          <div className="assignment-edit">
                            <select value={selectedReferee} onChange={(event) => setSelectedReferee(event.target.value)}>
                              <option value="">Selecciona un árbitro</option>
                              {arbitros.filter((item) => item.activo && (item.id === asignacion.arbitro_id || !partido.asignaciones.some((other) => other.id !== asignacion.id && other.arbitro_id === item.id))).map((item) => <option value={item.id} key={item.id}>{item.nombre} {item.apellido}</option>)}
                            </select>
                            <button type="button" className="btn-primary-custom" disabled={savingEdit || !selectedReferee} onClick={async () => {
                              setSavingEdit(true); setEditError('')
                              try {
                                const response = await apiFetch(`/asignaciones/${asignacion.id}/arbitro`, { method: 'PUT', body: JSON.stringify({ arbitro_id: Number(selectedReferee) }) })
                                const data = await response.json()
                                if (!response.ok) throw new Error(data.error || 'No se pudo cambiar el árbitro.')
                                setEditingId(null); await onAssigned()
                              } catch (error) { setEditError(error.message) } finally { setSavingEdit(false) }
                            }}>Guardar</button>
                            <button type="button" className="assign-cancel" onClick={() => { setEditingId(null); setEditError('') }}>Cancelar</button>
                            {editError && <small className="form-error">{editError}</small>}
                          </div>
                        ) : canEditAssignments && <button type="button" className="assignment-edit-button" onClick={() => { setEditingId(asignacion.id); setSelectedReferee(String(asignacion.arbitro_id)); setEditError('') }}>Cambiar árbitro</button>}
                        <div className="assignment-route-summary">
                          <span>{asignacion.arbitro?.ciudad_origen?.nombre || 'Origen'} → {partido.ciudad_juego?.nombre || 'Sede'}</span>
                          <span>{trasladoExterno ? `Traslado externo: ${trasladoExterno.medio}` : 'Sin traslado externo'}</span>
                        </div>
                        {asignacion.hospedaje && <small className="lodging">⌂ {asignacion.hospedaje.noches} noche(s){asignacion.hospedaje.hotel ? ` · ${asignacion.hospedaje.hotel}` : ''}</small>}
                        <CostBreakdown costs={asignacion} detail={asignacion.detalle_costos} title="Costos de la asignación" />
                      </div>
                    )
                  })}
                </div>
              ) : <p className="unassigned">Sin árbitros asignados</p>}
              {partido.asignaciones?.length >= 2
                ? <p className="assignment-complete-note">✓ Este partido ya tiene sus dos árbitros.</p>
                : <FormularioAsignacion partido={partido} arbitros={arbitros} onCreated={onAssigned} />}
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}
