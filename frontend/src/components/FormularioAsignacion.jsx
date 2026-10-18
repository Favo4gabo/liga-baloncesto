import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../services/api.js'
import CostBreakdown from './CostBreakdown.jsx'

export default function FormularioAsignacion({ partido, arbitros, onCreated }) {
  const [open, setOpen] = useState(false)
  const [arbitroId, setArbitroId] = useState('')
  const [medio, setMedio] = useState('')
  const [noches, setNoches] = useState(1)
  const [dias, setDias] = useState(1)
  const [salida, setSalida] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [preview, setPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState('')

  const disponibles = useMemo(
    () => arbitros.filter((arbitro) => arbitro.activo && !partido.asignaciones?.some((asignacion) => asignacion.arbitro_id === arbitro.id)),
    [arbitros, partido.asignaciones],
  )

  useEffect(() => {
    if (!open || !arbitroId) {
      setPreview(null)
      setPreviewError('')
      return undefined
    }

    const controller = new AbortController()
    setPreviewLoading(true)
    setPreviewError('')
    apiFetch(`/partidos/${partido.id}/calcular-costos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        arbitro_id: Number(arbitroId),
        cantidad_noches: Number(noches),
        cantidad_dias: Number(dias),
        medio_transporte: medio || null,
      }),
      signal: controller.signal,
    })
      .then(async (response) => {
        const data = await response.json()
        if (!response.ok) throw new Error(data.error || 'No se pudo calcular la estimación.')
        setPreview(data)
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setPreview(null)
          setPreviewError(err.message)
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setPreviewLoading(false)
      })

    return () => controller.abort()
  }, [open, arbitroId, noches, dias, medio, partido.id])

  async function submit(event) {
    event.preventDefault()
    if (!arbitroId) return setError('Selecciona un árbitro.')
    setSaving(true)
    setError('')
    try {
      const payload = {
        arbitro_id: Number(arbitroId),
        medio_transporte: medio || null,
        cantidad_noches: Number(noches),
        cantidad_dias: Number(dias),
      }
      if (salida) payload.fecha_salida = new Date(salida).toISOString()
      const response = await apiFetch(`/partidos/${partido.id}/asignar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'No se pudo crear la asignación.')
      await onCreated()
      setOpen(false)
      setArbitroId('')
      setPreview(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (!open) return <button className="assign-toggle" onClick={() => setOpen(true)}>＋ Asignar árbitro</button>

  return (
    <form className="assignment-form" onSubmit={submit}>
      <strong>Nueva asignación</strong>
      <small className="assignment-hint">Elige árbitro, noches y días. La estimación se actualiza con las tarifas de la base de datos.</small>
      <select required value={arbitroId} onChange={(event) => setArbitroId(event.target.value)}>
        <option value="">Selecciona un árbitro</option>
        {disponibles.map((arbitro) => <option value={arbitro.id} key={arbitro.id}>{arbitro.nombre} {arbitro.apellido} · {arbitro.ciudad_origen?.nombre}</option>)}
      </select>
      <div className="assignment-form-row">
        <label>Noches de hospedaje<input min="0" step="1" type="number" value={noches} onChange={(event) => setNoches(event.target.value)} /></label>
        <label>Días de viáticos<input min="1" step="1" type="number" value={dias} onChange={(event) => setDias(event.target.value)} /></label>
      </div>
      <div className="assignment-form-row">
        <label>Traslado externo<select value={medio} onChange={(event) => setMedio(event.target.value)}><option value="">Automático según distancia</option><option value="taxi">Taxi</option><option value="avion">Avión</option></select></label>
        <label>Salida (opcional)<input value={salida} onChange={(event) => setSalida(event.target.value)} type="datetime-local" title="Vacío: se usa el plan automático" /></label>
      </div>

      {arbitroId && previewLoading && <small className="assignment-hint">Calculando costos…</small>}
      {previewError && <small className="form-error">{previewError}</small>}
      {preview && <CostBreakdown costs={preview} detail={preview} title="Estimación antes de asignar" preview />}
      {error && <small className="form-error">{error}</small>}
      <div>
        <button type="submit" className="btn-primary-custom" disabled={saving || previewLoading || !preview}>{saving ? 'Guardando…' : 'Confirmar asignación'}</button>
        <button type="button" className="assign-cancel" onClick={() => setOpen(false)}>Cancelar</button>
      </div>
    </form>
  )
}
